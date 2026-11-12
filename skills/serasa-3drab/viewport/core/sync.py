"""
core/sync.py - RAB ikut berubah otomatis saat model SketchUp disimpan.

Alur:  SketchUp save -> SerasaRAB.export_mesh menulis ruko_model3d.json (geometri + luas per tag tiap objek)
       -> server memanggil apply_model() -> volume baris yang tertaut dihitung ulang -> file input RAB diperbarui
       (satu snapshot = bisa di-undo sekaligus) -> viewport segar sendiri. Google Sheet baru berubah setelah Push.

Tautan (src["bind"]) dibuat sekali per proyek oleh bind():
  direct      volume = volume awal + (luas model sekarang - luas saat ditautkan)  (bila luas model ≈ volume RAB, selisih <= 8 %)
  ratio       volume = volume awal x (luas sekarang / luas saat ditautkan)  -> ikut berubah proporsional
  count       jumlah unit = jumlah objek (pid) yang masih ada; ukuran kusen berubah -> catatan untuk Claude
Baris koreksi manual tidak ditimpa: ditandai "bentrok" + catatan. Objek hilang / objek baru -> catatan.
"""
import json, os, re, time

FIT = 0.08          # toleransi untuk mode direct
MIN_CHANGE = 0.005  # perubahan volume lebih kecil dari ini diabaikan
SIZE_TOL = 20       # mm, perubahan ukuran kusen yang dilaporkan
GRP = re.compile(r"(?:Group|Component)#\d+")


def _now(): return time.strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------- tabel luas dari ekspor SketchUp
def table(export_path):
    d = json.load(open(export_path, encoding="utf-8"))
    rows, objs = [], {}
    for o in d["objects"]:
        objs[o["name"]] = o; objs[str(o["pid"])] = o
        for tag, a in (o.get("qty") or {}).items():
            rows.append((o["name"], str(o["pid"]), tag, a / 1e6))
    return {"rows": rows, "objs": objs, "names": sorted({o["name"] for o in d["objects"]}), "exported": d.get("exported"),
            "rooms": sorted({r["name"] for r in d.get("rooms", [])})}


def _tag_ok(tag, pats):
    if not pats: return True
    t = tag.split("|")
    for p in pats:
        q = p.split("|")
        if len(q) == len(t) and all(a == "*" or a == b for a, b in zip(q, t)): return True
    return False


def metric(terms, tb):
    ids, tags = terms.get("ids"), terms.get("tags")
    s = 0.0
    for name, pid, tag, a in tb["rows"]:
        if ids and name not in ids and pid not in ids: continue
        if tags and not _tag_ok(tag, tags): continue
        s += a
    return s


# ---------------------------------------------------------------- tautan baris -> model
FACE_TYPES = {"ekspos": ["ekspos", "lain"], "putih": ["putih", "terracotta", "lain"], "terracotta": ["terracotta"]}
DIRS = ("Barat", "Timur", "Utara", "Selatan")


def _ids(src):
    out = []
    for g in (src or {}).get("groups", []) or []:
        m = GRP.search(str(g)) or re.match(r"\d{5,}", str(g))
        if m: out.append(m.group(0))
    out += GRP.findall((src or {}).get("detail", "") or "")
    return sorted(set(out))


def _rooms(text, rooms):
    """ruang yang disebut di teks; 'Toko 1 & 2' / 'Unit 1 dan 2' -> keduanya."""
    text = text or ""; out = []
    for r in rooms:
        base = r.split(" (")[0]
        m = re.match(r"(.*?)(\d+)$", base)
        if base in text or r in text: out.append(r); continue
        if m:
            pre = re.escape(m.group(1).strip())
            for g in re.finditer(pre + r"\s*(\d+)\s*(?:&|dan|,)\s*(\d+)", text):
                if m.group(2) in g.groups(): out.append(r)
    return sorted(set(out))


