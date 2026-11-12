# Metode take-off dari SKP (v2)

Fungsi ada di `scripts/skp_extract.rb` (modul `SerasaRAB`, VERSION 2.1). Satuan mm / m². Semua output JSON ringkas.

## 0. Muat script (hemat token)
1. `defined?(SerasaRAB) ? SerasaRAB::VERSION : 'belum'` — kalau `2.1`+, langsung pakai (plugin sudah terpasang).
2. Kalau belum / versi lama: `load "<folder skill>/scripts/skp_extract.rb"; SerasaRAB.install_plugin`.
   `install_plugin` menyalin file ke folder Plugins SketchUp (`Sketchup.find_support_file('Plugins')`, Mac & Windows)
   sebagai `serasa_skp_extract.rb` → termuat otomatis di sesi berikutnya. `npx skills add` tidak memasang plugin;
   langkah ini yang memasangnya, sekali per komputer (atau `scripts/install_sketchup_plugin.sh` di macOS).
   Agen cloud (folder skill tidak ada di komputer user): tulis file ke folder proyek yang terhubung
   (`_serasa_tools/skp_extract.rb`, device_commit_files dengan **staged path bernama unik tiap versi**), lalu
   `load` + `install_plugin`. **Jangan menempel isi script ke eval_ruby.**
3. `SerasaRAB.save_camera` sebelum mengubah tampilan; `SerasaRAB.restore` di akhir. Jangan edit geometri.

## 1. Kenali area & ruang (±4 panggilan)
1. `SerasaRAB.info([xmin,xmax,ymin,ymax])` → root di region (pid, nama, layer, bbox). Nama layer biasanya sudah
   memisahkan massa (mis. `A. RUKO FLOOR 1`, `A. RUKO WALL 1`) — cepat untuk menentukan region & pid dinding.
2. Screenshot (max_size 900–1200, `restore_view: false`):
   - `plan_view(cx, cy, tinggi_mm, z_potong)` — potongan ±1200 di atas lantai Lt.1 & Lt.2 (section cut otomatis tampil).
   - `persp([ex,ey,ez],[tx,ty,tz])` — 1–2 perspektif untuk material fasad.
   Skala: `px_per_m = tinggi_px / (tinggi_mm/1000)`; `x = cx + (px - W/2)/px_per_m`, `y = cy - (py - H/2)/px_per_m`.
3. Ruang = sisi dalam dinding (dari bbox `info`, as ± ½ tebal). Massa diputar → `angle` + rect `uv`.
4. `materials(region)` → material + `guess` (ekspos / putih / terracotta / kayu / kaca / lain). Pakai guess, koreksi
   seperlunya dari screenshot.

## 2. Satu panggilan take-off
```ruby
rooms = [{name:'L1 Toko 1', type:'uv', rect:[56748,62598,40110,43960], z:[500,3980]}, ...].to_json
bands = [["Lt1",0,3980],["Lt2",3980,6600],["Parapet",6600,99999]]   # elevasi absolut (mm)
SerasaRAB.takeoff(region, rooms, bands, angle, wall_pids)
```
`wall_pids` = pid group dinding (+ fascia/parapet) dari `info`. Kalau nil → semua root di region (lebih berisik:
ikut menghitung rangka secondary skin, ledge, dsb).
Hasil (±8 KB):
- `walls.rooms` `[ruang, tipe, m2]` → kandidat luas per ruang (`walls[].parts`); rekonsiliasi kontak, bukaan dan kebutuhan tiap lapisan sebelum digunakan. Plester, acian dan finishing tidak selalu sama luas.
- `walls.exterior` `[pita, arah, tipe, m2]` → zona eksterior (gabungkan per fasad / pita).
- `walls.one_side` `[pid, pita, m2]` → pasangan bata per lantai (jumlahkan per pita).
- `floors` / `under` → muka horizontal atas / bawah per group-material-elevasi; muka kecil dirangkum `mat:"kecil"`
  (anak tangga, rangka). Lantai/plafon ruang biasanya lebih rapi dihitung dari dimensi ruang bersih.
- `openings` → unit bukaan kaca: `frame_xyz` = ukuran bbox kusen (lebar = sisi horizontal terpanjang, tinggi = z),
  `leaves` = jumlah leaf berkaca (indikatif jumlah daun). Kaca **tanpa material** tidak terdeteksi → cek leaf tipis
  (≤10 mm) di `info` / screenshot.

Sampling 100 mm per pita z membantu membagi dinding menerus, tetapi melewatkan detail kecil/pertemuan. Periksa selisih memakai geometri eksak bila perlu; baca [rekonsiliasi volume](quantity-reconciliation.md).

## 3. Tambahan bila perlu
- `slopes(pids_atap)` → atap miring per material & kemiringan (muka `up` = penutup; `dn` kayu = plafon miring).
- `count_components(region, 'regex')` → roster, lampu, sanitair.
- `leaf_table(pids, angle)` → detail leaf bila hasil takeoff janggal.

## 4. Luasan (blok judul)
- Luas tanah/tapak = area yang ditandai (atau sertifikat bila diberikan).
- Luas lantai kotor = sisi luar dinding tiap massa + deck/teras/balkon **beratap**. Carport & area tanpa atap tidak.

## Catatan interpretasi
- Muka `-` tidak membuktikan cat putih atau bahan tertentu. Gunakan konteks/denah; pilihan anggaran yang belum pasti dicatat singkat di Audit. Plester dua sisi hanya untuk muka terbuka yang memang diplester.
- Dua pelat bertumpuk (mis. +2,98 dan +3,98) → yang bawah biasanya plafon Lt.1, yang atas lantai Lt.2.
- Tangga terpotong: hitung bagian yang dapat diukur; lanjutan pending kecuali estimasi terpisah sudah diizinkan. Jangan mengarang bentuk lanjutan atau mengabaikan konflik sekat/void.
- Mobil dan furnitur dekoratif bukan pekerjaan konstruksi. Signage/vegetasi hanya dihitung bila termasuk lingkup yang diminta; jangan mengambil lanskap bersama di luar batas area.
