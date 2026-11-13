#!/usr/bin/env python3
"""
build_rab.py v3 - Serasa RAB builder untuk Template RAB format baru (Nov 2026).

Format template (tab "Serasa Template"):
  A Bab | B Uraian (judul singkat, hanya di baris pertama grup) | C Ruang | D Lantai | E Kode Specs | F Spec |
  G Satuan | H Volume | I Harga Satuan | J Total Harga | K subtotal bab.  Header kolom baris 12, data mulai 13.
  - F = teks dropdown (data validation ONE_OF_RANGE AHS!$A$2:$A$2159, strict) -> uraian AHS PERSIS.
  - E = VLOOKUP(F; AHS!A:E;5;FALSE), G = VLOOKUP(F;AHS!A:D;3;FALSE), I = VLOOKUP(F; AHS!A:D;4;FALSE), J = I*H.
  - Tab AHS = IMPORTRANGE dari "Rekap AHS" (A Uraian, B Kategori, C Satuan, D Harga, E Kode). Tidak ada MASTER AHS/IKK.
  Pengecualian:
  - Bab kusen/pintu/jendela: E = kode tipe (P1, J1, PJ1 ...), F = spesifikasi lengkap + ukuran (teks bebas),
    G = unit, H = 1, I = harga hasil analisa (rujukan ke tab Audit).
  - Pekerjaan yang tidak ada di AHS: tetap diisi; E = kode analisa, F = uraian analisa (tanpa dropdown),
    I = rujukan ke harga analisa di tab Audit.
  Tab "Audit": (A) pekerjaan tidak ada di AHS + analisanya, (B) analisa kusen/pintu/jendela, (C) AHS yang terpakai.

Pemakaian:
  python3 build_rab.py input.json --ahs ahs.json --out out                  # cek + file siap kirim (connector)
  python3 build_rab.py input.json --push --creds key.json --spreadsheet ID --prepare template
  python3 build_rab.py input.json --push --creds key.json --spreadsheet ID --prepare clone:"<tab RAB lain>"
  python3 build_rab.py input.json --push --creds key.json --spreadsheet ID --prepare patch   # revisi: hanya baris berubah
--ahs (mode offline): JSON [{"u":uraian,"s":satuan,"h":harga,"c":kode}] atau CSV ekspor tab AHS. Mode push membaca AHS live.
Locale Indonesia: argumen ';' dan desimal ','.
"""
import argparse, csv, io, json, os, re, sys

HR = 12                       # baris header kolom
DS = HR + 1                   # baris data pertama
COLS = ["Bab", "Uraian", "Ruang", "Lantai", "Kode Specs", "Spec", "Satuan", "Volume", "Harga Satuan", "Total Harga"]
AHS_DV = "=AHS!$A$2:$A$2159"
RP = '[$Rp-421]#,##0'
PEND_BG = {"red": 1, "green": 0.949, "blue": 0.8}      # kuning muda (sama dengan template)
EST_BG = {"red": 1, "green": 217 / 255, "blue": 102 / 255}  # hanya Volume estimasi
FIN_LABEL = {"ekspos": "Aci Ekspos + Coating", "putih": "Cat Putih", "terracotta": "Cat Tekstur Terracotta", "pola": "Aci Ekspos Pola Blok"}


def num_id(x):
    return ("%.4f" % float(x)).rstrip("0").rstrip(".").replace(".", ",")

def q(s):  # string literal di dalam rumus
    return '"' + str(s).replace('"', '""') + '"'


# ---------------------------------------------------------------- AHS
def load_ahs(path):
    if path.endswith(".json"):
        return json.load(open(path, encoding="utf-8"))
    t = open(path, encoding="utf-8").read()
    if "## Sheet name: AHS" in t:
        t = t.split("## Sheet name: AHS\n", 1)[1].split("## Sheet name:", 1)[0]
    rows = list(csv.reader(io.StringIO(t)))[1:]
    return [{"u": r[0], "s": r[2], "h": r[3], "c": r[4] if len(r) > 4 else ""} for r in rows if r and r[0]]


class Ahs:
    def __init__(self, items):
        self.by = {}
        for a in items:
            self.by.setdefault(a["u"], a)            # VLOOKUP mengambil baris pertama
        self.dups = {u for u in self.by if sum(1 for a in items if a["u"] == u) > 1}

    def check(self, u):
        return u in self.by