def candidates(row, holder_src, wall, rooms):
    """kemungkinan definisi sumber untuk satu baris, dari yang paling spesifik."""
    src = holder_src or {}
    ids = _ids(src); c = []
    if src.get("pick"):
        objs = sorted({p.split("::")[0] for p in src["pick"]})
        tags = sorted({t for p in src["pick"] for t in p.split("::", 1)[1].split(";") if t})
        c.append({"ids": objs, "tags": tags or None})
        return c
    if wall:
        w, t = wall; types = FACE_TYPES.get(t, [t])
        if w.get("interior"):
            tags = [f"R|{w['room']}|{x}" for x in types]
        else:
            d = next((x for x in DIRS if x in w["room"]), "*")
            tags = [f"E|{d}|{x}" for x in types]
        if ids: c.append({"ids": ids, "tags": tags})
        c.append({"tags": tags})
        if ids: c.append({"ids": ids})
        return c
    text = " ".join(str(row.get(k) or "") for k in ("uraian", "uraian_group", "ruang"))
    rs = _rooms(text, rooms)
    low = text.lower()
    face = "C" if ("plafon" in low or "plafond" in low) else ("F" if ("lantai" in low or "keramik" in low or "granit" in low or "parket" in low) else None)
    if rs and face:
        tags = [f"{face}|{x}|*" for x in rs]
        if ids: c.append({"ids": ids, "tags": tags})
        c.append({"tags": tags})
    if ids: c.append({"ids": ids})
    return c


def bind(spec, rows, tb, force=False):
    """buat src["bind"] untuk baris model yang bisa dihitung ulang. Mengubah spec (dict) di tempat."""
    rooms = tb.get("rooms", [])
    seen, report = set(), {"direct": [], "ratio": [], "count": [], "skip": []}
    for r in rows:
        loc = r.get("loc")
        if not loc or r["kind"] in ("sub", "pending") or _key(loc) in seen: continue
        seen.add(_key(loc))
        if loc[0] == "wall" and len(loc) > 4 and loc[4]:   # luas khusus per lapisan (layer_parts) -> tidak ditautkan otomatis
            report["skip"].append(r["row"]); continue
        holder, key, src = _locate(spec, loc)
        if src is None or (src.get("bind") and not force): continue
        kind = src.get("kind")
        if kind != "skp" and not src.get("pick"): continue
        vol = holder.get(key, 1 if loc[0] == "open" else None)
        if not isinstance(vol, (int, float)) or vol <= 0: continue
        sat = (r.get("sat") or "").lower()
        if loc[0] == "open":
            pids = [g for g in _ids(src) if g.isdigit()]
            if not pids: report["skip"].append(r["row"]); continue
            o = holder
            src["bind"] = {"mode": "count", "pids": pids, "base_vol": vol, "size": [round(o.get("w", 0) * 1000), round(o.get("h", 0) * 1000)], "at": _now()}
            report["count"].append(r["row"]); continue
        if not (sat.startswith("m2") or sat.startswith("m3")): report["skip"].append(r["row"]); continue
        wall = (spec["walls"][loc[1]], loc[2]) if loc[0] == "wall" else None
        best = None
        for t in candidates(r, src, wall, rooms):
            m = metric(t, tb)
            if m <= 0: continue
            fit = abs(m - vol) / vol
            if best is None or (fit <= FIT and best[2] > FIT): best = (t, m, fit)
            if fit <= FIT: break
        if not best: report["skip"].append(r["row"]); continue
        t, m, fit = best
        mode = "direct" if fit <= FIT and sat.startswith("m2") else "ratio"
        # proporsional hanya bila sumbernya cukup spesifik (luas model 1/3 s.d. 3x volume); selain itu tidak otomatis
        if mode == "ratio" and sat.startswith("m2") and not (1 / 3 <= m / vol <= 3):
            report["skip"].append(r["row"]); continue
        src["bind"] = {"mode": mode, "terms": t, "base_metric": round(m, 4), "base_vol": vol, "at": _now()}
        report[mode].append(r["row"])
    spec.setdefault("meta", {})["model_bind"] = {"at": _now(), "objects": tb["names"]}
    return report


def _key(loc):   # satu angka volume = satu tautan (dinding: ruang x tipe x lapisan)
    return json.dumps([loc[0], loc[1], loc[2], loc[4] if len(loc) > 4 else None] if loc[0] == "wall" else loc[:3])


