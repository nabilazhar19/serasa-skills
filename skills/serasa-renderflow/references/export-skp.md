# Export scene dari SketchUp

Pakai [scripts/export_scenes.rb](../scripts/export_scenes.rb). Script: menyembunyikan dimensi, teks, label, section plane, dan guide **sementara**, export tiap scene 4000 px, lalu mengembalikan semua setting. Model tidak diubah dan tidak di-save.

## Cara jalan

Salin `export_scenes.rb` ke folder proyek (mis. `<proyek>/_claude_tmp/`), lalu di SketchUp:

```ruby
load "<proyek>/_claude_tmp/export_scenes.rb"
SerasaRenderExport.run("<proyek>/render/<YYMMDD>_<label>/sumber", scenes: ["KOM LIV","LIV1"], width: 4000)
```

- `scenes:` kosong/nil = semua scene di model.
- Nama file = nama scene SKP persis (`KOM LIV` → `KOM LIV.jpg`); hanya karakter terlarang Windows `\ / : * ? " < > |` diganti `-`.
- Mac & Windows sama. Di Windows tulis path Ruby dengan `/`: `load "C:/Users/<user>/.../export_scenes.rb"`.
- Hasil ringkas ditulis ke `sumber/_export.json` (scene, ukuran, ok/gagal) supaya bisa dibaca agen tanpa melihat layar.

Jalur akses:
- **SketchUp MCP** (`eval_ruby`) — jalankan dua baris di atas langsung.
- **MCP error token** (`SKETCHUP_MCP_TOKEN is not set`) — salin token dari Extensions → MCP Server → Settings ke config MCP, restart. Sementara itu pakai Ruby Console.
- **Ruby Console** (Extensions → Developer → Ruby Console) — ketik baris `load` + `run`, Return. Untuk agen yang mengendalikan layar, ini satu-satunya input yang perlu diketik.

## Cek sebelum render
- Buka 2–3 hasil export: tidak ada teks "mm", tag, sumbu, atau garis section.
- Bila label masih muncul (label dimensi kadang ada di dalam grup/komponen atau di tag tersendiri), sebutkan nama tag-nya ke pengguna atau sembunyikan tag tersebut lewat opsi `hide_tags: ["DIMENSI", ...]`.
