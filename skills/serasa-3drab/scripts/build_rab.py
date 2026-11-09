#!/usr/bin/env python3
"""
build_rab.py - Serasa RAB builder.

Mengubah file input JSON (hasil analisis SKP + denah) menjadi isi sheet RAB format Serasa:
  - <out>/rab_values.json     : nilai kolom A..H mulai baris data pertama (teks/angka, tanpa rumus harga)
  - <out>/rab_overrides.json  : sel yang butuh nilai/rumus khusus (spec AHS, harga pintu, subtotal, total)
  - <out>/analisa_rows.json   : isi tab Analisa (A..I, termasuk rumus)
  - <out>/header.json         : blok judul + luasan (A1:C8)
  - <out>/format_requests.json: request batchUpdate Google Sheets (lebar kolom, warna bab, dsb.)
  - <out>/summary.txt         : ringkasan baris & posisi bab

Opsional --push: langsung menulis ke Google Sheets memakai service account
(pip install google-api-python-client google-auth).

Konvensi spreadsheet template (locale Indonesia): pemisah argumen ';' dan desimal ','.
Lihat references/sheet-format.md.
"""
import argparse, json, os, sys

HEADER_ROW = 16           # baris header kolom (Bab | Uraian | ...) setelah 6 baris luasan disisipkan di baris 3-8
DATA_START = 17           # baris data pertama
COLS = ["Bab", "Uraian Pekerjaan", "Ruang / Area", "Lantai", "Kode Specs", "Spec", "Satuan", "Volume", "Harga Satuan", "Total Harga"]

FIN_LABEL = {"ekspos": "Aci Ekspos + Coating", "putih": "Cat Putih", "terracotta": "Cat Tekstur Terracotta", "pola": "Aci Ekspos Pola Blok"}
# finishing type -> (kode aci, kode finishing interior, kode finishing eksterior); None = tidak ada baris aci
FIN_CODES = {
    "ekspos":     ("AD2", "W6", "W6"),
    "putih":      ("AD1", "W1", "W2"),
    "terracotta": ("AD1", "W76", "W76"),
    "pola":       (None, "W7", "W7"),
}

def num_id(x):
    """angka -> literal desimal locale Indonesia untuk dipakai di dalam rumus"""
    s = ("%.4f" % x).rstrip("0").rstrip(".")
    return s.replace(".", ",")

def F_univ(r):
    return f'=IF($E{r}="";"";IFERROR(VLOOKUP($E{r};MAH;2;0);IFERROR(VLOOKUP($E{r};ANL;2;0);"")))'

def I_univ(r):
    return (f'=IF($E{r}="";"";IFERROR(VLOOKUP($E{r};MAH;6;0)*1,001;IFERROR(VLOOKUP($F{r};AHS!$A:$D;4;0);'
            f'IFERROR(VLOOKUP($E{r};ANL;8;0);0)))*$F$5)')

def J_univ(r):
    return f'=IF($H{r}="";"";$H{r}*$I{r})'