def _locate(spec, loc):
    k = loc[0]
    if k == "bab":
        it = spec["bab"][loc[1]]["rows"][loc[2]]
        return it, "vol", it.get("src")
    if k == "wall":
        w = spec["walls"][loc[1]]; layer = loc[4] if len(loc) > 4 else None
        return (w["layer_parts"][layer] if layer else w["parts"]), loc[2], (w.get("src") or {}).get(loc[2])
    if k == "open":
        o = spec["openings"][loc[1]]
        return o, "vol", o.get("src")
    return None, None, None


# ---------------------------------------------------------------- terapkan perubahan model
def apply_model(spec, rows, tb):
    """hitung ulang semua baris tertaut. Mengubah spec di tempat; kembalikan (changes, conflicts, notes)."""
    changes, conflicts, notes, seen = [], [], [], set()
    for r in rows:
        loc = r.get("loc")
        if not loc or _key(loc) in seen: continue
        seen.add(_key(loc))
        holder, key, src = _locate(spec, loc)
        if not src or not src.get("bind"): continue
        b = src["bind"]; old = holder.get(key, 1 if loc[0] == "open" else None)
        if b["mode"] == "count":
            alive = [p for p in b["pids"] if p in tb["objs"]]
            new = len(alive) if len(b["pids"]) > 1 else (b["base_vol"] if alive else 0)
            gone = [p for p in b["pids"] if p not in tb["objs"]]
            if gone: notes.append((r, None, f"Objek kusen pid {', '.join(gone)} tidak ada lagi di model (baris {r['row']} {r.get('ruang') or ''})."))
            for p in alive:
                bb = tb["objs"][p].get("bbox")
                if not bb: continue
                wnow, hnow = max(bb[3] - bb[0], bb[4] - bb[1]), bb[5] - bb[2]
                w0, h0 = b.get("size", [0, 0])
                if w0 and (abs(wnow - w0) > SIZE_TOL or abs(hnow - h0) > SIZE_TOL):
                    notes.append((r, tb["objs"][p]["name"], f"Ukuran kusen {r.get('code') or ''} berubah di model: {w0}x{h0} → {wnow}x{hnow} mm. Spesifikasi & analisa harga perlu dihitung ulang."))
                    b["size"] = [wnow, hnow]
        else:
            m = metric(b["terms"], tb)
            if b["mode"] == "direct": new = round(b["base_vol"] + (m - b["base_metric"]), 2)   # selisih luas model ditambahkan apa adanya
            else: new = round(b["base_vol"] * m / b["base_metric"], 2) if b["base_metric"] else old
            if m <= 0: notes.append((r, None, f"Sumber baris {r['row']} ({r.get('uraian') or r.get('uraian_group')}) tidak ditemukan lagi di model — volume dibiarkan {old}."))
            if m <= 0: continue
        if old is None or abs(new - old) < MIN_CHANGE: continue
        if src.get("manual"):
            if src.get("conflict", {}).get("model") != new:
                src["conflict"] = {"model": new, "at": _now()}
                conflicts.append({"row": r["row"], "uraian": r.get("uraian") or r.get("uraian_group"), "manual": old, "model": new})
            continue
        holder[key] = new
        src.pop("conflict", None)
        changes.append({"row": r["row"], "uraian": r.get("uraian") or r.get("uraian_group"), "ruang": r.get("ruang"), "old": old, "new": new,
                        "sat": r.get("sat"), "shared": r.get("shared") or []})
    # objek baru yang belum pernah ada saat ditautkan
    known = set((spec.get("meta", {}).get("model_bind") or {}).get("objects") or [])
    if known:
        new_objs = [n for n in tb["names"] if n not in known]
        for n in new_objs:
            o = tb["objs"][n]
            notes.append((None, n, f"Objek baru di model: {n} (layer {o.get('layer')}) — belum masuk baris RAB mana pun."))
        if new_objs: spec["meta"]["model_bind"]["objects"] = sorted(known | set(new_objs))
    return changes, conflicts, notes
