# Cakupan: semua objek dihitung (cara arsitek)

Tujuan: setiap objek di model masuk RAB atau dikecualikan dengan alasan. Objek yang terlewat (fasad, bench beton, ramp,
atap dua material, roster, railing, kanopi, planter, dll.) membuat total RAB **di bawah nilai sebenarnya**. Cara ukur
boleh luwes sesuai jenis objek, tetapi setiap angka harus bisa ditelusuri ke objeknya, dan hasil akhir tetap format Serasa.

## Alur
1. **Inventaris** — di SketchUp: `SerasaRAB.inventory(region, "<proyek>/_serasa_tools/work/inventory.json")`.
   Tiap objek: luas per material × orientasi (atas/bawah/vertikal/miring), volume bila solid, panjang tepi keras, ukuran,
   layer/tag, flag `str`, isi bertingkat per definisi (`parts`, dengan `count` untuk komponen kembar). Objek yang biasanya
   dilewati (kontur, vegetasi, mobil) tetap tercatat dengan `skip`.
2. **Klasifikasi** — agen membaca inventaris seperti arsitek (nama, layer, material, bentuk, ukuran, screenshot, denah) dan
   menentukan pekerjaan tiap objek/part. Satu objek boleh jadi beberapa pekerjaan (badan beton + pelapis kayu + railing);
   satu luas hanya dialokasikan sekali. Keputusan disimpan di `_serasa_tools/register.json` (lihat bawah).
3. **Volume** — dinding, lantai, plafon per ruang: `SerasaRAB.takeoff` per bangunan (sampel 100 mm, `wall_pids`, ruang &
   pita per bangunan). Objek lain: dari inventaris dengan dasar yang paling masuk akal (tabel di bawah).
   Tag muka viewport (sampel 400 mm) **bukan** alat ukur volume; hanya untuk menunjuk sumber dan melacak perubahan.
4. **Harga** — AHS bila tepat; selain itu analisa rinci [analisa](analisa.md), kelas spek menengah (bawah).
5. **Cek** — viewport: kartu **Cakupan model** (target 100% atau sisa objek dikecualikan dengan alasan; mode "Cakupan RAB"
   menampilkan objek yang belum masuk RAB berwarna merah) dan kartu **Rp/m² ekuivalen** (rentang wajar). Laporkan keduanya.

## Dasar ukur per jenis objek
| objek | dasar | catatan |
|---|---|---|
| dinding, finishing per ruang | `takeoff` (R/E per ruang, pita) | plester + aci + finishing dari struktur `walls` |
| pasangan bata/AAC | luas satu sisi per pita (`one_side`) | bukan volume solid (dinding SketchUp jarang solid) |
| lantai / plafon | `takeoff` (F/C per ruang) | |
| atap | luas miring **per material** (`faces[...].miring`) + rangka dari luas proyeksi | atap 2 material = 2 baris penutup |
| kanopi, skylight | luas per material + rangka | |
| fasad / secondary skin (strip, kisi, panel) | luas bidang tampak (proyeksi) atau panjang profil (`edges_m`, `parts.count × panjang`) | + rangka + finishing (cat/powder coat) |
| roster | jumlah modul (`parts.count`) atau luas bidang | + adukan, upah |
| bench / planter / elemen beton | volume (solid) atau luas × tebal; bekisting = luas muka; pelapis per material | |
| ramp | luas atas (grating/lantai) + rangka (m1/kg) + railing (m1) | |
| railing / handrail / list | panjang (m1) | |
| kusen / pintu / jendela | unit + analisa bukaan | lihat analisa.md |
| sanitair, lampu, perangkat | jumlah komponen (`parts.count`) | |
| struktur (kolom, balok, pelat, pondasi) | **hanya bila pengguna menyatakan model struktur ada** (biasanya tag `STR`): volume beton per elemen, besi = rasio kg/m³ wajar (tandai estimasi), bekisting = luas muka | tanpa model struktur → pending |
| kontur / tapak | luas tapak (persiapan, pembersihan) | bukan dikecualikan bila dipakai pekerjaan persiapan |

Yang boleh dikecualikan hanya yang jelas bukan pekerjaan konstruksi (vegetasi, mobil, orang, furnitur lepas, objek
konteks di luar lingkup) atau sudah termasuk paket lain (mis. engsel di dalam komponen pintu) — selalu dengan alasan.

## register.json
```json
{"objects": {
  "23068344": {"status": "rab", "work": "Fasad strip besi hollow 40x40 + cat duco", "rows": ["Bab IX baris fasad Kost"]},
  "1645170":  {"status": "rab", "work": "Atap rumah: shingle bitumen 156 m² + polikarbonat 21 m²"},
  "19045935": {"status": "exclude", "reason": "mobil (objek konteks)"}}}
```
Objek yang sudah dirujuk baris RAB (sumber id / tag muka) otomatis terhitung "rab"; register dipakai untuk keputusan yang
tidak terlihat dari sumber baris dan untuk pengecualian. Viewport: klik objek merah → "Kecualikan" (wajib alasan) atau
tulis catatan untuk agen agar pekerjaannya ditambahkan.

## Kelas spek & harga
- Spek **mengikuti desain** (material yang terlihat di model/render, gambar, catatan pengguna), kelas **menengah**. Jangan
  memilih spek termurah atau merek kelas bawah untuk mengejar angka; bila ragu antara dua kelas, pilih yang sesuai desain dan
  tulis alternatifnya di `note`.
- Harga pasar wajar dari supplier/distributor resmi; bukan harga promo/terendah marketplace.

## Kewajaran total (acuan proyek Serasa)
- Total biaya langsung **dengan struktur**: **Rp5,5–7 jt per m² luas ekuivalen**. Tanpa struktur (struktur pending) rentang
  dikurangi porsi struktur ±26% → ±Rp4,1–5,2 jt/m².
- Acuan: RAB Royal Blossom House (full spec, HPP Rp1.005.273.650) — luas ekuivalen 149,4 m² → **Rp6,73 jt/m²**.
- Luas ekuivalen (koefisien Serasa, sama dengan RBL): bangunan induk ×1 · teras ×0,5 · void/dak ×0,5 · carport beratap ×0,3 ·
  carport tanpa atap ×0,1 · planter ×0,1. Tulis di input `luasan.ekuivalen` (m²) dan rinciannya di `luasan.note`.
- Porsi bab RBL (pembanding kasar, rumah 2–3 lantai full spec): persiapan 5% · struktur 26% · dinding (pasangan+plester+aci) 11% ·
  kusen 11% · atap 8% · plumbing & sanitair 10% · listrik 8% · finishing (dinding+lantai+plafon) 15% · lain-lain 3% · kolam 3%.
- Di bawah rentang → periksa cakupan (objek merah), bab yang porsinya jauh di bawah acuan, dan spek yang terlalu murah,
  **sebelum** melapor. Di atas rentang → periksa hitung ganda dan spek yang melebihi desain.
- Atur di viewport.json: `"benchmark": {"min": 5500000, "max": 7000000, "struktur": true|false}`
  (`tools.py init --struktur ya|tidak`).
