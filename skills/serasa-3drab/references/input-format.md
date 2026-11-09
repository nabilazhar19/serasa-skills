# Format input `build_rab.py`

```jsonc
{
  "project": {
    "title": "BKU HOUSE (0113_BENGKULU HOUSE) - Area Rumah, Farm & Carport",
    "file_name": "0113_BENGKULU HOUSE",   // judul file Google Sheet (= nama folder proyek)
    "tab": "BKU House",                   // nama tab RAB
    "analisa_tab": "Analisa BKU",
    "zona": "Kota Bengkulu",              // persis seperti di tab IKK
    "basis": "Kota Bogor"
  },
  "luasan": {
    "tanah_label": "Luas Tanah (area merah: rumah, farm, carport)",
    "tanah": 625,
    "lantai": [                            // 1–3 lantai
      {"short": "Lt.1", "label": "Luas Lantai 1 (bangunan + deck/teras beratap)",
       "items": [["rumah", 94.7], ["deck barat bawah plafon", 32.7]]},
      {"short": "Lt.2", "label": "Luas Lantai 2", "items": [["ruang dalam", 85.8]]}
    ],
    "note": "opsional, catatan di bawah rincian"
  },
  "opening_codes": {"openingan":"X-01","swing":"X-02","swing_hw":"X-03","glass":"X-04","slide_hw":"X-05","fixed":"X-06","louvre":"X-07"},
  "walls": [   // satu item per ruang interior / zona eksterior; parts = luas per tipe finishing (m²)
    {"room": "Living & Pantry", "lantai": "Lantai 1", "interior": true, "parts": {"ekspos": 44.55, "putih": 12.1}},
    {"room": "Massa Lt.2 & Gevel", "lantai": "Lantai 2", "interior": false, "parts": {"ekspos": 84.01}, "finish_code": {"putih": "W20"}}
  ],
  "openings": [  // type: swing | slide | fix | louvre | ahs_m2
    {"uraian": "Living > Deck Timur / Pintu kaca sliding 4 panel, rangka aluminium hitam, tempered 8 mm",
     "lantai": "Lantai 1", "w": 4.5, "h": 2.44, "type": "slide", "panels": 4},
    {"uraian": "Storage > Depan / Pintu besi plat", "lantai": "Lantai 1", "w": 2.7, "h": 2.4, "type": "ahs_m2",
     "ahs": "Pembuatan dan pemasangan 1 m2 pintu besi pelat baja tebal 2 mm rangkap, rangka baja siku1,967,200.00"}
  ],
  "analisa": [
    {"code": "X-01", "name": "Openingan kusen ...", "sat": "m1", "note": "...",
     "components": [
       {"name": "Plester 5mm lebar 15 cm", "sat": "m2", "koef": 0.15, "price": "MASTER:PD2", "src": "MASTER PD2"},
       {"name": "Upah tali air", "sat": "m1", "koef": 1, "price": 18000, "src": "asumsi"}]}
  ],
  "bab": [
    {"no": "I", "title": "Pekerjaan Persiapan", "rows": [
      {"type": "master",  "uraian": "Listrik kerja", "ruang": "Seluruh area", "lantai": "All Floor", "code": "PP1", "sat": "bln", "vol": 6},
      {"type": "ahs",     "uraian": "Bouwplank", "ruang": "Keliling massa", "lantai": "All Floor", "ahs": "Pasangan 1 m' bouwplank", "sat": "m1", "vol": 73},
      {"type": "analisa", "uraian": "Jembatan grating", "ruang": "...", "lantai": "Lantai 1", "code": "X-12", "sat": "m2", "vol": 13.1},
      {"type": "note",    "uraian": "Tidak dihitung - struktur belum ada", "spec": "Menyusul"},
      {"type": "sub",     "title": "Pasangan roster"}
    ]},
    {"no": "IV", "title": "Pekerjaan Dinding, Plester & Acian", "rows": [
      {"type": "master", "...": "pasangan bata per massa"},
      {"type": "wall_plaster_aci"}           // -> plester & aci per ruang dari `walls` + openingan kusen per lantai (dari `openings`)
    ]},
    {"no": "V",  "title": "Pekerjaan Kusen, Pintu & Jendela", "rows": [{"type": "openings"}]},
    {"no": "IX", "title": "Pekerjaan Finishing Arsitektur", "rows": [{"type": "wall_finish"}, {"type": "sub", "title": "FINISHING LANTAI"}]}
  ]
}
```

Catatan:
- Volume selalu angka (titik desimal di JSON). Builder mengubah ke format locale saat dibutuhkan di rumus.
- Baris `master`: Spec & harga diambil otomatis dari MASTER AHS lewat kode. Baris `ahs`: nama AHS persis → Spec & harga. Baris `analisa`: kode → nama & harga dari tab Analisa.
- Harga pintu/jendela = luas × harga analisa (X-02/X-04/X-06/X-07) + hardware (X-03 per unit swing; X-05 × (daun−1) untuk sliding).
- Openingan kusen: swing/slide = 2×tinggi + lebar; fix/louvre = 2×(lebar+tinggi).
