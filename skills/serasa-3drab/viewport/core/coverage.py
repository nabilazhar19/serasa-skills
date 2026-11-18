"""
core/coverage.py - cakupan RAB terhadap model ("semua objek dihitung") + cek kewajaran harga per m2.

Cakupan: tiap objek di ekspor 3D berstatus
  rab      dirujuk baris RAB (id/pid di sumber baris, atau tag muka objek dipakai baris), atau register.status = "rab"
  exclude  sengaja tidak dihitung (register.status = "exclude" + alasan; layer kontur/vegetasi/mobil otomatis)
  missing  belum masuk RAB -> merah di mode "Cakupan RAB" viewport, daftar di panel
Register proyek: _serasa_tools/register.json (atau viewport.json "register"):
  {"objects": {"<pid>": {"status": "rab"|"exclude", "work": "fasad strip besi hollow", "reason": "...", "rows": [..]}}}
Persentase dihitung terhadap luas muka (objek kecil tidak menutupi objek besar yang terlewat).

Kewajaran harga: total RAB ÷ luas ekuivalen (input luasan.ekuivalen; koefisien di references/cakupan.md) dibandingkan
rentang viewport.json "benchmark" {min, max, struktur}. Tanpa struktur, rentang dikurangi porsi struktur (26%, acuan RBL).
"""
import json, os, re

SKIP = re.compile(r"KONTUR|VEGET|STREET|CAR BIKE|AMBIENCE|PLAN", re.I)
STRUCT_SHARE = 0.26
_cache = {}


def register_path(cfg):
    return cfg.get("register") or os.path.join(cfg["_base"], "register.json")


def load_register(cfg):
    try: return json.load(open(register_path(cfg), encoding="utf-8"))
    except (OSError, ValueError): return {"objects": {}}


def _objects(path):
    mt = os.path.getmtime(path)
    if _cache.get(path, (None,))[0] != mt:
        d = json.load(open(path, encoding="utf-8"))
        objs = [{"pid": str(o["pid"]), "name": o["name"], "layer": o.get("layer", ""),
                 "m2": sum(v for k, v in (o.get("qty") or {}).items() if not k.startswith("Q|")) / 1e6,
                 "tags": [k for k in (o.get("qty") or {}) if k and not k.startswith("Q|")]} for o in d.get("objects", [])]
        _cache[path] = (mt, objs)
    return _cache[path][1]


def _tag_hit(q, t):
    if q == t: return True
    if "*" not in q: return False
    a, b = q.split("|"), t.split("|")
    return len(a) == len(b) and all(x in ("*", y) for x, y in zip(a, b))


def compute(cfg, rows):
    path = cfg.get("model3d")
    if not path or not os.path.exists(path): return None
    objs = _objects(path); reg = load_register(cfg).get("objects", {})
    ids, tags = set(), set()
    for r in rows:
        hl = r.get("hl") or {}
        if r.get("kind") in ("sub", "pending") or not hl: continue
        ids.update(str(x) for x in hl.get("ids") or []); tags.update(hl.get("tags") or [])
        for p in hl.get("parts") or []: ids.add(p.split("::")[0])
    out = {"rab": [], "exclude": [], "missing": []}
    for o in objs:
        rg = reg.get(o["pid"]) or {}
        if rg.get("status") == "exclude" or (not rg and SKIP.search(o["layer"])): st = "exclude"
        elif rg.get("status") == "rab" or o["pid"] in ids or o["name"] in ids or any(_tag_hit(q, t) for t in o["tags"] for q in tags): st = "rab"
        else: st = "missing"
        out[st].append(o)
    tot = sum(o["m2"] for o in objs) or 1
    miss = sorted(out["missing"], key=lambda o: -o["m2"])
    return {"pct": round(100 * (1 - sum(o["m2"] for o in miss) / tot), 1), "objects": len(objs),
            "n_missing": len(miss), "n_exclude": len(out["exclude"]),
            "missing": [{k: o[k] for k in ("pid", "name", "layer")} | {"m2": round(o["m2"], 2)} for o in miss[:60]],
            "missing_ids": [o["pid"] for o in miss], "exclude_ids": [o["pid"] for o in out["exclude"]]}


def benchmark(cfg, spec, total):
    eq = (spec.get("luasan") or {}).get("ekuivalen")
    if not eq: return None
    b = cfg.get("benchmark") or {}
    lo, hi = b.get("min", 5_500_000), b.get("max", 7_000_000)
    if not b.get("struktur", False): lo, hi = lo * (1 - STRUCT_SHARE), hi * (1 - STRUCT_SHARE)
    v = total / eq
    return {"rp_m2": round(v), "min": round(lo), "max": round(hi), "ekuivalen": eq, "struktur": bool(b.get("struktur")),
            "status": "rendah" if v < lo else "tinggi" if v > hi else "wajar"}


def set_status(cfg, pid, status, reason="", work=""):
    reg = load_register(cfg)
    if status: reg.setdefault("objects", {})[str(pid)] = {"status": status, "reason": reason, "work": work}
    else: reg.setdefault("objects", {}).pop(str(pid), None)
    return reg
