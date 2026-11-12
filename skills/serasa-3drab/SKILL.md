---
name: serasa-3drab
description: Buat, lanjutkan, atau koreksi RAB format PT Serasa Rancang Indonesia dari SketchUp dan denah ke Google Sheets, dengan rincian per ruang, harga AHS live, analisa bukaan, dan Audit volume. Gunakan untuk RAB Serasa atau hitung biaya dari SKP; revisi mempertahankan perubahan manual pengguna.
---

# Serasa 3D RAB

Hasil: tab RAB pada salinan Template Serasa atau tab tujuan yang diminta, disertai tab Audit. Ikuti batas area dan tahap yang diminta pengguna; “lanjut bab” berarti melanjutkan tab yang sama. Jangan memperluas ke massa lain atau utilitas bersama tanpa dasar pembagian.

## Aturan inti

- **Nama yang terbaca manusia.** Ruang memakai nama area dan kode tipe: `Teras > Toko 1`, `Dinding Interior Toko 2 Fin. Cat Putih`. PID, ID internal, nama `Group#…`, dan jalur hierarki teknis hanya di data kerja lokal, tidak di RAB atau Audit.
- **Bahasa ringkas.** RAB memuat pekerjaan, lokasi, bahan dan ukuran; dasar perkiraan atau keterbatasan singkat masuk Audit. Gunakan `Dinding di belakang panel kayu`, bukan `substrate asumsi`. Keterangan belakang panel tetap ada hanya pada bidang yang terkena panel. Hindari kata “asumsi” berulang pada Ruang/Spec.
- **Volume estimasi:** H berwarna **#FFD966**, angka sementara tetap ada untuk diisi manual pengguna. Berlaku juga pada turunan ukuran estimasi: pasangan, plester, acian, finishing, openingan, plafon, waterproofing dan MEP. Persetujuan memakai estimasi tidak membuatnya menjadi ukuran terverifikasi. Pilihan bahan perkiraan saja tidak mengubah status volume terukur.
- **Pending:** seluruh baris **#FFF2CC**, E=`-`, F=`PENDING - alasan singkat`, H/I/J kosong, dicatat di Audit D. Bedakan pekerjaan belum terukur dari volume estimasi yang sudah dianggarkan. Pekerjaan tak relevan dilewati, bukan dibuat pending.
- **Paket dihitung sekali.** Bila analisa/paket sudah memuat aksesori, sealant, rangka, klip atau upah, jangan tambah baris RAB untuk komponen itu, termasuk baris nol bertuliskan “TERMASUK”. Komponen tetap boleh dirinci di analisa Audit jika belum termasuk harga komponen lain.
- **Validasi angka bukan validasi geometri.** Rumus bebas error tidak membuktikan volume benar atau tanpa hitung ganda. Rekonsiliasi sumber bidang sebelum mengisi Sheet.

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

Sumber SKP dan perubahan live pengguna dipertahankan; takeoff hanya inspeksi. Baca [metode SKP](references/skp-method.md) sebelum ekstraksi. Gunakan `SerasaRAB` bila tersedia; simpan hasil JSON lokal, bukan output panjang di chat. Periksa denah dan tampilan model, batas elevasi, tebal, material, bukaan dan bidang yang tidak dimodelkan. Nama material render tidak membuktikan bahan konstruksi.

### 3. Rekonsiliasi kuantitas sebelum harga

Baca [rekonsiliasi volume](references/quantity-reconciliation.md) saat takeoff atau koreksi volume. Buat register lokal per elemen/bidang, ruang, lantai, lapisan dan sumber. Deduplicasi kontak, intersection, geometri bertumpuk dan muka tertutup. Periksa pasangan–plester–acian per lantai, termasuk pita balkon/parapet dan bidang belakang panel. Jangan memaksa plester = 2×pasangan tanpa menjelaskan selisih.

