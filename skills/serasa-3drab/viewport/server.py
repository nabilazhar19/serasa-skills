#!/usr/bin/env python3
"""
server.py - viewport RAB Serasa (Python standar saja, Windows & Mac, tanpa install apa pun).

    python3 server.py --project "<folder proyek>" --open      # Mac
    py -3 server.py --project "<folder proyek>" --open        # Windows
    -> http://localhost:8765

Satu server untuk semua proyek: kalau server sudah jalan, perintah yang sama hanya memindahkan proyek aktif
(POST /api/switch) lalu membuka browser - aman dipanggil berulang oleh agen / plugin SketchUp.
Proyek = folder yang punya _serasa_tools/viewport.json (lihat core/project.py).

GET  /                -> web/index.html   (TERKUNCI: LOCK.json di folder skill berisi hash tampilan & kode; jangan diubah agen)
GET  /api/project     -> view model (core/model.py), di-cache sampai file berubah
GET  /api/model3d     -> geometri 3D biner ringkas (core/mesh.py dari ekspor SketchUp)
GET  /api/ahs         -> daftar spec AHS (pemilih spec)
GET  /api/ping        -> {"app": "serasa-viewport", "project": ...}
POST /api/switch      -> {"project": "<folder>"} ganti proyek aktif
POST /api/edit        -> koreksi (core/edits.py): vol, spec, pending, source, note, conflict, undo, bind, ahs_update, sheet_check, sheet_pull
POST /api/push        -> tulis ke Google Sheet (patch; bangun ulang hanya bila disetujui)
POST /api/stop        -> hentikan server
GET  /events          -> Server-Sent Events saat file proyek / kode berubah
"""
import argparse, glob, gzip, hashlib, importlib, json, os, sys, threading, time, urllib.request, webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

VERSION = "2.5"
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import core.project as project  # noqa: E402
import core.model as model  # noqa: E402
import core.mesh as mesh  # noqa: E402
import core.edits as edits  # noqa: E402
import core.sync as sync  # noqa: E402
import core.sheetsync as sheetsync  # noqa: E402
import core.analysis as analysis  # noqa: E402
import core.scopes as scopes  # noqa: E402
import core.scope_sheets as scope_sheets  # noqa: E402

STATE = {"version": 0, "scope": "init", "cache": None, "mesh": None, "static": {}, "project": None, "lock": threading.Lock(),
         "push": threading.Lock(), "edit": threading.RLock(), "design": None}
CT = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
      ".json": "application/json; charset=utf-8", ".png": "image/png", ".svg": "image/svg+xml"}
CORRECTIONS = ("koreksi_log.json", "koreksi_catatan.json", "viewport_status.json", "export_status.json")


def cfg():
    return project.load(STATE["project"]) if STATE["project"] else None


def design_check():
    """versi resmi dikunci: tampilan + kode viewport + builder + plugin (core/lock.py, LOCK.json)."""
    from core import lock
    return lock.check()


def watched():
    files = {os.path.abspath(__file__): "server"}
    for f in glob.glob(os.path.join(BASE, "core", "*.py")): files[f] = "core"
    for f in glob.glob(os.path.join(BASE, "web", "*.*")): files[f] = "web"   # vendor/ tidak dipantau (tidak pernah berubah)
    c = cfg()
    if not c: return files
    for k in ("input", "builder", "ahs"):
        if c.get(k): files[c[k]] = "data"
    for f in CORRECTIONS: files[os.path.join(c["_base"], f)] = "data"
    if c.get("model3d"): files[c["model3d"]] = "model3d"
    files[c["_config"]] = "data"
    return files


def snapshot():
    out = {}
    for f, scope in watched().items():
        try: st = os.stat(f); out[f] = (st.st_mtime, st.st_size, scope)
        except OSError: out[f] = (None, None, scope)
    return out


def build():
    c = cfg()
    try:
        data = model.load(c) if c else {"noproject": True, "generated_at": time.strftime("%H:%M:%S")}
    except Exception as e:  # tampilkan error di UI, server tetap hidup
        import traceback
        data = {"fatal": f"{type(e).__name__}: {e}", "trace": traceback.format_exc(), "generated_at": time.strftime("%H:%M:%S")}
    data["version"] = STATE["version"]; data["design"] = STATE["design"]; data["viewport"] = VERSION
    if c: data["project_path"] = os.path.dirname(c["_base"])
    return gzip.compress(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode(), 5), data


def bump(scopes):
    with STATE["lock"]:
        STATE["version"] += 1
        STATE["scope"] = "web" if scopes <= {"web"} else ("model3d" if scopes == {"model3d"} else "data")
        STATE["cache"] = None
        if "model3d" in scopes or "project" in scopes: STATE["mesh"] = None
        if "web" in scopes: STATE["static"] = {}; STATE["design"] = design_check()


