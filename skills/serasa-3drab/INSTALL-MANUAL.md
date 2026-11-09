# serasa-3drab — skill RAB format Serasa (SKP + denah → Google Sheet)

Skill agent AI untuk membuat RAB format PT Serasa Rancang Indonesia dari model SketchUp dan gambar denah.
Format mengikuti standar Agent Skills (`SKILL.md` + `scripts/` + `references/`), bisa dipakai Claude, Codex, atau agent lain.

## Isi
- `SKILL.md` — alur kerja & aturan (mulai dari sini)
- `scripts/skp_extract.rb` — ekstraksi kuantitas dari SketchUp (lewat MCP `eval_ruby` atau Ruby Console)
- `scripts/build_rab.py` — membangun isi sheet (nilai, rumus, format) dari input JSON; opsi `--push` via service account
- `references/` — metode take-off, pemetaan material → kode MASTER AHS, format input, format & jebakan Google Sheets
- `examples/bku_input.json` — input lengkap proyek 0113 Bengkulu House (hasil nyata)

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

## Uji cepat
```
python3 scripts/build_rab.py examples/bku_input.json --out out
cat out/summary.txt
```
