# Metode take-off dari SKP

Semua fungsi ada di `scripts/skp_extract.rb` (modul `SerasaRAB`). Satuan mm / m².

## 0. Persiapan
- `SerasaRAB.save_camera` sebelum mengubah tampilan; `SerasaRAB.restore` di akhir (hapus section plane, kembalikan kamera). Jangan edit geometri.
- Model Serasa biasanya berisi beberapa massa (rumah, kost, ruko) + kontur + plan CAD. Batasi semua query dengan `region = [xmin, xmax, ymin, ymax]` sesuai area yang ditandai di denah.
- Abaikan layer kontur/plan/street/vegetasi/mobil; group raksasa (perimeter seluruh site) diperiksa per anak.

## 1. Mengenali ruang
1. `plan_view(cx, cy, tinggi_mm, cut_z)` + screenshot. Skala piksel: `px_per_m = tinggi_gambar_px / (tinggi_mm/1000)`; `x = cx + (px - W/2)/px_per_m`, `y = cy - (py - H/2)/px_per_m` (mm→m).
2. Potong di ±1200 mm di atas lantai Lt.1 dan ±1200 mm di atas lantai Lt.2. Ambil juga 2–3 perspektif (dengan potongan 2700 mm) untuk melihat material dinding.
3. `leaf_table(pids, angle)` → dinding = leaf dengan salah satu dimensi u/v ≈ 100–200 mm dan tinggi ≈ tinggi lantai. Garis as dinding membatasi ruang.
4. **Massa diputar**: jika dinding tidak sejajar sumbu, cari sudutnya (mis. arah sisi terpanjang dinding) → pakai `angle` sehingga ruang jadi persegi di koordinat (u,v).
5. Ruang = sisi dalam dinding (as ± ½ tebal). Tulis JSON:
   ```json
   [{"name":"L1 Living & Pantry","type":"uv","rect":[21785,26635,47750,55602],"z":[300,3350]},
    {"name":"L1 Guest Bedroom","type":"xy","poly":[[15781,45045],[21468,45045],[21290,47694],[15781,47694]],"z":[300,3350]}]
   ```
   Rentang z memisahkan Lt.1 dan Lt.2 (dan ruang dobel tinggi/tangga ke atap).
6. Fungsi ruang: dari label denah bila layout cocok; kalau SKP tanpa label/furnitur, beri nama deskriptif + fungsi paling mungkin (catat sebagai asumsi).

## 2. Dinding
`classify_walls(pids_dinding, rooms_json, angle)` mengembalikan:
- `rooms`: luas muka per (ruang, material) → volume **plester = aci = finishing** per ruang.
- `exterior`: muka yang tidak menghadap ruang → kelompokkan jadi zona eksterior (massa utama Lt.1, Lt.2 & gevel, parapet, dinding sisi carport, dst).
- `wall_one_side`: luas satu sisi tiap leaf dinding → **pasangan bata** (jumlahkan per massa/lantai).
Pilih `pids` = group dinding + group dinding atas/parapet + massa kecil (annex, storage). Pisahkan dinding batas/pagar (bab X).
Luas muka dari SketchUp sudah **bersih dari lubang** bila bukaan dipotong di model.

## 3. Lantai, plafon, deck, lanskap
- `horizontals(region, zmin, zmax, true)`: lantai per group/material/elevasi. Grup lantai solid terhitung atas+bawah bila memakai filter `false`; dengan `up=true` hanya muka atas.
- Plafon: material plafon pada elevasi ±2800/5750 (muka bawah) → `horizontals(..., false)`; plafon miring/kayu di bawah atap dari `slopes`.
- Kontur site: koral/rumput/grassblock per material (hati-hati muka kontur di bawah bangunan — kurangi tapak bangunan & deck).

## 4. Bukaan
- `glazing(region)` → leaf kaca: lebar (w), z (tinggi), luas kaca. Kelompokkan panel ke unit (sliding 3–4 panel = 1 unit). Pintu solid: komponen pintu (cari nama komponen, layer "DOOR WINDOW", atau leaf tipis ±40 mm setinggi 2400).
- Catat: ruang asal > ruang tujuan, lebar × tinggi, tipe (`swing|slide|fix|louvre|ahs_m2`), jumlah daun, lantai.

## 5. Atap & kanopi
- `slopes(pids_atap)` → luas penutup = muka **up** bermaterial atap pada kemiringan > 0; dinding berlapis penutup atap (fasad shingle) = kemiringan 90°.
- Lapisan bawah atap (kayu/plafon miring) = muka **dn** material kayu.
- Kanopi: group terpisah (kaca, spandek, UPVC, kisi kayu) — luas per material.

## 6. Elemen berulang
`count_components(region, 'regex')` untuk bata roster, lampu, sanitair, dsb. Luas roster ≈ panjang × tinggi bidang roster.

## 7. Luasan bangunan (untuk blok judul)
- Luas tanah = luas area yang ditandai (atau dari sertifikat bila diberikan user).
- Luas lantai kotor = sisi luar dinding tiap massa + **deck/teras/selasar yang beratap** (di bawah plafon, dak, kanopi, atau overstek lantai atas). Carport & area tanpa atap tidak dihitung (sebutkan opsi carport/50% untuk KLB di laporan).