# ---------------------------------------------------------------- builder
class Builder:
    def __init__(self, spec, ahs):
        self.spec, self.ahs = spec, ahs
        self.rows = []          # list of dict(cells=[A..K], kind)
        self.bab_rows, self.sub_rows, self.subtotals = [], [], []
        self.errors, self.used = [], {}
        self._s = None
        self.audit = {a["code"]: a for a in spec.get("audit", [])}
        self.audit_used = {}
        self.pend = []

    def r(self): return DS + len(self.rows)

    def _push(self, cells, kind="data", dv=False):
        cells = cells + [""] * (11 - len(cells))
        # src/loc: asal angka & lokasi di input -> dipakai viewport (koreksi, sorotan 3D); tidak ditulis ke Sheet
        self.rows.append({"c": cells, "k": kind, "dv": dv, "src": getattr(self, "_src", None), "loc": getattr(self, "_loc", None)})

    def mark_estimated(self, source, start=None):
        """Propagasi estimasi ke hasil turunan; tidak mengubah volume atau harga."""
        if not source.get("estimated"): return
        for row in self.rows[start if start is not None else len(self.rows) - 1:]:
            if row["k"] in ("ahs", "audit", "kusen"):
                row["estimated"] = True
                row["quantity_note"] = source.get("quantity_note", "Perlu diisi manual dengan ukuran final.")

    # -- struktur
    def bab(self, no, title):
        if self._s is not None: self.close()
        self.bab_rows.append(self.r()); self._push([no, title], "bab"); self._s = self.r(); self._last_ur = None

    def close(self):
        s, e = self._s, self.r() - 1
        if e >= s:
            self.rows[-1]["c"][10] = f"=SUM(J{s}:J{e})"; self.subtotals.append((self.rows[s - 1 - DS]["c"][0], e))
        self._push([], "blank"); self._s = None

    def sub(self, title):
        self.sub_rows.append(self.r()); self._push(["", title], "sub"); self._last_ur = None

    def _ur(self, ur):
        """uraian hanya ditulis di baris pertama grup berurutan"""
        if ur and ur == getattr(self, "_last_ur", None): return ""
        self._last_ur = ur or self._last_ur
        return ur

    def ahs_row(self, ur, ruang, lantai, spec, vol):
        r = self.r()
        if not self.ahs.check(spec):
            self.errors.append(f"baris {r}: spec tidak ada di AHS -> '{spec}' (pakai tipe 'audit')")
        self.used.setdefault(spec, []).append(r)
        self._push(["", self._ur(ur), ruang, lantai,
                    f"=VLOOKUP(F{r};AHS!A:E;5;FALSE)", spec, f"=VLOOKUP(F{r};AHS!A:D;3;FALSE)", vol,
                    f"=VLOOKUP(F{r};AHS!A:D;4;FALSE)", f"=I{r}*H{r}"], "ahs", dv=True)

    def audit_row(self, ur, ruang, lantai, code, vol, spec=None, sat=None):
        r = self.r(); a = self.audit.get(code)
        if not a: self.errors.append(f"baris {r}: kode audit '{code}' tidak ada di input 'audit'"); a = {"name": code, "sat": ""}
        self.audit_used.setdefault(code, []).append(r)
        self._push(["", self._ur(ur), ruang, lantai, code, spec or a["name"], sat or a["sat"], vol,
                    ("AUDIT", code), f"=I{r}*H{r}"], "audit")

    def note(self, ur, spec=""):
        self._push(["", ur, "", "", "-", spec], "note")

    def pending(self, ur, ruang, lantai, reason):
        """pekerjaan yang ada di urutan pekerjaan tapi datanya belum ada di SKP -> baris kuning tanpa volume/harga"""
        r = self.r(); self.pend.append((r, ur, ruang, reason))
        self._push(["", self._ur(ur), ruang, lantai, "-", "PENDING - " + reason], "pending")

    # -- blok otomatis
    def _lab(self, w, t):
        return f'Dinding {"Interior" if w.get("interior", True) else "Eksterior"} {w["room"]} Fin. {FIN_LABEL.get(t, t)}'

    def walls(self, which, title=None, only=None):
        ws = self.spec["wall_specs"]
        title = title or {"plester": "Plester (Per ruangan)", "aci": "Aci (Per ruangan)", "finish": "Dinding (Per ruangan)"}[which]
        for wi, w in enumerate(self.spec["walls"]):
            layer = which if which in w.get("layer_parts", {}) else None   # layer_parts[which] menimpa parts untuk lapisan ini
            for t, a in w.get("layer_parts", {}).get(which, w["parts"]).items():
                if only and t not in only: continue
                if which == "plester": sp = ws["plester"]
                elif which == "aci": sp = ws["aci"].get(t)
                else:
                    sp = (w.get("finish_spec", {}).get(t)
                          or ws["finish"]["interior" if w.get("interior", True) else "exterior"].get(t))
                if not sp: continue
                self._src = (w.get("src") or {}).get(t); self._loc = ["wall", wi, t, which, layer]
                self.ahs_row(title, self._lab(w, t), w["lantai"], sp, a)
                self.mark_estimated({"estimated": w.get("estimated", False) or t in w.get("estimated_parts", []),
                                     "quantity_note": w.get("quantity_note", "Ukuran dinding perlu diisi manual.")})
        self._loc = None

    def openingan(self, code, ur="Openingan Kusen"):
        per = {}
        for o in self.spec.get("openings", []):
            w, h = float(o["w"]), float(o["h"])
            k = 2 * (w + h) if o.get("type") in ("fix", "louvre") else 2 * h + w
            lt = o["lantai"].split(" (")[0]          # 'Lantai 1 (+0,50)' -> 'Lantai 1'
            count = o.get("vol", 1)
            p = per.setdefault(lt, [0, 0, False]); p[0] += k * count; p[1] += count
            p[2] = p[2] or o.get("estimated", False)
        for lt, (m1, n, estimated) in per.items():
            self._loc = None
            self._src = {"kind": "rumus", "detail": f"Keliling {n} bukaan di {lt} (pintu 2T+L, jendela 2(L+T)) dari ukuran kusen bab V", "calc": f"= {m1:.2f} m1"}
            self.audit_row(ur, f"{n} bukaan (lihat bab kusen)", lt, code, round(m1, 2))
            self.mark_estimated({"estimated": estimated, "quantity_note": "Termasuk bukaan dengan ukuran/jumlah estimasi; periksa keliling final."})

    def openings(self):
        for oi, o in enumerate(self.spec.get("openings", [])):
            r = self.r(); code = o["code"]; self._src = o.get("src"); self._loc = ["open", oi]
            if code not in self.audit: self.errors.append(f"baris {r}: analisa kusen '{code}' tidak ada di 'audit'")
            self.audit_used.setdefault(code, []).append(r)
            self._push(["", o["jenis"], o["ruang"], o["lantai"], code, o["spec"], o.get("sat", "unit"), o.get("vol", 1),
                        ("AUDIT", code), f"=I{r}*H{r}"], "kusen")
            self.mark_estimated(o)
            self._last_ur = None

    def build(self):
        for bi, b in enumerate(self.spec["bab"]):
            self._loc = None; self.bab(b["no"], b["title"])
            for ri, it in enumerate(b.get("rows", [])):
                first = len(self.rows)
                t = it["type"]; self._src = it.get("src"); self._loc = ["bab", bi, ri]
                if t == "sub": self.sub(it["title"])
                elif t == "ahs": self.ahs_row(it.get("uraian", ""), it.get("ruang", ""), it.get("lantai", ""), it["spec"], it["vol"])
                elif t == "audit": self.audit_row(it.get("uraian", ""), it.get("ruang", ""), it.get("lantai", ""), it["code"], it["vol"])
                elif t == "note": self.note(it["uraian"], it.get("spec", ""))
                elif t in ("wall_plaster", "wall_aci", "wall_finish"):
                    self.walls({"wall_plaster": "plester", "wall_aci": "aci", "wall_finish": "finish"}[t], it.get("uraian"), it.get("only"))
                elif t == "openingan": self.openingan(it.get("code", "OPK"), it.get("uraian", "Openingan Kusen"))
                elif t == "pending": self.pending(it["uraian"], it.get("ruang", ""), it.get("lantai", ""), it.get("reason", "menunggu data (belum ada di SKP)"))
                elif t == "openings": self.openings()
                else: raise ValueError("row type tidak dikenal: " + t)
                self.mark_estimated(it, first)
        self._loc = None; self.close()
        self.total_row = self.r(); self._push(["Total", "", "", "", "", "", "", "", f"=SUM(K{DS}:K{self.total_row - 1})"], "total")
        for d in sorted(set(self.used) & self.ahs.dups):
            self.errors.append(f"PERINGATAN: uraian AHS ganda (VLOOKUP ambil yang pertama): {d}")
        return self


