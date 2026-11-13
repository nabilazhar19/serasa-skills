# Viewport RAB — lokal, untuk semua agen (Claude, Codex, dll.), Windows & Mac

Halaman lokal `http://localhost:8765`: model 3D dari SKP + tabel RAB. Setiap baris menunjuk bagian model sumber volumenya, dan pengguna bisa mengoreksi langsung di halaman lalu Push ke Sheet. Satu server melayani semua proyek; proyek aktif pindah otomatis. Server hanya memakai pustaka bawaan Python (library Google hanya untuk Push/Tarik dari Sheet).

## Lokasi
- Terpasang (setelah `scripts/setup.py` / `SerasaRAB.install_plugin`): folder bersama `~/Library/Application Support/SerasaRAB` (Mac) atau `%APPDATA%\SerasaRAB` (Windows). Isinya `viewport/`, `scripts/build_rab.py`, dan `env.json` (path Python).
- Belum terpasang: `<skill>/viewport/`.
- `T` di bawah = `<lokasi>/viewport/tools.py`; `PY` = `python3` (Mac) atau `py -3` / `python` (Windows), atau nilai `python` di `env.json`.
- Agen tanpa shell di komputer pengguna (cloud): jalankan perintah yang sama lewat SketchUp, `SerasaRAB.run_tools(['status','--project',dir,'--message','...'], wait: true)`. Bisa juga dengan menulis file proyek langsung (status/viewport.json). **Server harus berjalan di komputer pengguna**, tidak di sandbox agen.

## File per proyek (`<folder proyek>/_serasa_tools/`)
| file | penulis | isi |
|---|---|---|
| `viewport.json` | `T init` | judul, input, ahs, model3d, sheet_url/gid, spreadsheet_id, creds, ahs_source. Path relatif ke `_serasa_tools` |
| `viewport_status.json` | `T status` | tahap kerja agen, tampil di header (spinner; ✓ bila stage `selesai`) |
| `<nama>_input.json` | agen / viewport | input builder. Viewport memuat ulang otomatis saat file berubah |
| `<nama>_model3d.json` | SketchUp `watch_export` | format 4: geometri sekali per definisi + instance, muka per bidang, luas per tag, ukuran khusus. Diperbarui setelah Save (hanya objek berubah) |
| `serasa_watch.json` | SketchUp / agen | setelan ekspor: region, rooms, bands, angle, `measures` per pid, `skip_layers`, `display_layers` |
| `export_status.json` | SketchUp | progres ekspor setelah Save → tampil di header viewport |
| `koreksi_log.json`, `.koreksi/` | viewport | riwayat + snapshot (Undo) |
| `koreksi_catatan.json` | viewport | catatan pengguna untuk agen (`T notes`) |

## Siklus dalam alur skill
| saat | perintah |
|---|---|
| mulai (folder proyek & nama input diketahui) | `PY T init --project DIR --input <nama>_input.json --title "<PROYEK>"` lalu `PY T open --project DIR` |
| tiap langkah | `PY T status --project DIR --message "Take-off dinding Lt.1" --stage takeoff --step 2 --steps 6` |
| setelah take-off | SketchUp: `SerasaRAB.watch_export(region, "<DIR>/_serasa_tools/<nama>_model3d.json", rooms, bands, angle, {"measures": {...}})` lalu `T init --project DIR --model3d <nama>_model3d.json` |
| input ditulis | tidak perlu apa pun: tabel muncul/terbarui sendiri |
| setelah push pertama | `T init --project DIR --sheet-url URL --sheet-gid GID --spreadsheet-id ID --creds ../../_serasa_keys/<key>.json --ahs-source "<csv export AHS>"` lalu `T bind --project DIR` |
| akhir | `T status --project DIR --stage selesai --message "RAB terkirim ke Sheet"` dan sebutkan `http://localhost:8765` di laporan |

Langkah: 1 baca denah · 2 take-off SKP · 3 rekonsiliasi · 4 AHS & input · 5 tulis Sheet · 6 verifikasi. Status singkat, satu baris, bahasa pengguna.

## Koreksi dari viewport
- Edit volume/spec/pending, Undo, Riwayat, Tarik dari Sheet: dikerjakan viewport (snapshot + log). Agen tidak perlu terlibat.
- **Push** = `build_rab.py --prepare patch`: hanya sel yang berubah + Audit bila berubah. Bila struktur baris berubah (exit 3), viewport meminta izin rebuild (`--prepare none`).
- Catatan pengguna ("kerjakan catatan"): `T notes --project DIR` → kerjakan di input (bukan di Sheet, kecuali diminta) → `T note-done --project DIR --id N`. Perubahan input tampil di viewport sebagai perubahan belum di-push; pengguna yang menekan Push, atau agen push dengan `--prepare patch` bila diminta.
- **Save SKP → satu siklus**: plugin mengekspor ulang hanya objek yang berubah (dicicil, SketchUp tetap bisa dipakai; status di header) → baris tertaut dihitung ulang → harga, subtotal, total → Riwayat "Save SKP: n baris berubah; total Rp a → Rp b" + angka di tombol Push. Sheet belum berubah sampai Push. Volume tidak berubah → tidak masuk Riwayat.
- Objek sumber dihapus seluruhnya → volume 0. Objek baru → catatan. Ukuran kusen berubah + analisa punya `dimension_recipe` → harga paket dihitung ulang (bukaan lain bertipe sama dipecah ke kode baru); tanpa resep → catatan.
- Plugin/format ekspor baru → tautan disesuaikan sekali ("Model 3D format baru: n tautan disesuaikan, angka RAB tetap").