class Builder:
    def __init__(self, spec):
        self.spec = spec
        self.rows = []         # A..H
        self.over = {}         # "F15": value/formula
        self.bab_rows = []
        self.sub_rows = []
        self.bab_ranges = []
        self._bab_start = None

    def r(self):
        return DATA_START + len(self.rows)

    # ---- primitives
    def bab(self, no, title):
        if self._bab_start is not None:
            self.close()
        self.bab_rows.append(self.r())
        self.rows.append([no, title, "", "", "", "", "", ""])
        self._bab_start = self.r()

    def close(self):
        s, e = self._bab_start, self.r() - 1
        if e >= s:
            self.over[f"K{e}"] = f"=SUM(J{s}:J{e})"
        self.rows.append([""] * 8)
        self._bab_start = None

    def sub(self, title):
        self.sub_rows.append(self.r())
        self.rows.append(["", title, "", "", "", "", "", ""])

    def master(self, uraian, ruang, lantai, code, sat, vol):
        self.rows.append(["", uraian, ruang, lantai, code, "", sat, vol])

    def ahs(self, uraian, ruang, lantai, ahs_name, sat, vol):
        r = self.r()
        self.rows.append(["", uraian, ruang, lantai, "AHS", "", sat, vol])
        self.over[f"F{r}"] = ahs_name

    def anl(self, uraian, ruang, lantai, code, sat, vol):
        self.rows.append(["", uraian, ruang, lantai, code, "", sat, vol])

    def note(self, uraian, spec=""):
        r = self.r()
        self.rows.append(["", uraian, "", "", "-", "", "", ""])
        if spec:
            self.over[f"F{r}"] = spec

    def opening(self, o):
        """pintu/jendela per unit: harga = luas x analisa + hardware"""
        r = self.r()
        w, h = float(o["w"]), float(o["h"])
        a = round(w * h, 3)
        pn = int(o.get("panels", 1))
        typ = o["type"]
        c = self.spec.get("opening_codes", {})
        if typ == "swing":
            code = f'{c.get("swing","X-02")}/{c.get("swing_hw","X-03")}'
            price = f'=({num_id(a)}*VLOOKUP("{c.get("swing","X-02")}";ANL;8;0)+VLOOKUP("{c.get("swing_hw","X-03")}";ANL;8;0))*$F$5'
        elif typ == "slide":
            code = f'{c.get("glass","X-04")}/{c.get("slide_hw","X-05")}'
            n = max(pn - 1, 1)
            price = f'=({num_id(a)}*VLOOKUP("{c.get("glass","X-04")}";ANL;8;0)+{n}*VLOOKUP("{c.get("slide_hw","X-05")}";ANL;8;0))*$F$5'
        elif typ == "fix":
            code = c.get("fixed", "X-06")
            price = f'={num_id(a)}*VLOOKUP("{code}";ANL;8;0)*$F$5'
        elif typ == "louvre":
            code = c.get("louvre", "X-07")
            price = f'={num_id(a)}*VLOOKUP("{code}";ANL;8;0)*$F$5'
        elif typ == "ahs_m2":     # contoh: pintu besi dari AHS, volume m2
            self.ahs(o["uraian"], f'{int(round(w*100))}x{int(round(h*100))}', o["lantai"], o["ahs"], "m2", round(w * h, 2))
            return
        else:
            raise ValueError("opening type tidak dikenal: " + typ)
        size = f'{int(round(w*100))}x{int(round(h*100))}'
        spec = ("Luas bukaan %.2f m2" % a).replace(".", ",") + (f"; {pn} daun" if pn > 1 else "")
        self.rows.append(["", o["uraian"], size, o["lantai"], code, "", "unit", 1])
        self.over[f"F{r}"] = spec
        self.over[f"I{r}"] = price

    # ---- generated blocks
    def wall_block(self, walls, openings):
        def lab(w, t):
            return f'Dinding {"Interior" if w.get("interior", True) else "Eksterior"} {w["room"]} Fin. {FIN_LABEL.get(t, t)}'
        first = True
        for w in walls:
            for t, a in w["parts"].items():
                r = self.r()
                self.rows.append(["", "Plester (per ruang)" if first else "", lab(w, t), w["lantai"], "PD2", "", "M2", a])
                if first: self.sub_rows.append(r)
                first = False
        first = True
        for w in walls:
            for t, a in w["parts"].items():
                aci = FIN_CODES.get(t, ("AD1",))[0]
                if not aci:
                    continue
                r = self.r()
                self.rows.append(["", "Aci (per ruang)" if first else "", lab(w, t), w["lantai"], aci, "", "M2", a])
                if first: self.sub_rows.append(r)
                first = False
        # openingan kusen per lantai (m1 keliling bukaan)
        per = {}
        for o in openings:
            w, h = float(o["w"]), float(o["h"])
            k = 2 * (w + h) if o["type"] in ("fix", "louvre") else 2 * h + w
            per.setdefault(o["lantai"], [0, 0])
            per[o["lantai"]][0] += k
            per[o["lantai"]][1] += 1
        code = self.spec.get("opening_codes", {}).get("openingan", "X-01")
        for lt, (m1, n) in per.items():
            self.anl("Openingan kusen (sponneng bukaan pintu & jendela)", f"{n} bukaan (lihat Bab V)", lt, code, "m1", round(m1, 2))

    def finish_block(self, walls):
        def lab(w, t):
            return f'Dinding {"Interior" if w.get("interior", True) else "Eksterior"} {w["room"]} Fin. {FIN_LABEL.get(t, t)}'
        first = True
        for w in walls:
            for t, a in w["parts"].items():
                codes = FIN_CODES.get(t, ("AD1", "W1", "W2"))
                code = w.get("finish_code", {}).get(t) or (codes[1] if w.get("interior", True) else codes[2])
                r = self.r()
                self.rows.append(["", "FINISHING DINDING" if first else "", lab(w, t), w["lantai"], code, "", "M2", a])
                if first: self.sub_rows.append(r)
                first = False

    # ---- main
    def build(self):
        sp = self.spec
        for b in sp["bab"]:
            self.bab(b["no"], b["title"])
            for it in b.get("rows", []):
                t = it["type"]
                if t == "sub": self.sub(it["title"])
                elif t == "master": self.master(it["uraian"], it.get("ruang", ""), it.get("lantai", ""), it["code"], it["sat"], it["vol"])
                elif t == "ahs": self.ahs(it["uraian"], it.get("ruang", ""), it.get("lantai", ""), it["ahs"], it["sat"], it["vol"])
                elif t == "analisa": self.anl(it["uraian"], it.get("ruang", ""), it.get("lantai", ""), it["code"], it["sat"], it["vol"])
                elif t == "note": self.note(it["uraian"], it.get("spec", ""))
                elif t == "wall_plaster_aci": self.wall_block(sp["walls"], sp.get("openings", []))
                elif t == "wall_finish": self.finish_block(sp["walls"])
                elif t == "openings":
                    for o in sp.get("openings", []): self.opening(o)
                else: raise ValueError("row type tidak dikenal: " + t)
        self.close()
        tr = self.r()
        self.rows.append(["Total", "", "", "", "", "", "", ""])
        self.bab_rows.append(tr)
        self.over[f"I{tr}"] = f"=SUM(K{DATA_START}:K{tr-1})"
        self.total_row = tr
        return self

    def formulas_FIJ(self):
        """kolom F, I, J untuk seluruh baris data (rumus universal), override diterapkan di atasnya"""
        out = []
        for i, row in enumerate(self.rows):
            r = DATA_START + i
            out.append([F_univ(r), "", "", I_univ(r), J_univ(r)])  # F, G(skip), H(skip), I, J
        return out


