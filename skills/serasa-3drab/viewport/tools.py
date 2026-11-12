#!/usr/bin/env python3
"""
tools.py - perintah viewport untuk agen AI apa pun (Claude, Codex, dll.) & plugin SketchUp. Windows & Mac.

  python3 tools.py init   --project DIR --input ruko_input.json [--title ..] [--sheet-url URL --sheet-gid N]
                          [--spreadsheet-id ID] [--creds PATH] [--ahs ahs.json] [--model3d model3d.json] [--ahs-source URL]
  python3 tools.py status --project DIR --message "Take-off dinding Lt.1" [--stage takeoff] [--step 2 --steps 6]
  python3 tools.py open   --project DIR          # nyalakan server (di belakang layar) bila belum, pindah proyek, buka browser
  python3 tools.py ensure --project DIR          # sama tanpa membuka browser (dipakai plugin saat model dibuka)
  python3 tools.py bind   --project DIR          # tautkan baris RAB ke model 3D (RAB ikut berubah saat SKP disimpan)
  python3 tools.py notes  --project DIR          # daftar catatan koreksi yang masih terbuka (dari tombol catatan di viewport)
  python3 tools.py note-done --project DIR --id N   # tandai catatan selesai setelah dikerjakan
  python3 tools.py stop                          # hentikan server
  python3 tools.py check                         # cek lingkungan: Python, library Google, kunci desain
  python3 tools.py lock                          # (pengembang) perbarui web/LOCK.json setelah mengubah tampilan resmi

Semua path di viewport.json relatif terhadap folder _serasa_tools proyek.
"""
import argparse, hashlib, json, os, subprocess, sys, time, urllib.request, webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from core import project  # noqa: E402

PORT = 8765


def _ping(port=PORT):
    try: return json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1.5))
    except Exception: return None


def _post(path, body, port=PORT):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
    return json.load(urllib.request.urlopen(req, timeout=120))


def _tools_dir(p):
    p = os.path.abspath(os.path.expanduser(p))
    return p if os.path.basename(p) == "_serasa_tools" else os.path.join(p, "_serasa_tools")


def _python_bg():
    """python tanpa jendela konsol (Windows: pythonw.exe)."""
    exe = sys.executable
    if os.name == "nt":
        w = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(w): return w
    return exe


def start_server(proj, port=PORT):
    if _ping(port):
        if proj: _post("/api/switch", {"project": proj}, port)
        return "sudah jalan"
    log = open(os.path.join(HERE, "server.log"), "a", encoding="utf-8")
    cmd = [_python_bg(), os.path.join(HERE, "server.py"), "--port", str(port)] + (["--project", proj] if proj else [])
    kw = dict(stdout=log, stderr=log, stdin=subprocess.DEVNULL, cwd=HERE)
    if os.name == "nt": kw["creationflags"] = 0x00000008 | 0x00000200   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else: kw["start_new_session"] = True
    subprocess.Popen(cmd, **kw)
    for _ in range(40):
        time.sleep(0.25)
        if _ping(port): return "dinyalakan"
    raise SystemExit("server tidak menyala — lihat viewport/server.log")


def cmd_init(a):
    tools = _tools_dir(a.project); os.makedirs(tools, exist_ok=True)
    path = os.path.join(tools, "viewport.json")
    cfg = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    for k in ("title", "input", "ahs", "model3d", "sheet_url", "spreadsheet_id", "creds", "ahs_source", "ahs_sheet_url"):
        v = getattr(a, k.replace("-", "_"), None)
        if v is not None: cfg[k] = v
    if a.sheet_gid is not None: cfg["sheet_gid"] = a.sheet_gid
    cfg.setdefault("ahs", "ahs.json"); cfg.setdefault("title", os.path.basename(os.path.dirname(tools)))
    json.dump(cfg, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"viewport.json: {path}")


def cmd_status(a):
    tools = _tools_dir(a.project); os.makedirs(tools, exist_ok=True)
    st = {"stage": a.stage, "message": a.message, "step": a.step, "steps": a.steps, "at": time.strftime("%Y-%m-%d %H:%M:%S")}
    p = os.path.join(tools, "viewport_status.json")
    json.dump(st, open(p + ".tmp", "w", encoding="utf-8"), ensure_ascii=False); os.replace(p + ".tmp", p)
    print("status:", a.message)


def cmd_open(a, browser=True):
    conf = project.find_config(a.project) if a.project else None
    if a.project and not conf: raise SystemExit(f"belum ada viewport.json — jalankan dulu: tools.py init --project \"{a.project}\" ...")
    print("server:", start_server(conf))
    if browser: webbrowser.open(f"http://localhost:{PORT}")
    print(f"Viewport RAB: http://localhost:{PORT}")


