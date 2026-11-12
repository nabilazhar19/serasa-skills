# Format & penulisan Google Sheet (Template RAB format Nov 2026)

## Template
- ID `1zwpn8sGUDQK4_FUd86FiYBzSVwW9y-pygasOf73Kahg` ("Template RAB"). Tab: `AHS`, `Serasa Template`. **Tidak ada lagi** `MASTER AHS`, `IKK`, named range MAH/ANL, koefisien F5.
- `AHS` = `IMPORTRANGE` dari "Rekap AHS" (A Uraian, B Kategori, C Satuan, D Harga, E Kode). Harga sudah final (tidak dikali koefisien di RAB). Salinan template langsung bisa membaca IMPORTRANGE (sudah dicek).
- `Serasa Template`: F1 = Zona Proyek (dropdown ke tab 'Daftar Zona' yang tidak ikut di template; diisi teks saja, tidak memengaruhi harga). A1 judul, A2 nama proyek, A4:C7 luasan (Tapak, Total, Lt.1, Lt.2), A8 catatan, A9 "PT. Serasa Rancang Indonesia", logo A10:C11, **header kolom baris 12**, data mulai **baris 13**, freeze 12 baris. Lebar kolom & font Calibri 9 dari template dipertahankan.
- Locale Indonesia: `;` dan desimal `,`.

## Aturan isi kolom
| Kolom | Baris AHS (semua bab kecuali kusen) | Baris kusen/pintu/jendela | Baris non-AHS (analisa) |
|---|---|---|---|
| B Uraian | judul singkat, hanya di baris pertama grup | "Pintu" / "Jendela" / "Pintu jendela" | judul singkat |
| C Ruang | ruang/area + finishing (`Dinding Interior Toko 1 Fin. …`) | `Ruang A > Ruang B` | ruang/area |
| E Kode Specs | `=VLOOKUP(F;AHS!A:E;5;FALSE)` | kode tipe buatan: P1, P2, J1, PJ1 … (tipe sama = kode sama) | kode analisa (mis. `AUD-01`, `OPK`) |
| F Spec | **uraian AHS persis**, dropdown plaintext (validasi `ONE_OF_RANGE =AHS!$A$2:$A$2159`, strict) | spesifikasi lengkap + ukuran (teks bebas) | uraian analisa (teks, tanpa dropdown) |
| G Satuan | `=VLOOKUP(F;AHS!A:D;3;FALSE)` | unit | satuan analisa |
| I Harga | `=VLOOKUP(F;AHS!A:D;4;FALSE)` | `='Audit'!H<baris analisa>` | `='Audit'!H<baris analisa>` |
| J | `=I*H` | `=I*H` | `=I*H` |
K = `=SUM(J..)` di baris terakhir tiap bab; baris "Total": I = `=SUM(K…)`.

## Bab & urutan pekerjaan (tab template `urutan pekerjaan`)
Urutan bab, sub-judul, dan nama pekerjaan (kolom B) diambil dari tab `urutan pekerjaan` di template — baca ulang tiap proyek (A..C, ±330 baris; simpan ke file lokal, jangan dibaca berulang di chat). Ringkasnya:
I Persiapan · II Tanah, Galian & Urugan · III Struktur (lantai kerja, lalu pondasi/sloof/kolom/balok/pelat lantai/tangga beton/dak beton/dinding beton masing-masing Bekisting, Besi Ulir, Besi Polos, Beton) · IV Dinding, Plester & Acian (pasangan, roster, partisi, plester, acian, openingan kusen, profil) · V Kusen, Pintu & Jendela · VI Atap & Kanopi (rangka, penutup, insulasi, nok & flashing, lisplank, talang, kanopi, skylight) · VII Plumbing & Sanitari (PLUMBING, GWT, RAINWATER HARVESTING, SANITARI, PENGUJIAN) · VIII Listrik & Sistem Pendukung (LISTRIK, TATA UDARA DAN VENTILASI, SISTEM PENDUKUNG, PLTS, PENGUJIAN) · IX Finishing Arsitektur (FINISHING DINDING, FINISHING LANTAI, FINISHING TANGGA DAN BORDES, PEKERJAAN PLAFON, RAILING DAN HANDRAIL, SECONDARY SKIN, WATERPROOFING BANGUNAN) · X Luar & Lanskap (pagar, gerbang, LANDSCAPE) · XI Kolam.
- Pekerjaan tidak relevan dilewati. Pekerjaan relevan tanpa data di SKP → baris pending (kuning `#FFF2CC`, Kode "-", Spec "PENDING - alasan", tanpa volume/harga) dan masuk tab Audit bagian D.
- Waterproofing (KM, balkon, dak/kanopi) masuk bab IX, bukan bab atap. Openingan kusen masuk bab IV.

## Tab "Audit" (dibuat builder)
- **A. Pekerjaan yang tidak ada di AHS** — kode, uraian, satuan, komponen (koef × harga; `AHS:<uraian>` = harga live dari tab AHS), harga satuan (kolom H), baris RAB pemakai. Ini daftar usulan tambahan untuk Rekap AHS.
- **B. Analisa kusen, pintu & jendela** — per kode tipe, komponen dari ukuran di SKP (kusen m1, kaca m², hardware, upah).
- **C. Item AHS yang terpakai** — kode, uraian, satuan, jumlah baris, harga, volume total & total harga (SUMIF live ke tab RAB).
- **D. Pekerjaan pending** — baris RAB, uraian, ruang, alasan.
Nama tab: `Audit` (kalau sudah ada karena tab RAB lain: `Audit <tab>`).

## Menulis
Service account (disarankan; jalankan di shell komputer user, key di `00 Serasa Architect/_serasa_keys/`):
```
python3 build_rab.py input.json --push --creds <key.json> --spreadsheet <ID> --prepare template      # file baru (salinan template)
python3 build_rab.py input.json --push --creds <key.json> --spreadsheet <ID> --prepare clone:"<tab>" # area lain di file yang sama
python3 build_rab.py input.json --push --creds <key.json> --spreadsheet <ID> --prepare none          # tulis ulang (revisi)
```
- `template`: ganti nama `Serasa Template` → nama tab proyek, unmerge & kosongkan baris ≥13 (isi contoh), isi F1, buat tab Audit, tulis.
- Builder membaca AHS live dan **berhenti** bila ada Spec yang tidak persis sama dengan uraian AHS (pakai tipe `audit` untuk pekerjaan yang memang tidak ada).
- Output: `error=… harga0=… total=…` + subtotal per bab + jumlah AHS terpakai/analisa. Jangan membaca ulang sheet.
- File baru: salin template lewat connector Drive (`copy_file`, judul = nama proyek), lalu share ke email service account sebagai Editor (`share_file`).
Tanpa kredensial: `--ahs <ekspor AHS>` → `out/connector_batch.json` (satu batchUpdate, ±650 KB untuk ±150 baris; mahal di chat — usahakan push).

## Jebakan
- Spec harus **persis** (termasuk spasi, "Ø", tanda kutip). Ambil teks dari tab AHS, jangan diketik ulang.
- Uraian AHS ganda → VLOOKUP ambil baris pertama (builder memberi peringatan).
- Satuan `ls` pada item per-bulan (mis. PP5 listrik kerja) → volume = jumlah bulan, tulis di kolom Ruang.
- Sheet 11 kolom: sel cek ditaruh di kolom A, 3 baris di bawah Total (dihapus lagi oleh builder).
- `fields` bertanda kurung bisa ditolak → path bertitik.
