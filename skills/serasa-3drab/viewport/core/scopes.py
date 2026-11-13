"""
core/scopes.py - RAB terpisah per bangunan dari SATU input induk (hanya bila pengguna memintanya).

Aktif bila viewport.json punya `building_tabs`:
  [{"id": "rumah", "label": "Rumah", "tab": "RAB Rumah", "audit_tab": "Audit Rumah", "sheet_id": 1, "audit_id": 2,
    "match": "\\brumah\\b|kanopi servis"},                       # regex pada Ruang/Area (opsional)
   ...,
   {"id": "bersama", "label": "Area Bersama", "tab": ..., "shared": true}]   # penampung: tapak, pagar, biaya proyek, pending
Alokasi baris: field `building` di baris/bukaan/dinding (koreksi dari viewport) -> regex `match` pertama yang cocok ->
tab `shared` (atau tab terakhir). Tiap tab = input turunan (derive) dengan bab/bukaan/dinding/analisa miliknya.
Pekerjaan bersama dihitung sekali di tab shared, tidak dibebankan ulang ke bangunan.
"""
import copy, hashlib, json, os, re

WALL_ROWS = ("wall_plaster", "wall_aci", "wall_finish")


def tabs(cfg): return cfg.get("building_tabs") or []
def labels(cfg): return {t["id"]: t["label"] for t in tabs(cfg)}
def shared(cfg): return next((t["id"] for t in tabs(cfg) if t.get("shared")), tabs(cfg)[-1]["id"])


def classify(item, cfg):
    if item.get("building") in labels(cfg): return item["building"]
    text = str(item.get("ruang", item.get("room", "")))
    for t in tabs(cfg):
        if t.get("match") and t["id"] != shared(cfg) and re.search(t["match"], text, re.I): return t["id"]
    return shared(cfg)


def target(cfg, key): return next(x for x in tabs(cfg) if x["id"] == key)


def derive(master, key, cfg):
    """input turunan untuk satu bangunan + peta indeks turunan -> induk."""
    spec = copy.deepcopy(master); t = target(cfg, key); maps = {"bab": {}, "open": {}, "wall": {}}
    spec["project"].update(tab=t["tab"], audit_tab=t["audit_tab"], title=master["project"]["title"] + " — " + t["label"])
    spec["openings"] = []
    for i, o in enumerate(master.get("openings", [])):
        if classify(o, cfg) == key: maps["open"][len(spec["openings"])] = i; spec["openings"].append(copy.deepcopy(o))
    spec["walls"] = []
    for i, w in enumerate(master.get("walls", [])):
        if classify(w, cfg) == key: maps["wall"][len(spec["walls"])] = i; spec["walls"].append(copy.deepcopy(w))
    spec["bab"] = []
    for bi, b in enumerate(master["bab"]):
        kept, pending_sub = [], None
        for ri, row in enumerate(b["rows"]):
            kind = row["type"]
            if kind == "sub": pending_sub = (ri, row); continue
            keep = bool(spec["openings"]) if kind in ("openings", "openingan") else bool(spec["walls"]) if kind in WALL_ROWS else classify(row, cfg) == key
            if not keep: continue
            if pending_sub is not None: kept.append(pending_sub); pending_sub = None
            kept.append((ri, row))
        if not kept: continue
        nbi = len(spec["bab"]); nb = copy.deepcopy(b); nb["rows"] = []
        for ri, row in kept: maps["bab"][(nbi, len(nb["rows"]))] = (bi, ri); nb["rows"].append(copy.deepcopy(row))
        spec["bab"].append(nb)
    codes = {o["code"] for o in spec["openings"]}
    for b in spec["bab"]:
        for r in b["rows"]:
            if r["type"] in ("audit", "openingan"): codes.add(r.get("code", "OPK"))
    spec["audit"] = [a for a in spec.get("audit", []) if a["code"] in codes]
    sh = target(cfg, shared(cfg))
    spec["luasan"]["tanah_label"] = "Luas Tapak Proyek Bersama (m²)"
    for floor in spec["luasan"].get("lantai", []):
        if key == sh["id"]: floor["items"] = [[t["label"].capitalize() + " (tanpa luasan bangunan)", 0]]
        elif t.get("match"): floor["items"] = [x for x in floor["items"] if re.search(t["match"], str(x[0]), re.I)]
        else: floor["items"] = [x for x in floor["items"] if str(x[0]).lower() in (key, t["label"].lower())]
    spec["luasan"]["note"] = f"{t['label']} • pekerjaan tapak bersama dicatat satu kali pada {sh['tab']}"
    notes = [n for n in spec.get("audit_notes", []) if not (n.startswith("Neraca ") and t["label"] not in n)]   # neraca bangunan lain tidak ikut
    notes.append(f"Pembagian RAB: {t['label']}. Tapak, pagar keliling, taman, biaya proyek serta pending yang belum dialokasikan berada pada {sh['tab']}; tidak dibebankan ulang pada tiap bangunan.")
    spec["audit_notes"] = notes
    return spec, maps