def build_analisa(spec):
    rows = [["ANALISA HARGA SATUAN - " + spec["project"]["title"]],
            ["Harga di sheet ini = harga basis (setara kota basis). Di sheet RAB dikali koefisien IKK (F5). "
             "Komponen MASTER/AHS mengambil harga langsung dari tab tersebut; komponen lain = asumsi harga pasar."],
            ["Kode", "Uraian / Komponen", "Satuan", "Koef", "Harga Komponen", "Jumlah", "Sumber", "Harga Satuan", "Catatan"]]
    for it in spec["analisa"]:
        r0 = len(rows) + 1
        rows.append([it["code"], it["name"], it["sat"], "", "", "", "", None, it.get("note", "")])
        for c in it["components"]:
            r = len(rows) + 1
            price = c["price"]
            if isinstance(price, str) and price.startswith("MASTER:"):
                price = f'=VLOOKUP("{price[7:]}";\'MASTER AHS\'!$B$1:$G$400;6;0)'
            elif isinstance(price, str) and price.startswith("AHS:"):
                price = f'=VLOOKUP("{price[4:]}";AHS!$A:$D;4;0)'
            coef = c["koef"]
            rows.append(["", "   " + c["name"], c["sat"], coef, price, f"=D{r}*E{r}", c.get("src", "asumsi"), "", ""])
        r1 = len(rows)
        rows[r0 - 1][7] = f"=SUM(F{r0+1}:F{r1})"
        rows.append([""])
    return [x + [""] * (9 - len(x)) for x in rows]


