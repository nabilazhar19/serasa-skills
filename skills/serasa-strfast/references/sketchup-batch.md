# Batch geometri SketchUp

Gunakan adapter opsional setelah mengukur model dan menyusun koordinat. Adapter membuat grup solid dari manifest JSON. Gunakan tool pemodelan SketchUp yang tersedia atau gunakan daftar yang sama untuk pemodelan manual pada lingkungan yang tidak memiliki Ruby. Ukur dan identifikasi konflik terhadap arsitektur di luar adapter.

## Format manifest

```json
{
  "version": 1,
  "units": "mm",
  "project": "Contoh Rumah",
  "scope": "Skema rumah dan atap",
  "origin": [0, 0, 0],
  "elements": [
    {"id": "L1-K01", "system": "L1 · Kolom", "kind": "Kolom as A1", "basis": "skematik", "source": "Denah L1 as A1", "qto": "kandidat", "shape": "box", "min": [0, 0, 0], "max": [200, 300, 3300]},
    {"id": "AT-U01", "system": "Atap · Usuk", "kind": "Usuk bidang A", "basis": "skematik", "source": "Potongan atap A-A", "qto": "kandidat", "shape": "member", "start": [1000, 0, 3500], "end": [1000, 2500, 4600], "width": 40, "depth": 90},
    {"id": "PER-D01", "system": "Perimeter", "kind": "Dinding sisi 1", "basis": "terukur", "source": "Tampak perimeter sisi 1", "qto": "overlay", "shape": "prism", "loop": [[0, 1000, 0], [0, 4000, 0], [0, 4000, 2400], [0, 1000, 1600]], "offset": [120, 0, 0]}
  ]
}
```

Angka di atas hanya untuk menerangkan format. Isi koordinat `origin` bila memakai offset ke koordinat global; orientasi sumbu mengikuti model. Pakai `box` untuk balok/kolom sejajar sumbu, `member` untuk anggota horizontal atau miring dengan ujung berada pada tengah muka atas, dan `prism` untuk penampang khusus, bagian berotasi, atau dinding berprofil. Pada `member`, `width` tegak lurus garis proyeksi di denah, `depth` diukur vertikal, serta `cross_slope` opsional menentukan perubahan z per mm ke arah kiri relatif terhadap `start` → `end`. Pada `prism`, `loop` adalah poligon planar sederhana berurutan tanpa lubang dan `offset` adalah vektor ekstrusi. Pecah bagian berlubang menjadi potongan yang saling bertemu dengan ID berbeda.

Jaga `project`, `scope`, dan ID elemen stabil pada revisi. `basis` menyatakan dasar ukuran, dengan nilai `terukur` atau `skematik`. Simpan bagian yang masih `perlu data` di register koordinasi dan tambahkan ke manifest setelah dimensinya tersedia. `qto` bernilai `kandidat` untuk volume yang masih perlu rekonsiliasi atau `overlay` untuk geometri yang merepresentasikan bagian yang sudah dicatat di model lain.

## Jalankan dan verifikasi

1. **Uji daftar tanpa membuka SketchUp** melalui `ruby /path/to/strfast_sketchup.rb /path/to/manifest.json`. Perbaiki error ID, ukuran, satuan, bidang, atau duplikat persis sebelum membuat geometri. Potensi benturan, overlap sebagian, tumpuan, dan batas selubung tetap diperiksa pada model.
2. **Buat geometri di SketchUp** melalui Ruby Console atau jembatan yang menyediakan Ruby. Catat path aktif, buat snapshot, pastikan sudah keluar dari mode edit grup, dan gunakan path adapter serta manifest yang dapat dibaca oleh mesin SketchUp. Pakai path absolut sesuai lingkungan. Jalankan contoh berikut dengan path model yang sudah diverifikasi.

   ```ruby
   load '/path/to/serasa-strfast/scripts/strfast_sketchup.rb'
   result = SerasaStrFast.build('/path/to/manifest.json', expected_model_path: '/path/to/model.skp')
   puts result
   ```

3. **Revisi** memakai adapter hanya untuk penggantian seluruh lingkup yang sebelumnya dihasilkan adapter. Baca grup aktif serta `revision` pada kamus atribut `Serasa StrFast`. Tinjau dan gabungkan perubahan manual ke manifest, lalu tambahkan `replace_revision: 'nilai-revisi-yang-terbaca'` setelah menyimpan snapshot. Jika revisi parsial atau grup berasal dari cara lain, edit subgrup yang disepakati melalui tool model. Jika eksekusi sempat time out, periksa model dan ID elemen sebelum mengulangi.
4. **Cek hasil** dari jumlah elemen per sistem dan solid, lalu periksa potongan dan tampak arsitektur. Adapter tidak menyimpan file. Pastikan hasil disimpan ke tujuan yang diizinkan dan model dapat dibaca kembali bila alurnya memungkinkan.

Rujukan API untuk perbedaan perilaku antar versi. [Pembuatan geometri](https://ruby.sketchup.com/file.generating_geometry.html) · [Solid grup](https://ruby.sketchup.com/Sketchup/Group.html).