# ---------------------------------------------------------------- tab Audit
def build_audit(spec, b, tab, start=1):
    """mengembalikan (rows, harga_cell{code:'H12'}, info) ; kolom A..I"""
    T = f"'{tab}'"
    rows = [[f"AUDIT RAB - {spec['project']['title']}"],
            ["Dibuat otomatis oleh serasa-3drab. Harga non-AHS mengikuti sumber tiap komponen; komponen 'AHS:' mengambil harga live dari tab AHS."],
            [""]]
    price = {}

    def references(numbers):
        runs=[]
        for n in sorted(set(numbers)):
            if runs and n==runs[-1][-1]+1:runs[-1].append(n)
            else:runs.append([n])
        return "RAB: "+", ".join(f"F{x[0]}:F{x[-1]}" if len(x)>1 else f"F{x[0]}" for x in runs) if runs else "-"

    def block(title, items, note):
        rows.append([title]); rows.append([note])
        rows.append(["Kode", "Uraian / Komponen", "Satuan", "Koef", "Harga Komponen", "Jumlah", "Sumber", "Harga Satuan", "Dipakai di RAB"])
        for it in items:
            r0 = start + len(rows)
            used = b.audit_used.get(it["code"], [])
            rows.append([it["code"], it["name"], it["sat"], "", "", "", "", None,
                         references(used) + (f" | {it['note']}" if it.get("note") else "")])
            for c in it["components"]:
                r = start + len(rows); p = c["price"]
                if isinstance(p, str) and p.startswith("AHS:"):
                    p = f"=VLOOKUP({q(p[4:])};AHS!$A:$D;4;FALSE)"
                source=c.get("src", "Perlu verifikasi harga")
                if c.get("url"): source=f"=HYPERLINK({q(c['url'])};{q(source)})"
                rows.append(["", "   " + c["name"], c["sat"], c["koef"], p, f"=D{r}*E{r}", source, "", ""])
            r1 = start + len(rows) - 1
            rows[r0 - start][7] = f"=SUM(F{r0 + 1}:F{r1})"; price[it["code"]] = f"H{r0}"
            rows.append([""])

    kusen = [a for a in spec.get("audit", []) if a.get("group") == "kusen"]
    other = [a for a in spec.get("audit", []) if a.get("group") != "kusen"]
    block("A. PEKERJAAN YANG TIDAK ADA DI TAB AHS (harga dianalisa, perlu ditambahkan ke Rekap AHS)", other,
          "Di RAB: Spec ditulis sebagai teks (tanpa dropdown), Harga Satuan merujuk ke kolom H tabel ini.")
    block("B. ANALISA HARGA KUSEN, PINTU & JENDELA (dari model SKP)", kusen,
          "Kode tipe & spesifikasi ditulis di bab kusen; harga per unit = jumlah komponen di bawah.")
    rows.append(["C. ITEM AHS YANG TERPAKAI DI RAB"])
    rows.append(["Volume & jumlah dihitung live dari tab RAB (SUMIF kolom Spec)."])
    rows.append(["Kode", "Uraian AHS (Spec)", "Satuan", "Jml baris", "Harga Satuan", "Volume total", "Kategori", "Total Harga", "Baris RAB"])
    for u in sorted(b.used, key=lambda x: (b.ahs.by.get(x, {}).get("c", "zz"), x)):
        r = start + len(rows)
        rows.append([f"=IFERROR(VLOOKUP(B{r};AHS!$A:$E;5;FALSE);\"TIDAK ADA\")", u, f"=IFERROR(VLOOKUP(B{r};AHS!$A:$C;3;FALSE);\"\")",
                     f"=COUNTIF({T}!$F:$F;B{r})", f"=IFERROR(VLOOKUP(B{r};AHS!$A:$D;4;FALSE);0)",
                     f"=SUMIF({T}!$F:$F;B{r};{T}!$H:$H)", f"=IFERROR(VLOOKUP(B{r};AHS!$A:$B;2;FALSE);\"\")",
                     f"=SUMIF({T}!$F:$F;B{r};{T}!$J:$J)", ", ".join(str(x) for x in b.used[u])])
    rows.append([""]); r = start + len(rows)
    nC = len(b.used)
    rows.append(["", f"Jumlah item AHS terpakai: {nC}", "", "", "", "", "", f"=SUM(H{r - nC - 1}:H{r - 2})", ""])
    if b.pend:
        rows += [[""], ["D. PEKERJAAN PENDING (data belum ada di SKP, dilanjutkan nanti)"],
                 ["Baris di tab RAB berwarna kuning, tanpa volume & harga."],
                 ["Baris", "Uraian", "Ruang", "", "", "", "", "", "Alasan"]]
        for rr, ur, ruang, reason in b.pend:
            rows.append([f"F{rr}", ur, ruang, "", "", "", "", "", reason])
    estimates = [(DS + i, row) for i, row in enumerate(b.rows) if row.get("estimated")]
    notes = spec.get("audit_notes", [])
    if estimates or notes:
        rows += [[""], ["E. CATATAN VOLUME DAN CAKUPAN"],
                 ["Kuning pekat pada Volume = estimasi, wajib diisi manual. Kuning muda seluruh baris = pending."]]
        for rr, row in estimates:
            rows.append([f"H{rr}", row["c"][2], "", "", "", "", "", "", row["quantity_note"]])
        for note in notes:
            rows.append(["", "", "", "", "", "", "", "", note])
    return [x + [""] * (9 - len(x)) for x in rows], price