def build_header(spec):
    """blok A1:C8 (selalu 8 baris). Maks 3 lantai."""
    p, L = spec["project"], spec["luasan"]
    lt = L["lantai"]
    assert 1 <= len(lt) <= 3, "blok luasan mendukung 1-3 lantai"
    rows = [["Rencana Anggaran Biaya", "", ""],
            [p["title"], "", ""],
            [L.get("tanah_label", "Luas Tanah"), "", L["tanah"]],
            ["Luas Bangunan Total (" + " + ".join(x["short"] for x in lt) + ")", "", "=" + "+".join(f"C{5+i}" for i in range(len(lt)))]]
    for x in lt:
        rows.append([x["label"], "", "=" + "+".join(num_id(v) for _, v in x["items"])])
    notes = [x["short"] + " = " + " + ".join(f"{n} {num_id(v)}" for n, v in x["items"]) + " m²." for x in lt]
    notes.append(L.get("note", "Luas kotor dari model SKP (sisi luar dinding); deck/teras tanpa atap & carport tidak termasuk."))
    free = 8 - len(rows)
    if len(notes) > free:
        notes = notes[:free - 1] + [" ".join(notes[free - 1:])]
    rows += [[n, "", ""] for n in notes]
    rows += [["", "", ""]] * (8 - len(rows))
    return rows


