@echo off
rem Pasang Serasa RAB (Windows): klik dua kali file ini. Plugin SketchUp + viewport + library Python.
cd /d "%~dp0"
set PY=
where py >nul 2>nul && (py -3 -c "import sys; sys.exit(sys.version_info < (3,8))" >nul 2>nul && set PY=py -3)
if not defined PY (where python >nul 2>nul && (python -c "import sys; sys.exit(sys.version_info < (3,8))" >nul 2>nul && set PY=python))
if not defined PY (
  echo Python 3 belum ada - memasang lewat winget ...
  winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
  if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set PY="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)
if not defined PY (
  echo Gagal memasang Python. Unduh dari https://www.python.org/downloads/ lalu jalankan file ini lagi.
  pause & exit /b 1
)
%PY% scripts\setup.py %*
pause
