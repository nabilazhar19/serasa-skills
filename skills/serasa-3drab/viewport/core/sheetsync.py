"""
core/sheetsync.py - deteksi & ambil perubahan yang dibuat langsung di Google Sheet (tab RAB).

Perbandingan 3 arah per baris (dicocokkan lewat uraian+ruang+lantai, jadi tahan sisip/hapus baris):
  dasar  = isi tab saat push terakhir  (dari snapshot input yang di-push -> builder)
  sheet  = isi tab sekarang (dibaca via service account)
  web    = data viewport sekarang
Sheet != dasar  -> ada editan di Sheet.  Web juga berubah dan beda -> "bentrok" (pilih salah satu).
Kolom yang dibandingkan: Uraian (B), Ruang (C), Lantai (D), Spec (F), Volume (H). Kolom rumus (kode, satuan, harga) tidak.
Baris yang disisip/dihapus di Sheet dilaporkan sebagai perubahan struktur (jadi catatan untuk Claude).
"""
import difflib, importlib.util, json, os
from collections import Counter

FIELDS = {"C": 2, "D": 3, "F": 5, "H": 7}           # kolom -> index sel
LABEL = {"B": "uraian", "C": "ruang", "D": "lantai", "F": "spec", "H": "volume"}
DATA_KINDS = ("ahs", "audit", "pending", "note", "kusen")


def _builder(path):
    spec_ = importlib.util.spec_from_file_location("serasa_builder_sheet", path)
    mod = importlib.util.module_from_spec(spec_); spec_.loader.exec_module(mod); return mod


def build_rows(builder_path, spec, ahs_items):
    """baris data seperti yang ditulis builder ke Sheet: [{n, k, key, B, C, D, F, H, loc}]"""
    B = _builder(builder_path)
    b = B.Builder(json.loads(json.dumps(spec)), B.Ahs(ahs_items)).build()
    out, grp = [], ""
    for i, r in enumerate(b.rows):
        c = r["c"]
        if r["k"] in ("bab", "sub"): grp = ""
        if r["k"] not in DATA_KINDS: continue
        grp = c[1] or grp
        out.append({"n": B.DS + i, "k": r["k"], "key": _key(grp, c[2], c[3]), "B": c[1], "C": c[2], "D": c[3], "F": c[5], "H": _num(c[7]), "loc": r.get("loc"), "grp": grp})
    return out, B.DS


def _num(v):
    if v in ("", None): return None
    if isinstance(v, (int, float)): return round(float(v), 4)
    try: return round(float(str(v).replace(".", "").replace(",", ".")) if "," in str(v) else float(v), 4)
    except ValueError: return v


def _key(grp, ruang, lantai): return f"{(grp or '').strip()}|{(ruang or '').strip()}|{(lantai or '').strip()}"


def sheet_rows(values, ds):
    """isi tab dari API (UNFORMATTED_VALUE) -> baris data dengan kunci yang sama."""
    out, grp = [], ""
    for i, row in enumerate(values):
        c = list(row) + [""] * (11 - len(row))
        a, b_, f = str(c[0]).strip(), str(c[1]).strip(), str(c[5]).strip()
        if a and not b_ and not f: grp = ""; continue            # baris bab
        if a or (b_ and not c[2] and not f and not c[7]):        # bab / sub-judul / kosong
            if b_ and not f: grp = ""
            continue
        if not (b_ or c[2] or f or c[7] not in ("", None)): continue
        grp = b_ or grp
        out.append({"n": ds + i, "key": _key(grp, c[2], c[3]), "B": b_, "C": str(c[2]).strip(), "D": str(c[3]).strip(), "F": f, "H": _num(c[7]), "grp": grp})
    return out


def _same(a, b):
    if (a in (None, "")) != (b in (None, "")): return False
    if isinstance(a, float) or isinstance(b, float):
        try: return abs(float(a or 0) - float(b or 0)) < 0.005
        except (TypeError, ValueError): return a == b
    return (a or "") == (b or "")


def _align(xs, ys):
    sm = difflib.SequenceMatcher(None, [(x["key"], x.get("F")) for x in xs], [(y["key"], y.get("F")) for y in ys], autojunk=False)
    pairs, ins, dele = [], [], []
    def related(a, b):
        # Equal-sized replacement blocks can contain unrelated inserted/deleted
        # rows. Only map edits when other identifying fields still agree.
        return (a.get("grp") == b.get("grp") and
                (a.get("C") == b.get("C") or a.get("F") == b.get("F")))
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            pairs += [(xs[i1 + k], ys[j1 + k]) for k in range(i2 - i1)]
        elif tag == "replace" and (i2 - i1) == (j2 - j1):   # isi kunci berubah (mis. ruang diedit) tapi posisi sama
            for a, b in zip(xs[i1:i2], ys[j1:j2]):
                if related(a, b): pairs.append((a, b))
                else: dele.append(a); ins.append(b)
        else:
            dele += xs[i1:i2]; ins += ys[j1:j2]
    for a in list(dele):
        candidates = [b for b in ins if a["key"] == b["key"] and a.get("F") == b.get("F")]
        if len(candidates) == 1 and sum(x["key"] == a["key"] and x.get("F") == a.get("F") for x in dele) == 1:
            b = candidates[0]; pairs.append((a, b)); dele.remove(a); ins.remove(b)
    return pairs, ins, dele


def diff(base, sheet, web):
    """daftar perubahan di Sheet relatif ke dasar, plus nilai web untuk tiap baris."""
    pairs, ins, dele = _align(base, sheet)
    web_by = {}
    wp, _, _ = _align(base, web)
    for b, w in wp: web_by[b["n"]] = w
    items = []
    for b, s in pairs:
        w = web_by.get(b["n"])
        for col in ("C", "D", "F", "H"):
            if _same(b[col], s[col]): continue
            wv = w[col] if w else None
            if w and _same(wv, s[col]): continue                     # web sudah sama dengan sheet
            items.append({"id": f"{s['n']}:{col}", "sheet_row": s["n"], "col": col, "field": LABEL[col], "uraian": s["grp"], "ruang": s["C"],
                          "base": b[col], "sheet": s[col], "web": wv, "web_row": w["n"] if w else None, "loc": w["loc"] if w else None,
                          "kind": w["k"] if w else None, "conflict": bool(w) and not _same(wv, b[col])})
    struct = [{"type": "tambah", "sheet_row": s["n"], "uraian": s["grp"], "ruang": s["C"], "spec": s["F"], "vol": s["H"]} for s in ins] + \
             [{"type": "hapus", "base_row": b["n"], "uraian": b["grp"], "ruang": b["C"]} for b in dele]
    return {"items": items, "struct": struct}


def read_tab(creds_path, spreadsheet_id, tab, ds, n):
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build as gbuild
    except ImportError:
        raise ValueError("Library Google belum terpasang untuk Python server ini (pip install google-api-python-client google-auth)")
    creds = service_account.Credentials.from_service_account_file(creds_path, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    S = gbuild("sheets", "v4", credentials=creds, cache_discovery=False).spreadsheets()
    rng = f"'{tab}'!A{ds}:K{ds + n + 80}"
    res = S.values().get(spreadsheetId=spreadsheet_id, range=rng, valueRenderOption="UNFORMATTED_VALUE").execute()
    return res.get("values", [])
