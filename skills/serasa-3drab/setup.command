#!/bin/bash
# Pasang Serasa RAB (Mac): klik dua kali file ini. Plugin SketchUp + viewport + library Python.
cd "$(dirname "$0")"
PY=""
for c in /opt/homebrew/bin/python3 /usr/local/bin/python3 /Library/Frameworks/Python.framework/Versions/Current/bin/python3 /usr/bin/python3; do
  if [ -x "$c" ] && "$c" -c 'import sys; sys.exit(sys.version_info < (3,8))' 2>/dev/null; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "Python 3 belum ada. macOS akan menawarkan 'Command Line Developer Tools' — pilih Install, lalu klik dua kali file ini lagi."
  xcode-select --install 2>/dev/null; read -n 1 -s -r -p "Tekan tombol apa saja untuk menutup"; exit 1
fi
"$PY" scripts/setup.py "$@"
echo; read -n 1 -s -r -p "Selesai. Tekan tombol apa saja untuk menutup"