def translate(loc, maps):
    if not loc: return None
    out = list(loc)
    if out[0] == "bab": out[1], out[2] = maps["bab"][(out[1], out[2])]
    elif out[0] in ("open", "wall"): out[1] = maps[out[0]][out[1]]
    return out


def state_path(cfg): return os.path.join(cfg["_base"], ".koreksi", "split_state.json")
def identity(cfg):
    return {"spreadsheet_id": cfg["spreadsheet_id"], "input": os.path.realpath(cfg["input"]),
            "tabs": [{k: t.get(k) for k in ("id", "tab", "audit_tab", "sheet_id", "audit_id")} for t in tabs(cfg)]}


def state(cfg):
    """baseline per tab (input turunan saat push terakhir). Belum ada / tujuan berubah -> baseline kosong (semua dianggap baru)."""
    try:
        data = json.load(open(state_path(cfg), encoding="utf-8"))
        if data.get("target") == identity(cfg): return data
    except (OSError, ValueError): pass
    return {"target": identity(cfg), "pushed_specs": {}, "review_rows": {}}


def fingerprint(spec, builder, ahs):
    from core import sheetsync
    B = sheetsync._builder(builder); b = B.Builder(copy.deepcopy(spec), B.Ahs(ahs)).build()
    payload = {"rows": [{"c": r["c"], "kind": r["k"], "estimated": r.get("estimated"), "note": r.get("quantity_note")} for r in b.rows],
               "audit": spec.get("audit"), "notes": spec.get("audit_notes", []), "luasan": spec.get("luasan"), "project": spec["project"]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def view(spec, rows, babs, cfg, ahs):
    """data viewport per bangunan: total, luas, nomor baris di tab bangunan, status belum di-push."""
    from core import sheetsync
    st = state(cfg); buildings = []; rowmap = {}; L = labels(cfg)
    B = sheetsync._builder(cfg["builder"])
    for t in tabs(cfg):
        key = t["id"]; part, maps = derive(spec, key, cfg)
        native = B.Builder(copy.deepcopy(part), B.Ahs(ahs)).build()
        for i, r in enumerate(native.rows):
            loc = translate(r.get("loc"), maps)
            if loc and r["k"] not in ("bab", "sub", "blank", "total"): rowmap[json.dumps(loc)] = (key, B.DS + i)
        for r in rows:
            e = rowmap.get(json.dumps(r.get("loc"))) if r.get("loc") else None
            if e: r["building"], r["sheet_row"] = e; r["building_label"] = L[e[0]]
        bab_rows = {ch["no"]: n for ch, n in zip(part["bab"], getattr(native, "bab_rows", []))}
        master_no = {json.dumps(r.get("loc")): r["row"] for r in rows if r.get("loc")}
        sub_rows = {}
        for i, row in enumerate(native.rows):
            if row["k"] == "sub" and row.get("loc"):
                old = master_no.get(json.dumps(translate(row["loc"], maps)))
                if old: sub_rows[str(old)] = B.DS + i
        subset = [r for r in rows if r.get("building") == key]
        pushed = st["pushed_specs"].get(key)
        changed = pushed is None or fingerprint(part, cfg["builder"], ahs) != fingerprint(pushed, cfg["builder"], ahs)
        ids = sorted({str(i) for r in subset for i in (r.get("hl") or {}).get("ids", [])})
        buildings.append(dict(t, bab_rows=bab_rows, sub_rows=sub_rows, total=sum(r["total"] for r in subset), rows=len(subset),
                              pending=sum(r["kind"] == "pending" for r in subset), estimated=sum(bool(r.get("estimated")) for r in subset),
                              luasan=part["luasan"], ids=ids, unpushed=changed,
                              sheet_link=f"https://docs.google.com/spreadsheets/d/{cfg['spreadsheet_id']}/edit#gid={t.get('sheet_id')}"))
    for r in rows:   # baris tanpa padanan (mis. dihasilkan builder) -> tab penampung
        if r["kind"] != "sub" and "building" not in r: r["building"] = shared(cfg); r["building_label"] = L[r["building"]]
    return {"buildings": buildings, "unpushed": sum(b["unpushed"] for b in buildings), "multi_sheet": True}
