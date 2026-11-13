"""
core/sync.py - RAB ikut berubah otomatis saat model SketchUp disimpan.

Alur:  SketchUp save -> SerasaRAB.export_mesh menulis ruko_model3d.json (geometri + luas per tag tiap objek)
       -> server memanggil apply_model() -> volume baris yang tertaut dihitung ulang -> file input RAB diperbarui
       (satu snapshot = bisa di-undo sekaligus) -> viewport segar sendiri. Google Sheet baru berubah setelah Push.

Tautan (src["bind"]) dibuat sekali per proyek oleh bind():
  direct      volume = volume awal + (luas model sekarang - luas saat ditautkan)  (bila luas model ≈ volume RAB, selisih <= 8 %)
  ratio       volume = volume awal x (luas sekarang / luas saat ditautkan)  -> ikut berubah proporsional
  count       jumlah unit = jumlah objek (pid) yang masih ada; ukuran kusen berubah -> catatan untuk Claude
  measure     ukuran tambahan dari plugin (volume solid per pita, luas atap, keliling, roster) -> proporsional
Baris koreksi manual tidak ditimpa: ditandai "bentrok" + catatan. Objek baru -> catatan. Objek sumber yang
seluruhnya dihapus dari model -> volume 0 (bukan angka lama). Ukuran kusen berubah + analisa punya resep ukuran
(dimension_recipe) -> harga paket dihitung ulang (core/analysis.py); tanpa resep -> catatan.
Format ekspor berubah (mis. plugin baru) -> tautan disesuaikan ulang tanpa mengubah angka RAB (rebase).
"""
import json, os, re, time

FIT = 0.08          # toleransi untuk mode direct
MIN_CHANGE = 0.005  # perubahan volume lebih kecil dari ini diabaikan
SIZE_TOL = 5        # mm, perubahan ukuran kusen yang diproses
# pekerjaan yang volumenya diambil dari ukuran khusus plugin (resep di serasa_watch.json "measures"), bukan luas muka
MEASURE_RULES = [   # (regex uraian/spec, satuan yang cocok atau None, nama ukuran; {lantai} = kolom lantai baris)
    (r"pasangan (bata|dinding)", ("m2", "m3"), "solid_m3:{lantai}"),
    (r"rangka (atap|kanopi)", None, "roof_xy_m2"),
    (r"penutup (atap|kanopi|skylight)|insulasi atap", None, "roof_m2"),
    (r"bouwplank", ("m1", "m'"), "perimeter_m"),
    (r"roster", None, "roster_m2"),
]
GRP = re.compile(r"(?:Group|Component)#\d+")


def _now(): return time.strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------- tabel luas dari ekspor SketchUp
def table(export_path):
    d = json.load(open(export_path, encoding="utf-8"))
    rows, objs = [], {}
    for o in d["objects"]:
        objs.setdefault(o["name"], o); objs[str(o["pid"])] = o
        for tag, a in (o.get("qty") or {}).items():
            rows.append((o["name"], str(o["pid"]), tag, a / 1e6))
    return {"rows": rows, "objs": objs, "names": sorted({o["name"] for o in d["objects"]}), "exported": d.get("exported"),
            "rooms": sorted({r["name"] for r in d.get("rooms", [])}), "object_ids": sorted(str(o["pid"]) for o in d["objects"]),
            "basis": f"{d.get('format', 2)}/{d.get('quantity_version', 1)}", "revision": d.get("revision", d.get("exported"))}


def _tag_ok(tag, pats):
    if not pats: return True
    t = tag.split("|")
    for p in pats:
        q = p.split("|")
        if len(q) == len(t) and all(a == "*" or a == b for a, b in zip(q, t)): return True
    return False


