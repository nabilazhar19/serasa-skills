---
name: serasa-rab
description: Buat RAB (Rencana Anggaran Biaya) format PT Serasa Rancang Indonesia dari model SketchUp (.skp) dan gambar denah (PDF/gambar). Rincian per ruang (plester, aci, finishing per ruang), harga dari MASTER AHS / AHS + koefisien IKK, analisa harga baru di tab Analisa. Pakai saat user minta "buat RAB", "hitung RAB dari skp", "RAB format Serasa", atau melampirkan skp + denah untuk dihitung biayanya.
---

# Serasa RAB — dari SKP + denah ke Google Sheet RAB

Output akhir: **satu file Google Sheet baru** (salinan template Serasa) berisi tab RAB proyek dengan rincian per ruang, plus tab Analisa untuk item yang tidak ada di MASTER AHS. Contoh hasil jadi: proyek 0113_BENGKULU HOUSE (lihat `examples/bku_input.json`).

- Template (WAJIB dipakai, jangan buat dari nol): https://docs.google.com/spreadsheets/d/1zwpn8sGUDQK4_FUd86FiYBzSVwW9y-pygasOf73Kahg  (tab penting: `Serasa Template`, `MASTER AHS`, `AHS`, `IKK`)
- Referensi gaya rincian per ruang: RAB RBL House https://docs.google.com/spreadsheets/d/1OFg-ooIzrkmzNZQf-UvXY1StVOcY0_GXjFseb8Lh60U (tab `RBL House`)

## Input dari user
1. File **.skp** (desain final — kalau berbeda dengan PDF, **SKP yang dipakai**).
2. **Denah** (PDF/gambar) — untuk nama ruang, dimensi, dan **area yang ditandai** (mis. lingkaran merah). Hanya area yang ditandai yang dihitung.
3. Opsional: lokasi proyek (untuk IKK), batasan (mis. "struktur tidak dihitung"), nama file output (default = nama folder proyek).

Kalau ada hal yang tidak bisa diputuskan dari model (fungsi ruang tanpa label, material ambigu), ambil asumsi paling masuk akal, **tulis asumsinya di kolom Ruang/Spec**, dan laporkan di akhir. Jangan berhenti untuk bertanya kecuali keputusan itu mahal untuk diulang.

## Alat yang dibutuhkan (agent apa pun)
- Akses baca model SketchUp: MCP SketchUp (`eval_ruby`, `get_viewport_screenshot`) **atau** Ruby Console SketchUp yang dijalankan user. Script: `scripts/skp_extract.rb`.
- Pembaca PDF (pymupdf / pdf tool) untuk denah.
- Akses Google Sheets/Drive (connector, MCP, atau service account + `scripts/build_rab.py --push`).
- Python 3 untuk `scripts/build_rab.py`.

## Alur kerja

### 1. Baca denah & tentukan area hitung
- Render PDF ke PNG (≥150 dpi), lihat halaman denah. Catat ruang, level lantai (±0.00 dst), dimensi pokok, dan batas area yang ditandai.
- Bandingkan dengan SKP: jika layout beda, ikuti SKP; nama ruang boleh diambil dari denah bila masih cocok.

### 2. Analisis SKP (lihat `references/skp-method.md`)
1. Load `scripts/skp_extract.rb` (kirim isinya lewat `eval_ruby`, atau `load` di Ruby Console). Panggil `SerasaRAB.save_camera` dulu.
2. `SerasaRAB.info([xmin,xmax,ymin,ymax])` → daftar entitas di area. Tentukan region (mm) dari area yang ditandai.
3. Screenshot tampak atas dengan potongan: `SerasaRAB.plan_view(cx, cy, tinggi_mm, 1200)` (Lt.1) dan cut di Lt.2 (mis. 4600), plus 2–3 view perspektif. Petakan ruang.
4. Cek massa yang diputar: ambil sudut dinding utama (lihat `leaf_table`), pakai sebagai `angle`.
5. Definisikan ruang (JSON: `uv` rect atau `xy` polygon + rentang z per lantai) → `SerasaRAB.classify_walls(pids, rooms_json, angle)` → luas muka dinding **per ruang per material** (interior), muka eksterior per massa/arah, dan luas 1 sisi tiap dinding (= volume pasangan).
6. `SerasaRAB.horizontals(region, zmin, zmax, true)` → lantai/deck/perkerasan; `(..., false)` → plafon. `SerasaRAB.glazing(region)` → pintu/jendela kaca. `SerasaRAB.slopes(pids_atap)` → luas atap per material & kemiringan. `count_components` untuk elemen berulang (bata roster, lampu, sanitair).
7. `SerasaRAB.restore` — kembalikan kamera & hapus section plane. Jangan mengubah geometri model.

Perhatian: muka `"-"` (tanpa material) biasanya = cat putih; luas grup "tebal" dua sisi; lantai grup sering terhitung atas+bawah (bagi 2); hindari menghitung kontur/site, mobil, vegetasi.