# ---------------------------------------------------------------- requests
def _rng(sid, r0, r1, c0, c1): return {"sheetId": sid, "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1}

def _val(v):
    if isinstance(v, bool): return {"boolValue": v}
    if isinstance(v, (int, float)): return {"numberValue": v}
    v = "" if v is None else str(v)
    return {"formulaValue": v} if v.startswith("=") else {"stringValue": v}

def _fmt(bold=False, italic=False, size=9, h=None, num=None, wrap=None, bg=None):
    f = {"textFormat": {"fontFamily": "Calibri", "fontSize": size, "bold": bold, "italic": italic}, "verticalAlignment": "MIDDLE"}
    if h: f["horizontalAlignment"] = h
    if num: f["numberFormat"] = {"type": "NUMBER", "pattern": num}
    if wrap: f["wrapStrategy"] = wrap
    if bg: f["backgroundColor"] = bg
    return f

COLF = [dict(h="RIGHT"), dict(wrap="OVERFLOW_CELL"), dict(h="LEFT", wrap="WRAP"), dict(h="CENTER"), dict(h="CENTER"),
        dict(h="LEFT", wrap="WRAP"), dict(h="CENTER"), dict(h="CENTER", num="#,##0.00"), dict(h="CENTER", num=RP),
        dict(h="CENTER", num=RP), dict(h="CENTER", num=RP, bold=True)]

def rab_requests(sid, b, header, audit_tab, price):
    reqs = [{"updateCells": {"range": _rng(sid, 0, len(header), 0, 3), "rows": [{"values": [{"userEnteredValue": _val(v)} for v in r]} for r in header], "fields": "userEnteredValue"}},
            {"updateCells": {"range": _rng(sid, HR - 1, HR, 0, 10), "rows": [{"values": [{"userEnteredValue": _val(v)} for v in COLS]}], "fields": "userEnteredValue"}}]
    out = []
    for row in b.rows:
        vals = []
        for j, v in enumerate(row["c"]):
            if isinstance(v, tuple): v = f"='{audit_tab}'!{price.get(v[1], 'H1')}"
            kw = dict(COLF[j])
            if row["k"] in ("bab", "total") and j <= 1: kw["bold"] = True; kw["size"] = 10
            if row["k"] == "sub" and j == 1: kw["bold"] = True; kw["italic"] = True
            if row["k"] in ("ahs", "data") and j == 1: kw["bold"] = True
            if row["k"] == "total" and j == 8: kw["bold"] = True
            if row["k"] == "pending": kw["bg"] = PEND_BG; kw["italic"] = j == 5
            if row.get("estimated") and j == 7: kw["bg"] = EST_BG
            cell = {"userEnteredValue": _val(v), "userEnteredFormat": _fmt(**kw)}
            if j == 5 and row["dv"]:
                cell["dataValidation"] = {"condition": {"type": "ONE_OF_RANGE", "values": [{"userEnteredValue": AHS_DV}]}, "strict": True}
            vals.append(cell)
        out.append({"values": vals})
    reqs.append({"updateCells": {"range": _rng(sid, DS - 1, DS - 1 + len(out), 0, 11), "rows": out,
                                 "fields": "userEnteredValue,userEnteredFormat,dataValidation"}})
    reqs.append({"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": HR}}, "fields": "gridProperties.frozenRowCount"}})
    return reqs

