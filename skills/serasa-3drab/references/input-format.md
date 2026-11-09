# Format input `build_rab.py`

Contoh ringkas yang mencakup semua tipe baris: `examples/mini_input.json` (±5 KB) — **baca ini dulu**.
Contoh proyek lengkap (`examples/bku_input.json`, ±40 KB) hanya dibuka bila butuh referensi isi bab yang panjang
(MEP, kolam, lanskap).

## Struktur
- `project`: `title`, `tab` (nama tab RAB), `analisa_tab` (opsional), `zona` (persis seperti tab IKK), `basis`.
- `luasan`: `tanah_label`, `tanah`, `lantai` (1–3 item: `short`, `label`, `items` [[nama, m²], …]), `note`.
- `opening_codes`: kode analisa bukaan — `openingan, swing, swing_hw, glass, slide_hw, fixed, louvre`
  (default `X-01…X-07`; di file proyek yang sudah punya analisa, pakai prefix baru mis. `RKO-`).
- `analisa`: `[{code, name, sat, note?, components:[{name, sat, koef, price, src?}]}]`.
  `price` angka (harga basis) atau `"MASTER:<kode>"` / `"AHS:<nama persis>"` → jadi rumus lookup.
- `walls`: satu item per ruang interior / zona eksterior:
  `{room, lantai, interior, parts:{ekspos|putih|terracotta|pola: m²}, finish_code?:{tipe: kode}}`.
- `openings`: `{uraian "Ruang A > Ruang B / jenis", lantai, w, h (m), type swing|slide|fix|louvre|ahs_m2, panels, ahs?}`.
- `bab`: `[{no, title, rows:[…]}]`, tipe baris:
  - `master` `{uraian, ruang, lantai, code, sat, vol, spec?}` — `spec` menimpa Spec (wajib untuk kode bernama `#N/A`, mis. PP3)
  - `ahs` `{…, ahs:"<nama AHS persis>", sat, vol}`
  - `analisa` `{…, code, sat, vol}`
  - `note` `{uraian, spec}` (mis. struktur tidak dihitung) · `sub` `{title}`
  - blok otomatis: `wall_plaster_aci` (plester + aci per ruang dari `walls` + openingan kusen per lantai),
    `openings` (satu baris per bukaan), `wall_finish` (finishing dinding per ruang).

## Aturan harga bukaan
- swing: luas × harga `swing` + **jumlah daun** × `swing_hw`
- slide: luas × harga `glass` + (daun − 1) × `slide_hw`
- fix / louvre: luas × harga `fixed` / `louvre`
- ahs_m2: baris AHS dengan volume = luas
- Openingan kusen (m1): swing/slide = 2×tinggi + lebar; fix/louvre = 2×(lebar + tinggi).

Volume selalu angka (titik desimal di JSON); builder mengubah ke format locale di dalam rumus.
