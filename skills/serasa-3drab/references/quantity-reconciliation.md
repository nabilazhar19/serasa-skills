# Rekonsiliasi volume sebelum menulis RAB

## Register sumber lokal

Simpan angka mentah sebelum pembulatan: elemen/bidang induk, ruang, pita elevasi, lapisan, batas bukaan, luas/volume, tebal, metode dan status terukur/estimasi/pending. ID teknis hanya untuk penelusuran lokal. Satu bidang fisik punya satu identitas sumber; bidang itu boleh menerima beberapa lapisan berbeda, tetapi tidak dua kali lapisan yang sama.

## Pasangan, plester dan acian

1. Tetapkan pita lantai berdasarkan elevasi fisik, bukan nama layer saja. Pisahkan dinding, pita balkon, parapet, pengaku beton, pelat dan kanopi. Profil yang diplester harus memiliki induk pasangan/beton yang jelas; jangan otomatis menyebut semua profil sebagai bata.
2. Pasangan dihitung satu kali. Plester adalah muka terbuka yang benar-benar menerima plester: sisi dalam, luar, ujung, bawah/atas yang relevan. Hapus kontak dinding-dinding, muka tertutup pelat, rangkap komponen dan pertemuan T/L. Bukaan dikurangi sekali.
3. Bila pasangan memakai volume union ÷ tebal, hasilnya **luas ekuivalen**, tidak selalu sama dengan satu muka bersih. Simpan tebal model dan tebal material anggaran secara terpisah; jangan membagi memakai tebal AHS yang berbeda dari geometri.
4. Buat neraca per lantai: pasangan, plester muka utama, tambahan ujung/profil/reveal dan pengurang kontak/tertutup. Setiap selisih terhadap dua muka harus bisa ditelusuri; sampling 100 mm adalah pendekatan, bukan bukti presisi. Jika selisih tidak terjelaskan, periksa geometri eksak/union dan batas elevasi. Jangan meratakan selisih dengan mengubah angka agar rasio tepat dua.
5. Acian mengikuti kebutuhan finishing. Area keramik boleh perlu plester tanpa acian; jangan menambah acian atau coating di bawah keramik tanpa dasar sistem. Bidang belakang panel kayu dicatat sesuai lapisan yang benar-benar dibutuhkan. Panel tidak otomatis membuktikan ada pasangan baru atau perlu semua lapisan dasar.
6. Bukaan: ukuran lubang model, ukuran kusen dan daun dapat berbeda. Gunakan ukuran yang sesuai untuk pengurang pasangan dan keliling perapihan; jangan memaksa dimensi tipe yang dikonfirmasi menjadi ukuran lubang tanpa cek. Openingan tidak boleh menduplikasi reveal yang sudah dihitung di plester/acian.

## Finishing dan paket

- Acian ekspos + coating: jika acian sudah di Bab IV, Bab IX hanya coating; jangan paket aci+coating lagi.
- Panel/rangka: periksa apakah AHS mencakup rangka; jangan hitung bidang sama lagi sebagai secondary skin atau paket rangka tambahan.
- Tangga: ukur injakan/riser/bordes yang tampak setelah mengurangi tumpang tindih; jangan jumlah muka komponen tersembunyi. Tangga terputus tidak memberi dasar bentuk lanjutan; catat pending atau estimasi terpisah yang diizinkan.
- Pelat/plafon bertumpuk: identifikasi fungsi dan level, jangan dianggap lantai ketiga. Void tangga dan sekat/plafon WC memengaruhi bidang turunannya; propagasikan status estimasi.
- Teras: luas bangunan hanya memasukkan bagian beratap menurut dasar luasan yang dipakai, tetapi finishing teras fisik mencakup bagian terbuka juga. Bagi bidang tertutup/terbuka tanpa irisan dan pastikan jumlah sama dengan teras keseluruhan; harga hanya sekali.
- Waterproofing: pisahkan lantai dan upturn, kurangi pintu, bedakan WC, balkon, dak dan talang. Jangan menambah lapisan yang sudah termasuk paket lain.
- Sanitari/MEP yang belum dimodelkan: jumlah WC yang disetujui bukan ukuran sekat terverifikasi. Nyatakan dasar dimensi, rute dan titik secara singkat di Audit, tandai kuantitas turunannya, catat benturan dengan tangga jika belum selesai.

## Gerbang sebelum write

Bukan hanya `error=0`: cocokkan register sumber dengan baris RAB per lapisan, area lantai dan paket. Hilangnya item karena penamaan/filter sama pentingnya dengan hitung ganda. Simpan selisih mentah, pembulatan dan penjelasan singkat; jangan menyembunyikan ketidakpastian di angka total.
