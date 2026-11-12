#!/usr/bin/env python3
"""
build_rab.py v2 - Serasa RAB builder.

Input JSON (references/input-format.md) -> isi tab RAB format Serasa + baris analisa.

Dua cara menulis ke Google Sheets:
  A) --push (disarankan, hemat token): script menulis langsung lewat service account.
     pip install google-api-python-client google-auth
     python3 build_rab.py input.json --push --creds key.json --spreadsheet <ID> --prepare template
     python3 build_rab.py input.json --push --creds key.json --spreadsheet <ID> --prepare clone:"BKU House" --analisa-start auto
     Script mencetak ringkasan pendek saja (subtotal per bab, total, jumlah error) -> agen tidak perlu
     membaca ulang sheet.
  B) Tanpa kredensial (connector Sheets): script menulis 3 file siap kirim + 1 file cek:
     analisa.json (update_formulas), values_AH.json (update_values A:H polos), connector_batch.json
     (SATU update_spreadsheet: header, rumus universal via repeatCell, override, format), check_cell.json.
     Agen menyalin isi file apa adanya - tidak menyusun ulang baris, tidak mencetak data ke chat.

--prepare:
  template        tab "Serasa Template" di file salinan template -> duplikat, unmerge, kosongkan, sisip 6
                  baris luasan, kembalikan blok IKK ke E1:F5, buat tab Analisa, named range MAH/ANL.
  clone:<tab>     sheet proyek yang sudah ada -> duplikat tab proyek <tab> (sudah siap: IKK, logo),
                  kosongkan blok luasan & baris >= header. Analisa ditambahkan ke tab analisa yang
                  sudah dipakai named range ANL (mulai --analisa-start, 'auto' = 3 baris setelah baris terakhir).
  none            tab sudah siap; hanya tulis.

Locale spreadsheet Indonesia: pemisah argumen ';' dan desimal ','.
"""
import argparse, json, os, re, sys

COLS = ["Bab", "Uraian Pekerjaan", "Ruang / Area", "Lantai", "Kode Specs", "Spec", "Satuan", "Volume", "Harga Satuan", "Total Harga"]
FIN_LABEL = {"ekspos": "Aci Ekspos + Coating", "putih": "Cat Putih", "terracotta": "Cat Tekstur Terracotta", "pola": "Aci Ekspos Pola Blok"}
FIN_CODES = {"ekspos": ("AD2", "W6", "W6"), "putih": ("AD1", "W1", "W2"), "terracotta": ("AD1", "W76", "W76"), "pola": (None, "W7", "W7")}
DEFAULT_OPEN = {"openingan": "X-01", "swing": "X-02", "swing_hw": "X-03", "glass": "X-04", "slide_hw": "X-05", "fixed": "X-06", "louvre": "X-07"}


def num_id(x):
    return ("%.4f" % x).rstrip("0").rstrip(".").replace(".", ",")

def F_univ(r): return f'=IF($E{r}="";"";IFERROR(VLOOKUP($E{r};MAH;2;0);IFERROR(VLOOKUP($E{r};ANL;2;0);"")))'
def I_univ(r): return (f'=IF($E{r}="";"";IFERROR(VLOOKUP($E{r};MAH;6;0)*1,001;IFERROR(VLOOKUP($F{r};AHS!$A:$D;4;0);'
                       f'IFERROR(VLOOKUP($E{r};ANL;8;0);0)))*$F$5)')
def J_univ(r): return f'=IF($H{r}="";"";$H{r}*$I{r})'


