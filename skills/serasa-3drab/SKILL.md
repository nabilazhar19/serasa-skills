---
name: serasa-3drab
description: Buat RAB (Rencana Anggaran Biaya) format PT Serasa Rancang Indonesia dari model SketchUp (.skp) dan denah (PDF/gambar) - rincian per ruang (plester, aci, finishing), harga MASTER AHS/AHS + koefisien IKK, analisa harga di tab Analisa, di salinan Template RAB Google Sheet atau tab baru di file proyek yang sudah ada. Pakai saat user minta "buat RAB", "hitung RAB dari skp", "RAB format Serasa", atau melampirkan skp + denah untuk dihitung biayanya.
---

# Serasa 3D RAB (serasa-3drab) — dari SKP + denah ke Google Sheet RAB

Output: tab RAB format Serasa (rincian per ruang) + analisa harga untuk item di luar MASTER AHS, di
- **file baru** = salinan Template RAB (proyek baru), atau
- **tab baru di file proyek yang sudah ada** (mis. area Ruko di file 0113_BENGKULU HOUSE).

- Template (WAJIB dipakai, jangan buat dari nol): https://docs.google.com/spreadsheets/d/1zwpn8sGUDQK4_FUd86FiYBzSVwW9y-pygasOf73Kahg (tab `Serasa Template`, `MASTER AHS`, `AHS`, `IKK`)
- Referensi gaya rincian per ruang: RAB RBL House https://docs.google.com/spreadsheets/d/1OFg-ooIzrkmzNZQf-UvXY1StVOcY0_GXjFseb8Lh60U (tab `RBL House`)
- Contoh hasil: file 0113_BENGKULU HOUSE (tab `BKU House` = proyek baru, tab `Ruko BKL` = tab baru di file yang ada).

## Hemat token — aturan utama
1. **Baca reference hanya saat masuk langkahnya.** Jangan baca semua dokumen di awal; `examples/bku_input.json` (40 KB) hanya bila butuh contoh bab panjang — pakai `examples/mini_input.json`.
2. **Script dipakai dari file, tidak ditulis/ditempel ulang.** Ruby: `load` path (lihat langkah 2). Python: salin `scripts/build_rab.py` ke workspace apa adanya.
3. **Data RAB tidak lewat chat.** Pakai `--push` (service account). Tanpa kredensial: kirim isi file output builder apa adanya (3 panggilan), tanpa mencetak baris ke chat.
4. **Verifikasi = satu sel cek**, bukan membaca ulang seluruh sheet atau MASTER AHS.
5. Screenshot secukupnya (2 plan + 1–2 perspektif), max_size ≤ 1200.

## Lokasi scripts & references (cek berurutan)
1. Folder skill ini (`scripts/`, `references/`, `examples/`).
2. (Claude) Project "Automasi gambar kerja": `serasa-3drab/scripts/{skp_extract.rb,build_rab.py}`, `serasa-3drab/references/*.md`, `serasa-3drab/examples/{mini_input,ruko_bkl_input,bku_input}.json` (baca dengan project_read saat dibutuhkan, tulis ke workspace).
3. Paket `serasa-3drab.zip` / repo `serasa-skills` dari user. Kalau tidak ada sama sekali, minta user melampirkannya.

## Alat
- SketchUp: MCP SketchUp (`eval_ruby`, `get_viewport_screenshot`) atau Ruby Console yang dijalankan user.
- Denah PDF: render ke PNG (≥150 dpi) dengan pymupdf / pdf tool.
- Google Sheets/Drive: service account (`--push`, paling hemat) atau connector.
- Python 3 untuk `build_rab.py`.

## Input dari user
1. Model **.skp** (desain final — kalau beda dengan denah, **SKP yang dipakai**), terbuka di SketchUp (MCP SketchUp) atau file.
2. **Denah** dengan area yang ditandai (mis. kotak merah) — hanya area itu yang dihitung.
3. Tujuan sheet: file baru, atau link file proyek + nama tab baru. Opsional: lokasi (IKK), batasan ("struktur tidak dihitung").

Hal yang tidak bisa diputuskan dari model → ambil asumsi paling masuk akal, tulis di kolom Ruang/Spec, laporkan di akhir. Jangan berhenti bertanya kecuali keputusannya mahal diulang.

## Alur kerja

### 1. Denah → area hitung
Lihat gambar, catat ruang, fungsi, dimensi pokok, batas area yang ditandai. Nama ruang dari denah bila layout cocok.

### 2. SKP → kuantitas (`references/skp-method.md`)
1. `defined?(SerasaRAB) ? SerasaRAB::VERSION : 'belum'`. Kalau bukan `2.0`: `load "<path>/skp_extract.rb"` dari folder Plugins SketchUp atau `<folder proyek>/_serasa_tools/`. Kalau file belum ada di komputer user, tulis ke folder proyek yang terhubung (staged path bernama unik per versi), lalu `load`. **Jangan tempel isi script.**
2. `SerasaRAB.save_camera` → `info(region)` (pid & layer per massa) → `plan_view(cx,cy,h,z)` Lt.1 & Lt.2 + `persp(...)` → `materials(region)` (ada tebakan finishing).
3. Massa diputar terhadap sumbu dunia → ambil sudut dinding utama (`leaf_table`) sebagai `angle`, ruang pakai rect `uv`.
   Definisikan ruang (rect/poly + rentang z) dan `bands` per lantai → **satu panggilan** `SerasaRAB.takeoff(region, rooms, bands, angle, wall_pids)` → dinding per ruang × tipe, eksterior per pita × arah, pasangan per pita, lantai/plafon, bukaan (ukuran kusen dari `frame_xyz`).