def audit_requests(asid, rows):
    out = []; secC = False
    for r in rows:
        if isinstance(r[0], str) and r[0].startswith("C. "): secC = True
        title = isinstance(r[0], str) and re.match(r"^[ABCDE]\. |^AUDIT", r[0] or "")
        hdr = r[0] in ("Kode", "Baris")
        if isinstance(r[0], str) and r[0].startswith("D. "): secC = True
        code_row = bool(r[0]) and not title and not hdr and not str(r[0]).startswith("=") and not secC
        vals = []
        for j, v in enumerate(r):
            kw = dict(size=10 if title else 9, bold=bool(title or hdr or code_row or (j == 7 and code_row)))
            if j in (1, 6, 8): kw["wrap"] = "WRAP"
            if j in (4, 5, 7): kw["num"] = RP
            if j == 3: kw["num"] = "#,##0.00"
            if secC and j == 3: kw["num"] = "0"
            if secC and j == 5: kw["num"] = "#,##0.00"
            if hdr: kw["bg"] = {"red": 0.937, "green": 0.937, "blue": 0.937}
            vals.append({"userEnteredValue": _val(v), "userEnteredFormat": _fmt(**kw)})
        out.append({"values": vals})
    reqs = [{"updateCells": {"range": _rng(asid, 0, len(out), 0, 9), "rows": out, "fields": "userEnteredValue,userEnteredFormat"}}]
    for c, w in [(0, 70), (1, 520), (2, 60), (3, 70), (4, 110), (5, 110), (6, 220), (7, 120), (8, 300)]:
        reqs.append({"updateDimensionProperties": {"range": {"sheetId": asid, "dimension": "COLUMNS", "startIndex": c, "endIndex": c + 1}, "properties": {"pixelSize": w}, "fields": "pixelSize"}})
    reqs.append({"autoResizeDimensions":{"dimensions":{"sheetId":asid,"dimension":"ROWS","startIndex":0,"endIndex":len(out)}}})
    return reqs