def metric(terms, tb):
    ids, tags = terms.get("ids"), terms.get("tags")
    if terms.get("measure"):   # ukuran khusus plugin, per objek (pid)
        return sum((o.get("measures") or {}).get(terms["measure"], 0) for k, o in tb["objs"].items() if k == str(o["pid"]) and (not ids or k in ids))
    s = 0.0
    q_ok = any(t.startswith("Q|") for t in (tags or []))
    for name, pid, tag, a in tb["rows"]:
        if tag.startswith("Q|") and not q_ok: continue    # luas per pita hanya bila diminta
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
        q = re.match(r"^(.*?) (Lantai \d+) (.+)$", base)      # ruang bernama massa + lantai + nama (proyek multi-bangunan)
        if q and all(x.casefold() in text.casefold() for x in q.groups()): out.append(r); continue
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
    text = " ".join(str(row.get(k) or "") for k in ("uraian", "uraian_group", "ruang", "lantai"))
    rs = _rooms(text, rooms)
    low = text.lower()
    work = " ".join(str(row.get(k) or "") for k in ("uraian", "uraian_group")).lower()   # jenis pekerjaan (bukan kolom ruang/lantai)
    face = "C" if ("plafon" in work or "plafond" in work) else ("F" if any(x in work for x in ("lantai", "keramik", "granit", "parket")) else None)
    wall_work = any(x in work for x in ("dinding", "plester", "acian", "cat "))
    typ = next((t for k, t in (("ekspos", "ekspos"), ("terracotta", "terracotta"), ("kayu", "kayu"), ("putih", "putih")) if k in low), "*")
    ext = re.search(r"(?:Fasad|Eksterior)\s+(Barat|Timur|Utara|Selatan)", text)
    if wall_work and ext and not face:
        band = row.get("lantai") or ""
        tags = [f"Q|{band}|E|{ext.group(1)}|{typ}"] if band else [f"E|{ext.group(1)}|{typ}"]
        if ids: c.append({"ids": ids, "tags": tags})
        c.append({"tags": tags})
        return c
    if rs and wall_work and not face:
        tags = [f"R|{x}|{typ}" for x in rs]
        if ids: c.append({"ids": ids, "tags": tags})
        c.append({"tags": tags})
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
        if loc[0] == "open" or sat in ("unit", "buah", "bh", "set", "titik"):
            pids = [g for g in _ids(src) if g.isdigit()]
            if not pids: report["skip"].append(r["row"]); continue
            o = holder
            src["bind"] = {"mode": "count", "pids": pids, "base_vol": vol, "at": _now()}
            if loc[0] == "open":
                src["bind"]["size"] = [round(o.get("w", 0) * 1000), round(o.get("h", 0) * 1000)]
                bb = (tb["objs"].get(pids[0]) or {}).get("bbox") if len(pids) == 1 else None
                if bb: src["bind"]["model_size"] = [max(bb[3] - bb[0], bb[4] - bb[1]), bb[5] - bb[2]]
            report["count"].append(r["row"]); continue
        mname = measure_for(r, src)
        if mname:
            pids = [g for g in _ids(src) if g.isdigit()]
            t = {"ids": pids, "measure": mname}; m = metric(t, tb) if pids else 0
            if m > 0:
                src["bind"] = {"mode": "ratio", "terms": t, "base_metric": m, "base_vol": vol, "at": _now()}
                report["ratio"].append(r["row"]); continue
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
    spec.setdefault("meta", {})["model_bind"] = {"at": _now(), "objects": tb["names"], "object_ids": tb["object_ids"], "basis": tb["basis"]}
    return report


def measure_for(row, src):
    if src.get("measure"): return src["measure"]
    text = " ".join(str(row.get(k) or "") for k in ("uraian", "uraian_group", "spec")).lower()
    sat = (row.get("sat") or "").lower()
    for rx, sats, name in MEASURE_RULES:
        if re.search(rx, text) and (not sats or sat in sats):
            return name.format(lantai=row.get("lantai") or "")
    return None


