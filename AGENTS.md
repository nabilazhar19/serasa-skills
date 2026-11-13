# AGENTS.md — serasa-3drab (berlaku untuk Codex, Claude, dan agen lain)

Skill ini membuat RAB Serasa dari SketchUp + denah ke Google Sheets dengan Viewport RAB lokal. Baca `SKILL.md` dulu.

Aturan keras (ringkas; lengkapnya di SKILL.md):
1. Jangan mengubah file skill atau salinan terpasangnya (`viewport/`, `scripts/build_rab.py`, `scripts/skp_extract.rb`,
   `scripts/setup.py`, folder `SerasaRAB`, Plugins SketchUp). Bug/fitur kurang → laporkan sebagai usulan, jangan tambal.
2. Take-off hanya lewat fungsi `SerasaRAB`; tidak menulis script ekstraksi sendiri, tidak dump geometri, tidak membuat venv.
3. File kerja hanya di `<proyek>/_serasa_tools/work/`; tidak membuat folder `output`.
4. Viewport sejak awal: `tools.py init` + `open`, `status` tiap langkah, `bind` di akhir. `tools.py check` harus OK.
5. Sheet hanya berubah lewat Push (`build_rab.py --prepare patch`) kecuali diminta.
6. Analisa non-AHS rinci sesuai `references/analisa.md`.

Pengembang skill (bukan agen yang sedang membuat RAB): ubah di repo, uji (`python3 scripts/test_builder.py`), lalu
`python3 viewport/tools.py lock --version <x.y>`.
