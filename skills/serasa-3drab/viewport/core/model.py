"""
core/model.py - logika data viewport (tanpa HTTP, tanpa HTML).

Membaca file proyek yang sebenarnya:
  - input RAB (JSON, berisi volume + field `src` asal angka),
  - builder RAB (scripts/build_rab.py) -> baris & nomor baris persis seperti di Google Sheet,
  - cache tab AHS (ahs.json) untuk satuan & harga.
Menghasilkan satu dict "view model" yang dipakai viewport. Fungsi `load(cfg)` dipanggil ulang setiap kali file berubah.
"""
import importlib.util, json, os, re, time

KINDS = {
    "skp": "Model SKP",
    "rumus": "Rumus dari bukaan",
    "estimasi": "Estimasi (tidak dimodelkan)",
    "asumsi": "Asumsi",
    "denah": "Denah",
    "pending": "Pending",
    None: "Tanpa sumber",
}


def _rp(v):
    """'Rp1.234.567' / 1234.5 -> float"""
    if isinstance(v, (int, float)): return float(v)
    s = re.sub(r"[^0-9,.-]", "", str(v or "")).replace(".", "").replace(",", ".")
    try: return float(s)
    except ValueError: return 0.0


def _import_builder(path):
    spec = importlib.util.spec_from_file_location(f"serasa_builder_{int(time.time() * 1000)}", path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def _audit_prices(spec, ahs_by):
    """harga satuan analisa (tab Audit) = jumlah koef x harga komponen"""
    out = {}
    for a in spec.get("audit", []):
        tot, comps = 0.0, []
        for c in a["components"]:
            p = c["price"]
            if isinstance(p, str) and p.startswith("AHS:"):
                p = _rp(ahs_by.get(p[4:], {}).get("h"))
            sub = float(c["koef"]) * float(p); tot += sub
            comps.append({"name": c["name"], "sat": c["sat"], "koef": c["koef"], "price": p, "sub": sub, "src": c.get("src", "asumsi")})
        out[a["code"]] = {"price": tot, "name": a["name"], "sat": a["sat"], "note": a.get("note", ""), "components": comps}
    return out


GRP = re.compile(r"Group#\d+|Component#\d+")
DIRS = ("Barat", "Timur", "Utara", "Selatan")
# tipe finishing di input -> tipe tebakan muka di model (lihat SerasaRAB.fin_guess)
FACE_TYPES = {"ekspos": ["ekspos", "lain"], "putih": ["putih", "terracotta", "lain"], "terracotta": ["terracotta"]}


def _ids(src):
    """id objek SKP yang disebut sumber: nama definisi (Group#762) atau persistent id (21361376)."""
    out = []
    for g in (src or {}).get("groups", []) or []:
        m = GRP.search(str(g)) or re.match(r"\d{5,}", str(g))
        if m: out.append(m.group(0))
    for m in GRP.findall((src or {}).get("detail", "") or ""): out.append(m)
    return sorted(set(out))


def _wall_index(spec):
    """id(src) -> keterangan dinding, untuk menyorot muka per ruang x tipe di model 3D."""
    idx = {}
    for w in spec.get("walls", []):
        for t, s in (w.get("src") or {}).items():
            if isinstance(s, dict): idx[id(s)] = (w, t)
    return idx


def _highlight(src, wall):
    if (src or {}).get("pick"):  # sumber dipilih manual di viewport: daftar bagian "objek::tag"
        return {"ids": [], "tags": [], "room": None, "parts": src["pick"]}
    hl = {"ids": _ids(src), "tags": [], "room": None}
    terms = ((src or {}).get("bind") or {}).get("terms") or {}
    if terms.get("tags") and not wall:   # tautan model: sorot muka yang benar-benar dihitung (bukan seluruh objek)
        hl["tags"] = sorted({("E|" + "|".join(t.split("|")[3:])) if t.startswith("Q|") else t for t in terms["tags"]})
        if terms.get("ids"): hl["ids"] = [str(x) for x in terms["ids"]]; hl["tag_ids_only"] = True
        return hl
    if wall:
        w, t = wall; types = FACE_TYPES.get(t, [t])
        if w.get("interior"):
            hl["tags"] = [f"R|{w['room']}|{x}" for x in types]; hl["room"] = w["room"]
        else:
            d = next((x for x in DIRS if x in w["room"]), "*")
            hl["tags"] = [f"E|{d}|{x}" for x in types]
            hl["tag_ids_only"] = bool(hl["ids"])  # sorot muka luar hanya pada objek yang disebut
    return hl


def _unpushed(log):
    n = 0
    for e in reversed(log):
        if e["op"] == "push" and e["summary"].startswith("push ke Sheet berhasil"): break
        if not e.get("undone") and e["op"] not in ("push", "bind", "ahs"): n += 1
    return n


def share_key(loc):
    """baris yang memakai angka volume yang sama (dinding: ruang x tipe x lapisan layer_parts)."""
    if not loc: return None
    if loc[0] == "wall": return json.dumps([loc[0], loc[1], loc[2], loc[4] if len(loc) > 4 else None])
    return json.dumps(loc[:3])


def _status(cfg):
    try: return json.load(open(cfg["status"], encoding="utf-8"))
    except (OSError, ValueError, KeyError): return None


def _export_status(cfg):   # ditulis plugin SketchUp saat mengekspor model setelah Save
    try:
        st = json.load(open(os.path.join(cfg["_base"], "export_status.json"), encoding="utf-8"))
        if st.get("state") in ("running", "writing") and time.time() - time.mktime(time.strptime(st["at"], "%Y-%m-%d %H:%M:%S")) > 120:
            st["state"] = "stale"   # SketchUp ditutup di tengah ekspor
        return st
    except (OSError, ValueError, KeyError): return None


def empty(cfg, files):
    """proyek baru: input RAB belum ada -> viewport tetap tampil (model 3D + status kerja agen)."""
    return {"empty": True, "project": {"title": cfg.get("title", ""), "tab": "", "sheet_link": None}, "meta": {}, "status": _status(cfg), "export_status": _export_status(cfg),
            "luasan": None, "babs": [], "rows": [], "stats": {}, "kinds": {str(k): v for k, v in KINDS.items()}, "total": 0, "errors": [],
            "history": {"log": [], "notes": [], "can_undo": False, "open_notes": 0}, "push_ready": False, "unpushed": 0,
            "files": {k: {"path": v, "mtime": os.path.getmtime(v) if os.path.exists(v) else None} for k, v in files.items()},
            "model3d": {"url": "/api/model3d", "mtime": os.path.getmtime(files["model3d"])} if os.path.exists(files.get("model3d") or "") else None,
            "generated_at": time.strftime("%H:%M:%S")}


def load(cfg, base=None):
    files = {k: cfg[k] for k in ("input", "builder", "ahs", "model3d") if cfg.get(k)}
    if not os.path.exists(files.get("input") or "") or not os.path.exists(files.get("ahs") or ""): return empty(cfg, files)
    errors = []
    spec = json.load(open(files["input"], encoding="utf-8"))
    ahs_items = json.load(open(files["ahs"], encoding="utf-8"))
    B = _import_builder(files["builder"])
    b = B.Builder(spec, B.Ahs(ahs_items)).build()
    errors += b.errors
    ahs_by = {}
    for a in ahs_items: ahs_by.setdefault(a["u"], a)
    audit = _audit_prices(spec, ahs_by)
    walls = _wall_index(spec)

    rows, babs, cur = [], [], None
    for i, row in enumerate(b.rows):
        n = B.DS + i; c = row["c"]; k = row["k"]
        if k == "bab":
            cur = {"no": c[0], "title": c[1], "row": n, "total": 0.0, "count": 0, "pending": 0}; babs.append(cur); continue
        if k in ("blank", "total"): continue
        if k == "sub":
            rows.append({"row": n, "kind": "sub", "bab": cur["no"], "uraian": c[1], "loc": row.get("loc")}); continue
        r = {"row": n, "kind": k, "bab": cur["no"], "uraian": c[1], "ruang": c[2], "lantai": c[3],
             "spec": c[5], "vol": c[7] if isinstance(c[7], (int, float)) else None, "src": row.get("src")}
        r["hl"] = _highlight(r["src"], walls.get(id(row.get("src"))))
        loc = row.get("loc"); r["loc"] = loc
        it = spec["bab"][loc[1]]["rows"][loc[2]] if loc and loc[0] == "bab" else None
        r["can"] = {"vol": bool(loc) and k != "pending", "source": bool(loc) and k != "pending",
                    "spec": (bool(it) and it.get("type") == "ahs") or (bool(loc) and loc[0] == "wall" and loc[3] == "finish"),
                    "pending": bool(it) and (k != "pending" or "_was" in it)}
        r["manual"] = (r["src"] or {}).get("manual")
        r["bind"] = ((r["src"] or {}).get("bind") or {}).get("mode")
        r["conflict"] = (r["src"] or {}).get("conflict")
        if row.get("estimated"): r["estimated"] = True; r["quantity_note"] = row.get("quantity_note")
        if k == "ahs":
            a = ahs_by.get(c[5], {})
            r.update(code=a.get("c", "?"), sat=a.get("s", ""), price=_rp(a.get("h")), price_src="AHS")
        elif k in ("audit", "kusen"):
            code = c[4]; a = audit.get(code, {})
            r.update(code=code, sat=c[6], price=a.get("price", 0.0), price_src="Analisa (tab Audit)", analysis=a)
        else:  # pending / note
            r.update(code="-", sat="", price=None, price_src=None)
        r["total"] = (r["vol"] or 0) * (r["price"] or 0)
        if not r["uraian"]:  # uraian dikosongkan builder untuk baris lanjutan grup
            prev = next((x for x in reversed(rows) if x.get("uraian") and x["kind"] != "sub"), None)
            r["uraian_group"] = prev["uraian"] if prev else ""
        cur["total"] += r["total"]; cur["count"] += 1; cur["pending"] += k == "pending"
        if not r["src"] and k != "note": errors.append(f"baris {n}: volume tanpa sumber ({c[1] or c[2]})")
        rows.append(r)

    same = {}
    for r in rows:
        if r.get("loc"): same.setdefault(share_key(r["loc"]), []).append(r["row"])
    for r in rows:
        if r.get("loc"): r["shared"] = [x for x in same[share_key(r["loc"])] if x != r["row"]]

    tools = os.path.dirname(files["input"])
    rd = lambda f: json.load(open(os.path.join(tools, f), encoding="utf-8")) if os.path.exists(os.path.join(tools, f)) else []
    log, notes = rd("koreksi_log.json"), rd("koreksi_catatan.json")
    proj = dict(spec["project"]); proj.setdefault("title", cfg.get("title"))
    if cfg.get("ahs_sheet_url"): proj["ahs_link"] = cfg["ahs_sheet_url"]
    if cfg.get("sheet_url"):
        proj["sheet_link"] = cfg["sheet_url"].split("#")[0].split("?")[0] + (f"#gid={cfg['sheet_gid']}" if cfg.get("sheet_gid") is not None else "")

    stats = {}
    for r in rows:
        if r["kind"] == "sub": continue
        kk = (r.get("src") or {}).get("kind")
        st = stats.setdefault(kk or "none", {"label": KINDS.get(kk, kk), "rows": 0, "total": 0.0}); st["rows"] += 1; st["total"] += r["total"]

    result = {
        "history": {"log": log[-40:][::-1], "notes": notes[::-1], "can_undo": any(not e.get("undone") for e in log),
                    "open_notes": sum(n.get("status") == "open" for n in notes)},
        "push_ready": bool(cfg.get("spreadsheet_id") and cfg.get("creds")),
        "unpushed": _unpushed(log),
        "model_bind": bool((spec.get("meta") or {}).get("model_bind")),
        "ahs_state": rd(os.path.join(".koreksi", "ahs_state.json")) or None,
        "ahs_source": bool(cfg.get("ahs_source")),
        "project": proj, "meta": spec.get("meta", {}), "status": _status(cfg), "export_status": _export_status(cfg),
        "estimated": sum(1 for r in rows if r.get("estimated")),
        "luasan": spec["luasan"],
        "babs": babs, "rows": rows, "stats": stats, "kinds": {str(k): v for k, v in KINDS.items()},
        "total": sum(x["total"] for x in babs),
        "errors": errors,
        "files": {k: {"path": v, "mtime": os.path.getmtime(v) if os.path.exists(v) else None} for k, v in files.items()},
        "model3d": {"url": "/api/model3d", "mtime": os.path.getmtime(files["model3d"])} if os.path.exists(files.get("model3d", "")) else None,
        "generated_at": time.strftime("%H:%M:%S"),
    }
    if cfg.get("building_tabs"):   # RAB per bangunan (hanya bila diminta pengguna)
        from core.scopes import view
        result.update(view(spec, rows, babs, cfg, ahs_items))
    return result


def total_for_spec(spec, ahs_items, builder_path):
    """Use the same component prices and builder quantities as the viewport."""
    B=_import_builder(builder_path)
    builder=B.Builder(json.loads(json.dumps(spec)), B.Ahs(ahs_items)).build()
    by={}
    for a in ahs_items:by.setdefault(a['u'],a)
    audit=_audit_prices(spec,by)
    total=0.0
    for row in builder.rows:
        c=row['c'];kind=row['k']
        if kind=='ahs':price=_rp(by.get(c[5],{}).get('h'))
        elif kind in ('audit','kusen'):price=audit.get(c[4],{}).get('price',0)
        else:continue
        total+=float(c[7] or 0)*price
    return total
