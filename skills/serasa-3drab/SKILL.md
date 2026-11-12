---
name: serasa-3drab
description: Buat RAB (Rencana Anggaran Biaya) format PT Serasa Rancang Indonesia dari model SketchUp (.skp) dan denah - rincian per ruang, Spec dropdown dari tab AHS (kode & harga VLOOKUP), kode + spesifikasi + analisa harga kusen/pintu/jendela dari model, tab Audit (pekerjaan non-AHS & AHS terpakai), di salinan Template RAB Google Sheet. Pakai saat user minta "buat RAB", "hitung RAB dari skp", "RAB format Serasa", atau melampirkan skp + denah.
---

# Serasa 3D RAB (serasa-3drab) — dari SKP + denah ke Google Sheet RAB

Output: salinan Template RAB (judul = nama proyek, mis. `0113_BENGKULU HOUSE REV1`) berisi
- tab RAB proyek (tab `Serasa Template` diganti nama, mis. `Ruko BKL`) dengan rincian per ruang, dan
- tab **`Audit`**: (A) pekerjaan yang tidak ada di AHS + analisanya, (B) analisa harga kusen/pintu/jendela, (C) item AHS yang terpakai.

- Template (WAJIB, jangan buat dari nol): https://docs.google.com/spreadsheets/d/1zwpn8sGUDQK4_FUd86FiYBzSVwW9y-pygasOf73Kahg — tab `AHS` (IMPORTRANGE Rekap AHS: A Uraian, B Kategori, C Satuan, D Harga, E Kode) + `Serasa Template`. Tidak ada lagi MASTER AHS / IKK / koefisien.
- Contoh hasil format baru: file `0113_BENGKULU HOUSE REV1`, tab `ruko bkl 2` + `Audit ruko bkl 2` (urutan pekerjaan + pending). Tab `Ruko BKL` di file yang sama belum mengikuti urutan pekerjaan. File lama `0113_BENGKULU HOUSE` memakai format lama (MASTER AHS) — jangan dijadikan acuan format.

## Aturan format RAB (template Nov 2026)
1. **Uraian (B)** = judul singkat, hanya di baris pertama grup. **Spec (F)** = referensinya.
2. **Semua bab kecuali kusen**: Spec = **uraian tab AHS persis**, dropdown plaintext (validasi `=AHS!$A$2:$A$2159`); Kode (E), Satuan (G), Harga (I) = VLOOKUP ke tab AHS dari Spec. Jangan mengetik harga/kode manual.
3. **Bab kusen, pintu & jendela**: Kode = kode tipe buatan (P1, P2, J1, PJ1…; tipe identik = kode sama), Spec = spesifikasi lengkap pintu/jendela termasuk ukuran (dari model SKP), Satuan unit, Harga = analisa dari model (komponen di tab Audit bagian B).
4. **Pekerjaan yang ada di model tapi tidak ada di AHS**: tetap diisi (RAB harus penuh) — analisa harganya, tulis Spec sebagai teks tanpa dropdown, Harga merujuk ke tab Audit bagian A. Jangan memaksakan item AHS yang tidak sesuai.
5. Tab Audit bagian C mencatat semua item AHS yang terpakai (kode, uraian, jumlah baris, volume & total live).
6. **Urutan bab & pekerjaan WAJIB mengikuti tab template `urutan pekerjaan`** (judul bab I–XI, sub-judul, dan nama pekerjaan di kolom B). Kolom Uraian memakai nama pekerjaan dari tab itu; rincian (ruang, finishing, ukuran) ditulis di kolom Ruang. Pekerjaan yang tidak relevan untuk proyek dilewati; bab yang tidak relevan (mis. Kolam) dilewati.
7. **Pekerjaan relevan yang datanya belum ada di SKP** (struktur: pondasi/sloof/kolom/balok/pelat/tangga/dak per Bekisting-Besi Ulir-Besi Polos-Beton, galian pondasi, urugan kembali; atau item persiapan yang menunggu metode kontraktor) → baris **pending**: kuning, Kode "-", Spec "PENDING - <alasan>", tanpa volume/harga; tercatat di tab Audit bagian D supaya bisa dilanjutkan nanti.