class Builder:
    def __init__(self, spec, data_start):
        self.spec, self.ds = spec, data_start
        self.rows, self.over, self.bab_rows, self.sub_rows, self.subtotals = [], {}, [], [], []
        self._s = None
        self.oc = {**DEFAULT_OPEN, **spec.get("opening_codes", {})}

    def r(self): return self.ds + len(self.rows)

    def bab(self, no, title):
        if self._s is not None: self.close()
        self.bab_rows.append(self.r()); self.rows.append([no, title] + [""] * 6); self._s = self.r()

    def close(self):
        s, e = self._s, self.r() - 1
        if e >= s:
            self.over[f"K{e}"] = f"=SUM(J{s}:J{e})"; self.subtotals.append((self.rows[s - 1 - self.ds][0], e))
        self.rows.append([""] * 8); self._s = None

    def sub(self, title):
        self.sub_rows.append(self.r()); self.rows.append(["", title] + [""] * 6)

    def line(self, uraian, ruang, lantai, code, sat, vol, spec=""):
        r = self.r(); self.rows.append(["", uraian, ruang, lantai, code, "", sat, vol])
        if spec: self.over[f"F{r}"] = spec

    def opening(self, o):
        r = self.r(); w, h = float(o["w"]), float(o["h"]); a = round(w * h, 3)
        pn = int(o.get("panels", 1)); t = o["type"]; c = self.oc
        if t == "swing":
            code = f'{c["swing"]}/{c["swing_hw"]}'
            price = f'=({num_id(a)}*VLOOKUP("{c["swing"]}";ANL;8;0)+{pn}*VLOOKUP("{c["swing_hw"]}";ANL;8;0))*$F$5'
        elif t == "slide":
            code = f'{c["glass"]}/{c["slide_hw"]}'
            price = f'=({num_id(a)}*VLOOKUP("{c["glass"]}";ANL;8;0)+{max(pn - 1, 1)}*VLOOKUP("{c["slide_hw"]}";ANL;8;0))*$F$5'
        elif t in ("fix", "louvre"):
            code = c["fixed"] if t == "fix" else c["louvre"]
            price = f'={num_id(a)}*VLOOKUP("{code}";ANL;8;0)*$F$5'
        elif t == "ahs_m2":
            r0 = self.r(); self.rows.append(["", o["uraian"], f'{round(w*100)}x{round(h*100)}', o["lantai"], "AHS", "", "m2", round(a, 2)])
            self.over[f"F{r0}"] = o["ahs"]; return
        else:
            raise ValueError("opening type tidak dikenal: " + t)
        spec = ("Luas bukaan %.2f m2" % a).replace(".", ",") + (f"; {pn} daun" if pn > 1 else "")
        self.rows.append(["", o["uraian"], f'{round(w*100)}x{round(h*100)}', o["lantai"], code, "", "unit", 1])
        self.over[f"F{r}"] = spec; self.over[f"I{r}"] = price

    def _lab(self, w, t):
        return f'Dinding {"Interior" if w.get("interior", True) else "Eksterior"} {w["room"]} Fin. {FIN_LABEL.get(t, t)}'

    def _wall_rows(self, title, code_of):
        first = True
        for w in self.spec["walls"]:
            for t, a in w["parts"].items():
                code = code_of(w, t)
                if not code: continue
                if first: self.sub_rows.append(self.r())
                self.rows.append(["", title if first else "", self._lab(w, t), w["lantai"], code, "", "M2", a]); first = False

    def wall_block(self):
        self._wall_rows("Plester (per ruang)", lambda w, t: "PD2")
        self._wall_rows("Aci (per ruang)", lambda w, t: FIN_CODES.get(t, ("AD1",))[0])
        per = {}
        for o in self.spec.get("openings", []):
            w, h = float(o["w"]), float(o["h"])
            k = 2 * (w + h) if o["type"] in ("fix", "louvre") else 2 * h + w
            p = per.setdefault(o["lantai"], [0, 0]); p[0] += k; p[1] += 1
        for lt, (m1, n) in per.items():
            self.line("Openingan kusen (sponneng bukaan pintu & jendela)", f"{n} bukaan (lihat Bab V)", lt, self.oc["openingan"], "m1", round(m1, 2))

    def finish_block(self):
        def code(w, t):
            cs = FIN_CODES.get(t, ("AD1", "W1", "W2"))
            return w.get("finish_code", {}).get(t) or (cs[1] if w.get("interior", True) else cs[2])
        self._wall_rows("FINISHING DINDING", code)

    def build(self):
        for b in self.spec["bab"]:
            self.bab(b["no"], b["title"])
            for it in b.get("rows", []):
                t = it["type"]
                if t == "sub": self.sub(it["title"])
                elif t in ("master", "analisa"): self.line(it["uraian"], it.get("ruang", ""), it.get("lantai", ""), it["code"], it["sat"], it["vol"], it.get("spec", ""))
                elif t == "ahs": self.line(it["uraian"], it.get("ruang", ""), it.get("lantai", ""), "AHS", it["sat"], it["vol"], it["ahs"])
                elif t == "note":
                    r = self.r(); self.rows.append(["", it["uraian"], "", "", "-", "", "", ""])
                    if it.get("spec"): self.over[f"F{r}"] = it["spec"]
                elif t == "wall_plaster_aci": self.wall_block()
                elif t == "wall_finish": self.finish_block()
                elif t == "openings":
                    for o in self.spec.get("openings", []): self.opening(o)
                else: raise ValueError("row type tidak dikenal: " + t)
        self.close()
        self.total_row = self.r(); self.rows.append(["Total"] + [""] * 7); self.bab_rows.append(self.total_row)
        self.over[f"I{self.total_row}"] = f"=SUM(K{self.ds}:K{self.total_row - 1})"
        self.over[f"J{self.total_row}"] = ""; self.over[f"F{self.total_row}"] = ""
        return self