def model_changed():
    """SketchUp baru menyimpan model -> hitung ulang baris RAB yang tertaut (core/sync.py)."""
    try:
        c = cfg()
        if not c or not os.path.exists(c.get("input") or ""): return
        with STATE["edit"]:
            data = model.load(c)
            res = edits.Editor(c, c["_base"]).model_sync(data.get("rows", []))
        if res: print(time.strftime("%H:%M:%S"), res["summary"], flush=True)
    except Exception as e:
        print("sinkron model gagal:", type(e).__name__, e, flush=True)


def ahs_check():
    """cek sheet Analisa Harga Satuan (link publik ahs_source) saat proyek dibuka."""
    try:
        c = cfg()
        if c and c.get("ahs_source") and c.get("ahs"):
            print(time.strftime("%H:%M:%S"), edits.Editor(c, c["_base"]).ahs_update()["summary"], flush=True)
    except Exception as e:
        print("cek AHS:", e, flush=True)


def switch(path):
    conf = project.find_config(path)
    if not conf: raise ValueError(f"tidak ada _serasa_tools/viewport.json di {path}")
    STATE["project"] = conf; project.remember(conf)
    bump({"data", "project"}); STATE["scope"] = "project"
    threading.Thread(target=ahs_check, daemon=True).start()
    return conf


def watcher(interval):
    global model, mesh, edits, sync, sheetsync, project, analysis, scopes, scope_sheets
    prev = snapshot()
    while True:
        time.sleep(interval)
        cur = snapshot()
        changed = [(f, v[2]) for f, v in cur.items() if prev.get(f, (None,))[:2] != v[:2]]
        if changed and set(cur) == set(prev):
            changed_scopes = {s for _, s in changed}
            if "server" in changed_scopes:  # server.py sendiri berubah -> jalankan ulang proses ini (browser tersambung lagi otomatis)
                print(time.strftime("%H:%M:%S"), "server.py berubah, memulai ulang...", flush=True)
                args = [a for a in sys.argv[1:]]
                os.execv(sys.executable, [sys.executable, os.path.abspath(__file__)] + args)
            if "core" in changed_scopes:
                try:
                    project, model, mesh, edits, sync, sheetsync, analysis, scopes, scope_sheets = (importlib.reload(m) for m in (project, model, mesh, edits, sync, sheetsync, analysis, scopes, scope_sheets))
                except Exception as e: print("reload core gagal:", e)
            if "model3d" in changed_scopes: model_changed()
            bump(changed_scopes)
            print(time.strftime("%H:%M:%S"), "berubah:", ", ".join(os.path.basename(f) for f, _ in changed), flush=True)
        prev = cur


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass

    def _send(self, code, body, ctype, gz=False, cache="no-store"):
        if not gz and len(body) > 1400 and "gzip" in (self.headers.get("Accept-Encoding") or "") and ctype.startswith(("text", "application/json")):
            body, gz = gzip.compress(body, 5), True
        if gz and "gzip" not in (self.headers.get("Accept-Encoding") or ""): body, gz = gzip.decompress(body), False
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Cache-Control", cache)
        if gz: self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def _json(self, code, obj): return self._send(code, json.dumps(obj, ensure_ascii=False).encode(), CT[".json"])

    def _project(self):
        with STATE["lock"]:
            if STATE["cache"] is None: STATE["cache"] = build()
            return STATE["cache"]

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/ping": return self._json(200, {"app": "serasa-viewport", "version": VERSION, "project": STATE["project"]})
        if path == "/api/project": return self._send(200, self._project()[0], CT[".json"], gz=True)
        if path == "/api/model3d":
            c = cfg()
            if not c or not c.get("model3d") or not os.path.isfile(c["model3d"]): return self._json(404, {"error": "model3d belum diekspor"})
            with STATE["lock"]:
                if STATE["mesh"] is None: STATE["mesh"] = gzip.compress(mesh.pack(c["model3d"])[0], 1)
                body = STATE["mesh"]
            return self._send(200, body, "application/octet-stream", gz=True)
        if path == "/api/ahs":
            c = cfg(); items = json.load(open(c["ahs"], encoding="utf-8")) if c and os.path.exists(c.get("ahs") or "") else []
            return self._json(200, [[a["u"], a.get("c", ""), a.get("s", ""), a.get("h", ""), a.get("k", "")] for a in items])
        if path == "/events":
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.send_header("Cache-Control", "no-store"); self.end_headers()
            seen = STATE["version"]
            try:
                self.wfile.write(f"data: {json.dumps({'version': seen, 'scope': 'hello'})}\n\n".encode()); self.wfile.flush()
                t = time.time()
                while True:
                    time.sleep(0.15)
                    if STATE["version"] != seen:
                        seen = STATE["version"]
                        self.wfile.write(f"data: {json.dumps({'version': seen, 'scope': STATE['scope']})}\n\n".encode()); self.wfile.flush()
                    elif time.time() - t > 15:
                        self.wfile.write(b": ping\n\n"); self.wfile.flush(); t = time.time()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                return
        f = os.path.normpath(os.path.join(BASE, "web", "index.html" if path == "/" else path.lstrip("/")))
        if not f.startswith(os.path.join(BASE, "web")) or not os.path.isfile(f) or f.endswith(".json"):
            return self._send(404, b"not found", "text/plain")
        vendor = os.sep + "vendor" + os.sep in f
        key = (f, os.path.getmtime(f))
        body = STATE["static"].get(key)
        if body is None:
            raw = open(f, "rb").read()
            body = gzip.compress(raw, 6) if f.endswith((".js", ".css", ".html")) else raw
            STATE["static"][key] = body
        return self._send(200, body, CT.get(os.path.splitext(f)[1], "application/octet-stream"), gz=f.endswith((".js", ".css", ".html")),
                          cache="public, max-age=604800, immutable" if vendor else "no-cache")

    def do_POST(self):
        path = self.path.split("?")[0]
        origin = self.headers.get("Origin") or ""
        if origin and not origin.startswith(("http://localhost", "http://127.0.0.1")):  # hanya dari halaman viewport sendiri
            return self._json(403, {"ok": False, "error": "origin ditolak"})
        n = int(self.headers.get("Content-Length") or 0)
        try: req = json.loads(self.rfile.read(n) or b"{}")
        except ValueError: return self._json(400, {"ok": False, "error": "JSON tidak valid"})
        try:
            if path == "/api/stop":
                threading.Timer(0.3, lambda: os._exit(0)).start(); return self._json(200, {"ok": True})
            if path == "/api/switch":
                return self._json(200, {"ok": True, "project": switch(req.get("project") or "")})
            c = cfg()
            if not c: raise ValueError("belum ada proyek aktif")
            ed = edits.Editor(c, c["_base"])
            if path == "/api/edit":
                with STATE["edit"]:
                    data = self._project()[1]
                    res = ed.apply(req, {r["row"]: r for r in data.get("rows", [])})
            elif path == "/api/push":
                if not STATE["push"].acquire(blocking=False): return self._json(409, {"ok": False, "error": "push sedang berjalan"})
                try:
                    with STATE["edit"]: res = ed.push(force=bool(req.get("force")), rebuild=bool(req.get("rebuild")))
                finally: STATE["push"].release()
            else:
                return self._json(404, {"ok": False, "error": "tidak ada"})
        except (ValueError, KeyError, IndexError) as e:
            return self._json(400, {"ok": False, "error": str(e)})
        except Exception as e:
            return self._json(500, {"ok": False, "error": f"{type(e).__name__}: {e}"})
        if res.get("review") or res.get("rebuild_needed") or req.get("op") == "sheet_check": return self._json(200, res)  # laporan saja
        bump({"data"})  # langsung segarkan, tidak menunggu watcher
        return self._json(200, res)


