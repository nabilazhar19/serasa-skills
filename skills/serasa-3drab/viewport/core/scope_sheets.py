"""
core/scope_sheets.py - cek editan Sheet & Push untuk RAB terpisah per bangunan (core/scopes.py, viewport.json building_tabs).

Tiap tab bangunan ditulis dari input turunan (scopes.derive) dengan builder yang sama (--prepare patch; struktur berubah ->
konfirmasi rebuild tab itu saja). Baseline per tab di .koreksi/split_state.json. Satu tab gagal -> tab yang sudah berhasil
tetap tercatat, kegagalan dilaporkan. Jangan menjalankan builder langsung pada input induk proyek building_tabs.
"""
import copy, os, subprocess, sys, time
from core import scopes, sheetsync


def check(editor):
    cfg = editor.cfg; st = scopes.state(cfg); spec = editor.spec(); ahs = editor._read(editor.ahs, [])
    items, struct, sheet_rows = [], [], {}
    for t in scopes.tabs(cfg):
        key = t["id"]; web, maps = scopes.derive(spec, key, cfg); wr, ds = sheetsync.build_rows(editor.builder, web, ahs)
        base = st.get("review_rows", {}).get(key)
        if base is None:
            pushed = st["pushed_specs"].get(key)
            base = sheetsync.build_rows(editor.builder, pushed, ahs)[0] if pushed else []
        vals = sheetsync.read_tab(editor._creds(), cfg["spreadsheet_id"], t["tab"], ds, max(len(base), len(wr)))
        live = sheetsync.sheet_rows(vals, ds); sheet_rows[key] = live
        if not base: continue          # tab belum pernah di-push dari viewport: tidak ada dasar perbandingan
        d = sheetsync.diff(base, live, wr)
        for it in d["items"]:
            it["id"] = key + ":" + it["id"]; it["loc"] = scopes.translate(it["loc"], maps); it["sheet_tab"] = t["tab"]; it["uraian"] = t["label"] + " · " + it["uraian"]; items.append(it)
        for e in d["struct"]: e["uraian"] = t["label"] + " · " + e["uraian"]; e["sheet_tab"] = t["tab"]; struct.append(e)
    editor._last_sheet = sheet_rows
    n = len(scopes.tabs(cfg))
    return dict(ok=True, tab=f"Semua RAB · {n} tab", items=items, struct=struct,
                summary=f"{len(items)} perubahan di Sheet, {len(struct)} baris ditambah/dihapus" if items or struct else f"Ke-{n} tab RAB sama dengan push terakhir")


def reviewed(editor, rows):
    st = scopes.state(editor.cfg); st["review_rows"] = rows
    os.makedirs(os.path.dirname(scopes.state_path(editor.cfg)), exist_ok=True); editor._write(scopes.state_path(editor.cfg), st)


def push(editor, force=False, rebuild=False):
    cfg = editor.cfg
    if not force:
        d = check(editor)
        if d["items"] or d["struct"]:
            return dict(d, ok=False, review=True, summary="Ada editan langsung di tab RAB — tinjau sebelum Push semua tab")
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    creds = service_account.Credentials.from_service_account_file(editor._creds(), scopes=["https://www.googleapis.com/auth/spreadsheets"])
    api = build("sheets", "v4", credentials=creds, cache_discovery=False).spreadsheets(); ID = cfg["spreadsheet_id"]
    spec = editor.spec(); ahs = editor._read(editor.ahs, []); B = sheetsync._builder(editor.builder)
    meta = api.get(spreadsheetId=ID, fields="sheets(properties)").execute(); by = {s["properties"]["sheetId"]: s["properties"] for s in meta["sheets"]}
    prepared, structural = [], []
    for t in scopes.tabs(cfg):
        if t.get("sheet_id") not in by or by[t["sheet_id"]]["title"] != t["tab"] or (t.get("audit_id") in by and by[t["audit_id"]]["title"] != t["audit_tab"]):
            raise ValueError(f"Tab tujuan {t['label']} tidak ditemukan / namanya berubah; periksa building_tabs di viewport.json")
        part, _ = scopes.derive(spec, t["id"], cfg); b = B.Builder(copy.deepcopy(part), B.Ahs(ahs)).build()
        _, price = B.build_audit(part, b, t["tab"]); prepared.append((t, part))
        end = min(by[t["sheet_id"]]["gridProperties"]["rowCount"], B.DS + len(b.rows) + 60)
        live = api.values().get(spreadsheetId=ID, range=f"'{t['tab']}'!A{B.DS}:K{end}", valueRenderOption="FORMULA").execute().get("values", [])
        same, _, _ = B.plan_patch(b, live, t["audit_tab"], price)
        if not same or len(live) > len(b.rows) + 3: structural.append(t["label"])
    if structural and not rebuild:
        return dict(ok=False, rebuild_needed=True, summary="Struktur berubah pada " + ", ".join(structural) +
                    ". Push akan menyusun ulang RAB dan Audit tab tersebut; format manual pada tab itu diganti.")
    st = scopes.state(cfg); done = []; t0 = time.time(); folder = os.path.join(cfg["_base"], ".koreksi", "split_push"); os.makedirs(folder, exist_ok=True)
    for t, part in prepared:
        path = os.path.join(folder, t["id"] + ".json"); editor._write(path, part)
        mode = "none" if t["label"] in structural else "patch"
        r = subprocess.run([sys.executable, editor.builder, path, "--push", "--creds", editor._creds(), "--spreadsheet", ID, "--prepare", mode],
                           capture_output=True, text=True, timeout=300, cwd=folder)
        if r.returncode:
            return dict(ok=False, summary="Push belum selesai. Sudah diperbarui: " + (", ".join(done) or "belum ada") + f"; gagal pada {t['label']}. " + (r.stdout + "\n" + r.stderr)[-1800:])
        done.append(t["label"]); st["pushed_specs"][t["id"]] = part; st.setdefault("review_rows", {}).pop(t["id"], None)
        editor._write(scopes.state_path(cfg), st)
    log = editor._read(editor.logf, [])
    log.append(dict(id=len(log) + 1, at=time.strftime("%Y-%m-%d %H:%M:%S"), op="push", row=None, uraian=None,
                    summary=f"push ke Sheet berhasil — {len(done)} RAB dan Audit ({time.time() - t0:.0f} dtk)", snap=None, undone=True))
    editor._write(editor.logf, log)
    return dict(ok=True, summary="Push selesai: " + ", ".join(done) + " beserta Audit masing-masing.")