### 3. Pemetaan material → kode MASTER AHS
Lihat `references/finishing-mapping.md`. Prioritas harga: **MASTER AHS → AHS (nama persis) → tab Analisa** (buat analisa singkat bila tidak ada; contoh: openingan kusen, pintu/jendela).

### 4. Susun input JSON
Format lengkap: `references/input-format.md`; contoh nyata: `examples/bku_input.json`. Isi:
- `project` (judul, nama file, nama tab, zona IKK, basis), `luasan` (tanah, luas tiap lantai termasuk deck/teras beratap),
- `walls` (per ruang & per zona eksterior: luas per tipe finishing `ekspos|putih|terracotta|pola`),
- `openings` (pintu/jendela: uraian "Ruang A > Ruang B / jenis", lebar, tinggi, tipe, jumlah daun),
- `analisa` (item analisa harga), `bab` I–XI dengan baris `master|ahs|analisa|note|sub` + blok otomatis `wall_plaster_aci`, `openings`, `wall_finish`.

Jalankan: `python3 scripts/build_rab.py input.json --out out` → cek `out/summary.txt`.

### 5. Siapkan spreadsheet (lihat `references/sheet-format.md`)
1. Salin template → judul = nama folder proyek (jika folder template tidak bisa ditulis, salin ke root Drive user).
2. Duplikat tab `Serasa Template` → nama tab proyek; tambah tab `Analisa <kode>`.
3. Di tab proyek: **unmerge** baris ≥10, kosongkan isi & format A10:K akhir, **sisipkan 6 baris di bawah baris 2** (baris 3–8 untuk luasan), lalu **cutPaste blok IKK E9:F11 → E3:F5** supaya koefisien tetap di `F5`. Tambah baris sampai cukup (≥ baris total + 5).
4. Buat named range: `MAH` = `'MASTER AHS'!B1:G400`, `ANL` = `'Analisa <kode>'!A1:H300`.
5. Set `F1` = zona proyek (nama persis di tab IKK, mis. "Kota Bengkulu"), `F2` = basis (default "Kota Bogor").

### 6. Tulis ke sheet
Urutan: `analisa_rows.json` → `header.json` (A1:C8) → `colheader.json` (baris 16) → `rab_values.json` (A17:H…) → `rab_formulas_F.json` → `rab_formulas_IJ.json` → `rab_overrides.json` (menimpa sel tertentu) → `format_requests.json` (batchUpdate; isi `--sheet-id`/`--analisa-sheet-id`).
Semua rumus memakai locale Indonesia (`;` dan desimal `,`). Dengan service account: `--push --creds key.json --spreadsheet <id>`.

### 7. Rapikan & verifikasi
- Hapus tab yang tidak dipakai (RBL House, Serasa Template, TOP Cost n Fee, RBL House Alternatif, Sheet14, HPP…, INTGR, Sheet4, dll). **Sisakan & sembunyikan**: `AHS`, `IKK`, `MASTER AHS`, `Analisa <kode>`. Tab proyek satu-satunya yang terlihat.
- Baca ulang sheet: tidak ada `#N/A`/`#REF!`, Spec terisi, harga ≠ 0 (kecuali struktur), subtotal tiap bab di kolom K, total di kolom I baris "Total".
- Laporkan ke user: link file, total & subtotal per bab, luasan, **daftar asumsi** (nama ruang, material, item estimasi), dan **komponen desain yang belum dihitung**.

## Aturan format Serasa (ringkas)
- Kolom: Bab | Uraian Pekerjaan | Ruang / Area | Lantai | Kode Specs | Spec | Satuan | Volume | Harga Satuan | Total Harga | (K = subtotal bab).
- Bab: I Persiapan · II Tanah/Galian/Urugan · III Struktur · IV Dinding, Plester & Acian · V Kusen, Pintu & Jendela · VI Atap & Kanopi · VII Plumbing & Sanitari · VIII Listrik · IX Finishing (dinding, lantai, tangga, plafon, railing, waterproofing) · X Luar & Lanskap · XI Kolam.
- **Per ruang**: plester, aci, dan finishing dinding satu baris per (ruang × tipe finishing), label `Dinding Interior <Ruang> Fin. <finishing>` / `Dinding Eksterior <zona> Fin. ...`. Lantai & plafon juga per ruang.
- Pintu/jendela: satu baris per bukaan, uraian `Ruang A > Ruang B / jenis, material, jumlah panel, bukaan`, kolom Ruang = ukuran `LxT` cm.
- Openingan kusen dihitung m1 keliling bukaan per lantai (analisa sponneng plester+aci).
- Harga satuan = harga basis × 1,001 × koefisien IKK (`$F$5`) untuk MASTER AHS; AHS & Analisa × `$F$5`.
- Item yang tidak dimodelkan (MEP) boleh diisi estimasi, tulis "estimasi" di uraian/sub-judul.
- Blok luasan di bawah judul: Luas Tanah, Luas Bangunan Total, Luas tiap lantai (**termasuk deck/teras/selasar yang beratap**; carport & area tanpa atap tidak), plus catatan rincian.