def rebase(spec, rows, tb):
    """format ekspor berubah -> titik acuan tautan diganti ukuran baru, angka RAB tidak berubah."""
    n = 0; seen = set()
    for r in rows:
        loc = r.get("loc")
        if not loc or _key(loc) in seen: continue
        seen.add(_key(loc))
        holder, key, src = _locate(spec, loc)
        b = (src or {}).get("bind")
        if not b: continue
        if b["mode"] == "count":
            if loc[0] == "open" and len(b["pids"]) == 1 and b["pids"][0] in tb["objs"]:
                bb = tb["objs"][b["pids"][0]].get("bbox")
                if bb: b["model_size"] = [max(bb[3] - bb[0], bb[4] - bb[1]), bb[5] - bb[2]]
            n += 1; continue
        m = metric(b["terms"], tb); vol = holder.get(key)
        if m > 0 and isinstance(vol, (int, float)):
            b["base_metric"] = m; b["base_vol"] = vol; n += 1
        dep = b.get("analysis")
        if dep:
            v = metric({"ids": b["terms"].get("ids"), "measure": dep["measure"]}, tb)
            an = next((x for x in spec.get("audit", []) if x["code"] == dep["code"]), None)
            if v > 0 and an:
                dep["base_metric"] = v; b["base_vol"] = vol if isinstance(vol, (int, float)) else b["base_vol"]
                if dep.get("parameter") and an.get("metric_params"): dep["base_value"] = an["metric_params"].get(dep["parameter"], dep.get("base_value"))
                elif an.get("components"): dep["base_koef"] = an["components"][0]["koef"]
    meta = spec.setdefault("meta", {}).setdefault("model_bind", {})
    meta.update(basis=tb["basis"], object_ids=tb["object_ids"], objects=tb["names"])
    return n


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
            if gone: notes.append((r, None, f"Objek pid {', '.join(gone)} tidak ada lagi di model (baris {r['row']} {r.get('ruang') or ''})."))
            if loc[0] == "open" and len(alive) == 1:
                _resized(spec, r, holder, src, b, tb, alive[0], changes, notes)
            elif loc[0] == "open" and len(alive) > 1:
                sizes = {tuple(_wh(tb["objs"][p]["bbox"])) for p in alive if tb["objs"][p].get("bbox")}
                if len(sizes) > 1: notes.append((r, None, f"Ukuran instance {r.get('code') or ''} di baris {r['row']} berbeda-beda — pisahkan tipe sebelum menghitung harga."))
        else:
            m = metric(b["terms"], tb)
            ids = [x for x in (b["terms"].get("ids") or []) if str(x).isdigit()]
            if m <= 0 and ids and all(str(x) not in tb["objs"] for x in ids):
                new = 0   # semua objek sumber dihapus dari model -> pekerjaan hilang, bukan angka lama
            elif m <= 0:
                notes.append((r, None, f"Sumber baris {r['row']} ({r.get('uraian') or r.get('uraian_group')}) tidak ditemukan lagi di model — volume dibiarkan {old}."))
                continue
            elif b["mode"] == "direct": new = round(b["base_vol"] + (m - b["base_metric"]), 3)   # selisih luas model ditambahkan apa adanya
            else: new = round(b["base_vol"] * m / b["base_metric"], 3) if b["base_metric"] else old
            dep = b.get("analysis")
            exact = b["base_vol"] * m / b["base_metric"] if b["mode"] == "ratio" and b["base_metric"] and m > 0 else new
            if dep and exact and exact > 0: _dependency(spec, r, b, dep, exact, tb, changes)
        tol = 0.0005 if (r.get("sat") or "").lower().startswith("m3") else MIN_CHANGE
        if old is None or new is None or abs(new - old) < tol: continue
        if src.get("manual"):
            if src.get("conflict", {}).get("model") != new:
                src["conflict"] = {"model": new, "at": _now()}
                conflicts.append({"row": r["row"], "uraian": r.get("uraian") or r.get("uraian_group"), "manual": old, "model": new})
            continue
        holder[key] = new
        src.pop("conflict", None)
        changes.append({"row": r["row"], "uraian": r.get("uraian") or r.get("uraian_group"), "ruang": r.get("ruang"), "old": old, "new": new,
                        "sat": r.get("sat"), "shared": r.get("shared") or []})
    # objek baru (instance, bukan nama definisi: salinan kedua komponen yang sama juga terdeteksi)
    meta = spec.setdefault("meta", {}).setdefault("model_bind", {})
    known = set(meta.get("object_ids") or [])
    if known:
        for pid in sorted(set(tb["object_ids"]) - known):
            o = tb["objs"][pid]
            notes.append((None, o["name"], f"Objek baru di model: {o['name']} (layer {o.get('layer')}) — belum masuk baris RAB mana pun."))
    meta["object_ids"] = tb["object_ids"]; meta["objects"] = tb["names"]
    return changes, conflicts, notes


def _wh(bb): return [max(bb[3] - bb[0], bb[4] - bb[1]), bb[5] - bb[2]]


