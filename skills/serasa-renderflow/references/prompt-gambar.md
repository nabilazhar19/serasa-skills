# Panduan Prompt Gambar — Serasa Archviz

Sumber: `prompt_gambar.md` (panduan Serasa). Bagian "Panduan" di bawah adalah aturan baku dan tidak diubah. Bagian "Penerapan di RenderFlow" menjelaskan cara mengisinya per scene.

## Panduan

### Alur
1. **Analisis setiap gambar Base**: geometry, camera, material, lighting, context, dan karakter adegan.
2. **Terapkan preservation lock** dengan prioritas **geometry → camera → material → context → realism**. Jangan mengubah desain tanpa instruksi eksplisit.
3. **Tulis satu prompt khusus per Base** (bahasa Inggris, sekitar 150–300 kata).

### Struktur prompt (urutan wajib)
1. **Transformation Objective** — jadikan model 3D/SketchUp foto arsitektur ultra-realistis; gambar asli sebagai blueprint.
2. **Architectural Geometry & Camera Lock** — pertahankan bentuk, proporsi, bukaan, elemen, furniture, landscape, sudut kamera, perspektif, framing, crop, dan rasio.
3. **Lighting & Atmosphere Enhancement** — cahaya natural sesuai gambar, global illumination, bounce light, bayangan lembut, exposure seimbang.
4. **PBR Material Enhancement** — pertahankan jenis, warna, pola, skala, dan lokasi material; tingkatkan microtexture, roughness, refleksi, dan imperfections halus.
5. **Environmental Realism** — tingkatkan kedalaman atmosfer, refleksi, dan respons bayangan; jangan tambah objek.
6. **Professional Photography Output** — tampilan fotografi arsitektur profesional, dynamic range realistis, ketajaman natural; hindari CGI look.
7. **Absolute Priority** — hanya realism, lighting, material response, reflections, shadows, dan kualitas foto yang boleh ditingkatkan.
8. **Negative Constraints** — larangan redesign/pergeseran kamera/pergantian material/penambahan objek disatukan dalam narasi; pisahkan *Negative Prompt* hanya jika diminta.

### Template siap isi

```text
Transform the provided [SketchUp/3D model] image into an ultra-photorealistic professional architectural photograph. Treat the original image as an immutable visual blueprint.

Preserve the exact architectural geometry, massing, proportions, facade and openings, structural details, furniture, fixtures, landscape arrangement, and material placement. Lock the original camera position, height, perspective, viewing angle, framing, crop, composition, and aspect ratio.

Enhance [existing lighting condition] with natural global illumination, realistic bounce light, soft shadows, and balanced exposure, respecting the source atmosphere.

Maintain the original material identity, colors, patterns, texture scale, finish, and placement. Improve only surface microtexture, roughness variation, realistic reflections, contact response, and subtle imperfections.

Refine atmospheric depth, environmental reflections, and realistic shadow behavior without changing or adding objects. Produce high-end architectural photography with natural sharpness, realistic dynamic range, physically accurate light, and no artificial CGI appearance.

Absolute priority: improve realism and photographic quality only. Do not redesign, change geometry or camera, replace materials, alter composition, or introduce new elements.
```

## Penerapan di RenderFlow

### Langkah 1 — Analisis Base (tulis dulu, jangan langsung prompt)

Lihat gambar sumber, lalu isi enam baris ini di `prompts.md` di bawah `## <SCENE>` → `### Analisis`:

| Aspek | Isi |
|---|---|
| Geometry | ruang/massa, bukaan, elemen struktur, furniture & fixture utama |
| Camera | posisi (eye level / tinggi), arah, lensa kesan (wide/normal), crop |
| Material | material per bidang + warna; tandai **kritis** yang tidak boleh bergeser (warna klien, kusen hitam, HPL tertentu) |
| Lighting | sumber cahaya yang sudah ada di gambar, arah, kesan waktu |
| Context | luar jendela, landscape, langit, tetangga |
| Karakter | suasana adegan dalam 3–5 kata |

### Langkah 2 — Tulis prompt dari template

Template dipakai sebagai kerangka, urutan 8 bagian tidak boleh berubah. Hasil analisis masuk ke bagian yang sesuai:

| Bagian | Diisi dengan |
|---|---|
| 1 Transformation Objective | `[SketchUp/3D model]` → jenis view + ringkasan scene, mis. "SketchUp interior view of a double-height living room" |
| 2 Geometry & Camera Lock | sebut elemen utama dari baris Geometry (mis. "the black-framed full-height sliding doors, the red spiral stair") dan posisi kamera dari baris Camera |
| 3 Lighting | `[existing lighting condition]` ← baris Lighting |
| 4 PBR Material | sebut material per bidang + warna; material **kritis** ditulis eksplisit (nama + warna, hex bila ada di SKP), mis. "the vertical door handle remains bright cobalt blue, not navy" |
| 5 Environmental Realism | baris Context (mis. "keep the existing garden and palms exactly as placed") |
| 6 Photography Output | tetap |
| 7 Absolute Priority | tetap |
| 8 Negative Constraints | tetap dalam narasi; tambahkan larangan spesifik scene di kalimat yang sama bila perlu (mis. "do not render any text, dimension labels, or tags") |

Cek akhir:
- 150–300 kata (hitung).
- Urutan 1→8 utuh; tidak ada bagian template yang dihapus.
- Tidak ada objek/material yang tidak terlihat di Base.
- *Negative Prompt* terpisah hanya bila pengguna memintanya.

Hex warna dari SketchUp: `Sketchup.active_model.materials["<nama>"].color.to_a`.

### Simpan

`prompts.md`: `## <SCENE>` → `### Analisis` (tabel) → `### Prompt` (final). Versi ulang: `### Prompt v2` dengan satu baris alasan (mis. "biru handle jadi navy → pertegas di bagian 4").

### Pelajaran run 22 Nov 2026 (Puri Bintaro 1)
- Warna klien bergeser (handle biru → navy) saat material kritis tidak disebut eksplisit di bagian 4.
- Label "mm" ikut ter-render karena ada di gambar Base; solusi utama di export (lihat export-skp), larangan teks di bagian 8 hanya cadangan.
