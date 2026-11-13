#!/usr/bin/env python3
"""
setup.py - pasang Serasa RAB di komputer ini (Windows & Mac). Aman dijalankan berulang (update = jalankan lagi).

  python3 scripts/setup.py            # pasang/perbarui semuanya
  python3 scripts/setup.py --check    # hanya cek, tidak mengubah apa pun
  python3 scripts/setup.py --no-deps  # lewati pip

Yang dikerjakan:
 1. Salin skill (viewport/, scripts/, requirements.txt) ke folder bersama:
      Mac      ~/Library/Application Support/SerasaRAB
      Windows  %APPDATA%\\SerasaRAB
    -> satu viewport untuk semua proyek, semua versi SketchUp, dan semua agen (Claude, Codex, dll.).
    state.json & server.log di sana dipertahankan.
 2. Pasang plugin SketchUp (serasa_skp_extract.rb) ke folder Plugins SEMUA versi SketchUp yang ada
    (SketchUp 2017 ... 2026+, juga versi yang belum pernah dibuka tapi foldernya ada).
 3. Pasang library Python yang dibutuhkan Push / Tarik dari Sheet (google-api-python-client, google-auth)
    untuk Python yang menjalankan script ini, lalu catat path Python itu di env.json
    (dipakai plugin SketchUp untuk menyalakan viewport tanpa Terminal).
Tanpa library tambahan selain Python 3.8+.
"""
import argparse, glob, json, os, shutil, subprocess, sys, time

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION = "2.5"
DEPS = {"googleapiclient": "google-api-python-client", "google.oauth2": "google-auth"}
SKIP = {"__pycache__", "state.json", "server.log", ".DS_Store"}
WIN = os.name == "nt"


def home():
    if WIN: return os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~\\AppData\\Roaming"), "SerasaRAB")
    if sys.platform == "darwin": return os.path.expanduser("~/Library/Application Support/SerasaRAB")
    return os.path.expanduser("~/.local/share/SerasaRAB")


def sketchup_plugin_dirs():
    """folder Plugins untuk setiap versi SketchUp yang terpasang/pernah dibuka."""
    if WIN:
        roots = [os.path.join(os.environ.get("APPDATA", ""), "SketchUp")]
        pats = ["SketchUp 20*", "SketchUp 2*"]
    else:
        roots = [os.path.expanduser("~/Library/Application Support")]
        pats = ["SketchUp 20*", "SketchUp 2*"]
    found = set()
    for r in roots:
        for p in pats:
            for d in glob.glob(os.path.join(r, p)):
                if os.path.isdir(d): found.add(os.path.join(d, "SketchUp", "Plugins"))
    # SketchUp terpasang tapi belum pernah dibuka: buat foldernya dari daftar aplikasi
    if WIN:
        for pf in {os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramW6432", r"C:\Program Files")}:
            for d in glob.glob(os.path.join(pf, "SketchUp", "SketchUp 20*")):
                found.add(os.path.join(os.environ.get("APPDATA", ""), "SketchUp", os.path.basename(d), "SketchUp", "Plugins"))
    elif sys.platform == "darwin":
        for d in glob.glob("/Applications/SketchUp 20*"):
            found.add(os.path.join(roots[0], os.path.basename(d), "SketchUp", "Plugins"))
    return sorted(found)


def copy_tree(src, dst):
    n = 0
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in SKIP]
        rel = os.path.relpath(root, src); out = os.path.join(dst, rel) if rel != "." else dst
        os.makedirs(out, exist_ok=True)
        for f in files:
            if f in SKIP or f.endswith(".pyc"): continue
            s, d = os.path.join(root, f), os.path.join(out, f)
            if not os.path.exists(d) or open(s, "rb").read() != open(d, "rb").read():
                shutil.copy2(s, d); n += 1
    return n