## Hemat token
1. Baca reference hanya saat masuk langkahnya; contoh input: `examples/mini_input.json` (kecil) atau `examples/ruko_bkl2_input.json` (lengkap, urutan pekerjaan + pending).
2. Script dipakai dari file. Ruby: plugin `SerasaRAB` (langkah 2). Python: `scripts/build_rab.py` apa adanya.
3. Data RAB tidak lewat chat: `--push` service account. Builder memvalidasi Spec terhadap AHS live dan mencetak ringkasan.
4. Verifikasi = ringkasan builder (`error`, `harga0`, total, subtotal); jangan membaca ulang seluruh sheet/AHS.
5. Mencari uraian AHS: ekspor/baca kolom A+E tab AHS sekali ke file lokal, lalu cari dengan script (grep kata kunci), bukan dibaca di chat.

## Lokasi scripts & references (cek berurutan)
1. Folder skill ini (`scripts/`, `references/`, `examples/`).
2. Claude Project "Automasi gambar kerja": `serasa-3drab/scripts/*`, `serasa-3drab/references/*.md`, `serasa-3drab/examples/*.json` (project_read saat dibutuhkan).
3. Paket `serasa-3drab.zip` / repo `serasa-skills` dari user.
`scripts/legacy/build_rab_v2.py` hanya untuk file format lama (MASTER AHS).

## Alat
- SketchUp: MCP SketchUp (`eval_ruby`, `get_viewport_screenshot`) atau Ruby Console.
- Google Sheets/Drive: connector Drive (copy & share file) + service account (`--push`, dijalankan di shell komputer user; key di `00 Serasa Architect/_serasa_keys/`).
- Python 3 + `google-api-python-client google-auth` di shell yang menjalankan push.

## Input dari user
1. Model **.skp** (desain final — kalau beda dengan denah, **SKP yang dipakai**).
2. **Denah** dengan area yang ditandai — hanya area itu yang dihitung.
3. Nama file/tab tujuan. Opsional: lokasi (zona), batasan ("struktur tidak dihitung").
Hal yang tidak bisa diputuskan dari model → asumsi paling masuk akal, tulis di kolom Ruang/Spec, laporkan di akhir. Jangan berhenti bertanya kecuali keputusannya mahal diulang.

## Alur kerja
### 1. Denah → area hitung
Ruang, fungsi, dimensi pokok, batas area yang ditandai.

### 2. SKP → kuantitas (`references/skp-method.md`)
1. `defined?(SerasaRAB) ? SerasaRAB::VERSION : 'belum'`. `2.1`+ → pakai. Belum/lama → `load "<folder skill>/scripts/skp_extract.rb"; SerasaRAB.install_plugin`. Agen cloud: tulis file ke folder proyek terhubung (`_serasa_tools/`, staged path unik), lalu `load` + `install_plugin`. **Jangan tempel isi script.**
2. Model yang terbuka harus model proyek ini (`Sketchup.active_model.title`); jangan menutup/mengganti model user tanpa izin.
3. `save_camera` → `info(region)` → `plan_view` Lt.1 & Lt.2 + `persp` → `materials(region)`.
4. Ruang + `bands` → **satu panggilan** `takeoff(region, rooms, bands, angle, wall_pids)` → dinding per ruang × tipe, eksterior per pita × arah, pasangan per pita, lantai/plafon, bukaan (`frame_xyz` = ukuran kusen, `leaves` = jumlah daun).
5. Catat detail kusen untuk spesifikasi: ukuran, jumlah daun, jenis bukaan, material kusen/daun, kaca, hardware yang terlihat di model (nama komponen/material, mis. "Glass Patch Chrome").
6. `restore`.

### 3. Pekerjaan → uraian AHS (`references/finishing-mapping.md`)
Cari padanan di tab AHS untuk setiap pekerjaan. Ada → tipe `ahs` dengan uraian persis. Tidak ada / tidak sesuai model → tipe `audit` + analisa (komponen boleh `AHS:<uraian>` agar harga ikut AHS live).