## Ukuran khusus (`measures` di serasa_watch.json)
Hanya dihitung untuk pid yang disebut; dipakai baris yang volumenya bukan luas muka (`sync.MEASURE_RULES`: pasangan → volume per lantai, rangka atap → luas proyeksi, penutup atap → luas miring, bouwplank → keliling, roster → luas modul).
```json
"measures": {"16690814": {"bands": [["Lantai 1", 400, 3600], ["Lantai 2", 3600, 6490]], "masonry_exclude": "/Component#"},
             "1645170": {"roof_materials": ["Bitumen Roof Shingles"]}, "16701872": {"perimeter": true},
             "1633493": {"roster": true}, "1644821": {"solid": true}, "10836702": {"seat_name": "Group#222"}}
```
Hasil: `solid_m3`, `top_m2`, `solid_m3:<pita>`, `roof_m2`, `roof_xy_m2`, `perimeter_m`, `roster_m2` (modul otomatis = potongan paling sering; atau regex nama definisi), `seat_m2`/`concrete_m3`/`steel_m3`, `envelope_m2`.

## Di halaman
- **Klik bidang** di 3D → bidang itu disorot (biru tua) di objeknya; panel kanan: luas bidang & objek, tag ruang/arah, baris RAB yang menghitung bidang itu, dan baris yang mengacu ke objek utuh. "Pilih seluruh objek" untuk beralih.
- **Garis potong**: Utuh / Denah (geser tinggi, tombol per lantai) / Potongan (Timur–Barat atau Utara–Selatan, geser, balik) / Kotak (6 sisi, tarik titik biru). "Isi potongan" mengisi bidang terpotong dengan abu gelap (hanya solid tertutup). Bagian terpotong tidak bisa diklik.

## Kunci versi resmi (wajib)
Tampilan **dan** kode viewport, builder, plugin dan setup dikunci `LOCK.json` (sha256). Agen tidak mengubahnya — termasuk salinan di folder `SerasaRAB` dan Plugins SketchUp. `PY T check` harus `kunci versi resmi: OK` dan plugin di semua SketchUp sama dengan versi resmi; bila berbeda, viewport menampilkan peringatan dan `scripts/setup.py` mengembalikannya (file tambahan dinonaktifkan jadi `.tidak-resmi`). Perubahan resmi hanya di repo skill: ubah, uji, `PY T lock --version <baru>`.

## Gangguan
- `T check`: Python, library Google, kunci desain, server.
- Server tidak menyala: `viewport/server.log`. Port 8765 dipakai program lain → hentikan program itu (viewport selalu di 8765 agar plugin, agen dan bookmark sama).
- Push "Library Google belum terpasang": jalankan `scripts/setup.py` dengan Python yang sama dengan `env.json`.

## RAB terpisah per bangunan (hanya bila pengguna memintanya secara eksplisit)
Default satu tab RAB. Bila pengguna meminta tab terpisah (mis. Rumah / Kost / Ruko): tetap SATU input induk; tambahkan `building_tabs` di
`viewport.json`:
```json
"building_tabs": [
  {"id": "rumah", "label": "Rumah", "tab": "RAB Rumah", "audit_tab": "Audit Rumah", "sheet_id": 101, "audit_id": 111, "match": "\\brumah\\b"},
  {"id": "kost",  "label": "Kost",  "tab": "RAB Kost",  "audit_tab": "Audit Kost",  "sheet_id": 102, "audit_id": 112, "match": "\\bkost?\\b"},
  {"id": "bersama", "label": "Area Bersama", "tab": "RAB Area Bersama", "audit_tab": "Audit Area Bersama", "sheet_id": 104, "audit_id": 114, "shared": true}]
```
- Alokasi baris: `building` di baris/bukaan/dinding → regex `match` pada Ruang/Area → tab `shared` (tapak, pagar, taman, biaya proyek, pending belum teralokasi; dihitung sekali).
- Tab & Audit tiap bangunan dibuat dulu di Sheet (salin format tab RAB template), `sheet_id`/`audit_id` = gid tab itu. Rekap proyek boleh berupa tab formula yang menjumlah total tiap tab.
- Viewport: strip bangunan di bawah header (tabel, total, luas, sorotan model per bangunan; total proyek tetap tampil), pilihan "Bangunan RAB" di panel baris untuk memindahkan alokasi, tombol **Push semua RAB** (patch per tab; struktur berubah → konfirmasi rebuild tab itu saja; baseline per tab di `.koreksi/split_state.json`).
- **Jangan** menjalankan `build_rab.py` langsung pada input induk proyek `building_tabs`; Push lewat viewport (`core/scope_sheets.py`).
