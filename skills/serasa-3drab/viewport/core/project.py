"""
core/project.py - setelan proyek untuk viewport (satu viewport untuk semua proyek, Windows & Mac).

Tiap proyek punya  <folder proyek>/_serasa_tools/viewport.json  (path relatif terhadap folder _serasa_tools):
  {
    "title": "RUKO BKL (0113_BENGKULU HOUSE REV1)",
    "input": "ruko_bkl2_input.json",          # input RAB (JSON builder)
    "ahs": "ahs.json",                         # cache tab AHS
    "model3d": "ruko_model3d.json",            # ekspor SketchUp (SerasaRAB.export_mesh / watch_export)
    "builder": null,                           # null = scripts/build_rab.py bawaan skill
    "sheet_url": "...", "sheet_gid": 123,      # tombol Buka Sheet
    "spreadsheet_id": "...", "creds": "../../_serasa_keys/sa-keys.json",   # Push / Tarik dari Sheet
    "ahs_source": "https://docs.google.com/.../export?format=csv&gid=0",   # AHS live (link publik)
    "ahs_sheet_url": "..."
  }
Agen menulis status kerja ke  _serasa_tools/viewport_status.json  -> tampil di header viewport:
  {"stage": "takeoff", "message": "Take-off dinding Lt.1", "step": 2, "steps": 6}
"""
import json, os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # .../viewport
DEFAULT_BUILDER = os.path.normpath(os.path.join(HERE, "..", "scripts", "build_rab.py"))
PATH_KEYS = ("input", "ahs", "model3d", "builder", "creds")
STATE = os.path.join(HERE, "state.json")                                     # proyek terakhir yang dibuka


def find_config(target):
    """terima folder proyek, folder _serasa_tools, atau path viewport*.json."""
    if not target: return None
    t = os.path.abspath(os.path.expanduser(target))
    if os.path.isfile(t): return t
    for p in (os.path.join(t, "_serasa_tools", "viewport.json"), os.path.join(t, "viewport.json")):
        if os.path.isfile(p): return p
    return None


def remember(path):
    try: json.dump({"project": path}, open(STATE, "w", encoding="utf-8"))
    except OSError: pass


def last():
    try: return json.load(open(STATE, encoding="utf-8")).get("project")
    except (OSError, ValueError): return None


def load(path):
    cfg = json.load(open(path, encoding="utf-8"))
    base = os.path.dirname(os.path.abspath(path))
    cfg["_config"] = os.path.abspath(path); cfg["_base"] = base
    if not cfg.get("builder"): cfg["builder"] = DEFAULT_BUILDER
    for k in PATH_KEYS:
        if cfg.get(k): cfg[k] = os.path.normpath(os.path.join(base, os.path.expanduser(cfg[k])))
    cfg["status"] = os.path.join(base, "viewport_status.json")
    cfg.setdefault("title", os.path.basename(os.path.dirname(base)))
    return cfg
