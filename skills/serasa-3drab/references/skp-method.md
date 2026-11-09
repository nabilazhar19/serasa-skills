# Metode take-off dari SKP (v2)

Fungsi ada di `scripts/skp_extract.rb` (modul `SerasaRAB`, VERSION 2.0). Satuan mm / m². Semua output JSON ringkas.

## 0. Muat script (hemat token)
1. `defined?(SerasaRAB) ? SerasaRAB::VERSION : 'belum'` — kalau `2.0`, langsung pakai.
2. Kalau belum / versi lama: `load "<path>/skp_extract.rb"` (satu baris). Path yang dipakai:
   folder Plugins SketchUp (dimuat otomatis) atau salinan di folder proyek (`_serasa_tools/skp_extract.rb`).
   Kalau file belum ada di komputer user: tulis file ke folder proyek yang terhubung (device_commit_files,
   **staged path dengan nama unik tiap versi** — commit ulang dari staged path yang sama bisa mengirim versi lama),
   lalu `load`. **Jangan menempel isi script ke eval_ruby.**
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
- `walls.rooms` `[ruang, tipe, m2]` → plester = aci = finishing per ruang (`walls[].parts` di input).
- `walls.exterior` `[pita, arah, tipe, m2]` → zona eksterior (gabungkan per fasad / pita).
- `walls.one_side` `[pid, pita, m2]` → pasangan bata per lantai (jumlahkan per pita).
- `floors` / `under` → muka horizontal atas / bawah per group-material-elevasi; muka kecil dirangkum `mat:"kecil"`
  (anak tangga, rangka). Lantai/plafon ruang biasanya lebih rapi dihitung dari dimensi ruang bersih.
- `openings` → unit bukaan kaca: `frame_xyz` = ukuran bbox kusen (lebar = sisi horizontal terpanjang, tinggi = z),
  `leaves` = jumlah leaf berkaca (indikatif jumlah daun). Kaca **tanpa material** tidak terdeteksi → cek leaf tipis
  (≤10 mm) di `info` / screenshot.

Sampling 100 mm per pita z: akurat untuk dinding yang menerus beberapa lantai (versi lama salah membagi lantai).

## 3. Tambahan bila perlu
- `slopes(pids_atap)` → atap miring per material & kemiringan (muka `up` = penutup; `dn` kayu = plafon miring).
- `count_components(region, 'regex')` → roster, lampu, sanitair.
- `leaf_table(pids, angle)` → detail leaf bila hasil takeoff janggal.

## 4. Luasan (blok judul)
- Luas tanah/tapak = area yang ditandai (atau sertifikat bila diberikan).
- Luas lantai kotor = sisi luar dinding tiap massa + deck/teras/balkon **beratap**. Carport & area tanpa atap tidak.

## Catatan interpretasi
- Muka `-` (tanpa material) = cat putih. Dinding tebal terhitung dua sisi (interior + eksterior) — memang begitu.
- Dua pelat bertumpuk (mis. +2,98 dan +3,98) → yang bawah biasanya plafon Lt.1, yang atas lantai Lt.2.
- Tangga yang terpotong di model: asumsikan menerus ke lantai atas, tulis asumsinya.
- Signage, furnitur, mobil, vegetasi: tidak dihitung.