def already_running(port, target, open_browser):
    """kalau viewport sudah jalan di port ini: pindah proyek (bila diminta) + buka browser, lalu keluar."""
    try:
        info = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1.5))
    except Exception:
        return False
    if info.get("app") != "serasa-viewport": sys.exit(f"port {port} dipakai aplikasi lain — pakai --port lain")
    if target:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/switch", data=json.dumps({"project": target}).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        print(json.load(urllib.request.urlopen(req, timeout=10)))
    if open_browser: webbrowser.open(f"http://localhost:{port}")
    print(f"Viewport RAB sudah jalan: http://localhost:{port}")
    return True


def main():
    ap = argparse.ArgumentParser(description="Viewport RAB Serasa")
    ap.add_argument("--project", help="folder proyek (berisi _serasa_tools/viewport.json) atau path viewport.json")
    ap.add_argument("--port", type=int, default=8765); ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--interval", type=float, default=0.3); ap.add_argument("--open", action="store_true", help="buka browser")
    a = ap.parse_args()
    if already_running(a.port, a.project, a.open): return
    target = project.find_config(a.project) if a.project else project.find_config(project.last() or "")
    if a.project and not target: sys.exit(f"tidak ada _serasa_tools/viewport.json di {a.project}")
    STATE["project"] = target; STATE["design"] = design_check()
    if target: project.remember(target)
    threading.Thread(target=watcher, args=(a.interval,), daemon=True).start()
    threading.Thread(target=ahs_check, daemon=True).start()
    ThreadingHTTPServer.allow_reuse_address = os.name != "nt"; ThreadingHTTPServer.daemon_threads = True
    srv = ThreadingHTTPServer((a.host, a.port), H)
    print(f"Viewport RAB {VERSION}: http://localhost:{a.port}  proyek: {target or '-'}  (Ctrl+C untuk berhenti)", flush=True)
    if a.open: threading.Timer(0.6, lambda: webbrowser.open(f"http://localhost:{a.port}")).start()
    try: srv.serve_forever()
    except KeyboardInterrupt: pass


if __name__ == "__main__":
    main()