def build_analisa(spec, start, with_header):
    rows = []
    if with_header:
        rows += [["ANALISA HARGA SATUAN - " + spec["project"]["title"]],
                 ["Harga di sheet ini = harga basis. Di sheet RAB dikali koefisien IKK (F5). MASTER/AHS diambil langsung; lainnya asumsi harga pasar."],
                 ["Kode", "Uraian / Komponen", "Satuan", "Koef", "Harga Komponen", "Jumlah", "Sumber", "Harga Satuan", "Catatan"]]
    else:
        rows += [["ANALISA HARGA SATUAN - " + spec["project"]["title"]]]
    for it in spec.get("analisa", []):
        r0 = start + len(rows)
        rows.append([it["code"], it["name"], it["sat"], "", "", "", "", None, it.get("note", "")])
        for c in it["components"]:
            r = start + len(rows); p = c["price"]
            if isinstance(p, str) and p.startswith("MASTER:"): p = f'=VLOOKUP("{p[7:]}";\'MASTER AHS\'!$B$1:$G$400;6;0)'
            elif isinstance(p, str) and p.startswith("AHS:"): p = f'=VLOOKUP("{p[4:]}";AHS!$A:$D;4;0)'
            rows.append(["", "   " + c["name"], c["sat"], c["koef"], p, f"=D{r}*E{r}", c.get("src", "asumsi"), "", ""])
        rows[r0 - start][7] = f"=SUM(F{r0 + 1}:F{start + len(rows) - 1})"
        rows.append([""])
    return [x + [""] * (9 - len(x)) for x in rows]


def build_header(spec):
    p, L = spec["project"], spec["luasan"]; lt = L["lantai"]
    assert 1 <= len(lt) <= 3, "blok luasan mendukung 1-3 lantai"
    rows = [["Rencana Anggaran Biaya", "", ""], [p["title"], "", ""], [L.get("tanah_label", "Luas Tanah"), "", L["tanah"]],
            ["Luas Bangunan Total (" + " + ".join(x["short"] for x in lt) + ")", "", "=" + "+".join(f"C{5 + i}" for i in range(len(lt)))]]
    rows += [[x["label"], "", "=" + "+".join(num_id(v) for _, v in x["items"])] for x in lt]
    notes = [x["short"] + " = " + " + ".join(f"{n} {num_id(v)}" for n, v in x["items"]) + " m²." for x in lt]
    notes.append(L.get("note", "Luas kotor dari model SKP (sisi luar dinding); area tanpa atap & carport tidak termasuk."))
    free = 8 - len(rows)
    if len(notes) > free: notes = notes[:free - 1] + [" ".join(notes[free - 1:])]
    rows += [[n, "", ""] for n in notes]; rows += [["", "", ""]] * (8 - len(rows))
    return rows


