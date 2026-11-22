---
name: serasa-renderflow
description: Render fotorealistik scene SketchUp di Google Flow (Nano Banana) dengan prompt "blueprint" Serasa, lalu rapikan hasil 2K ke folder render proyek. Gunakan saat diminta render di Flow, render scene SKP, atau photorealize export SketchUp. Jalan di Claude (Claude in Chrome / browser bawaan) dan ChatGPT (agent Chrome), di Mac maupun Windows.
---

# Serasa RenderFlow

Hasil: satu folder render rapi berisi gambar sumber, render 2K per scene, prompt yang dipakai, dan log QC. Render harus **memfoto-realkan model apa adanya**: geometri, kamera, material, dan warna tidak boleh berubah.

## 0. Tanya dulu (satu pertanyaan, sekali)

Tanyakan sumber gambar, kecuali pengguna sudah menyebutnya:

1. **Folder export SKP yang sudah ada** → minta path folder; pakai semua `.jpg/.png` di sana, atau scene yang disebut.
2. **Export sendiri dari SKP** → minta model/scene (tanpa pilihan = semua scene di model). Ikuti [export-skp](references/export-skp.md).
3. **Upload gambar langsung** ke chat → pakai file yang diunggah.

Sekalian tanyakan (pakai default bila tidak dijawab): scene mana, catatan material/warna kritis (mis. "handle biru klien", "HPL Sunshine Yellow"), waktu cahaya (default: ikuti sumber).

## 1. Siapkan folder kerja

Nama sesi `<YYMMDD>_<label>` (label = nama proyek/scene singkat). Sesi berikutnya di hari yang sama: `_2`. **Nama scene = nama scene di SKP, persis** (spasi & huruf besar dipertahankan); hanya karakter terlarang Windows `\ / : * ? " < > |` diganti `-`. Nama yang sama dipakai di `prompts.md`, `log.md`, dan pencarian ingredient di Flow. Sumber dari upload/folder lama: pakai nama file tanpa ekstensi. Struktur tetap:

```
render/<YYMMDD>_<label>/          satu subfolder per sesi
  sumber/        <Nama Scene>.jpg       (nama = nama scene di SKP, mis. "KOM LIV.jpg")
  hasil/         <Nama Scene>_render2K.jpg  (versi ulang: _render2K_v2.jpg)
  prompts.md     satu bagian "## <SCENE>" per scene, prompt final yang dipakai
  log.md         tabel scene | id Flow | status | catatan QC
```

- **Folder proyek terhubung** (Claude: connected folder / device bridge; ChatGPT: folder yang bisa diakses) → buat langsung di `<proyek>/render/<YYMMDD>_<label>/`. Jika sumber dari export, export langsung ke `sumber/`.
- **Tidak terhubung** → buat folder yang sama di workspace, kirim hasil sebagai file/zip di akhir, dan sebutkan bahwa hasil bisa dipindah ke `<proyek>/render/` begitu folder proyek tersambung.
- Unduhan Flow masuk ke folder Downloads (Mac `~/Downloads`, Windows `%USERPROFILE%\Downloads`): **pindahkan** (bukan salin) ke `hasil/` dan ganti nama, supaya Downloads tidak menyisakan duplikat.

## 2. Tulis prompt per scene

Ikuti [Panduan Prompt Gambar Serasa](references/prompt-gambar.md) untuk tiap gambar Base:
1. **Analisis** geometry, camera, material, lighting, context, karakter adegan (tandai material kritis).
2. **Preservation lock** dengan prioritas geometry → camera → material → context → realism.
3. **Satu prompt per Base**, bahasa Inggris, 150–300 kata, struktur 8 bagian urut, larangan disatukan dalam narasi.

Hanya sebut yang terlihat di Base. Simpan analisis + prompt ke `prompts.md` sebelum membuka Flow.

## 3. Render di Google Flow

Ikuti [flow-ui](references/flow-ui.md). Ringkas:
1. Project baru → Image, 16:9 (atau sesuai rasio sumber), Nano Banana (versi terbaru yang tersedia), thinking High, x1.
2. Upload semua sumber sekaligus.
3. Per scene: ingredient = gambar sumber → tempel prompt → generate. Boleh antre beberapa scene; jangan menunggu satu selesai.
4. Catat id/hash gambar Flow ke `log.md` begitu muncul.

## 4. QC sebelum unduh

Bandingkan render dengan sumber (sisi-sisi) untuk tiap scene:
- kamera/crop sama, tidak ada objek hilang/bertambah, bukaan & kusen di posisi sama;
- warna kritis cocok (kusen hitam tetap hitam, warna klien tidak bergeser — mis. biru jadi navy);
- tidak ada teks/label/dimensi/watermark ("mm", tag, angka).

Gagal → perbaiki penyebabnya, bukan hanya generate ulang: teks di render = sumber masih memuat label (ulang export, lihat export-skp); warna bergeser = pertegas baris kunci warna. Maks 2 ulangan per scene; sisanya tandai `perlu cek` di `log.md` dan laporkan.

## 5. Unduh 2K dan rapikan

Per gambar lolos QC: detail view → Download → **2K Upscaled** → tunggu file selesai → pindah ke `hasil/<SCENE>_render2K.jpg`. Akhiri dengan cek: jumlah file `hasil/` = jumlah scene lolos, tidak ada file 0 byte.

## Laporan akhir

Singkat: jumlah scene ter-render, scene `perlu cek` + alasannya, lokasi folder, link project Flow. Jangan merangkum langkah.

## Catatan platform

| | Claude | ChatGPT |
|---|---|---|
| Browser | Claude in Chrome atau browser bawaan desktop (baca skill browsernya dulu) | agent Chrome ("GPT for Chrome") |
| Akses file (Mac & Windows) | device bridge / connected folder | folder yang diizinkan; jika tidak ada, upload manual |
| SketchUp | SketchUp MCP (`eval_ruby`, `export_scene`) atau Ruby Console | Ruby Console (tempel 1 baris `load`) |
| Upload ke Flow | `file_upload` + patch file picker (lihat flow-ui) | dialog unggah Chrome; bila agent tidak bisa memilih file, pengguna drag-drop folder `sumber/` sekali |

**Mac & Windows.** Tidak ada langkah khusus OS kecuali yang ditulis di tabel ini dan di referensi:
- Path: pakai path yang dilaporkan tool/folder terhubung; di Ruby pakai `/` juga di Windows (`C:/Users/...`).
- Pindah/ganti nama file: pakai tool file agen (device bridge, file tools) atau perintah sesuai OS (`mv` di Mac, `Move-Item` di PowerShell). Jangan memakai perintah Mac di Windows.
- Shortcut: Mac `Cmd`, Windows `Ctrl` (mis. Save SketchUp `Cmd+S` / `Ctrl+S`). Menu SketchUp sama di kedua OS.

Login Google, persetujuan, dan kuota Flow tetap di tangan pengguna. Jangan mengisi password.
