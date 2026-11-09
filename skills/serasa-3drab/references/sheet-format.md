# Format & penulisan Google Sheet

## Template
- ID: `1zwpn8sGUDQK4_FUd86FiYBzSVwW9y-pygasOf73Kahg` ("Template RAB", milik tim.serasa.architect).
- Tab: `AHS` (A uraian, C satuan, D harga), `Serasa Template` (kerangka RAB), `IKK` (B zona, C indeks), `MASTER AHS` (B kode, C nama, G harga basis).
- Locale **Indonesia**: rumus pakai `;` dan desimal `,` (`*1,001`). Angka dikirim sebagai number biasa.

## Pilih mode
| Situasi | `--prepare` | `--header-row` | Analisa |
|---|---|---|---|
| Proyek baru (file = salinan template) | `template` | 16 (default) | tab baru `Analisa <kode>` mulai baris 1 |
| Area baru di file proyek yang sudah ada (mis. Ruko di file Bengkulu) | `clone:"<tab proyek lama>"` | sama dengan tab sumber (cek baris yang berisi "Bab"; BKU House = 15) | ditambah di tab analisa yang dipakai named range `ANL`, `--analisa-start auto`, **prefix kode baru** (mis. `RKO-`) agar tidak bentrok |
| Tab sudah disiapkan manual | `none` | sesuai tab | sesuai |

Mode clone memakai ulang semua yang sudah ada di tab sumber: blok IKK E1:F5 (zona & koefisien), logo, named range MAH/ANL, tab tersembunyi. Pastikan analisa tidak melewati baris 300 (batas ANL).

## Menulis
### A. Service account (disarankan — data tidak lewat chat)
Persiapan sekali per user/komputer:
1. Google Cloud Console → buat project → aktifkan **Google Sheets API** → buat **Service Account** → Keys → Add key → JSON.
2. Simpan key di komputer user (mis. `~/.serasa/sa-key.json`); jangan diunggah ke chat/Project.
3. Share file RAB (atau folder proyek di Drive) ke email service account sebagai **Editor**.
4. `pip install google-api-python-client google-auth` di environment yang punya akses internet ke googleapis.com
   (shell komputer user bila jaringan cloud dibatasi).

Jalankan di **shell komputer user** (Cowork: `device_bash`, Linux VM): library harus di-install di shell itu juga
(`python3 -m pip install --user google-api-python-client google-auth`; install di macOS biasa tidak terbaca VM).
Key di luar folder proyek, mis. `00 Serasa Architect/_serasa_keys/` — minta akses folder itu (read) bila belum
terhubung; path di shell: `$HOME/mnt/_serasa_keys/<file>.json`. Jangan pernah mencetak isi key; cukup cek `client_email`.
Sudah diuji (9 Nov 2026, mode clone, ±7 detik): hasil identik dengan penulisan via connector.

Salin template tetap lewat connector Drive (`copy_file`) atau manual — service account tidak punya kuota Drive untuk memiliki file. Lalu:
```
python3 build_rab.py input.json --push --creds ~/.serasa/sa-key.json --spreadsheet <ID> --prepare template
python3 build_rab.py input.json --push --creds ... --spreadsheet <ID> --prepare clone:"BKU House" --header-row 15 --analisa-start auto
```
Script mencetak: tab & baris analisa, `error=… harga0=… total=…`, subtotal per bab. Itu sudah cukup untuk laporan — **jangan membaca ulang sheet**.

### B. Connector Sheets (tanpa kredensial)
Siapkan tab dulu (duplicateSheet + kosongkan, lihat langkah template di bawah), lalu:
```
python3 build_rab.py input.json --out out --header-row <hr> --analisa-start <n> --sheet-id <id tab RAB> --analisa-sheet-id <id tab analisa>
```
Kirim **isi file apa adanya** (jangan menyusun ulang/mencetak baris ke chat):
1. `out/analisa.json` → `update_formulas` ke `'<tab analisa>'!<range>`
2. `out/values_AH.json` → `update_values` ke `'<tab>'!<range>`
3. `out/connector_batch.json` → satu `update_spreadsheet` (header A1:C8, header kolom, rumus universal F/I/J via repeatCell, override, format, rowCount)
4. `out/check_cell.json` → tulis rumus ke sel itu, baca **satu sel** (`error|harga0|total|subtotal;…`), lalu kosongkan.

### Langkah siapkan tab manual (mode template, connector)
1. `duplicateSheet` `Serasa Template` → tab proyek; `addSheet` `Analisa <kode>` (300×10).
2. `unmergeCells` A10:K(akhir); `updateCells` A10:K(akhir) fields `userEnteredValue,userEnteredFormat`.
3. `insertDimension` ROWS 2..8 (6 baris) → blok luasan di baris 3–8; `cutPaste` E9:F11 → E3 (koefisien tetap di **F5**).
4. Named range `MAH` = `'MASTER AHS'!B1:G400`, `ANL` = `'Analisa <kode>'!A1:H300`. `F1` zona, `F2` basis.
Mode clone (connector): `duplicateSheet` tab lama → `updateCells` A<hr>:K(akhir) & A1:C8 (values) kosong.

## Tata letak hasil
- A1 "Rencana Anggaran Biaya", A2 judul, A3:C8 luasan, E1:F5 Zona/Basis/IKK/Koefisien, A9 "PT. Serasa Rancang Indonesia", logo A10:C11.
- Header kolom di `hr`, data mulai `hr+1`. Rumus universal:
  - F: `=IF($E17="";"";IFERROR(VLOOKUP($E17;MAH;2;0);IFERROR(VLOOKUP($E17;ANL;2;0);"")))`
  - I: `=IF($E17="";"";IFERROR(VLOOKUP($E17;MAH;6;0)*1,001;IFERROR(VLOOKUP($F17;AHS!$A:$D;4;0);IFERROR(VLOOKUP($E17;ANL;8;0);0)))*$F$5)`
  - J: `=IF($H17="";"";$H17*$I17)`; K (baris terakhir tiap bab) `=SUM(J..)`; Total: I = `=SUM(K..)`.
- Override: F teks untuk AHS/pintu/kode `#N/A`; I rumus khusus pintu/jendela.

## Akhir (mode template)
Hapus tab contoh; sisakan & sembunyikan `AHS`, `IKK`, `MASTER AHS`, `Analisa <kode>`.

## Jebakan
- Sheet hanya 11 kolom (A–K): sel bantu di luar K gagal → sel cek ditaruh di kolom A, 3 baris di bawah Total.
- `fields` bertanda kurung (`userEnteredFormat(a,b)`) bisa ditolak → pakai `userEnteredFormat.a,userEnteredFormat.b`.
- Desimal di dalam rumus harus koma. Kode master bernama `#N/A` (PP2–PP6, E6, E10…) → isi `spec` manual.
- Kode duplikat di master (R22, E7, L8…) → VLOOKUP ambil baris pertama.
- Insert baris di atas data menggeser `$F$5`; selalu kembalikan blok IKK ke E1:F5 (cutPaste).