def install_home(dst, dry):
    if os.path.abspath(SKILL) == os.path.abspath(dst): return "sudah di folder bersama"
    if dry: return f"akan disalin ke {dst}"
    n = copy_tree(os.path.join(SKILL, "viewport"), os.path.join(dst, "viewport"))
    os.makedirs(os.path.join(dst, "scripts"), exist_ok=True)
    for f in ("build_rab.py", "setup.py", "skp_extract.rb"):
        s = os.path.join(SKILL, "scripts", f)
        if os.path.exists(s): shutil.copy2(s, os.path.join(dst, "scripts", f)); n += 1
    # file kode tambahan yang bukan bagian versi resmi (mis. tambalan agen) dinonaktifkan, tidak dihapus
    for f in glob.glob(os.path.join(dst, "viewport", "core", "*.py")) + glob.glob(os.path.join(dst, "viewport", "web", "*.*")):
        rel = os.path.relpath(f, dst)
        if not os.path.exists(os.path.join(SKILL, rel)) and not f.endswith(".json"):
            os.replace(f, f + ".tidak-resmi"); n += 1
    for f in ("requirements.txt", "setup.command", "setup.bat", "LOCK.json", "AGENTS.md"):
        s = os.path.join(SKILL, f)
        if os.path.exists(s): shutil.copy2(s, os.path.join(dst, f))
    return f"{n} file diperbarui di {dst}"


def install_plugins(dst, dry):
    rb = os.path.join(SKILL, "scripts", "skp_extract.rb")
    out = []
    for d in sketchup_plugin_dirs():
        target = os.path.join(d, "serasa_skp_extract.rb")
        if dry: out.append(f"{target} ({'ada' if os.path.exists(target) else 'belum'})"); continue
        try:
            os.makedirs(d, exist_ok=True); shutil.copy2(rb, target); out.append(target)
        except OSError as e:
            out.append(f"GAGAL {target}: {e}")
    return out


def missing_deps():
    miss = []
    for mod, pkg in DEPS.items():
        try: __import__(mod)
        except ImportError: miss.append(pkg)
    return miss


def pip_install(pkgs):
    base = [sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check"]
    try: subprocess.run([sys.executable, "-m", "pip", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, OSError):
        subprocess.run([sys.executable, "-m", "ensurepip", "--user"], capture_output=True)
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    tries = [base + pkgs] if in_venv else [base + ["--user"] + pkgs, base + ["--user", "--break-system-packages"] + pkgs, base + pkgs]
    last = ""
    for cmd in tries:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0: return True, ""
        last = (r.stderr or r.stdout).strip().splitlines()[-1:] or [""]
    return False, last[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true"); ap.add_argument("--no-deps", action="store_true")
    ap.add_argument("--home", help="(uji) folder bersama lain")
    a = ap.parse_args()
    dst = a.home or home(); dry = a.check
    print(f"Serasa RAB {VERSION} · Python {sys.version.split()[0]} ({sys.executable})")
    if sys.version_info < (3, 8): sys.exit("Butuh Python 3.8 atau lebih baru.")
    print("folder bersama:", install_home(dst, dry))
    plugs = install_plugins(dst, dry)
    print("plugin SketchUp:" if plugs else "plugin SketchUp: tidak ada SketchUp terdeteksi (buka SketchUp sekali, lalu jalankan lagi)")
    for p in plugs: print("  -", p)
    miss = missing_deps(); ok = True
    if miss and not a.no_deps and not dry:
        good, err = pip_install(miss)
        import importlib; importlib.invalidate_caches()
        if not good:
            ok = False; print("library Google: GAGAL dipasang —", err)
        else:
            miss = []
    print("library Google:", "ada" if not miss else ("belum: " + ", ".join(miss) if dry or a.no_deps else "lihat di atas"))
    if not dry:
        os.makedirs(dst, exist_ok=True)
        env = {"version": VERSION, "python": sys.executable, "home": dst, "skill": SKILL,
               "plugins": [p for p in plugs if not p.startswith("GAGAL")], "installed": time.strftime("%Y-%m-%d %H:%M:%S")}
        json.dump(env, open(os.path.join(dst, "env.json"), "w", encoding="utf-8"), indent=1)
        print("env.json:", os.path.join(dst, "env.json"))
        print(f"\nViewport: python3 \"{os.path.join(dst, 'viewport', 'tools.py')}\" open --project <folder proyek>")
        if plugs: print("Restart SketchUp sekali -> menu Extensions › Serasa RAB.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
