---
name: serasa-3drab
description: Buat, lanjutkan, atau koreksi RAB format PT Serasa Rancang Indonesia dari SketchUp dan denah ke Google Sheets, dengan rincian per ruang, harga AHS live, analisa bukaan, dan Audit volume. Gunakan untuk RAB Serasa atau hitung biaya dari SKP; revisi mempertahankan perubahan manual pengguna.
---

# Serasa 3D RAB

Hasil: tab RAB pada salinan Template Serasa atau tab tujuan yang diminta, disertai tab Audit, **dan Viewport RAB lokal** (`http://localhost:8765`: model 3D + tabel RAB, tiap baris menunjuk sumber volumenya, koreksi & Push dari halaman) yang tampil sejak awal sampai akhir. Ikuti batas area dan tahap yang diminta pengguna; “lanjut bab” berarti melanjutkan tab yang sama. Jangan memperluas ke massa lain atau utilitas bersama tanpa dasar pembagian.

## Aturan keras (semua agen: Claude, Codex, dll.)

1. **Jangan mengubah file skill**: `viewport/` (web, core, server, tools), `scripts/build_rab.py`, `scripts/skp_extract.rb`, `scripts/setup.py`, termasuk salinan terpasang di folder `SerasaRAB` dan Plugins SketchUp. Fungsi kurang atau bug → selesaikan pekerjaan dengan alat yang ada, lalu laporkan di akhir sebagai usulan perbaikan skill. Jangan menambal. `T check` harus `kunci versi resmi: OK`; bila tidak, jalankan `scripts/setup.py` untuk mengembalikan.
2. **Take-off hanya lewat `SerasaRAB`** (`takeoff`, `slopes`, `count_components`, `glazing`, `watch_export` + `measures`). Jangan menulis script ekstraksi/hitung geometri sendiri, jangan mengekspor geometri mentah, jangan membuat venv atau memasang library di luar `setup.py`.
3. **File kerja hanya di `<proyek>/_serasa_tools/work/`**, ditimpa (bukan versi-versian). Tidak membuat folder `output` atau salinan bertanggal. Hasil yang dipakai viewport: `_serasa_tools/<nama>_input.json`, `<nama>_model3d.json`, `viewport.json`.
4. **Ekspor 3D hanya area yang dihitung** (`region`), ukuran khusus (volume, atap, roster, keliling) hanya untuk objek yang dipakai baris RAB lewat `measures` di `serasa_watch.json`.
5. **Sheet hanya berubah lewat Push** (`build_rab.py --prepare patch`), kecuali pengguna meminta lain. Koreksi pengguna di viewport dihormati: baris koreksi manual tidak ditimpa.
6. **Analisa non-AHS rinci** sesuai [analisa](references/analisa.md): komponen per bagian dengan rumus ukuran, hardware per daun, sumber + tanggal harga.

## Aturan inti

- **Nama yang terbaca manusia.** Ruang memakai nama area dan kode tipe: `Teras > Toko 1`, `Dinding Interior Toko 2 Fin. Cat Putih`. PID, ID internal, nama `Group#…`, dan jalur hierarki teknis hanya di data kerja lokal, tidak di RAB atau Audit.
- **Bahasa ringkas.** RAB memuat pekerjaan, lokasi, bahan dan ukuran; dasar perkiraan atau keterbatasan singkat masuk Audit. Gunakan `Dinding di belakang panel kayu`, bukan `substrate asumsi`. Keterangan belakang panel tetap ada hanya pada bidang yang terkena panel. Hindari kata “asumsi” berulang pada Ruang/Spec.
- **Volume estimasi:** H berwarna **#FFD966**, angka sementara tetap ada untuk diisi manual pengguna. Berlaku juga pada turunan ukuran estimasi: pasangan, plester, acian, finishing, openingan, plafon, waterproofing dan MEP. Persetujuan memakai estimasi tidak membuatnya menjadi ukuran terverifikasi. Pilihan bahan perkiraan saja tidak mengubah status volume terukur.
- **Pending:** seluruh baris **#FFF2CC**, E=`-`, F=`PENDING - alasan singkat`, H/I/J kosong, dicatat di Audit D. Bedakan pekerjaan belum terukur dari volume estimasi yang sudah dianggarkan. Pekerjaan tak relevan dilewati, bukan dibuat pending.
- **Paket dihitung sekali.** Bila analisa/paket sudah memuat aksesori, sealant, rangka, klip atau upah, jangan tambah baris RAB untuk komponen itu, termasuk baris nol bertuliskan “TERMASUK”. Komponen tetap boleh dirinci di analisa Audit jika belum termasuk harga komponen lain.
- **Validasi angka bukan validasi geometri.** Rumus bebas error tidak membuktikan volume benar atau tanpa hitung ganda. Rekonsiliasi sumber bidang sebelum mengisi Sheet.

## Persiapan & Viewport RAB (berlaku untuk Claude, Codex, atau agen lain; Windows & Mac)

