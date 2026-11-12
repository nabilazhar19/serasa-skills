"""
core/mesh.py - ubah ekspor SketchUp (JSON besar, SerasaRAB.export_mesh) jadi paket biner ringkas untuk viewport.

Isi paket:  [uint32 panjang meta][meta JSON utf-8][padding ke kelipatan 4][Int16 x,y,z per vertex]
- vertex relatif ke titik tengah model, satuan `scale` mm (1 mm bila model < ±32 m dari tengah)
- bagian (part) digabung per (objek, tag muka, kaca/tidak) -> jauh lebih sedikit objek yang digambar browser
- warna disimpan sebagai "runs" (jumlah vertex + RGBA), luas tiap part (m²) dihitung di sini
Hasil di-cache server sampai file ekspor berubah.
"""
import array, json, math, struct, sys


def _area(p, i):  # luas segitiga mulai index i (koordinat mm) -> mm²
    ax, ay, az = p[i + 3] - p[i], p[i + 4] - p[i + 1], p[i + 5] - p[i + 2]
    bx, by, bz = p[i + 6] - p[i], p[i + 7] - p[i + 1], p[i + 8] - p[i + 2]
    cx, cy, cz = ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx
    return 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)


def pack(path):
    d = json.load(open(path, encoding="utf-8"))
    mn = [1e18] * 3; mx = [-1e18] * 3
    for o in d["objects"]:
        for p in o["parts"]:
            q = p["p"]
            for k in range(3):
                v = q[k::3]
                if v: mn[k] = min(mn[k], min(v)); mx[k] = max(mx[k], max(v))
    origin = [round((mn[0] + mx[0]) / 2), round((mn[1] + mx[1]) / 2), round(mn[2])]
    ext = max(max(abs(mx[k] - origin[k]), abs(mn[k] - origin[k])) for k in range(3))
    scale = max(1, math.ceil(ext / 32000))

    groups = {}  # (oi, tag, glass) -> list of (pts, rgba)
    for oi, o in enumerate(d["objects"]):
        for p in o["parts"]:
            glass = p["c"][3] < 200
            groups.setdefault((oi, p["t"], glass), []).append(p)

    buf = array.array("h"); parts = []
    for (oi, tag, glass), ps in groups.items():
        start = len(buf) // 3; runs = []; area = 0.0
        for p in ps:
            q = p["p"]; n = len(q) // 3
            for i in range(0, len(q), 3):
                buf.append(round((q[i] - origin[0]) / scale)); buf.append(round((q[i + 1] - origin[1]) / scale)); buf.append(round((q[i + 2] - origin[2]) / scale))
            for i in range(0, len(q), 9): area += _area(q, i)
            if runs and runs[-1][1:] == list(p["c"]): runs[-1][0] += n
            else: runs.append([n] + list(p["c"]))
        parts.append({"o": oi, "t": tag, "glass": glass, "start": start, "count": len(buf) // 3 - start, "area": round(area / 1e6, 3), "runs": runs})

    meta = {"exported": d.get("exported"), "model": d.get("model"), "rooms": d.get("rooms", []), "bands": d.get("bands", []),
            "origin": origin, "scale": scale,
            "objects": [{"pid": o["pid"], "name": o["name"], "layer": o["layer"]} for o in d["objects"]], "parts": parts}
    mb = json.dumps(meta, ensure_ascii=False, separators=(",", ":")).encode()
    mb += b" " * (-(len(mb) + 4) % 4)
    if sys.byteorder != "little": buf.byteswap()
    return struct.pack("<I", len(mb)) + mb + buf.tobytes(), meta