4. Tambahan seperlunya: `slopes` (atap miring), `count_components` (roster, lampu, sanitair).
5. `SerasaRAB.restore`. Jangan mengubah geometri.

Perhatian: muka `-` (tanpa material) = cat putih; dinding tebal terhitung dua sisi; pelat bertumpuk/grup lantai bisa terhitung atas+bawah; jangan hitung kontur/site, mobil, vegetasi, signage.

### 3. Material → kode (`references/finishing-mapping.md`)
Prioritas harga: **MASTER AHS → AHS (nama persis) → Analisa**. Default dinding: ekspos = PD2+AD2+W6 · putih = PD2+AD1+W1/W2 · terracotta = PD2+AD1+W76 · pola = PD2+W7. Kode bernama `#N/A` di master → isi `spec`.

### 4. Input JSON (`references/input-format.md`, contoh `examples/mini_input.json`)
`project`, `luasan`, `opening_codes`, `analisa`, `walls`, `openings`, `bab` I–XI. Di file proyek yang sudah ada, kode analisa pakai **prefix baru** (mis. `RKO-`).

### 5. Tulis ke sheet (`references/sheet-format.md`)
- Proyek baru: salin template (connector Drive `copy_file`, judul = nama folder proyek) → `--prepare template`.
- Tab baru di file yang ada: `--prepare clone:"<tab proyek lama>" --header-row <baris "Bab" di tab itu> --analisa-start auto`.
- Dengan service account: `python3 build_rab.py input.json --push --creds <key.json> --spreadsheet <ID> --prepare …` → script menyiapkan tab, menulis, dan mencetak ringkasan (error, harga 0, total, subtotal per bab).
- Tanpa kredensial: siapkan tab via connector (duplicateSheet + kosongkan), jalankan builder tanpa `--push` dengan `--sheet-id/--analisa-sheet-id`, kirim `analisa.json` → `values_AH.json` → `connector_batch.json` apa adanya, lalu `check_cell.json`.

### 6. Verifikasi & laporan
- Hasil cek harus `error=0`, `harga0=0` (kecuali baris struktur bertanda `-`).
- Mode template: hapus tab contoh (RBL House, Serasa Template, TOP Cost n Fee, RBL House Alternatif, Sheet14, HPP…, INTGR, Sheet4, dll); sisakan & sembunyikan `AHS`, `IKK`, `MASTER AHS`, tab Analisa.
- Laporkan: total & subtotal per bab, luasan, **asumsi** (nama ruang, material, item estimasi), dan **komponen yang belum dihitung**.

## Aturan format Serasa (ringkas)
- Kolom: Bab | Uraian Pekerjaan | Ruang / Area | Lantai | Kode Specs | Spec | Satuan | Volume | Harga Satuan | Total Harga | (K = subtotal bab).
- Bab: I Persiapan · II Tanah · III Struktur · IV Dinding, Plester & Acian · V Kusen, Pintu & Jendela · VI Atap & Kanopi · VII Plumbing & Sanitari · VIII Listrik · IX Finishing · X Luar & Lanskap · XI Kolam (bab yang tidak relevan dilewati).
- Per ruang: plester, aci, finishing dinding satu baris per (ruang × tipe), label `Dinding Interior <Ruang> Fin. <finishing>` / `Dinding Eksterior <zona> Fin. …`. Lantai & plafon per ruang.
- Pintu/jendela: satu baris per bukaan, `Ruang A > Ruang B / jenis, material, jumlah daun`, kolom Ruang = `LxT` cm. Hardware swing dikali jumlah daun.
- Openingan kusen: m1 keliling bukaan per lantai.
- Harga = basis × 1,001 × koefisien IKK (`$F$5`) untuk MASTER AHS; AHS & Analisa × `$F$5`.
- MEP yang tidak dimodelkan boleh estimasi; tulis "estimasi" di sub-judul.
- Blok luasan: tanah/tapak, total, tiap lantai (**termasuk deck/teras/balkon beratap**; carport & area tanpa atap tidak), catatan rincian.

## Jebakan yang sudah ditemui
- Template punya merge di baris 10–11, E97:F97, 327–328 → unmerge dulu (dikerjakan `--prepare template`).
- Sheet hanya 11 kolom: sel bantu harus di kolom A–K.
- `fields` bertanda kurung bisa ditolak → pakai path bertitik.
- Desimal di dalam rumus harus koma. Locale `;`.
- Dinding yang menerus beberapa lantai: pakai `takeoff`/`walls_sampled` (per pita z), bukan `classify_walls` lama.
- Kaca tanpa material tidak terdeteksi `glazing` → cek leaf tipis di `info`/screenshot.
- `plan_view` sudah menyalakan section cut; kalau potongan tetap tidak tampil, cek `rendering_options['DisplaySectionCuts']`.
- Commit file ke komputer user dari staged path yang sama bisa mengirim versi lama → pakai nama staged unik.
- Service account tidak bisa memiliki file baru di Drive → salin template lewat connector/manual, lalu share ke email SA.
- Copy template bisa gagal permission di folder tim → salin ke root Drive user lalu beri tahu user.