**Sekali per komputer:** di SketchUp `defined?(SerasaRAB) ? SerasaRAB::VERSION : 'belum'`. Bila belum atau < 2.5: `load "<skill>/scripts/skp_extract.rb"; SerasaRAB.install_plugin`, yang menjalankan `scripts/setup.py` dan memasang plugin ke semua versi SketchUp, viewport ke folder bersama, serta library Python. Tanpa akses SketchUp: `python3 scripts/setup.py` (Windows `py -3 scripts\setup.py`; tanpa Python: `setup.bat`/`setup.command`). Agen di cloud: salin folder skill ke folder proyek pengguna yang terhubung, lalu `load`/`install_plugin` dari sana. **Jangan menempel isi script.**

**Siklus viewport** — perintah lengkap di [viewport](references/viewport.md); `T` = `viewport/tools.py` di folder bersama:
1. Begitu folder proyek & nama input diketahui: `T init --project DIR --input <nama>_input.json --title …` lalu `T open --project DIR`. Viewport terbuka di browser pengguna dan menunggu data.
2. Tiap langkah alur kerja di bawah: `T status --project DIR --message "<langkah>" --step n --steps 6`. Satu baris, tanpa ID.
3. Setelah take-off: `SerasaRAB.watch_export(region, "<DIR>/_serasa_tools/<nama>_model3d.json", rooms, bands, angle, {measures: {...}})` + `T init --model3d …`; model 3D muncul. Setelah itu tiap Save SKP: hanya objek yang berubah diekspor ulang (beberapa detik, SketchUp tetap bisa dipakai) → volume, harga, total, Riwayat dan angka Push di viewport ikut berubah. Menu Extensions › Serasa RAB › Ekspor penuh bila perlu.
4. Input yang ditulis langsung tampil (tanpa restart). Setelah push: `T init` dengan sheet_url/gid/spreadsheet_id/creds/ahs_source, `T bind`, lalu `T status --stage selesai`. Sebutkan `http://localhost:8765` di laporan.
5. Koreksi pengguna: viewport mengurus edit/undo/Tarik dari Sheet/Push (`--prepare patch`). "Kerjakan catatan" → `T notes` → ubah input → `T note-done --id N`.

**Kunci versi resmi:** tampilan dan kode viewport, builder dan plugin dikunci `LOCK.json` (aturan keras 1). Perubahan hanya oleh pengembang skill di repo, lalu `T lock --version <baru>`.

## Sumber dan format

Template wajib: https://docs.google.com/spreadsheets/d/1zwpn8sGUDQK4_FUd86FiYBzSVwW9y-pygasOf73Kahg
- `AHS`: A uraian, B kategori, C satuan, D harga final, E kode. Tidak ada MASTER AHS/IKK/koefisien tambahan.
- `Serasa Template`: 11 kolom; header baris 12; data mulai 13. Pertahankan format, identitas perusahaan, logo dan validasi.
- `urutan pekerjaan`: baca live sekali per tahap kerja, simpan lokal; pakai judul bab, subjudul dan Uraian persis sesuai urutan. Lewati yang tidak relevan, misalnya kolam pada lingkup tanpa kolam.

Semua baris AHS: F = uraian AHS persis, dropdown `=AHS!$A$2:$A$2159`; E/G/I = VLOOKUP dari F, J=H×I. K subtotal bab dan I baris Total mengikuti template. Jangan mengetik kode/harga AHS manual. Harga non-AHS dan bukaan merujuk analisa Audit. Kode P/J/PJ sama hanya untuk tipe dengan ukuran dan spesifikasi identik. Lihat [format Sheet](references/sheet-format.md) saat menulis.

## Alur kerja

### 1. Kenali pekerjaan baru atau kelanjutan

Baca denah/batas merah, model aktif, tab tujuan dan tahap yang sudah selesai. Untuk kelanjutan, baca **Sheet live sebelum input lama**: harga, pilihan bahan, volume, formula dan warna mungkin diubah pengguna. Simpan snapshot dan daftar baris lokal. Jangan mulai ulang atau memindahkan tab tanpa diminta.

### 2. Ukur melalui SketchUp MCP

Gunakan skill `sketchup-mcp-workflow` bila tersedia: verifikasi versi bridge dan path model aktif. Jika model berbeda, minta pengguna mengaktifkan model yang benar sambil mengerjakan sumber lain yang independen. Jangan mengukur model lain.

Sumber SKP dan perubahan live pengguna dipertahankan; takeoff hanya inspeksi. Baca [metode SKP](references/skp-method.md) sebelum ekstraksi. Gunakan `SerasaRAB` (v2.5+); simpan hasil JSON lokal, bukan output panjang di chat. Periksa denah dan tampilan model, batas elevasi, tebal, material, bukaan dan bidang yang tidak dimodelkan. Nama material render tidak membuktikan bahan konstruksi.

### 3. Rekonsiliasi kuantitas sebelum harga

