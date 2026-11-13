"""
core/mesh.py - ubah ekspor SketchUp (SerasaRAB, format 4) jadi paket biner ringkas untuk viewport.

Ekspor format 4 menyimpan geometri SEKALI per definisi (koordinat lokal mm) + daftar instance (matriks) per objek,
jadi model dengan banyak komponen kembar (roster, kusen, sanitair) tetap kecil. Browser yang merangkai instance.

Paket:  [uint32 panjang meta][meta JSON][padding 4][Float32 V][Uint32 T][Float32 E]
  V  = vertex lokal semua definisi (mm), T = indeks segitiga per definisi (lokal), E = titik garis tepi SketchUp (mm lokal)
  meta.defs[i]   = {name, v:[offset, jumlah_float], t:[offset, jumlah_index], e:[offset, jumlah_float], f:[[material, jumlah_segitiga], ..],
                    c: 1 bila solid tertutup (dipakai untuk isian bidang potong)}
  meta.objects[] = {pid, name, layer, bbox, leaves:[[def, m12, material_warisan]], ft:[[tagset, jumlah_muka], ..]}
  meta.materials = [[nama, r, g, b, a]], meta.tagsets = ["", "R|Toko 1|putih", ..], meta.origin = titik acuan (mm)
Ekspor lama (format 2/3: segitiga dunia per part) diubah ke bentuk yang sama: 1 part = 1 "definisi" + 1 muka.
Hasil di-cache server sampai file ekspor berubah.
"""
import array, json, struct, sys

IDENT = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]


def _legacy(d):
    """format lama (parts dengan segitiga dunia) -> struktur format 4."""
    mats, mi, tagsets, ti, defs, objs = [], {}, [""], {"": 0}, [], []
    for o in d["objects"]:
        leaves, ft = [], []
        for p in o["parts"]:
            c = tuple(p["c"])
            if c not in mi: mi[c] = len(mats); mats.append(["rgba" + str(c)] + list(c))
            t = p.get("t") or ""
            if t not in ti: ti[t] = len(tagsets); tagsets.append(t)
            n = len(p["p"]) // 9
            defs.append({"name": o["name"], "f": [[mi[c], n]], "v": p["p"], "t": list(range(n * 3)), "e": []})
            leaves.append([len(defs) - 1, IDENT, -1]); ft.append([ti[t], 1])
        objs.append({k: o[k] for k in ("pid", "name", "layer", "bbox") if k in o} | {"leaves": leaves, "ft": ft, "edges_auto": True})
    return {"materials": mats, "tagsets": tagsets, "defs": defs, "objects": objs}


def pack(path):
    d = json.load(open(path, encoding="utf-8"))
    src = d if d.get("format", 0) >= 4 else dict(d, **_legacy(d))
    mn, mx = [1e18] * 3, [-1e18] * 3
    for o in src["objects"]:
        bb = o.get("bbox")
        if bb and len(bb) == 6:
            for k in range(3): mn[k] = min(mn[k], bb[k]); mx[k] = max(mx[k], bb[k + 3])
    if mn[0] > mx[0]: mn, mx = [0, 0, 0], [0, 0, 0]
    origin = [round((mn[0] + mx[0]) / 2), round((mn[1] + mx[1]) / 2), round(mn[2])]

    V, T, E = array.array("f"), array.array("I"), array.array("f")
    defs = []
    for g in src["defs"]:
        dv = [len(V), len(g["v"])]; V.fromlist([float(x) for x in g["v"]])
        dt = [len(T), len(g["t"])]; T.fromlist([int(x) for x in g["t"]])
        de = [len(E), len(g.get("e") or [])]; E.fromlist([float(x) for x in g.get("e") or []])
        defs.append({"name": g.get("name", ""), "v": dv, "t": dt, "e": de, "f": g["f"], "c": g.get("c", 0)})
    meta = {"format": 4, "exported": d.get("exported"), "model": d.get("model"), "rooms": d.get("rooms", []), "bands": d.get("bands", []),
            "origin": origin, "materials": src["materials"], "tagsets": src["tagsets"], "defs": defs,
            "objects": [{k: o[k] for k in ("pid", "name", "layer", "bbox", "leaves", "ft", "edges_auto") if k in o} for o in src["objects"]],
            "stats": d.get("stats")}
    mb = json.dumps(meta, ensure_ascii=False, separators=(",", ":")).encode()
    mb += b" " * (-(len(mb) + 4) % 4)
    if sys.byteorder != "little":
        for a in (V, T, E): a.byteswap()
    return struct.pack("<I", len(mb)) + mb + V.tobytes() + T.tobytes() + E.tobytes(), meta


if __name__ == "__main__":   # uji cepat: python3 core/mesh.py <ekspor.json>
    import time
    t = time.time(); b, m = pack(sys.argv[1])
    print(f"{len(b) / 1e6:.1f} MB, {len(m['defs'])} definisi, {len(m['objects'])} objek, {time.time() - t:.2f} dtk")
