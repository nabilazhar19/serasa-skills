#!/usr/bin/env bash
# Pasang skp_extract.rb ke folder Plugins SketchUp (macOS) supaya modul SerasaRAB termuat otomatis.
# Windows: salin manual ke %APPDATA%\SketchUp\SketchUp 20xx\SketchUp\Plugins\
set -e
SRC="$(cd "$(dirname "$0")" && pwd)/skp_extract.rb"
n=0
for d in "$HOME/Library/Application Support"/SketchUp\ 20*/SketchUp/Plugins; do
  [ -d "$d" ] || continue
  cp "$SRC" "$d/serasa_skp_extract.rb"; echo "terpasang: $d/serasa_skp_extract.rb"; n=$((n+1))
done
[ $n -gt 0 ] || { echo "Folder Plugins SketchUp tidak ditemukan. Buka SketchUp sekali, lalu ulangi."; exit 1; }
echo "Restart SketchUp. Cek di Ruby Console: SerasaRAB::VERSION"
