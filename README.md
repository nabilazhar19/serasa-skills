# Serasa Agent Skills

Kumpulan skill agent AI internal PT Serasa Rancang Indonesia.

| Skill | Fungsi |
|---|---|
| `serasa-3drab` | Buat RAB format Serasa dari model SketchUp (.skp) + denah ke Google Sheet (rincian per ruang, MASTER AHS/AHS + IKK, tab Analisa) |

## Install (Claude Code, Codex, Cursor, dll.)

Butuh Node.js 18+.

```bash
# global (semua proyek), pilih agent secara interaktif
npx skills add <OWNER>/serasa-skills -g

# langsung ke Claude Code + Codex tanpa pertanyaan
npx skills add <OWNER>/serasa-skills --skill serasa-3drab -g -a claude-code -a codex -y
```

Lokasi hasil install:
- Claude Code: `~/.claude/skills/serasa-3drab/`
- Codex: `~/.agents/skills/serasa-3drab/` (lokasi standar Agent Skills yang dibaca Codex)

Update ke versi terbaru: jalankan ulang perintah `npx skills add` yang sama.

Cek isi repo tanpa install: `npx skills add <OWNER>/serasa-skills --list`

## Kebutuhan saat dipakai
- Akses SketchUp lewat MCP (eval_ruby + screenshot) atau Ruby Console.
- Akses Google Sheets/Drive ke Template RAB Serasa (`1zwpn8sGUDQK4_FUd86FiYBzSVwW9y-pygasOf73Kahg`).
- Python 3 (opsional `pip install -r skills/serasa-3drab/requirements.txt`).

## Menambah skill baru
Buat folder `skills/<nama-skill>/` berisi `SKILL.md` (frontmatter `name` + `description`), lalu commit & push.
