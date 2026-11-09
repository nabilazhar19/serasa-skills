# Format & persiapan Google Sheet

## Template
- ID: `1zwpn8sGUDQK4_FUd86FiYBzSVwW9y-pygasOf73Kahg` ("Template RAB", milik tim.serasa.architect).
- Tab: `AHS` (A uraian, C satuan, D harga), `Serasa Template` (kerangka RAB), `IKK` (B zona, C indeks), `MASTER AHS` (B kode, C nama, G harga basis), plus tab contoh lain yang **dihapus** di file hasil.
- Locale spreadsheet **Indonesia**: rumus pakai `;` sebagai pemisah argumen dan `,` sebagai desimal (`*1,001`). Angka dikirim lewat API sebagai number biasa.

## Langkah persiapan (urutan penting)
1. `copy_file` template → judul = nama folder proyek. Jika error permission di folder template, salin ke `root` Drive user.
2. `duplicateSheet` `Serasa Template` → tab proyek (index 1); `addSheet` → `Analisa <kode>` (300 baris, 10 kolom).
3. Di tab proyek:
   - `unmergeCells` A10:K(akhir) — template punya merge di baris 10–11 (header), E97:F97, baris 327–328. Merge yang tertinggal akan "memakan" baris data.
   - `updateCells` A10:K(akhir) fields `userEnteredValue,userEnteredFormat` kosong (hapus isi contoh).
   - `insertDimension` ROWS index 2..8 (6 baris) → blok luasan di baris 3–8.
   - `cutPaste` E9:F11 → E3 (blok IKK kembali ke E1:F5; **koefisien tetap di F5**). Cek F3/F4 = INDEX/MATCH ke IKK dan F5 = `=F3/F4`.
   - `updateSheetProperties` rowCount ≥ baris total + 10.
4. Named range: `MAH` → `'MASTER AHS'!B1:G400`; `ANL` → `'Analisa <kode>'!A1:H300`.
5. `F1` = zona proyek, `F2` = basis harga.

## Tata letak hasil
- A1 "Rencana Anggaran Biaya", A2 judul proyek, A3:C8 luasan (C3 tanah, C4 total = jumlah lantai, C5.. tiap lantai sebagai rumus penjumlahan rincian, baris sisa = catatan kecil miring), E1:F5 Zona/Basis/IKK/Koefisien, A9 "PT. Serasa Rancang Indonesia", logo di A11:C12.
- Baris 16 header kolom; data mulai baris 17.
- Rumus universal (ditulis per baris oleh builder):
  - F: `=IF($E17="";"";IFERROR(VLOOKUP($E17;MAH;2;0);IFERROR(VLOOKUP($E17;ANL;2;0);"")))`
  - I: `=IF($E17="";"";IFERROR(VLOOKUP($E17;MAH;6;0)*1,001;IFERROR(VLOOKUP($F17;AHS!$A:$D;4;0);IFERROR(VLOOKUP($E17;ANL;8;0);0)))*$F$5)`
  - J: `=IF($H17="";"";$H17*$I17)`
  - K (baris terakhir tiap bab): `=SUM(Js:Je)`; baris Total: I = `=SUM(K17:K<total-1>)`.
- Override: F berisi teks untuk baris AHS (nama persis) & pintu ("Luas bukaan … m2"); I berisi rumus khusus pintu/jendela.
- Format: font Arial 9, wrap; H `#,##0.00`; I–K `"Rp"#,##0`; header abu (0.85); baris bab bold + krem (0.93,0.89,0.82); sub-judul bold italic; freeze 16 baris.

## Akhir
- Hapus tab selain: tab proyek, `Analisa <kode>`, `AHS`, `IKK`, `MASTER AHS`. Sembunyikan (`hidden: true`) keempat tab pendukung → hanya tab proyek yang terlihat.
- Verifikasi tidak ada `#N/A`, `#REF!`, harga 0 yang tidak disengaja.

## Jebakan yang sudah ditemui
- `repeatCell` dengan `fields` berisi koma di dalam kurung (`userEnteredFormat(textFormat,…)`) ditolak sebagian proxy API → pakai path bertitik: `userEnteredFormat.textFormat,userEnteredFormat.wrapStrategy`.
- `repeatCell` dengan `formulaValue` relatif otomatis menyesuaikan nomor baris (aman untuk rumus universal).
- Kode master dengan nama `#N/A` (PP2–PP6, E6, E10…) → Spec kosong; isi Spec manual.
- Kode duplikat di master (R22, E7, L8…) → VLOOKUP ambil baris pertama; cek harganya.
- Desimal di dalam rumus harus koma (`2,88*…`), bukan titik.
- Insert baris di atas data otomatis menggeser `$F$5`; selalu kembalikan blok IKK ke E1:F5 dengan cutPaste (referensi ikut pindah).
