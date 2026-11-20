# Pemeriksaan koordinasi struktur

| Area | Geometri yang diperiksa | Penanganan |
| --- | --- | --- |
| Kolom dan balok | Kedua muka dinding, tebal finishing, perpindahan as, kepala dan kaki kolom, bukaan sampai level atas | Pakai inti dinding atau tumpuan yang dapat ditelusuri. Sisakan toleransi yang sesuai dasar gambar. Jika ketentuan desain mengekspos beton, cek muka terhadap detail yang memang diekspos. |
| Bentang dan kantilever | Titik tumpu, panjang as-ke-as, panjang bebas dari muka, zona transfer, pelat dan muka bawah | Tandai balok yang berhenti tanpa tumpuan, kolom putus dan balok transfer. Sesuaikan pemisahan volume dengan konvensi QTO. |
| Atap | Selubung per bidang, nok/jurai, bukaan dan chamfer, profil yang benar-benar bersinggungan, jalur ke elemen utama | Iris mengikuti tiap kemiringan dan batas bukaan. Cek beda level di area pertemuan. Usuk/reng/gording dapat dimodelkan sesuai jenis sistem dan keberadaannya. Sisakan konflik jika posisi tumpuan atau sistem atap belum diberikan. |
| Dinding perimeter | Batas tapak yang diketahui, perubahan elevasi, profil atas dan bawah, level tanah di kedua sisi, bukaan | Potong profil sesuai desain. Jika dinding menahan tanah atau beban khusus, beri status perlu data struktur/geoteknik dan hindari menyamakan kebutuhan dengan dinding pagar biasa. |
| Pagar dan gerbang | Pilar, ring/pengikat, bidang roster, ruang kendaraan dan pedestrian, arah, rel atau sapuan daun | Koordinasikan rangka dengan kondisi terbuka dan tertutup sejauh data tersedia. Letakkan pengikat bawah tanpa menabrak ambang atau utilitas. Hitung rangka atau paket gerbang sekali. |
| Revisi | Grup sasaran, modul bersama, entitas luar lingkup, selisih daftar sebelum dan sesudah | Edit hanya grup yang ditargetkan. Pada komponen bersama, periksa semua instans sebelum mengubah definisi atau buat definisi mandiri untuk revisi setempat. |

## Lulus cek geometri

1. **Cakupan** — Cek tiap lantai dan sistem termasuk lingkup, bukaan utama, serta titik tumpuan. Daftar elemen yang belum dapat ditetapkan memiliki alasan dan lokasi.
2. **Dimensi** — Cocokkan ujung elemen, ukuran, dan elevasi dengan sumber atau catatan asumsi. Untuk model miring atau berputar, periksa di koordinat proyek dan ruang lokal elemen.
3. **Selubung** — Lihat potongan melintang dan memanjang pada lokasi konflik. Bandingkan vertex atau bidang yang relevan dengan muka arsitektur. Periksa tepi atap, tonjolan satu ujung balok, dan pita tipis di muka finishing.
4. **Keterhubungan** — Uji pasangan elemen pada muka kontak. Bedakan pertemuan yang disengaja, gap, tumpang tindih yang butuh pemotongan, dan komponen yang hanya tampak tersambung dari satu sudut. Periksa dukungan sampai tumpuan yang diketahui.
5. **Integritas** — Cocokkan jumlah dan ID dengan daftar, cek solid tertutup yang bervolume positif, dan tinjau potensi duplikasi lintas sistem. Catat overlap yang disengaja serta pemilik volume jika ada QTO.
6. **Akhir** — Periksa model masih aktif pada file yang diminta, kembalikan tampilan sementara, pastikan hasil bisa disimpan/dibaca dan laporkan cek yang benar-benar dijalankan.