### 4. Input JSON (`references/input-format.md`)
`project`, `luasan`, `walls` + `wall_specs`, `openings` (kode tipe, jenis, ruang A > B, lantai, w, h, type, panels, spec lengkap), `audit` (analisa non-AHS + kusen `group: "kusen"`), `bab` mengikuti `urutan pekerjaan` dengan baris `ahs | audit | pending | sub | wall_plaster | wall_aci | wall_finish (uraian, only) | openingan | openings`. Contoh lengkap: `examples/ruko_bkl2_input.json`.
Cek offline dulu: `python3 build_rab.py input.json --ahs <ekspor AHS>` → harus tanpa error.

### 5. Tulis ke sheet (`references/sheet-format.md`)
1. Salin template dengan connector Drive `copy_file` (judul = nama proyek, folder = folder file proyek sebelumnya bila ada), lalu `share_file` ke email service account sebagai writer.
2. Cek tab AHS di salinan terbaca (IMPORTRANGE aktif).
3. `python3 build_rab.py input.json --push --creds <key> --spreadsheet <ID> --prepare template` (file baru) · `clone:"<tab>"` (area lain di file yang sama) · `none` (tulis ulang/revisi).

### 6. Verifikasi & laporan
- Ringkasan builder harus `error=0`, `harga0=0`.
- Laporkan: link file, total & subtotal per bab, luasan, daftar pekerjaan non-AHS (tab Audit A) dan analisa kusen (B), jumlah item AHS terpakai (C), jumlah baris pending (D), **asumsi**.

## Aturan isi (ringkas)
- Bab (tab `urutan pekerjaan`): I Persiapan · II Tanah, Galian & Urugan · III Struktur · IV Dinding, Plester & Acian (pasangan, plester per ruang, acian per ruang, openingan kusen) · V Kusen, Pintu & Jendela · VI Atap & Kanopi · VII Plumbing & Sanitari (PLUMBING, GWT, rainwater, SANITARI, PENGUJIAN) · VIII Listrik & Sistem Pendukung (LISTRIK, TATA UDARA, SISTEM PENDUKUNG, PLTS, PENGUJIAN) · IX Finishing Arsitektur (FINISHING DINDING, LANTAI, TANGGA DAN BORDES, PLAFON, RAILING, SECONDARY SKIN, WATERPROOFING) · X Luar & Lanskap · XI Kolam. Baca tab itu dari template setiap kali (bisa berubah).
- Ruang per baris dinding: `Dinding Interior <Ruang> Fin. <finishing>` / `Dinding Eksterior <zona> Fin. …`; pintu/jendela: `Ruang A > Ruang B`.
- Default template: pasangan PW11, plester PD1, aci AD1 (cat) / AD2 (ekspos).
- Openingan kusen: m1 keliling bukaan per lantai (analisa `OPK`).
- MEP yang tidak dimodelkan boleh estimasi; tulis "estimasi" di sub-judul.
- Luasan: tapak, total, tiap lantai (termasuk teras/balkon beratap; carport & area tanpa atap tidak), catatan rincian di A8.

## Jebakan
- Spec harus persis sama dengan uraian AHS (spasi, "Ø", kutip). Builder berhenti bila tidak cocok.
- Uraian AHS ganda → VLOOKUP ambil baris pertama (builder memberi peringatan).
- Item satuan `ls` yang dihitung per bulan (PP5) → volume = jumlah bulan, jelaskan di kolom Ruang.
- F1 Zona: dropdown ke tab 'Daftar Zona' yang tidak ikut di template → isi teks saja.
- Sheet 11 kolom; sel bantu di kolom A.
- Dinding yang menerus beberapa lantai: `takeoff`/`walls_sampled` (per pita z).
- Kaca tanpa material tidak terdeteksi `glazing` → cek leaf tipis di `info`/screenshot.
- Commit file ke komputer user dari staged path yang sama bisa mengirim versi lama → nama staged unik.
- Service account tidak bisa memiliki file baru → salin lewat connector, lalu share ke SA.
- Copy template bisa gagal permission di folder tim → salin ke root Drive user lalu beri tahu user.
- `npx skills add` hanya menyalin folder skill; plugin SketchUp terpasang saat `install_plugin` pertama kali dijalankan (atau `scripts/install_sketchup_plugin.sh` di macOS).