# ---------- request builders (dipakai push & connector batch)
def _rng(sid, r0, r1, c0, c1): return {"sheetId": sid, "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1}

def _cell(v):
    if isinstance(v, bool): return {"boolValue": v}
    if isinstance(v, (int, float)): return {"numberValue": v}
    v = "" if v is None else str(v)
    return {"formulaValue": v} if v.startswith("=") else {"stringValue": v}

def _rows_req(sid, r0, c0, rows):
    w = max(len(r) for r in rows)
    return {"updateCells": {"range": _rng(sid, r0, r0 + len(rows), c0, c0 + w),
                            "rows": [{"values": [{"userEnteredValue": _cell(v)} for v in r + [""] * (w - len(r))]} for r in rows],
                            "fields": "userEnteredValue"}}

def data_requests(sid, b, header, hr, with_values=True):
    ds, last = b.ds, b.total_row
    req = [_rows_req(sid, 0, 0, header), _rows_req(sid, hr - 1, 0, [COLS])]
    if with_values: req.append(_rows_req(sid, ds - 1, 0, b.rows))
    for col, f in ((5, F_univ), (8, I_univ), (9, J_univ)):
        req.append({"repeatCell": {"range": _rng(sid, ds - 1, last, col, col + 1), "cell": {"userEnteredValue": {"formulaValue": f(ds)}}, "fields": "userEnteredValue"}})
    for k, v in b.over.items():
        c, r = "ABCDEFGHIJK".index(k[0]), int(k[1:])
        req.append(_rows_req(sid, r - 1, c, [[v]]))
    return req

def format_requests(sid, b, hr, n_lantai):
    last, hdr = b.total_row, b.ds - 1; nl = 3 + n_lantai
    TF = "userEnteredFormat.textFormat"
    req = [
        {"repeatCell": {"range": _rng(sid, hdr, last, 0, 11), "cell": {"userEnteredFormat": {"textFormat": {"fontFamily": "Arial", "fontSize": 9, "bold": False}, "verticalAlignment": "MIDDLE", "wrapStrategy": "WRAP"}}, "fields": TF + ",userEnteredFormat.verticalAlignment,userEnteredFormat.wrapStrategy"}},
        {"repeatCell": {"range": _rng(sid, hdr, last, 7, 8), "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"}, "horizontalAlignment": "RIGHT"}}, "fields": "userEnteredFormat.numberFormat,userEnteredFormat.horizontalAlignment"}},
        {"repeatCell": {"range": _rng(sid, hdr, last, 8, 11), "cell": {"userEnteredFormat": {"numberFormat": {"type": "CURRENCY", "pattern": "\"Rp\"#,##0"}, "horizontalAlignment": "RIGHT"}}, "fields": "userEnteredFormat.numberFormat,userEnteredFormat.horizontalAlignment"}},
        {"repeatCell": {"range": _rng(sid, hdr, last, 10, 11), "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "fontSize": 9}}}, "fields": TF}},
        {"repeatCell": {"range": _rng(sid, hr - 1, hr, 0, 11), "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "fontSize": 10}, "backgroundColor": {"red": 0.85, "green": 0.85, "blue": 0.85}, "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE", "wrapStrategy": "WRAP"}}, "fields": TF + ",userEnteredFormat.backgroundColor,userEnteredFormat.horizontalAlignment,userEnteredFormat.verticalAlignment,userEnteredFormat.wrapStrategy"}},
        {"updateBorders": {"range": _rng(sid, hr - 1, last, 0, 11), "innerHorizontal": {"style": "SOLID", "color": {"red": 0.85, "green": 0.85, "blue": 0.85}}, "bottom": {"style": "SOLID"}, "top": {"style": "SOLID"}}},
        {"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": hr}}, "fields": "gridProperties.frozenRowCount"}},
        {"repeatCell": {"range": _rng(sid, 2, nl, 2, 3), "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.0 \"m²\""}, "textFormat": {"fontFamily": "Calibri", "fontSize": 10, "bold": True}, "horizontalAlignment": "LEFT"}}, "fields": "userEnteredFormat.numberFormat," + TF + ",userEnteredFormat.horizontalAlignment"}},
        {"repeatCell": {"range": _rng(sid, 2, nl, 0, 1), "cell": {"userEnteredFormat": {"textFormat": {"fontFamily": "Calibri", "fontSize": 10}, "wrapStrategy": "OVERFLOW_CELL"}}, "fields": TF + ",userEnteredFormat.wrapStrategy"}},
        {"repeatCell": {"range": _rng(sid, nl, 8, 0, 1), "cell": {"userEnteredFormat": {"textFormat": {"fontFamily": "Calibri", "fontSize": 8, "italic": True, "foregroundColor": {"red": 0.4, "green": 0.4, "blue": 0.4}}, "wrapStrategy": "OVERFLOW_CELL"}}, "fields": TF + ",userEnteredFormat.wrapStrategy"}},
        {"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"rowCount": last + 15}}, "fields": "gridProperties.rowCount"}},
    ]
    for r in b.bab_rows:
        req.append({"repeatCell": {"range": _rng(sid, r - 1, r, 0, 11), "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "fontSize": 10}, "backgroundColor": {"red": 0.93, "green": 0.89, "blue": 0.82}}}, "fields": TF + ",userEnteredFormat.backgroundColor"}})
    for r in b.sub_rows:
        req.append({"repeatCell": {"range": _rng(sid, r - 1, r, 1, 2), "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "italic": True, "fontSize": 9}}}, "fields": TF}})
    for c, w in [(0, 40), (1, 280), (2, 280), (3, 75), (4, 75), (5, 300), (6, 65), (7, 65), (8, 120), (9, 120), (10, 120)]:
        req.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": c, "endIndex": c + 1}, "properties": {"pixelSize": w}, "fields": "pixelSize"}})
    return req

def check_formula(b):
    ds, tr = b.ds, b.total_row
    return (f'=SUMPRODUCT(--ISERROR(F{ds}:K{tr}))&"|"&COUNTIFS(E{ds}:E{tr};"<>";E{ds}:E{tr};"<>-";I{ds}:I{tr};0)'
            f'&"|"&TEXT(I{tr};"#,##0")&"|"&TEXTJOIN(";";TRUE;' + ";".join(f'TEXT(K{e};"0")' for _, e in b.subtotals) + ")")


# ---------- push (service account)
def push(a, spec, b, header, analisa_fn):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build as gbuild
    creds = service_account.Credentials.from_service_account_file(a.creds, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    S = gbuild("sheets", "v4", credentials=creds, cache_discovery=False).spreadsheets(); sid_ = a.spreadsheet
    def batch(reqs):
        return S.batchUpdate(spreadsheetId=sid_, body={"requests": reqs}).execute() if reqs else None
    def vals(rng):
        return S.values().get(spreadsheetId=sid_, range=rng, valueRenderOption="FORMULA").execute().get("values", [])
    meta = S.get(spreadsheetId=sid_, fields="sheets(properties(sheetId,title,gridProperties),merges),namedRanges").execute()
    sheets = {s["properties"]["title"]: s for s in meta["sheets"]}
    named = {n["name"]: n for n in meta.get("namedRanges", [])}
    tab, atab = spec["project"]["tab"], spec["project"].get("analisa_tab", "Analisa " + spec["project"]["tab"])
    if tab in sheets and a.prepare != "none":
        sys.exit(f"Tab '{tab}' sudah ada - ganti nama tab di input atau pakai --prepare none")
    mode = a.prepare
    if mode == "template":
        src = sheets["Serasa Template"]["properties"]
        r = batch([{"duplicateSheet": {"sourceSheetId": src["sheetId"], "insertSheetIndex": 1, "newSheetName": tab}}])
        sid = r["replies"][0]["duplicateSheet"]["properties"]["sheetId"]
        end = src["gridProperties"]["rowCount"]
        reqs = [{"unmergeCells": {"range": _rng(sid, 9, end, 0, 11)}},
                {"updateCells": {"range": _rng(sid, 9, end, 0, 11), "fields": "userEnteredValue,userEnteredFormat"}},
                {"insertDimension": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 2, "endIndex": 8}, "inheritFromBefore": True}},
                {"cutPaste": {"source": _rng(sid, 8, 11, 4, 6), "destination": {"sheetId": sid, "rowIndex": 2, "columnIndex": 4}, "pasteType": "PASTE_NORMAL"}}]
        if atab not in sheets:
            reqs.append({"addSheet": {"properties": {"title": atab, "gridProperties": {"rowCount": 300, "columnCount": 10}}}})
        rep = batch(reqs) or {}
        added = [x["addSheet"]["properties"]["sheetId"] for x in rep.get("replies", []) if x and "addSheet" in x]
        asid = added[0] if added else sheets[atab]["properties"]["sheetId"]
        mah = sheets["MASTER AHS"]["properties"]["sheetId"]
        nr = []
        for name, rg in (("MAH", _rng(mah, 0, 400, 1, 7)), ("ANL", _rng(asid, 0, 300, 0, 8))):
            if name in named: nr.append({"updateNamedRange": {"namedRange": {"namedRangeId": named[name]["namedRangeId"], "name": name, "range": rg}, "fields": "range"}})
            else: nr.append({"addNamedRange": {"namedRange": {"name": name, "range": rg}}})
        batch(nr)
        S.values().update(spreadsheetId=sid_, range=f"'{tab}'!F1:F2", valueInputOption="USER_ENTERED",
                          body={"values": [[spec["project"]["zona"]], [spec["project"].get("basis", "Kota Bogor")]]}).execute()
        astart = 1
    elif mode.startswith("clone:"):
        srcname = mode[6:]; src = sheets[srcname]["properties"]
        r = batch([{"duplicateSheet": {"sourceSheetId": src["sheetId"], "insertSheetIndex": src.get("index", 0) + 1, "newSheetName": tab}}])
        sid = r["replies"][0]["duplicateSheet"]["properties"]["sheetId"]; end = src["gridProperties"]["rowCount"]
        batch([{"updateCells": {"range": _rng(sid, a.header_row - 1, end, 0, 11), "fields": "userEnteredValue,userEnteredFormat"}},
               {"updateCells": {"range": _rng(sid, 0, 8, 0, 3), "fields": "userEnteredValue"}}])
        anl = named["ANL"]["range"]; asid = anl["sheetId"]
        atab = [t for t, s in sheets.items() if s["properties"]["sheetId"] == asid][0]
        if a.analisa_start == "auto":
            colA = vals(f"'{atab}'!A1:B{anl.get('endRowIndex', 300)}")
            astart = max([i + 1 for i, row in enumerate(colA) if any(str(x).strip() for x in row)] + [0]) + 3
        else:
            astart = int(a.analisa_start)
    else:
        sid = sheets[tab]["properties"]["sheetId"]; astart = int(a.analisa_start) if a.analisa_start != "auto" else 1
        asid = named["ANL"]["range"]["sheetId"]; atab = [t for t, s in sheets.items() if s["properties"]["sheetId"] == asid][0]
    analisa = analisa_fn(astart, astart == 1)
    if astart + len(analisa) > 300: sys.exit("Analisa melewati baris 300 (batas named range ANL) - perbesar ANL dulu")
    batch([_rows_req(asid, astart - 1, 0, analisa)])
    batch(data_requests(sid, b, header, a.header_row) + format_requests(sid, b, a.header_row, len(spec["luasan"]["lantai"])))
    # verifikasi singkat (tanpa membaca seluruh sheet)
    S.values().update(spreadsheetId=sid_, range=f"'{tab}'!A{b.total_row + 3}", valueInputOption="USER_ENTERED", body={"values": [[check_formula(b)]]}).execute()
    chk = S.values().get(spreadsheetId=sid_, range=f"'{tab}'!A{b.total_row + 3}").execute()["values"][0][0]
    S.values().clear(spreadsheetId=sid_, range=f"'{tab}'!A{b.total_row + 3}").execute()
    err, zero, total, subs = (chk.split("|") + ["", "", "", ""])[:4]
    print(f"PUSHED tab '{tab}' (sheetId {sid}); analisa '{atab}' baris {astart}..{astart + len(analisa) - 1}")
    print(f"error={err} harga0={zero} total=Rp{total}")  # harga0 = baris berkode dengan harga 0
    for (no, _), v in zip(b.subtotals, subs.split(";")): print(f"  Bab {no}: Rp{int(float(v or 0)):,}".replace(",", "."))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input"); ap.add_argument("--out", default="out")
    ap.add_argument("--header-row", type=int, default=16, help="baris header kolom (template baru: 16; tab hasil clone mengikuti sumber, mis. BKU House = 15)")
    ap.add_argument("--analisa-start", default="1", help="baris awal analisa; 'auto' untuk clone (setelah baris terakhir)")
    ap.add_argument("--sheet-id", type=int, default=0, help="sheetId tab RAB (mode connector)")
    ap.add_argument("--analisa-sheet-id", type=int, default=0, help="sheetId tab analisa (mode connector)")
    ap.add_argument("--push", action="store_true"); ap.add_argument("--creds"); ap.add_argument("--spreadsheet")
    ap.add_argument("--prepare", default="none", help="template | clone:<nama tab> | none")
    a = ap.parse_args()
    spec = json.load(open(a.input, encoding="utf-8"))
    b = Builder(spec, a.header_row + 1).build(); header = build_header(spec)
    analisa_fn = lambda start, hdr: build_analisa(spec, start, hdr)
    print(f"Baris data {b.ds}..{b.total_row}; bab di {b.bab_rows}; {len(b.rows)} baris")
    if a.push:
        if not (a.creds and a.spreadsheet): sys.exit("--push butuh --creds dan --spreadsheet")
        return push(a, spec, b, header, analisa_fn)
    os.makedirs(a.out, exist_ok=True)
    astart = 1 if a.analisa_start == "auto" else int(a.analisa_start)
    analisa = analisa_fn(astart, astart == 1)
    # 1) nilai A:H polos -> update_values (format paling ringkas); 2) analisa -> update_formulas;
    # 3) sisanya (header, rumus universal, override, format) -> satu update_spreadsheet
    dump = lambda n, o: json.dump(o, open(os.path.join(a.out, n), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    dump("values_AH.json", {"range": f"A{b.ds}:H{b.total_row}", "values": b.rows})
    dump("analisa.json", {"range": f"A{astart}:I{astart + len(analisa) - 1}", "values": analisa})
    batch = data_requests(a.sheet_id, b, header, a.header_row, with_values=False) + format_requests(a.sheet_id, b, a.header_row, len(spec["luasan"]["lantai"]))
    dump("connector_batch.json", batch)
    json.dump({"cell": f"A{b.total_row + 3}", "formula": check_formula(b), "baca": "error|harga0|total|subtotal per bab (;) - tulis rumus, baca 1 sel, lalu kosongkan sel itu",
               "bab": [no for no, _ in b.subtotals]}, open(os.path.join(a.out, "check_cell.json"), "w", encoding="utf-8"), ensure_ascii=False)
    n = os.path.getsize(os.path.join(a.out, "connector_batch.json"))
    sz = lambda f: os.path.getsize(os.path.join(a.out, f)) // 1024
    print(f"Urutan kirim (connector): analisa.json -> update_formulas tab analisa ({sz('analisa.json')} KB, baris {astart}..{astart + len(analisa) - 1}); "
          f"values_AH.json -> update_values tab RAB ({sz('values_AH.json')} KB); connector_batch.json -> update_spreadsheet ({len(batch)} request, {n // 1024} KB); "
          f"lalu check_cell.json")


if __name__ == "__main__":
    main()