Ketidaklengkapan model: ambil ukuran yang didukung denah; jika perlu keputusan penting, tanyakan singkat sambil meneruskan pekerjaan independen. Estimasi yang diizinkan diberi penanda. Struktur, sambungan, benturan dan lanjutan tangga tanpa dasar tetap pending. Jangan memodelkan atau menyatakan konflik sudah selesai karena anggarannya ada.

### 4. Pilih AHS dan susun input

Baca AHS live sekali ke cache lokal, cari padanan lokal sesuai [pemetaan finishing](references/finishing-mapping.md). Default template adalah pilihan anggaran, bukan bukti bahan model. Paket terpasang dibandingkan cakupannya dengan komponen lain agar tidak ganda. Bila AHS tidak sesuai, buat analisa Audit; jangan memaksakan padanan.

Gunakan [format input](references/input-format.md). Builder mendukung `estimated: true`, `quantity_note`, `audit_notes`, serta `layer_parts` untuk membedakan area plester/acian/finish. Input lama tanpa flag tidak menandai estimasi otomatis: klasifikasikan sumber dulu. Jalankan offline sebelum push. Contoh `examples/ruko_bkl2_input.json` hanya contoh struktur; ukuran, harga, lingkup dan persetujuannya tidak berlaku otomatis untuk proyek baru.

### 5. Tulis sesuai mode

- **RAB baru:** salin seluruh template melalui connector Drive, beri akses service account bila diperlukan; jalankan `scripts/build_rab.py` untuk tab baru. Kredensial lokal di folder `_serasa_keys` bila tersedia, jangan tampilkan isinya.
- **Kelanjutan/koreksi:** ikuti [revisi bertahap](references/incremental-edit.md). Tambahkan bab sebelum Total atau patch rentang sasaran; salin format/validasi dari baris sejenis, lalu tulis formula sesuai baris baru. Pertahankan angka manual dan warna. **`--prepare none` menghapus dan membangun ulang data RAB/Audit; jangan gunakan untuk patch atau lanjut bab.** Rebuild hanya bila memang diperlukan dan perubahan live sudah direkonsiliasi ke input.

Audit A non-AHS, B analisa bukaan, C AHS terpakai dengan SUMIF live, D pending, E catatan ringkas dan sumber volume estimasi. Referensi baris harus mengikuti posisi akhir. Jangan memasukkan daftar ID model.

### 6. Verifikasi dan laporkan

Periksa perubahan saja ditambah dependennya: formula error/harga nol, subtotal dan total, cakupan paket, register bidang, estimasi H kuning, pending tanpa angka, serta referensi Audit. Pastikan angka/formula/warna bab sebelumnya tetap kecuali koreksi yang diminta. Baca balik rentang tulis dan cek tampilan; bila render tidak tersedia, periksa format dan ukuran baris melalui API, sebutkan batas pemeriksaannya jika relevan.

Laporkan link tab, total sementara, perubahan utama dan pending yang material. Jangan menyebut RAB final lengkap bila struktur/detail atau volume manual belum terisi. Berhenti pada tahap yang diminta.

## Hemat pemanggilan dan konteks

- Cache metadata, AHS dan urutan pekerjaan sekali per tahap. Baca ulang hanya yang dapat berubah dan memengaruhi write.
- Ukur elemen terkait dalam satu ekspor; proses geometri lokal. Chat menerima ringkasan masalah/total, bukan seluruh mesh, AHS, atau batch JSON.
- Simpan snapshot Sheet, register baris, sumber volume, alasan estimasi dan hasil verifikasi di output proyek agar kelanjutan tidak mengukur ulang tanpa alasan.
- Perubahan terbatas memakai patch kecil, bukan rebuild semua bab. Verifikasi sekali setelah perubahan, ulangi hanya untuk kegagalan atau koreksi baru.
- Baca references sesuai langkah; script ada di `scripts/`. Tidak perlu mengambil contoh proyek lain bila format dan sumber aktif sudah jelas.
