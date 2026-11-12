# Serasa Agent Skills

Kumpulan skill agent AI internal PT Serasa Rancang Indonesia.

| Skill | Fungsi |
|---|---|
| `serasa-3drab` | Buat, lanjutkan, dan koreksi RAB dari SketchUp + denah ke Google Sheets; AHS live, Audit volume, penanda estimasi, perlindungan input manual, dan Viewport RAB 3D lokal |

## Install (Claude Code, Codex, Cursor, dll.)

Butuh Node.js 18+.

```bash
# global (semua proyek), pilih agent secara interaktif
npx skills add nabilazhar19/serasa-skills -g

# langsung ke Claude Code + Codex tanpa pertanyaan
npx skills add nabilazhar19/serasa-skills --skill serasa-3drab -g -a claude-code -a codex -y
```

Lokasi hasil install:
- Claude Code: `~/.claude/skills/serasa-3drab/`
- Codex: `~/.agents/skills/serasa-3drab/` (lokasi standar Agent Skills yang dibaca Codex)

Update ke versi terbaru: jalankan ulang perintah `npx skills add` yang sama.

Cek isi repo tanpa install: `npx skills add nabilazhar19/serasa-skills --list`

## Kebutuhan saat dipakai
- Akses SketchUp lewat MCP (eval_ruby + screenshot) atau Ruby Console.
- Akses Google Sheets/Drive ke Template RAB Serasa (`1zwpn8sGUDQK4_FUd86FiYBzSVwW9y-pygasOf73Kahg`).
- Python 3.8+. Plugin SketchUp (semua versi), Viewport RAB, dan library Python terpasang otomatis saat skill pertama dipakai (`SerasaRAB.install_plugin` → `scripts/setup.py`); `npx skills add` sendiri hanya menyalin file. Manual: klik dua kali `skills/serasa-3drab/setup.command` (Mac) / `setup.bat` (Windows).
- Disarankan: service account Google untuk `--push` (lihat `references/sheet-format.md`).

## Menambah skill baru
Buat folder `skills/<nama-skill>/` berisi `SKILL.md` (frontmatter `name` + `description`), lalu commit & push.
