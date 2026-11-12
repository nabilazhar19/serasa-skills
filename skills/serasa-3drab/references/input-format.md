# Format input `build_rab.py` v3 (template Nov 2026)

Contoh ringkas: `examples/mini_input.json`. Contoh lengkap (urutan pekerjaan + pending): `examples/ruko_bkl2_input.json` (tab `ruko bkl 2`, file 0113_BENGKULU HOUSE REV1).
Urutan `bab` dan nama `uraian` mengikuti tab template `urutan pekerjaan`.

```jsonc
{
  "project": {"title": "...", "tab": "Ruko BKL", "audit_tab": "Audit", "zona": "Kota Bengkulu"},
  "luasan": {"tanah_label": "Luas Tapak ...", "tanah": 58.9,
             "lantai": [{"short": "Lt.1", "label": "Luas Lantai 1 ...", "items": [["toko", 47.9], ["teras", 7.9]]}],  // 1-2 lantai (template punya 2 baris)
             "note": "..."},
  "walls": [{"room": "Toko 1", "lantai": "Lantai 1", "interior": true, "parts": {"ekspos": 30.66, "putih": 34.85},
             "finish_spec": {"putih": "<uraian AHS lain bila beda dari default>"}}],
  "wall_specs": {                                   // uraian AHS PERSIS
    "plester": "Pekerjaan Plesteran Tebal 10 mm, ...",
    "aci":    {"ekspos": "<AD2>", "putih": "<AD1>", "terracotta": "<AD1>"},
    "finish": {"interior": {"ekspos": "<W6>", "putih": "<W1>", "terracotta": "<W76>"},
               "exterior": {"ekspos": "<W6>", "putih": "<W2>", "terracotta": "<W76>"}}},
  "openings": [{"code": "P1", "jenis": "Pintu", "ruang": "Teras > Toko 1", "lantai": "Lantai 1 (+0,50)",
                "w": 1.04, "h": 2.0, "type": "swing|slide|fix|louvre", "panels": 1,
                "spec": "Pintu kaca swing 1 daun, ukuran bukaan 104 x 200 cm. Kusen ..., kaca ..., hardware ..."}],
  "audit": [   // semua harga analisa: pekerjaan non-AHS + analisa tiap kode kusen ("group": "kusen")
    {"code": "OPK", "name": "Plester aci openingan kusen ...", "sat": "m1", "note": "...",
     "components": [{"name": "Plester 5 mm lebar 15 cm", "sat": "m2", "koef": 0.15, "price": "AHS:<uraian AHS>", "src": "AHS PD2"},
                    {"name": "Upah tali air", "sat": "m1", "koef": 1, "price": 18000}]},
    {"code": "P1", "group": "kusen", "name": "Pintu kaca swing 1 daun 104 x 200", "sat": "unit", "components": [...]}],
  "bab": [{"no": "I", "title": "Pekerjaan Persiapan", "rows": [
      {"type": "ahs", "uraian": "Listrik kerja", "ruang": "...", "lantai": "All Floor", "spec": "<uraian AHS persis>", "vol": 4},
      {"type": "audit", "uraian": "Pembersihan lokasi rutin", "ruang": "...", "lantai": "All Floor", "code": "AUD-01", "vol": 4},
      {"type": "pending", "uraian": "Kolom - Bekisting", "ruang": "Ruko 2 unit", "lantai": "All Floor", "reason": "menunggu data struktur (belum ada di SKP)"},
      {"type": "sub", "title": "Plumbing (estimasi)"},
      {"type": "wall_plaster", "uraian": "Plester dinding"}, {"type": "wall_aci", "uraian": "Acian dinding"},
      {"type": "wall_finish", "uraian": "Pengecatan dinding", "only": ["putih", "terracotta"]},   // per ruang; only = filter tipe
      {"type": "openingan", "code": "OPK", "uraian": "Openingan kusen / perapihan bukaan pintu dan jendela"},                                     // m1 keliling bukaan per lantai
      {"type": "openings"}]}]                                                   // satu baris per bukaan
}
```
Aturan:
- `uraian` = nama pekerjaan dari tab `urutan pekerjaan`; baris berurutan dengan uraian sama otomatis dikosongkan (hanya baris pertama grup).
- `pending` = pekerjaan relevan yang datanya belum ada (struktur dst.) → baris kuning tanpa volume/harga, tercatat di Audit D.
- Tipe `ahs` wajib memakai uraian yang ada di tab AHS; kalau tidak ada → buat item `audit` (jangan memaksakan item AHS yang tidak sesuai).
- Kode tipe kusen sama untuk unit identik (P1 dipakai dua kali), satu baris per bukaan.
- Openingan kusen: swing/slide = 2×tinggi + lebar, fix/louvre = 2×(lebar + tinggi); dikelompokkan per lantai dasar (teks sebelum " (").
- Volume angka (titik desimal di JSON).

## Status volume dan area tiap lapisan

Builder mendukung field berikut (opsional demi kompatibilitas input lama):

```json
{
  "audit_notes": ["Dinding memakai AAC 10 cm; detail bahan perlu verifikasi."],
  "walls": [{
    "room": "WC Toko 1", "lantai": "Lantai 1", "interior": true,
    "parts": {"putih": 12.4},
    "layer_parts": {"plester": {"putih": 12.4}, "aci": {"putih": 1.0}, "finish": {"putih": 1.0}},
    "estimated": true, "quantity_note": "Ukuran WC dari denah; isi ukuran final."
  }]
}
```

- Pada baris `ahs` / `audit`, tambahkan `estimated: true` dan `quantity_note` bila volumenya estimasi. Berlaku juga pada `openings[]`; keliling openingan agregat ditandai jika ada bukaan estimasi.
- Flag pada blok pembangkit (misalnya `wall_plaster`) menandai semua baris hasil blok itu. Untuk sebagian dinding, gunakan flag pada record `walls[]` atau daftar `estimated_parts: ["putih"]`; turunan bagian itu ikut ditandai.
- `layer_parts` menimpa `parts` hanya untuk lapisan yang disebut (`plester`, `aci`, `finish`); `{}` melewati lapisan itu. Bila tidak ada, builder memakai `parts` lama. Jangan menganggap luas semua lapisan sama tanpa rekonsiliasi. Bila batas bidang/metodenya kompleks, gunakan baris `ahs` eksplisit per ruang/lapisan dari register yang sudah diperiksa.
- Flag hanya memberi warna H #FFD966 dan catatan di Audit E, tidak menghapus angka/harga. Flag tidak otomatis mendeteksi estimasi: agen harus mengklasifikasikan sumber. Catatan pilihan bahan saja memakai `audit_notes`, tidak menandai volume terukur.
- Jangan gunakan nama teknis/internal ID dalam `room`, `ruang`, `note`, `spec` atau teks Audit. Simpan jejak teknis di register lokal terpisah.
- Isi kosong dan pilihan bahan live milik pengguna tidak boleh dipulihkan dari JSON lama saat melanjutkan. Snapshot live dan patch adalah acuan; input builder untuk rebuild harus direkonsiliasi dulu.
