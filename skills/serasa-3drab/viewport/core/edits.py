"""
core/edits.py - koreksi RAB dari viewport (tanpa HTTP).

Semua perubahan ditulis LANGSUNG ke file input RAB (jadi builder, viewport dan push ke Sheet memakai data yang sama),
dengan pengaman:
  - snapshot input sebelum tiap perubahan  -> _serasa_tools/.koreksi/<waktu>_<op>.json  (dipakai undo)
  - log perubahan                         -> _serasa_tools/koreksi_log.json
  - catatan koreksi untuk dikerjakan Claude -> _serasa_tools/koreksi_catatan.json
Volume yang diubah manual ditandai di src["manual"] (nilai asli dari model tetap disimpan).
"""
import csv, io, json, os, re, shutil, subprocess, sys, time, urllib.request

MAX_SNAP = 60


def _now(): return time.strftime("%Y-%m-%d %H:%M:%S")


class Editor:
    def __init__(self, cfg, base):
        p = lambda k: os.path.normpath(os.path.join(base, cfg[k]))
        self.cfg, self.base, self.input, self.builder = cfg, base, p("input"), p("builder")
        self.ahs = p("ahs") if cfg.get("ahs") else None
        tools = os.path.dirname(self.input)
        self.snapdir = os.path.join(tools, ".koreksi")
        self.logf = os.path.join(tools, "koreksi_log.json")
        self.notesf = os.path.join(tools, "koreksi_catatan.json")

    # ---------------------------------------------------------------- file
    def _read(self, f, default):
        try: return json.load(open(f, encoding="utf-8"))
        except (OSError, ValueError): return default

    def _write(self, f, data):
        tmp = f + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh: json.dump(data, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, f)  # atomik: watcher tidak pernah membaca file setengah jadi

    def spec(self): return self._read(self.input, None)

    def _commit(self, spec, op, row, summary, details=None, target=None):
        target = target or self.input
        os.makedirs(self.snapdir, exist_ok=True)
        snap = os.path.join(self.snapdir, time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}_{op}.json")
        shutil.copy2(target, snap)
        self._write(target, spec)
        log = self._read(self.logf, [])
        e = {"id": len(log) + 1, "at": _now(), "op": op, "row": row.get("row") if row else None,
             "uraian": (row or {}).get("uraian") or (row or {}).get("uraian_group"), "summary": summary,
             "snap": os.path.basename(snap), "undone": False}
        if target != self.input: e["target"] = os.path.basename(target)
        if details: e["details"] = details
        log.append(e)
        self._write(self.logf, log)
        snaps = sorted(os.listdir(self.snapdir))  # batasi jumlah snapshot
        for old in snaps[:-MAX_SNAP]: os.remove(os.path.join(self.snapdir, old))
        return {"ok": True, "summary": summary}

    # ---------------------------------------------------------------- target baris -> tempat di input
    @staticmethod
    def _target(spec, loc):
        if not loc: raise ValueError("baris ini dihitung otomatis (mis. openingan) dan tidak bisa diedit langsung")
        k = loc[0]
        if k == "bab":
            it = spec["bab"][loc[1]]["rows"][loc[2]]
            return it, "vol", it
        if k == "wall":
            w = spec["walls"][loc[1]]
            layer = loc[4] if len(loc) > 4 else None          # layer_parts[lapisan] menimpa parts untuk lapisan itu
            return (w["layer_parts"][layer] if layer else w["parts"]), loc[2], w.setdefault("src", {})
        if k == "open":
            o = spec["openings"][loc[1]]
            return o, "vol", o
        raise ValueError(f"lokasi tidak dikenal: {loc}")

    @staticmethod
    def _src(holder, loc):
        if loc[0] == "wall":
            return holder.setdefault(loc[2], {"kind": "skp"})
        return holder.setdefault("src", {"kind": "asumsi"})

    # ---------------------------------------------------------------- operasi
    def apply(self, req, rows_by_no):
        op = req.get("op")
        if op == "undo": return self.undo()
        if op == "note": return self.add_note(req, rows_by_no.get(req.get("row")))
        if op == "note_done": return self.note_done(req.get("id"), req.get("done", True))
        if op == "ahs_update": return self.ahs_update()
        if op == "sheet_check": return self.sheet_check()
        if op == "sheet_pull": return self.sheet_pull(req.get("take") or [])
        if op == "bind": return self.bind(rows_by_no, force=True)
        row = rows_by_no.get(req.get("row"))
        if not row: raise ValueError("baris tidak ditemukan")
        spec = self.spec(); loc = row.get("loc")
        if op == "vol":
            cont, key, holder = self._target(spec, loc)
            v = float(req["value"]); old = cont.get(key)
            cont[key] = round(v, 4)
            s = self._src(holder, loc)
            m = s.setdefault("manual", {"vol_asli": old})
            m.update(at=_now(), note=req.get("note", ""))
            if m.get("vol_asli") == cont[key]: s.pop("manual")  # dikembalikan ke angka asli
            return self._commit(spec, op, row, f"volume {old} → {cont[key]}")
        if op == "spec":
            new = req["spec"]
            if self.ahs and new not in {a["u"] for a in self._read(self.ahs, [])}: raise ValueError("spec tidak ada di tab AHS")
            if loc and loc[0] == "wall" and loc[3] == "finish":   # finishing dinding: spec khusus dinding ini
                w = spec["walls"][loc[1]]; fs = w.setdefault("finish_spec", {}); old = fs.get(loc[2]) or row.get("spec") or ""
                fs[loc[2]] = new
                return self._commit(spec, op, row, f"spec finishing '{old[:40]}' → '{new[:40]}'")
            if not loc or loc[0] != "bab": raise ValueError("spec plester/aci berlaku untuk semua dinding — ubah lewat catatan untuk Claude")
            it = spec["bab"][loc[1]]["rows"][loc[2]]
            if it.get("type") != "ahs": raise ValueError("spec hanya untuk baris tipe AHS")
            old = it["spec"]; it["spec"] = new
            return self._commit(spec, op, row, f"spec '{old[:40]}' → '{new[:40]}'")
        if op == "pending":
            if not loc or loc[0] != "bab": raise ValueError("hanya baris di bab (bukan dinding/kusen) yang bisa dijadikan pending")
            rows = spec["bab"][loc[1]]["rows"]; it = rows[loc[2]]
            if req.get("on", True):
                if it["type"] == "pending": raise ValueError("baris sudah pending")
                rows[loc[2]] = {"type": "pending", "uraian": it.get("uraian", ""), "ruang": it.get("ruang", ""), "lantai": it.get("lantai", ""),
                                "reason": req.get("reason") or "dikoreksi dari viewport", "src": {"kind": "pending", "detail": req.get("reason", "")}, "_was": it}
                return self._commit(spec, op, row, "dijadikan pending")
            if "_was" not in it: raise ValueError("baris pending ini tidak punya data asal; isi lewat Claude (catatan koreksi)")
            rows[loc[2]] = it["_was"]
            return self._commit(spec, op, row, "pending dibatalkan")
        if op == "source":
            cont, key, holder = self._target(spec, loc)
            s = self._src(holder, loc)
            parts = sorted(set(req.get("parts") or []))
            if parts:
                s["pick"] = parts; s["kind"] = "skp"
            else:
                s.pop("pick", None)
            summary = f"sumber model: {len(parts)} bagian"
            if req.get("use_area") and req.get("area"):
                old = cont.get(key); cont[key] = round(float(req["area"]), 2)
                m = s.setdefault("manual", {"vol_asli": old}); m.update(at=_now(), note=f"luas {len(parts)} bagian model dipilih di viewport")
                summary += f", volume {old} → {cont[key]}"
            return self._commit(spec, op, row, summary)
        if op == "conflict":   # pilih angka model atau tetap angka manual
            cont, key, holder = self._target(spec, loc)
            s = self._src(holder, loc); c = s.get("conflict")
            if not c: raise ValueError("baris ini tidak sedang bentrok")
            if req.get("use") == "model":
                old = cont.get(key); cont[key] = c["model"]; s.pop("manual", None); s.pop("conflict", None)
                return self._commit(spec, op, row, f"pakai angka model {old} → {c['model']}")
            s.pop("conflict", None); s["manual"]["model_diabaikan"] = c["model"]
            return self._commit(spec, op, row, f"tetap angka manual (model {c['model']} diabaikan)")
        raise ValueError(f"operasi tidak dikenal: {op}")

    # ---------------------------------------------------------------- model SketchUp -> RAB
    def _tb(self):
        from core import sync
        p = self.cfg["model3d"]
        return sync, sync.table(p)

    def bind(self, rows_by_no, force=False):
        sync, tb = self._tb()
        spec = self.spec()
        rep = sync.bind(spec, list(rows_by_no.values()), tb, force=force)
        n = sum(len(v) for k, v in rep.items() if k != "skip")
        return self._commit(spec, "bind", None, f"{n} baris ditautkan ke model ({len(rep['direct'])} langsung, {len(rep['ratio'])} proporsional, {len(rep['count'])} hitung unit)", details=rep)

    def model_sync(self, rows):
        """dipanggil server saat file ekspor SketchUp berubah."""
        sync, tb = self._tb()
        spec = self.spec()
        if not (spec.get("meta") or {}).get("model_bind"): return None
        changes, conflicts, notes = sync.apply_model(spec, rows, tb)
        for r, obj, text in notes: self.add_note({"row": r["row"] if r else None, "object": obj, "text": text, "auto": True}, r)
        if not changes and not conflicts:
            return None
        parts = []
        if changes: parts.append(f"{len(changes)} baris berubah")
        if conflicts: parts.append(f"{len(conflicts)} bentrok dengan koreksi manual")
        return self._commit(spec, "model", None, f"Model SKP disimpan ({tb['exported']}): " + ", ".join(parts),
                            details={"changes": changes, "conflicts": conflicts})

    # ---------------------------------------------------------------- AHS dari sheet Analisa Harga Satuan (link publik)
    @staticmethod
    def _rp(s):
        n = re.sub(r"\D", "", s or "")
        return "Rp" + f"{int(n):,}".replace(",", ".") if n else (s or "")

    def _fetch(self, url):
        try:
            with urllib.request.urlopen(url, timeout=30) as r: return r.read().decode("utf-8")
        except Exception:   # mis. sertifikat SSL Python di macOS -> pakai curl bawaan sistem
            r = subprocess.run(["curl", "-sSL", "--max-time", "30", url], capture_output=True, text=True)
            if r.returncode != 0: raise ValueError(f"gagal mengambil AHS: {r.stderr.strip()[:200]}")
            return r.stdout

    def ahs_update(self):
        url = self.cfg.get("ahs_source")
        if not url: raise ValueError("config.json belum berisi ahs_source")
        text = self._fetch(url)
        if text.lstrip().startswith("<"):
            raise ValueError("sheet Analisa Harga Satuan belum bisa dibaca publik — set Share > 'Anyone with the link: Viewer'")
        rows = list(csv.reader(io.StringIO(text)))
        head = [h.strip().lower() for h in rows[0]]
        if head[:5] != ["uraian", "kategori", "satuan", "harga", "kode"]: raise ValueError(f"kolom sheet AHS tidak dikenali: {rows[0][:5]}")
        new = [{"u": r[0].strip(), "k": r[1].strip(), "s": r[2].strip(), "h": self._rp(r[3]), "c": r[4].strip()} for r in rows[1:] if len(r) >= 5 and r[0].strip()]
        if len(new) < 100: raise ValueError(f"isi sheet AHS terlalu sedikit ({len(new)} baris) — dibatalkan")
        old = self._read(self.ahs, [])
        om = {a["u"]: a for a in old}; nm = {a["u"]: a for a in new}
        changed = [{"u": u, "c": nm[u]["c"], "old": om[u]["h"], "new": nm[u]["h"]} for u in nm if u in om and (om[u]["h"], om[u]["c"], om[u]["s"]) != (nm[u]["h"], nm[u]["c"], nm[u]["s"])]
        added = [u for u in nm if u not in om]; removed = [u for u in om if u not in nm]
        st = os.path.join(os.path.dirname(self.input), ".koreksi", "ahs_state.json")
        os.makedirs(os.path.dirname(st), exist_ok=True)
        self._write(st, {"checked": _now(), "count": len(new)})
        if not (changed or added or removed):
            return {"ok": True, "summary": f"AHS sudah terbaru ({len(new)} spec)", "unchanged": True}
        used = {it.get("spec") for b in (self.spec() or {}).get("bab", []) for it in b.get("rows", [])}
        hit = [c for c in changed if c["u"] in used] + [{"u": u, "removed": True} for u in removed if u in used]
        summary = f"AHS diperbarui: {len(changed)} harga/kode berubah, {len(added)} spec baru, {len(removed)} dihapus"
        if hit: summary += f" · {len(hit)} dipakai di RAB ini"
        return self._commit(new, "ahs", None, summary, details={"changed": changed[:200], "added": added[:200], "removed": removed[:200], "used": hit}, target=self.ahs)

    # ---------------------------------------------------------------- Google Sheet -> web
    def _paths(self):
        tools = os.path.dirname(self.input)
        return os.path.join(tools, ".koreksi", "pushed_input.json"), os.path.join(tools, ".koreksi", "sheet_base.json")

    def _base_spec(self):
        """input seperti saat push terakhir."""
        pushed, _ = self._paths()
        if os.path.exists(pushed): return self._read(pushed, None)
        log = self._read(self.logf, [])
        last = max([i for i, e in enumerate(log) if e["op"] == "push" and e["summary"].startswith("push ke Sheet berhasil")] + [-1])
        for e in log[last + 1:]:
            if e.get("snap") and not e.get("target"):
                p = os.path.join(self.snapdir, e["snap"])
                if os.path.exists(p): return self._read(p, None)
        return self.spec()

    def _creds(self):
        c = self.cfg
        if not (c.get("spreadsheet_id") and c.get("creds")): raise ValueError("config.json belum berisi spreadsheet_id / creds")
        return os.path.normpath(os.path.join(self.base, os.path.expanduser(c["creds"])))

    def sheet_check(self):
        from core import sheetsync as SS
        spec = self.spec(); ahs = self._read(self.ahs, [])
        web, ds = SS.build_rows(self.builder, spec, ahs)
        _, sbase = self._paths()
        base = self._read(sbase, None) if os.path.exists(sbase) else SS.build_rows(self.builder, self._base_spec(), ahs)[0]
        vals = SS.read_tab(self._creds(), self.cfg["spreadsheet_id"], spec["project"]["tab"], ds, max(len(web), len(base)))
        sheet = SS.sheet_rows(vals, ds)
        d = SS.diff(base, sheet, web)
        d.update(ok=True, tab=spec["project"]["tab"], summary=f"{len(d['items'])} perubahan di Sheet, {len(d['struct'])} baris ditambah/dihapus" if (d["items"] or d["struct"]) else "Sheet sama dengan push terakhir")
        self._last_sheet = sheet
        return d

    def sheet_pull(self, take):
        d = self.sheet_check(); sheet = self._last_sheet
        spec = self.spec(); take = set(take); done, skipped = [], []
        ahs_u = {a["u"] for a in self._read(self.ahs, [])}
        by_loc = {}
        for it in d["items"]:
            if it["id"] in take: by_loc.setdefault(json.dumps(it["loc"]), []).append(it)
        for k, its in by_loc.items():
            loc = json.loads(k)
            if not loc: skipped += [f"baris {i['sheet_row']} {i['field']}: tidak bisa dipetakan" for i in its]; continue
            cols = {i["col"]: i for i in its}
            if loc[0] == "bab":
                rows = spec["bab"][loc[1]]["rows"]; it = rows[loc[2]]
                if it["type"] == "pending" and "F" in cols:      # baris pending diisi di Sheet
                    sp = cols["F"]["sheet"]
                    if sp not in ahs_u: skipped.append(f"baris {cols['F']['sheet_row']}: spec '{sp[:40]}' tidak ada di AHS"); continue
                    vol = cols["H"]["sheet"] if "H" in cols else None
                    rows[loc[2]] = {"type": "ahs", "uraian": it.get("uraian", ""), "ruang": cols["C"]["sheet"] if "C" in cols else it.get("ruang", ""),
                                    "lantai": it.get("lantai", ""), "spec": sp, "vol": vol or 0,
                                    "src": {"kind": "asumsi", "detail": "Diisi langsung di Google Sheet", "sheet": {"at": _now()}}, "_was": it}
                    done += list(cols.values()); continue
                for col, i in cols.items():
                    if col == "H": it["vol"] = i["sheet"]
                    elif col == "F":
                        if i["sheet"] not in ahs_u and it.get("type") == "ahs": skipped.append(f"baris {i['sheet_row']}: spec tidak ada di AHS"); continue
                        it["spec"] = i["sheet"]
                    elif col == "C": it["ruang"] = i["sheet"]
                    elif col == "D": it["lantai"] = i["sheet"]
                    done.append(i)
                if "H" in cols:
                    s = it.setdefault("src", {"kind": "asumsi"})
                    m = s.setdefault("manual", {"vol_asli": cols["H"]["base"]}); m.update(at=_now(), note="diubah di Google Sheet")
                continue
            if loc[0] in ("wall", "open"):
                cont, key, holder = self._target(spec, loc)
                for col, i in cols.items():
                    if col == "H":
                        cont[key] = i["sheet"]; s = self._src(holder, loc)
                        m = s.setdefault("manual", {"vol_asli": i["base"]}); m.update(at=_now(), note="diubah di Google Sheet"); done.append(i)
                    elif col == "F" and loc[0] == "wall" and loc[3] == "finish" and i["sheet"] in ahs_u:
                        spec["walls"][loc[1]].setdefault("finish_spec", {})[loc[2]] = i["sheet"]; done.append(i)
                    else: skipped.append(f"baris {i['sheet_row']} {i['field']}: ubah lewat viewport/Claude")
        for st in d["struct"]:
            txt = (f"Di Google Sheet ada baris baru (baris {st['sheet_row']}): {st['uraian']} · {st['ruang']} · {st.get('spec') or ''} · vol {st.get('vol')}"
                   if st["type"] == "tambah" else f"Di Google Sheet baris '{st['uraian']} · {st['ruang']}' dihapus")
            self.add_note({"text": txt + " — masukkan ke input RAB atau abaikan.", "auto": True}, None)
        _, sbase = self._paths()
        os.makedirs(os.path.dirname(sbase), exist_ok=True); self._write(sbase, sheet)   # editan Sheet sudah ditinjau
        if not done:
            return {"ok": True, "summary": "Tidak ada perubahan yang diambil" + (f" ({len(skipped)} dilewati)" if skipped else ""), "skipped": skipped}
        return self._commit(spec, "sheet", None, f"Tarik dari Sheet: {len(done)} perubahan diambil" + (f", {len(skipped)} dilewati" if skipped else ""),
                            details={"items": [{k: i[k] for k in ("sheet_row", "field", "uraian", "ruang", "base", "sheet")} for i in done], "skipped": skipped})

    def unpushed(self):
        n = 0
        for e in reversed(self._read(self.logf, [])):
            if e["op"] == "push" and e["summary"].startswith("push ke Sheet berhasil"): break
            if not e.get("undone") and e["op"] not in ("push", "bind", "ahs"): n += 1
        return n

    def undo(self):
        log = self._read(self.logf, [])
        last = next((e for e in reversed(log) if not e.get("undone")), None)
        if not last: raise ValueError("tidak ada perubahan untuk di-undo")
        snap = os.path.join(self.snapdir, last["snap"])
        if not os.path.exists(snap): raise ValueError("snapshot sudah terhapus")
        dest = os.path.join(os.path.dirname(self.input), last["target"]) if last.get("target") else self.input
        shutil.copy2(snap, dest + ".tmp"); os.replace(dest + ".tmp", dest)
        last["undone"] = True; last["undone_at"] = _now()
        self._write(self.logf, log)
        return {"ok": True, "summary": f"undo: {last['summary']} (baris {last['row']})"}

    # ---------------------------------------------------------------- catatan (dikerjakan Claude)
    def add_note(self, req, row):
        text = (req.get("text") or "").strip()
        if not text: raise ValueError("catatan kosong")
        notes = self._read(self.notesf, [])
        if any(n["status"] == "open" and n["text"] == text for n in notes): return {"ok": True, "summary": "catatan sudah ada"}
        notes.append({"auto": bool(req.get("auto")), "id": max([n["id"] for n in notes] + [0]) + 1, "at": _now(), "row": req.get("row"),
                      "uraian": (row or {}).get("uraian") or (row or {}).get("uraian_group"), "ruang": (row or {}).get("ruang"),
                      "object": req.get("object"), "text": text, "status": "open"})
        self._write(self.notesf, notes)
        return {"ok": True, "summary": "catatan disimpan"}

    def note_done(self, nid, done=True):
        notes = self._read(self.notesf, [])
        for n in notes:
            if n["id"] == nid: n["status"] = "done" if done else "open"; n["done_at"] = _now()
        self._write(self.notesf, notes)
        return {"ok": True, "summary": "catatan diperbarui"}

    def history(self):
        return {"log": self._read(self.logf, [])[-50:][::-1], "notes": self._read(self.notesf, [])[::-1]}

    # ---------------------------------------------------------------- push ke Google Sheet
    def push(self, force=False, rebuild=False):
        if not force:
            d = self.sheet_check()
            if d["items"] or d["struct"]:
                d.update(ok=False, review=True, summary="Ada editan langsung di Google Sheet — tinjau dulu sebelum menimpa")
                return d
        c = self.cfg
        if not (c.get("spreadsheet_id") and c.get("creds")): raise ValueError("config.json belum berisi spreadsheet_id / creds")
        creds = os.path.normpath(os.path.join(self.base, os.path.expanduser(c["creds"])))
        if not os.path.exists(creds): raise ValueError("file kredensial service account tidak ditemukan")
        # patch = hanya baris yang berubah (format manual di baris lain aman); none = bangun ulang tab (hanya bila struktur berubah & disetujui)
        cmd = [sys.executable, self.builder, self.input, "--push", "--creds", creds, "--spreadsheet", c["spreadsheet_id"], "--prepare", "none" if rebuild else "patch"]
        t0 = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=os.path.dirname(self.input))
        out = (r.stdout + ("\n" + r.stderr if r.stderr.strip() else "")).strip()
        if r.returncode == 3:   # struktur RAB berubah -> perlu bangun ulang tab, minta persetujuan dulu
            return {"ok": False, "rebuild_needed": True, "summary": "Struktur RAB berubah (baris ditambah/dihapus/bab bergeser). Push penuh akan membangun ulang tab RAB & Audit — format manual di tab itu hilang."}
        if "No module named 'google" in out:
            out = "Library Google belum terpasang untuk Python ini. Jalankan di Terminal:\n" \
                  f"{sys.executable} -m pip install --user google-api-python-client google-auth\n\n" + out[-800:]
        if r.returncode == 0:   # dasar perbandingan berikutnya = input yang barusan di-push
            pushed, sbase = self._paths(); os.makedirs(os.path.dirname(pushed), exist_ok=True)
            shutil.copy2(self.input, pushed)
            if os.path.exists(sbase): os.remove(sbase)
        log = self._read(self.logf, [])
        log.append({"id": len(log) + 1, "at": _now(), "op": "push", "row": None, "uraian": None,
                    "summary": ("push ke Sheet berhasil" if r.returncode == 0 else "push GAGAL") + f" ({time.time() - t0:.0f} dtk)", "snap": None, "undone": True})
        self._write(self.logf, log)
        return {"ok": r.returncode == 0, "summary": out[-3000:]}
