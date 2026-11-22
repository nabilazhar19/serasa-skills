# Google Flow — langkah UI

Teruji 22 Nov 2026 (Claude in Chrome, Mac). Flow berjalan di Chrome, jadi langkahnya sama di Windows. UI Flow bisa berubah: jika tombol tidak ada, baca halaman (read_page / screenshot) dan cari padanannya, jangan menebak koordinat lama.

## Setup project
1. Buka `https://labs.google/fx/tools/flow` (pengguna sudah login Google).
2. New project → panel setting: **Image**, rasio **16:9** (atau sesuai sumber), model **Nano Banana** versi terbaru, **thinking High**, jumlah output **x1**.
3. Catat URL project (`flow.google.com/project/<id>`) ke `log.md`.

## Upload sumber
Semua sumber diunggah sekali di awal (Add media → Upload). Batas praktis 10 MB per file; export 4000 px JPG kualitas 0.95 biasanya 1–3 MB.

**Claude in Chrome** — tombol Upload membuka file picker sistem yang tidak bisa dikendalikan. Patch dulu lewat JS, lalu pakai `file_upload`:
```js
HTMLInputElement.prototype._click = HTMLInputElement.prototype.click;
HTMLInputElement.prototype.click = function(){ if(this.type!=='file') return this._click(); };
```
Klik Add media → Upload (input file sekarang ada di DOM tanpa membuka picker), lalu `file_upload` dengan path di container. File dari komputer pengguna (Mac/Windows) di-stage dulu (`device_stage_files`) ke `/mnt/user-data/uploads/...`.

**Browser bawaan Claude desktop / ChatGPT agent Chrome** — pakai dialog unggah biasa atau drag-drop bila tool upload tersedia; bila agent tidak bisa memilih file, minta pengguna drag-drop folder `sumber/` ke Flow sekali, lalu lanjutkan.

## Generate per scene
1. Tombol **+** (ingredients) di kotak prompt → cari nama file (= nama scene SKP) → klik hasilnya.
2. Tempel prompt dari `prompts.md` → Generate.
3. Lanjut scene berikutnya tanpa menunggu; Flow mengantre.
4. Setelah gambar muncul, buka detail view → catat id/hash dari URL ke `log.md`.

## Unduh 2K
Detail view → ikon Download → **2K Upscaled**. Upscale ±15 detik per gambar; tunggu sampai file muncul di folder Downloads (Mac `~/Downloads`, Windows `%USERPROFILE%\Downloads`; ukuran stabil, bukan `.crdownload`) sebelum gambar berikutnya. Lalu pindahkan + ganti nama ke `hasil/<Nama Scene>_render2K.jpg`.

Mencocokkan file unduhan ke scene: urutkan Downloads per waktu dan cocokkan dengan urutan unduh di `log.md`; jangan menebak dari nama file Flow.

## Kalau macet
- Kuota/limit Flow habis → berhenti, laporkan scene yang sudah selesai; jangan buat akun lain.
- Generate gagal "policy" → biasanya karena orang/teks di sumber; hapus dari export atau laporkan.
- Elemen UI tidak merespons 2–3 kali → berhenti dan tanya pengguna.