def _resized(spec, r, holder, src, b, tb, pid, changes, notes):
    """ukuran kusen di model berubah -> analisa dihitung ulang bila ada resep ukuran, selain itu catatan."""
    bb = tb["objs"][pid].get("bbox")
    if not bb: return
    now = _wh(bb); ref = b.get("model_size") or b.get("size") or now; w0, h0 = b.get("size") or ref
    if abs(now[0] - ref[0]) <= SIZE_TOL and abs(now[1] - ref[1]) <= SIZE_TOL: return
    # ukuran kusen = ukuran tercatat x perubahan amplop model (amplop bisa memuat handle/daun terbuka)
    wn, hn = round(w0 * now[0] / ref[0]), round(h0 * now[1] / ref[1])
    name = tb["objs"][pid]["name"]
    if src.get("manual_dimensions"):
        notes.append((r, name, f"Ukuran {r.get('code') or ''} berubah di model ({w0}×{h0} → {wn}×{hn} mm); ukuran koreksi manual dipertahankan.")); return
    if resize_opening(spec, holder, wn / 1000, hn / 1000):
        changes.append({"row": r["row"], "uraian": f"Ukuran {holder.get('code')}", "ruang": r.get("ruang"), "old": f"{w0}×{h0}", "new": f"{wn}×{hn}", "sat": "mm"})
        b["size"] = [wn, hn]; b["model_size"] = now
    else:
        notes.append((r, name, f"Ukuran kusen {r.get('code') or ''} berubah di model: {w0}×{h0} → {wn}×{hn} mm. Analisa {r.get('code') or ''} belum punya resep ukuran — hitung ulang harganya."))
        b["model_size"] = now


def _dependency(spec, r, b, dep, new, tb, changes):
    """koefisien analisa yang ikut ukuran model (mis. kebutuhan grating per m2) dihitung ulang."""
    an = next((a for a in spec.get("audit", []) if a["code"] == dep["code"]), None)
    v = metric({"ids": b["terms"].get("ids"), "measure": dep["measure"]}, tb)
    if not an or v <= 0 or not dep.get("base_metric"): return
    if an.get("metric_params") and dep.get("parameter"):
        from core.analysis import recalculate
        val = dep["base_value"] * v / dep["base_metric"] * b["base_vol"] / new
        old = an["metric_params"].get(dep["parameter"])
        if old is None or abs(val - old) > 5e-6:
            recalculate(an, extra={dep["parameter"]: val})
            changes.append({"row": r["row"], "uraian": f"Analisa {an['code']}", "old": old, "new": round(val, 4), "sat": dep["parameter"]})
    elif len(an.get("components", [])) == 1 and dep.get("base_koef"):
        k = round(dep["base_koef"] * v / dep["base_metric"] * b["base_vol"] / new, 6); c = an["components"][0]
        if abs(c["koef"] - k) > 5e-6:
            changes.append({"row": r["row"], "uraian": f"Analisa {an['code']}", "old": c["koef"], "new": k, "sat": "koef"}); c["koef"] = k


def resize_opening(spec, opening, width, height):
    """kusen berubah ukuran -> analisa paketnya dihitung ulang (resep ukuran, core/analysis.py).
    Tipe yang dipakai bersama bukaan lain dipecah jadi kode baru supaya bukaan lain tidak ikut berubah."""
    import copy
    an = next((a for a in spec.get("audit", []) if a["code"] == opening.get("code")), None)
    if not an or width <= 0 or height <= 0 or not an.get("dimension_recipe"): return False
    code = opening["code"]
    if sum(o.get("code") == code for o in spec.get("openings", [])) > 1:
        an = copy.deepcopy(an)
        pre = re.match(r"[A-Za-z]+", code).group(0); used = {a["code"] for a in spec["audit"]}; i = 1
        while f"{pre}{i}" in used: i += 1
        opening["code"] = an["code"] = f"{pre}{i}"; spec["audit"].append(an)
    from core.analysis import recalculate
    opening["w"], opening["h"] = round(width, 4), round(height, 4)
    recalculate(an, width, height)
    pat = r"[\d.,]+\s*[×x]\s*[\d.,]+\s*cm"; size = f"{width * 100:.1f} × {height * 100:.1f} cm"
    opening["spec"] = re.sub(pat, size, opening.get("spec", ""), count=1); an["name"] = re.sub(pat, size, an["name"], count=1)
    return True