def format_requests(sheet_id, b, analisa_sheet_id, n_analisa, spec_lantai):
    def rng(r0, r1, c0, c1, sid=sheet_id):
        return {"sheetId": sid, "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1}
    last = b.total_row
    hdr = DATA_START - 1        # index 0-based baris data pertama
    nl = 2 + 1 + len(spec_lantai)  # index akhir baris luasan (tanah, total, lantai)
    req = [
        {"repeatCell": {"range": rng(hdr, last, 0, 11), "cell": {"userEnteredFormat": {"textFormat": {"fontFamily": "Arial", "fontSize": 9, "bold": False}, "verticalAlignment": "MIDDLE", "wrapStrategy": "WRAP"}}, "fields": "userEnteredFormat.textFormat,userEnteredFormat.verticalAlignment,userEnteredFormat.wrapStrategy"}},
        {"repeatCell": {"range": rng(hdr, last, 7, 8), "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"}, "horizontalAlignment": "RIGHT"}}, "fields": "userEnteredFormat.numberFormat,userEnteredFormat.horizontalAlignment"}},
        {"repeatCell": {"range": rng(hdr, last, 8, 11), "cell": {"userEnteredFormat": {"numberFormat": {"type": "CURRENCY", "pattern": "\"Rp\"#,##0"}, "horizontalAlignment": "RIGHT"}}, "fields": "userEnteredFormat.numberFormat,userEnteredFormat.horizontalAlignment"}},
        {"repeatCell": {"range": rng(hdr, last, 10, 11), "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "fontSize": 9}}}, "fields": "userEnteredFormat.textFormat"}},
        {"repeatCell": {"range": rng(hdr - 1, hdr, 0, 11), "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "fontSize": 10}, "backgroundColor": {"red": 0.85, "green": 0.85, "blue": 0.85}, "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE", "wrapStrategy": "WRAP"}}, "fields": "userEnteredFormat.textFormat,userEnteredFormat.backgroundColor,userEnteredFormat.horizontalAlignment,userEnteredFormat.verticalAlignment,userEnteredFormat.wrapStrategy"}},
        {"updateBorders": {"range": rng(hdr - 1, last, 0, 11), "innerHorizontal": {"style": "SOLID", "color": {"red": 0.85, "green": 0.85, "blue": 0.85}}, "bottom": {"style": "SOLID"}, "top": {"style": "SOLID"}}},
        {"updateSheetProperties": {"properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": hdr}}, "fields": "gridProperties.frozenRowCount"}},
        # luasan
        {"repeatCell": {"range": rng(2, nl + 1, 2, 3), "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.0 \"m²\""}, "textFormat": {"fontFamily": "Calibri", "fontSize": 10, "bold": True}, "horizontalAlignment": "LEFT"}}, "fields": "userEnteredFormat.numberFormat,userEnteredFormat.textFormat,userEnteredFormat.horizontalAlignment"}},
        {"repeatCell": {"range": rng(2, nl + 1, 0, 1), "cell": {"userEnteredFormat": {"textFormat": {"fontFamily": "Calibri", "fontSize": 10}, "wrapStrategy": "OVERFLOW_CELL"}}, "fields": "userEnteredFormat.textFormat,userEnteredFormat.wrapStrategy"}},
        {"repeatCell": {"range": rng(nl + 1, 8, 0, 1), "cell": {"userEnteredFormat": {"textFormat": {"fontFamily": "Calibri", "fontSize": 8, "italic": True, "foregroundColor": {"red": 0.4, "green": 0.4, "blue": 0.4}}, "wrapStrategy": "OVERFLOW_CELL"}}, "fields": "userEnteredFormat.textFormat,userEnteredFormat.wrapStrategy"}},
    ]
    for r in b.bab_rows:
        req.append({"repeatCell": {"range": rng(r - 1, r, 0, 11), "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "fontSize": 10}, "backgroundColor": {"red": 0.93, "green": 0.89, "blue": 0.82}}}, "fields": "userEnteredFormat.textFormat,userEnteredFormat.backgroundColor"}})
    for r in b.sub_rows:
        req.append({"repeatCell": {"range": rng(r - 1, r, 1, 2), "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "italic": True, "fontSize": 9}}}, "fields": "userEnteredFormat.textFormat"}})
    for c, w in [(0, 40), (1, 280), (2, 280), (3, 75), (4, 75), (5, 300), (6, 65), (7, 65), (8, 120), (9, 120), (10, 120)]:
        req.append({"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": c, "endIndex": c + 1}, "properties": {"pixelSize": w}, "fields": "pixelSize"}})
    # analisa
    a = analisa_sheet_id
    req += [
        {"repeatCell": {"range": rng(3, n_analisa, 4, 6, a), "cell": {"userEnteredFormat": {"numberFormat": {"type": "CURRENCY", "pattern": "\"Rp\"#,##0"}}}, "fields": "userEnteredFormat.numberFormat"}},
        {"repeatCell": {"range": rng(3, n_analisa, 7, 8, a), "cell": {"userEnteredFormat": {"numberFormat": {"type": "CURRENCY", "pattern": "\"Rp\"#,##0"}, "textFormat": {"bold": True}}}, "fields": "userEnteredFormat.numberFormat,userEnteredFormat.textFormat"}},
        {"repeatCell": {"range": rng(2, 3, 0, 9, a), "cell": {"userEnteredFormat": {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.85, "green": 0.85, "blue": 0.85}}}, "fields": "userEnteredFormat.textFormat,userEnteredFormat.backgroundColor"}},
        {"addConditionalFormatRule": {"rule": {"ranges": [rng(3, n_analisa, 0, 9, a)], "booleanRule": {"condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": "=$A4<>\"\""}]}, "format": {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.93, "green": 0.89, "blue": 0.82}}}}, "index": 0}},
        {"updateDimensionProperties": {"range": {"sheetId": a, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2}, "properties": {"pixelSize": 420}, "fields": "pixelSize"}},
        {"updateSheetProperties": {"properties": {"sheetId": a, "gridProperties": {"frozenRowCount": 3}}, "fields": "gridProperties.frozenRowCount"}},
    ]
    return req