Baca [rekonsiliasi volume](references/quantity-reconciliation.md) saat takeoff atau koreksi volume. Buat register lokal per elemen/bidang, ruang, lantai, lapisan dan sumber. Deduplicasi kontak, intersection, geometri bertumpuk dan muka tertutup. Periksa pasangan–plester–acian per lantai, termasuk pita balkon/parapet dan bidang belakang panel. Jangan memaksa plester = 2×pasangan tanpa menjelaskan selisih.

Ketidaklengkapan model: ambil ukuran yang didukung denah; jika perlu keputusan penting, tanyakan singkat sambil meneruskan pekerjaan independen. Estimasi yang diizinkan diberi penanda. Struktur, sambungan, benturan dan lanjutan tangga tanpa dasar tetap pending. Jangan memodelkan atau menyatakan konflik sudah selesai karena anggarannya ada.

### 4. Pilih AHS dan susun input

Baca AHS live sekali ke cache lokal, cari padanan lokal sesuai [pemetaan finishing](references/finishing-mapping.md). Default template adalah pilihan anggaran, bukan bukti bahan model. Paket terpasang dibandingkan cakupannya dengan komponen lain agar tidak ganda. Bila AHS tidak sesuai, buat analisa Audit; jangan memaksakan padanan.

Gunakan [format input](references/input-format.md). Builder mendukung `estimated: true`, `quantity_note`, `audit_notes`, serta `layer_parts` untuk membedakan area plester/acian/finish. Input lama tanpa flag tidak menandai estimasi otomatis: klasifikasikan sumber dulu. Tulis input ke `<folder proyek>/_serasa_tools/<nama>_input.json` (sumber yang sama dibaca viewport), dengan `src` per bidang bila ada (asal angka untuk panel Sumber). Jalankan offline sebelum push. Contoh `examples/ruko_bkl2_input.json` hanya contoh struktur; ukuran, harga, lingkup dan persetujuannya tidak berlaku otomatis untuk proyek baru.

### 5. Tulis sesuai mode

- **RAB baru:** salin seluruh template melalui connector Drive, beri akses service account bila diperlukan; jalankan `scripts/build_rab.py` untuk tab baru. Kredensial lokal di folder `_serasa_keys` bila tersedia, jangan tampilkan isinya.
- **Kelanjutan/koreksi:** ikuti [revisi bertahap](references/incremental-edit.md). Tambahkan bab sebelum Total atau patch rentang sasaran; salin format/validasi dari baris sejenis, lalu tulis formula sesuai baris baru. Pertahankan angka manual dan warna. Koreksi angka/spec tanpa ubah struktur: `build_rab.py … --push --prepare patch` (hanya sel berubah; exit 3 = struktur berubah, perlu rebuild). **`--prepare none` menghapus dan membangun ulang data RAB/Audit; jangan gunakan untuk patch atau lanjut bab.** Rebuild hanya bila memang diperlukan dan perubahan live sudah direkonsiliasi ke input.

Audit A non-AHS, B analisa bukaan (rinci, [analisa](references/analisa.md)), C AHS terpakai dengan SUMIF live, D pending, E catatan ringkas dan sumber volume estimasi. Referensi baris harus mengikuti posisi akhir. Jangan memasukkan daftar ID model.

### 6. Verifikasi dan laporkan

Periksa perubahan saja ditambah dependennya: formula error/harga nol, subtotal dan total, cakupan paket, register bidang, estimasi H kuning, pending tanpa angka, serta referensi Audit. Pastikan angka/formula/warna bab sebelumnya tetap kecuali koreksi yang diminta. Baca balik rentang tulis dan cek tampilan; bila render tidak tersedia, periksa format dan ukuran baris melalui API, sebutkan batas pemeriksaannya jika relevan.

Laporkan link tab, link viewport, total sementara, perubahan utama dan pending yang material. Jangan menyebut RAB final lengkap bila struktur/detail atau volume manual belum terisi. Berhenti pada tahap yang diminta.

## Hemat pemanggilan dan konteks

- Cache metadata, AHS dan urutan pekerjaan sekali per tahap. Baca ulang hanya yang dapat berubah dan memengaruhi write.
- Ukur elemen terkait dalam satu ekspor; proses geometri lokal. Chat menerima ringkasan masalah/total, bukan seluruh mesh, AHS, atau batch JSON.
- Simpan snapshot Sheet, register baris, sumber volume, alasan estimasi dan hasil verifikasi di `_serasa_tools/work/` (ringkas, ditimpa) agar kelanjutan tidak mengukur ulang tanpa alasan.
- Perubahan terbatas memakai patch kecil, bukan rebuild semua bab. Verifikasi sekali setelah perubahan, ulangi hanya untuk kegagalan atau koreksi baru.
- Baca references sesuai langkah; script ada di `scripts/`. Tidak perlu mengambil contoh proyek lain bila format dan sumber aktif sudah jelas.
