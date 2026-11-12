# serasa-3drab — skill RAB format Serasa (SKP + denah → Google Sheet)

Skill agent AI untuk membuat RAB format PT Serasa Rancang Indonesia dari model SketchUp dan gambar denah.
Format mengikuti standar Agent Skills (`SKILL.md` + `scripts/` + `references/`), bisa dipakai Claude, Codex, atau agent lain.

## Isi
- `SKILL.md` — alur kerja & aturan (mulai dari sini)
- `scripts/skp_extract.rb` — ekstraksi kuantitas dari SketchUp (v2: `SerasaRAB.takeoff` satu panggilan)
- `scripts/install_sketchup_plugin.sh` — pasang `skp_extract.rb` ke folder Plugins SketchUp (macOS) agar termuat otomatis
- `scripts/build_rab.py` — membangun & menulis sheet dari input JSON; `--push` via service account (mode `--prepare template` / `clone:<tab>`), atau file siap kirim untuk connector
- `references/` — metode take-off, pemetaan pekerjaan → AHS live, rekonsiliasi volume, revisi bertahap, format input, format & jebakan Google Sheets
- `examples/mini_input.json` — contoh ringkas format template Nov 2026 (baca ini dulu)
- `examples/ruko_bkl2_input.json` — contoh struktur input lengkap; hitung ulang ukuran dan harga untuk proyek aktif
- `examples/legacy/`, `scripts/legacy/` — format lama (MASTER AHS), hanya untuk file lama

## Instalasi
**Claude Code / Claude (desktop)**: salin folder ke `~/.claude/skills/serasa-3drab/` (personal) atau `<repo>/.claude/skills/serasa-3drab/` (per proyek).

**Codex (CLI/IDE)**: salin folder ke `~/.codex/skills/serasa-3drab/` (atau `.codex/skills/` di repo). Codex membaca `SKILL.md` yang sama. Jika versi Codex belum mendukung skills, tambahkan ke `AGENTS.md`:
```
Untuk membuat RAB format Serasa, ikuti ~/.codex/skills/serasa-3drab/SKILL.md
```

**Agent lain**: berikan isi `SKILL.md` sebagai instruksi sistem dan sediakan folder ini di workspace.

## Kebutuhan
- Akses SketchUp: MCP SketchUp (eval_ruby + screenshot) atau user menjalankan Ruby Console.
- Akses Google Sheets/Drive ke template `1zwpn8sGUDQK4_FUd86FiYBzSVwW9y-pygasOf73Kahg` (minimal view + bisa membuat salinan).
- Python 3; opsional `pip install -r requirements.txt` untuk `--push` dan `pymupdf` untuk membaca PDF denah.

## Setelah install (sekali per komputer)
1. SketchUp: otomatis — saat skill pertama kali dipakai, agen menjalankan `SerasaRAB.install_plugin` (Mac & Windows). Manual (macOS): `bash scripts/install_sketchup_plugin.sh`, lalu restart SketchUp.
2. Service account Google (agar data RAB tidak lewat chat): lihat `references/sheet-format.md` bagian "Service account".

## Uji cepat
```
python3 scripts/build_rab.py examples/mini_input.json --ahs <ekspor tab AHS (.csv/.json)> --out out
```