def cmd_bind(a):
    conf = project.find_config(a.project)
    if not conf: raise SystemExit("viewport.json tidak ditemukan")
    if _ping():   # lewat server supaya snapshot/undo/log konsisten
        _post("/api/switch", {"project": conf}); print(_post("/api/edit", {"op": "bind"})["summary"]); return
    from core import model, edits
    c = project.load(conf); d = model.load(c)
    print(edits.Editor(c, c["_base"]).bind({r["row"]: r for r in d["rows"]}, force=True)["summary"])


def cmd_notes(a):
    f = os.path.join(_tools_dir(a.project), "koreksi_catatan.json")
    notes = [n for n in (json.load(open(f, encoding="utf-8")) if os.path.exists(f) else []) if n.get("status") == "open"]
    if not notes: print("tidak ada catatan terbuka"); return
    for n in notes:
        print(f"#{n['id']} baris {n.get('row') or '-'} · {n.get('uraian') or ''} · {n.get('ruang') or ''}"
              + (f" · objek {n['object']}" if n.get("object") else "") + f"\n   {n['text']}")


def cmd_note_done(a):
    conf = project.find_config(a.project)
    if _ping() and conf:
        _post("/api/switch", {"project": conf}); print(_post("/api/edit", {"op": "note_done", "id": a.id})["summary"]); return
    f = os.path.join(_tools_dir(a.project), "koreksi_catatan.json")
    notes = json.load(open(f, encoding="utf-8"))
    for n in notes:
        if n["id"] == a.id: n["status"] = "done"; n["done_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    json.dump(notes, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1); print("catatan diperbarui")


def cmd_stop(a):
    if not _ping(): print("server tidak jalan"); return
    try: _post("/api/stop", {})
    except Exception: pass
    print("server dihentikan")


def lock_files():
    out = {}
    for root, _, fs in os.walk(os.path.join(HERE, "web")):
        for f in sorted(fs):
            if f == "LOCK.json": continue
            p = os.path.join(root, f); rel = os.path.relpath(p, os.path.join(HERE, "web")).replace(os.sep, "/")
            out[rel] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return out


def cmd_lock(a):
    p = os.path.join(HERE, "web", "LOCK.json")
    json.dump({"version": a.version, "files": lock_files()}, open(p, "w", encoding="utf-8"), indent=1)
    print("LOCK.json diperbarui:", p)


def cmd_check(a):
    ok = True
    print(f"Python {sys.version.split()[0]} ({sys.executable})")
    try:
        import googleapiclient, google.oauth2  # noqa: F401
        print("library Google: ada")
    except ImportError:
        ok = False; print("library Google: BELUM (jalankan scripts/setup.py) — dibutuhkan untuk Push / Tarik dari Sheet")
    lock = json.load(open(os.path.join(HERE, "web", "LOCK.json"), encoding="utf-8"))
    bad = [k for k, v in lock_files().items() if lock["files"].get(k) != v]
    print("kunci desain:", "OK" if not bad else f"BERUBAH {bad}"); ok = ok and not bad
    print("server:", "jalan" if _ping() else "tidak jalan")
    sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init"); p.add_argument("--project", required=True)
    for k in ("title", "input", "ahs", "model3d", "sheet-url", "spreadsheet-id", "creds", "ahs-source", "ahs-sheet-url"): p.add_argument("--" + k)
    p.add_argument("--sheet-gid", type=int)
    p = sub.add_parser("status"); p.add_argument("--project", required=True); p.add_argument("--message", required=True)
    p.add_argument("--stage", default="kerja"); p.add_argument("--step", type=int); p.add_argument("--steps", type=int)
    for c in ("open", "ensure", "bind"): sub.add_parser(c).add_argument("--project", required=c == "bind")
    sub.add_parser("notes").add_argument("--project", required=True)
    p = sub.add_parser("note-done"); p.add_argument("--project", required=True); p.add_argument("--id", type=int, required=True)
    sub.add_parser("stop"); sub.add_parser("check")
    p = sub.add_parser("lock"); p.add_argument("--version", default="1.0")
    a = ap.parse_args()
    {"init": cmd_init, "status": cmd_status, "open": cmd_open, "ensure": lambda x: cmd_open(x, browser=False), "bind": cmd_bind,
     "notes": cmd_notes, "note-done": cmd_note_done, "stop": cmd_stop, "check": cmd_check, "lock": cmd_lock}[a.cmd](a)


if __name__ == "__main__":
    main()