def build_header(spec):
    p, L = spec["project"], spec["luasan"]; lt = L["lantai"]
    rows = [["Rencana Anggaran Biaya", "", ""], [p["title"], "", ""], ["", "", ""],
            [L.get("tanah_label", "Luas Tapak"), "", L["tanah"]],
            ["Luas Bangunan Total (" + " + ".join(x["short"] for x in lt) + ")", "", "=" + "+".join(f"C{6 + i}" for i in range(len(lt)))]]
    rows += [[x["label"], "", "=" + "+".join(num_id(v) for _, v in x["items"])] for x in lt]
    note = " | ".join(x["short"] + " = " + " + ".join(f"{n} {num_id(v)}" for n, v in x["items"]) + " m²" for x in lt)
    if L.get("note"): note += ". " + L["note"]
    rows.append([note, "", ""])
    return rows[:8]

def check_formula(b):
    tr = b.total_row
    return (f'=SUMPRODUCT(--ISERROR(E{DS}:K{tr}))&"|"&COUNTIFS(F{DS}:F{tr};"<>";E{DS}:E{tr};"<>-";I{DS}:I{tr};0)'
            f'&"|"&TEXT(I{tr};"0")&"|"&TEXTJOIN(";";TRUE;' + ";".join(f'TEXT(K{e};"0")' for _, e in b.subtotals) + ")")