def push(spec, b, analisa, header, fmt, creds_path, spreadsheet_id):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build as gbuild
    creds = service_account.Credentials.from_service_account_file(creds_path, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    svc = gbuild("sheets", "v4", credentials=creds).spreadsheets()
    tab, atab = spec["project"]["tab"], spec["project"]["analisa_tab"]
    def put(rng, vals):
        svc.values().update(spreadsheetId=spreadsheet_id, range=rng, valueInputOption="USER_ENTERED", body={"values": vals}).execute()
    put(f"'{atab}'!A1:I{len(analisa)}", analisa)
    put(f"'{tab}'!A1:C{len(header)}", header)
    put(f"'{tab}'!A{HEADER_ROW}:J{HEADER_ROW}", [COLS])
    last = b.total_row
    put(f"'{tab}'!A{DATA_START}:H{last}", b.rows)
    fij = b.formulas_FIJ()
    put(f"'{tab}'!F{DATA_START}:F{last}", [[x[0]] for x in fij])
    put(f"'{tab}'!I{DATA_START}:J{last}", [[x[3], x[4]] for x in fij])
    data = [{"range": f"'{tab}'!{k}", "values": [[v]]} for k, v in b.over.items()]
    svc.values().batchUpdate(spreadsheetId=spreadsheet_id, body={"valueInputOption": "USER_ENTERED", "data": data}).execute()
    svc.batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": fmt}).execute()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out", default="out")
    ap.add_argument("--sheet-id", type=int, default=0, help="sheetId tab RAB (untuk format_requests)")
    ap.add_argument("--analisa-sheet-id", type=int, default=0)
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--creds")
    ap.add_argument("--spreadsheet")
    a = ap.parse_args()
    spec = json.load(open(a.input, encoding="utf-8"))
    os.makedirs(a.out, exist_ok=True)
    b = Builder(spec).build()
    analisa = build_analisa(spec)
    header = build_header(spec)
    fmt = format_requests(a.sheet_id, b, a.analisa_sheet_id, len(analisa), spec["luasan"]["lantai"])
    fij = b.formulas_FIJ()
    dump = lambda n, o: json.dump(o, open(os.path.join(a.out, n), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    dump("rab_values.json", {"range": f"A{DATA_START}:H{b.total_row}", "values": b.rows})
    dump("rab_formulas_F.json", {"range": f"F{DATA_START}:F{b.total_row}", "values": [[x[0]] for x in fij]})
    dump("rab_formulas_IJ.json", {"range": f"I{DATA_START}:J{b.total_row}", "values": [[x[3], x[4]] for x in fij]})
    dump("rab_overrides.json", b.over)
    dump("analisa_rows.json", {"range": f"A1:I{len(analisa)}", "values": analisa})
    dump("header.json", {"range": f"A1:C{len(header)}", "values": header})
    dump("colheader.json", {"range": f"A{HEADER_ROW}:J{HEADER_ROW}", "values": [COLS]})
    dump("format_requests.json", fmt)
    with open(os.path.join(a.out, "summary.txt"), "w", encoding="utf-8") as f:
        f.write(f"Baris data {DATA_START}..{b.total_row}; total di I{b.total_row}\n")
        f.write("Baris bab: " + ", ".join(map(str, b.bab_rows)) + "\n")
        f.write("Subtotal: " + ", ".join(k for k in b.over if k.startswith("K")) + "\n")
    print(open(os.path.join(a.out, "summary.txt")).read())
    if a.push:
        push(spec, b, analisa, header, fmt, a.creds, a.spreadsheet)
        print("pushed")

if __name__ == "__main__":
    main()
