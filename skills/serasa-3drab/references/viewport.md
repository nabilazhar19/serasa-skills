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
| `<nama>_model3d.json` | SketchUp `watch_export` | mesh + luas per tag; diekspor ulang tiap model disimpan |
| `serasa_watch.json` | SketchUp | setelan ekspor ulang otomatis (tetap aktif setelah SketchUp dibuka ulang) |
| `koreksi_log.json`, `.koreksi/` | viewport | riwayat + snapshot (Undo) |
| `koreksi_catatan.json` | viewport | catatan pengguna untuk agen (`T notes`) |

## Siklus dalam alur skill
| saat | perintah |
|---|---|
| mulai (folder proyek & nama input diketahui) | `PY T init --project DIR --input <nama>_input.json --title "<PROYEK>"` lalu `PY T open --project DIR` |
| tiap langkah | `PY T status --project DIR --message "Take-off dinding Lt.1" --stage takeoff --step 2 --steps 6` |
| setelah take-off | SketchUp: `SerasaRAB.watch_export(region, "<DIR>/_serasa_tools/<nama>_model3d.json", rooms, bands, angle)` lalu `T init --project DIR --model3d <nama>_model3d.json` |
| input ditulis | tidak perlu apa pun: tabel muncul/terbarui sendiri |
| setelah push pertama | `T init --project DIR --sheet-url URL --sheet-gid GID --spreadsheet-id ID --creds ../../_serasa_keys/<key>.json --ahs-source "<csv export AHS>"` lalu `T bind --project DIR` |
| akhir | `T status --project DIR --stage selesai --message "RAB terkirim ke Sheet"` dan sebutkan `http://localhost:8765` di laporan |

Langkah: 1 baca denah · 2 take-off SKP · 3 rekonsiliasi · 4 AHS & input · 5 tulis Sheet · 6 verifikasi. Status singkat, satu baris, bahasa pengguna.

## Koreksi dari viewport
- Edit volume/spec/pending, Undo, Riwayat, Tarik dari Sheet: dikerjakan viewport (snapshot + log). Agen tidak perlu terlibat.
- **Push** = `build_rab.py --prepare patch`: hanya sel yang berubah + Audit bila berubah. Bila struktur baris berubah (exit 3), viewport meminta izin rebuild (`--prepare none`).
- Catatan pengguna ("kerjakan catatan"): `T notes --project DIR` → kerjakan di input (bukan di Sheet, kecuali diminta) → `T note-done --project DIR --id N`. Perubahan input tampil di viewport sebagai perubahan belum di-push; pengguna yang menekan Push, atau agen push dengan `--prepare patch` bila diminta.
- SKP disimpan → model3d diekspor ulang → baris yang ditautkan (`bind`) ikut berubah di web (belum ke Sheet); objek baru/hilang menjadi catatan otomatis.

## Kunci desain (wajib)
Tampilan viewport sudah final. **Jangan mengubah apa pun di `viewport/web/`** (HTML, CSS, JS, vendor) kecuali pengguna secara eksplisit meminta perubahan tampilan. `PY T check` harus menunjukkan `kunci desain: OK`. Bila berubah tanpa diminta, viewport menampilkan peringatan; kembalikan dari repo. Perubahan resmi: ubah, uji, lalu `PY T lock --version <baru>`.
Logika baru masuk `core/` atau `server.py`; data baru cukup lewat field yang sudah ada (`estimated`, `quantity_note`, `src`, status).

## Gangguan
- `T check`: Python, library Google, kunci desain, server.
- Server tidak menyala: `viewport/server.log`. Port 8765 dipakai program lain → hentikan program itu (viewport selalu di 8765 agar plugin, agen dan bookmark sama).
- Push "Library Google belum terpasang": jalankan `scripts/setup.py` dengan Python yang sama dengan `env.json`.