# ---------------------------------------------------------------- push
def push(a, spec, ahs_items_cb):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build as gbuild
    creds = service_account.Credentials.from_service_account_file(a.creds, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    S = gbuild("sheets", "v4", credentials=creds, cache_discovery=False).spreadsheets(); ID = a.spreadsheet
    batch = lambda reqs: S.batchUpdate(spreadsheetId=ID, body={"requests": reqs}).execute() if reqs else {}
    vals = S.values().get(spreadsheetId=ID, range="AHS!A1:E3000").execute().get("values", [])[1:]
    ahs = Ahs([{"u": r[0], "s": r[2] if len(r) > 2 else "", "h": r[3] if len(r) > 3 else "", "c": r[4] if len(r) > 4 else ""} for r in vals if r and r[0]])
    b = Builder(spec, ahs).build()
    errs = [e for e in b.errors if not e.startswith("PERINGATAN")]
    for e in b.errors: print(e)
    if errs: sys.exit("BERHENTI: perbaiki error di atas dulu")
    meta = S.get(spreadsheetId=ID, fields="sheets(properties(sheetId,title,index,gridProperties),merges)").execute()
    sh = {s["properties"]["title"]: s for s in meta["sheets"]}
    tab = spec["project"]["tab"]
    atab = spec["project"].get("audit_tab", "Audit")
    if a.prepare == "template":
        src = sh["Serasa Template"]; sid = src["properties"]["sheetId"]; end = src["properties"]["gridProperties"]["rowCount"]
        reqs = [{"updateSheetProperties": {"properties": {"sheetId": sid, "title": tab}, "fields": "title"}}]
        reqs += [{"unmergeCells": {"range": m}} for m in src.get("merges", []) if m["startRowIndex"] >= HR]
        reqs.append({"updateCells": {"range": _rng(sid, HR, end, 0, 11), "fields": "userEnteredValue,userEnteredFormat,dataValidation"}})
        if spec["project"].get("zona"):
            reqs.append({"updateCells": {"range": _rng(sid, 0, 1, 5, 6), "rows": [{"values": [{"userEnteredValue": _val(spec["project"]["zona"])}]}], "fields": "userEnteredValue"}})
        batch(reqs)
    elif a.prepare.startswith("clone:"):
        src = sh[a.prepare[6:]]; end = src["properties"]["gridProperties"]["rowCount"]
        r = batch([{"duplicateSheet": {"sourceSheetId": src["properties"]["sheetId"], "insertSheetIndex": src["properties"]["index"] + 1, "newSheetName": tab}}])
        sid = r["replies"][0]["duplicateSheet"]["properties"]["sheetId"]
        batch([{"updateCells": {"range": _rng(sid, HR, end, 0, 11), "fields": "userEnteredValue,userEnteredFormat,dataValidation"}}])
        if atab in sh: atab = f"Audit {tab}"
    else:   # none = tulis ulang tab yang sudah ada (revisi): kosongkan baris data & tab audit
        src = sh[tab]; sid = src["properties"]["sheetId"]; end = src["properties"]["gridProperties"]["rowCount"]
        reqs = [{"unmergeCells": {"range": m}} for m in src.get("merges", []) if m["startRowIndex"] >= HR]
        reqs.append({"updateCells": {"range": _rng(sid, HR, end, 0, 11), "fields": "userEnteredValue,userEnteredFormat,dataValidation"}})
        if atab in sh:
            reqs.append({"updateCells": {"range": _rng(sh[atab]["properties"]["sheetId"], 0, sh[atab]["properties"]["gridProperties"]["rowCount"], 0, 9), "fields": "userEnteredValue,userEnteredFormat"}})
        batch(reqs)
    if atab in sh and a.prepare != "none":
        sys.exit(f"Tab '{atab}' sudah ada")
    if atab not in sh:
        r = batch([{"addSheet": {"properties": {"title": atab, "gridProperties": {"rowCount": 400, "columnCount": 9, "frozenRowCount": 2}}}}])
        asid = r["replies"][0]["addSheet"]["properties"]["sheetId"]
    else:
        asid = sh[atab]["properties"]["sheetId"]
    arows, price = build_audit(spec, b, tab)
    need = b.total_row + 15
    batch([{"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"rowCount": max(need, 50)}}, "fields": "gridProperties.rowCount"}}]
          + audit_requests(asid, arows) + rab_requests(sid, b, build_header(spec), atab, price))
    cell = f"'{tab}'!A{b.total_row + 3}"
    S.values().update(spreadsheetId=ID, range=cell, valueInputOption="USER_ENTERED", body={"values": [[check_formula(b)]]}).execute()
    chk = S.values().get(spreadsheetId=ID, range=cell).execute()["values"][0][0]
    S.values().clear(spreadsheetId=ID, range=cell).execute()
    err, zero, total, subs = (chk.split("|") + ["", "", "", ""])[:4]
    print(f"PUSHED tab '{tab}' (sheetId {sid}), audit '{atab}' (sheetId {asid}); baris data {DS}..{b.total_row}")
    print(f"error={err} harga0={zero} total=Rp{int(float(total or 0)):,}".replace(",", "."))
    for (no, _), v in zip(b.subtotals, subs.split(";")): print(f"  Bab {no}: Rp{int(float(v or 0)):,}".replace(",", "."))
    print(f"AHS terpakai: {len(b.used)} item; non-AHS/analisa: {len(b.audit_used)} kode; pending: {len(b.pend)} baris")


# ---------------------------------------------------------------- patch (revisi tanpa membangun ulang tab)
def _norm(v):
    if v is None: return ""
    if isinstance(v, bool): return str(v)
    if isinstance(v, (int, float)): return round(float(v), 6)
    v = str(v).strip()
    if v.startswith("="): return v.replace(";", ",").replace(" ", "")
    try: return round(float(v), 6)
    except ValueError: return v


def plan_patch(b, live, audit_tab, price):
    """bandingkan baris builder dengan isi live (FORMULA). Hasil: (struktur_sama, [index baris berubah])."""
    want = []
    for row in b.rows:
        want.append([f"='{audit_tab}'!{price.get(v[1], 'H1')}" if isinstance(v, tuple) else v for v in row["c"]])
    live = [list(r) + [""] * (11 - len(r)) for r in live[:len(want)]]
    live += [[""] * 11] * (len(want) - len(live))
    same = True
    for w, l, row in zip(want, live, b.rows):   # struktur: bab di posisi yang sama & total di baris yang sama
        if row["k"] in ("bab", "total") and _norm(w[0]) != _norm(l[0]): same = False; break
    changed = [i for i, (w, l) in enumerate(zip(want, live)) if [_norm(x) for x in w] != [_norm(x) for x in l[:11]]]
    return same, changed, want


def patch(a, spec):
    """--prepare patch: tulis hanya baris yang berubah (nilai+format baris itu); Audit ditulis ulang bila isinya berubah.
    Format/warna manual di baris lain tidak disentuh. Struktur berubah (bab bergeser / total pindah) -> keluar kode 3."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build as gbuild
    creds = service_account.Credentials.from_service_account_file(a.creds, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    S = gbuild("sheets", "v4", credentials=creds, cache_discovery=False).spreadsheets(); ID = a.spreadsheet
    vals = S.values().get(spreadsheetId=ID, range="AHS!A1:E3000").execute().get("values", [])[1:]
    ahs = Ahs([{"u": r[0], "s": r[2] if len(r) > 2 else "", "h": r[3] if len(r) > 3 else "", "c": r[4] if len(r) > 4 else ""} for r in vals if r and r[0]])
    b = Builder(spec, ahs).build()
    errs = [e for e in b.errors if not e.startswith("PERINGATAN")]
    if errs:
        for e in errs: print(e)
        sys.exit("BERHENTI: perbaiki error di atas dulu")
    tab = spec["project"]["tab"]; atab = spec["project"].get("audit_tab", "Audit")
    meta = S.get(spreadsheetId=ID, fields="sheets(properties(sheetId,title,gridProperties))").execute()
    sh = {x["properties"]["title"]: x["properties"] for x in meta["sheets"]}
    if tab not in sh or atab not in sh: sys.exit(f"tab '{tab}' / '{atab}' tidak ada — pakai --prepare template/clone")
    sid, asid = sh[tab]["sheetId"], sh[atab]["sheetId"]
    live = S.values().get(spreadsheetId=ID, range=f"'{tab}'!A{DS}:K{DS + len(b.rows) + 60}", valueRenderOption="FORMULA").execute().get("values", [])
    arows, price = build_audit(spec, b, tab)
    same, changed, _ = plan_patch(b, live, atab, price)
    if not same or len(live) > len(b.rows) + 3:
        print("STRUKTUR BERUBAH: jumlah/posisi baris RAB beda dengan tab live -> perlu --prepare none (bangun ulang)")
        sys.exit(3)
    full = rab_requests(sid, b, build_header(spec), atab, price)[2]["updateCells"]["rows"]
    reqs = [{"updateCells": {"range": _rng(sid, DS - 1 + i, DS + i, 0, 11), "rows": [full[i]], "fields": "userEnteredValue,userEnteredFormat,dataValidation"}} for i in changed]
    hdr = build_header(spec)
    live_h = S.values().get(spreadsheetId=ID, range=f"'{tab}'!A1:C{len(hdr)}", valueRenderOption="FORMULA").execute().get("values", [])
    for i, r in enumerate(hdr):
        lr = (live_h[i] if i < len(live_h) else []) + [""] * 3
        if i >= 3 and [_norm(x) for x in r] != [_norm(x) for x in lr[:3]]:
            reqs.append({"updateCells": {"range": _rng(sid, i, i + 1, 0, 3), "rows": [{"values": [{"userEnteredValue": _val(v)} for v in r]}], "fields": "userEnteredValue"}})
    live_a = S.values().get(spreadsheetId=ID, range=f"'{atab}'!A1:I{len(arows) + 80}", valueRenderOption="FORMULA").execute().get("values", [])
    audit_changed = len(live_a) != len([r for r in arows]) or any([_norm(x) for x in r] != [_norm(x) for x in (list(l) + [""] * 9)[:9]] for r, l in zip(arows, live_a))
    if audit_changed:
        reqs.append({"updateCells": {"range": _rng(asid, 0, sh[atab]["gridProperties"]["rowCount"], 0, 9), "fields": "userEnteredValue,userEnteredFormat"}})
        reqs += audit_requests(asid, arows)
    if reqs: S.batchUpdate(spreadsheetId=ID, body={"requests": reqs}).execute()
    cell = f"'{tab}'!A{b.total_row + 3}"
    S.values().update(spreadsheetId=ID, range=cell, valueInputOption="USER_ENTERED", body={"values": [[check_formula(b)]]}).execute()
    chk = S.values().get(spreadsheetId=ID, range=cell).execute()["values"][0][0]
    S.values().clear(spreadsheetId=ID, range=cell).execute()
    err, zero, total, subs = (chk.split("|") + ["", "", "", ""])[:4]
    print(f"PATCH tab '{tab}': {len(changed)} baris ditulis ({', '.join(str(DS + i) for i in changed[:30])}{'…' if len(changed) > 30 else ''}); "
          f"audit {'ditulis ulang' if audit_changed else 'tetap'}")
    print(f"error={err} harga0={zero} total=Rp{int(float(total or 0)):,}".replace(",", "."))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input"); ap.add_argument("--out", default="out"); ap.add_argument("--ahs")
    ap.add_argument("--push", action="store_true"); ap.add_argument("--creds"); ap.add_argument("--spreadsheet")
    ap.add_argument("--prepare", default="template", help="template | clone:<tab> | patch (tulis baris yang berubah saja) | none (bangun ulang tab)")
    ap.add_argument("--sheet-id", type=int, default=0); ap.add_argument("--audit-sheet-id", type=int, default=1)
    a = ap.parse_args()
    spec = json.load(open(a.input, encoding="utf-8"))
    if a.push:
        if not (a.creds and a.spreadsheet): sys.exit("--push butuh --creds dan --spreadsheet")
        if a.prepare == "patch": return patch(a, spec)
        return push(a, spec, None)
    if not a.ahs: sys.exit("mode offline butuh --ahs (ekspor tab AHS) untuk validasi spec")
    b = Builder(spec, Ahs(load_ahs(a.ahs))).build()
    for e in b.errors: print(e)
    os.makedirs(a.out, exist_ok=True)
    atab = spec["project"].get("audit_tab", "Audit")
    arows, price = build_audit(spec, b, spec["project"]["tab"])
    reqs = audit_requests(a.audit_sheet_id, arows) + rab_requests(a.sheet_id, b, build_header(spec), atab, price)
    json.dump(reqs, open(os.path.join(a.out, "connector_batch.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump({"cell": f"A{b.total_row + 3}", "formula": check_formula(b)}, open(os.path.join(a.out, "check_cell.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print(f"Baris data {DS}..{b.total_row}; bab {b.bab_rows}; AHS terpakai {len(b.used)}; analisa {len(b.audit_used)}; "
          f"connector_batch.json {os.path.getsize(os.path.join(a.out, 'connector_batch.json')) // 1024} KB")


if __name__ == "__main__":
    main()
