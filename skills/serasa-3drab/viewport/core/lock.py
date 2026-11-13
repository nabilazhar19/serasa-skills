"""
core/lock.py - kunci versi resmi skill (tampilan viewport + kode viewport, builder, plugin SketchUp).

LOCK.json di folder skill (atau folder bersama SerasaRAB) berisi sha256 tiap file resmi. Agen TIDAK boleh mengubah file ini;
perbaikan masuk lewat repo skill lalu dipasang ulang (scripts/setup.py). Viewport menampilkan peringatan bila ada yang berbeda,
`tools.py check` gagal, dan setup.py mengembalikan file resmi.
"""
import glob, hashlib, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # .../serasa-3drab atau .../SerasaRAB
LOCK = os.path.join(ROOT, "LOCK.json")
PATTERNS = ["viewport/web/*.html", "viewport/web/*.js", "viewport/web/*.css", "viewport/server.py", "viewport/tools.py",
            "viewport/core/*.py", "scripts/build_rab.py", "scripts/skp_extract.rb", "scripts/setup.py"]


def files():
    out = []
    for p in PATTERNS: out += glob.glob(os.path.join(ROOT, *p.split("/")))
    return sorted(os.path.relpath(f, ROOT).replace(os.sep, "/") for f in out)


def sha(path):
    return hashlib.sha256(open(path, "rb").read().replace(b"\r\n", b"\n")).hexdigest()   # CRLF (Windows/git) dianggap sama


def write(version):
    json.dump({"version": version, "files": {f: sha(os.path.join(ROOT, f)) for f in files()}}, open(LOCK, "w", encoding="utf-8"), indent=1)
    return LOCK


def check():
    try: lock = json.load(open(LOCK, encoding="utf-8"))
    except (OSError, ValueError): return {"ok": False, "changed": ["LOCK.json hilang"], "version": None}
    changed = []
    for rel, h in lock.get("files", {}).items():
        p = os.path.join(ROOT, *rel.split("/"))
        try: ok = sha(p) == h
        except OSError: ok = False
        if not ok: changed.append(rel)
    extra = [f for f in files() if f not in lock.get("files", {})]
    return {"ok": not changed and not extra, "changed": changed + [f + " (baru)" for f in extra], "version": lock.get("version")}
