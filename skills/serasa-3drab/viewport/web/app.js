// app.js - UI viewport RAB: tabel + inspector + koreksi + sambungan ke tampilan 3D.
// Data: /api/project (core/model.py), /api/model3d (core/mesh.py). Koreksi: POST /api/edit, /api/push (core/edits.py).
import { Viewer3D } from "/viewer3d.js";

const $ = (s) => document.querySelector(s);
const S = { data: null, bab: null, kind: null, q: "", sel: null, pick: null, prevVals: {}, meshMtime: null, view: "detail", edit: null, ahs: null, busy: false, again: false };
const rp = (v) => v == null ? "" : "Rp" + Math.round(v).toLocaleString("id-ID");
const num = (v) => v == null ? "" : Number(v).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const kindOf = (r) => (r.src && r.src.kind) || "none";
const badge = (k, label) => `<span class="src"><i class="k-${k}"></i>${esc(label || k)}</span>`;
const unitHtml = (v, u) => `${esc(v)}${u ? `<small>${esc(u)}</small>` : ""}`;
const kindLabel = (k) => S.data.kinds[k === "none" ? "None" : k] || k;
const SHORT = { skp: "SKP", rumus: "Rumus", estimasi: "Estimasi", asumsi: "Asumsi", denah: "Denah", pending: "Pending", none: "—" };
const hasHl = (r) => r.hl && ((r.hl.ids || []).length || (r.hl.tags || []).length || (r.hl.parts || []).length);
const rowOf = (n) => S.data && S.data.rows.find((x) => x.row === n);
const title = (r) => r.uraian || r.uraian_group || "";

const viewer = new Viewer3D($("#canvas"), {
  onPick: (p) => { S.pick = p; S.sel = null; S.view = "detail"; render(); if (!p) { viewer.highlight(null, false); $("#hud").innerHTML = ""; } },
  onEdit: (keys, area) => { S.edit.keys = keys; S.edit.area = area; editBar(); },
});

// ---------------------------------------------------------------- data
async function loadMesh() {
  const res = await fetch("/api/model3d", { cache: "no-store" });
  if (!res.ok) { $("#nomodel").hidden = false; return; }
  $("#nomodel").hidden = true;
  S.mesh = viewer.load(await res.arrayBuffer());
  $("#cut").innerHTML = `<button data-cut="" class="on">Utuh</button>` +
    (S.mesh.bands || []).filter((b) => b[0] !== "Parapet").map((b) => `<button data-cut="${Math.round(b[1] + 1300)}">Potong ${esc(b[0])}</button>`).join("");
  usage(); render(); if (S.sel) select(S.sel, false);
}

async function load(flash) {
  if (S.busy) { S.again = true; return; }   // gabungkan beberapa event perubahan jadi satu muat ulang
  S.busy = true;
  try {
    let d;
    try { d = await (await fetch("/api/project", { cache: "no-store" })).json(); }
    catch (e) { setLive(false, "server tidak terjangkau"); return; }
    if (d.fatal) { document.body.innerHTML = `<div class="fatal"><b>Error memuat proyek</b> (${esc(d.generated_at)})\n\n${esc(d.fatal)}\n\n${esc(d.trace)}</div>`; return; }
    if (d.noproject) { document.body.innerHTML = `<div class="noproj"><b>Viewport RAB Serasa</b><p>Belum ada proyek aktif. Buka model SKP proyek di SketchUp lalu pilih <i>Extensions › Serasa › Buka Viewport RAB</i>, atau jalankan skill serasa-3drab.</p></div>`; return; }
    const changed = new Set(), key = (r) => r.row + "|" + r.vol + "|" + r.price + "|" + r.ruang + "|" + kindOf(r);
    if (flash && S.data) for (const r of d.rows) if (!S.prevVals[key(r)]) changed.add(r.row);
    S.prevVals = {}; for (const r of d.rows) S.prevVals[key(r)] = 1;
    S.data = d; render(changed); usage();
    const mt = d.model3d && d.model3d.mtime;
    if (mt !== S.meshMtime) { S.meshMtime = mt; loadMesh(); }
    else if (S.sel && !S.edit) select(S.sel, false);
  } finally {
    S.busy = false; if (S.again) { S.again = false; load(true); }
  }
}

function usage() {
  if (!S.data) return;
  const u = new Set();
  for (const r of S.data.rows) if (r.hl && r.kind !== "pending") for (const k of ["ids", "tags", "parts"]) (r.hl[k] || []).forEach((x) => u.add(x));
  viewer.setUsage(u);
}

async function post(url, body) {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const j = await res.json().catch(() => ({ ok: false, error: "respons tidak valid" }));
  if (!res.ok || j.ok === false) throw new Error(j.error || j.summary || "gagal");
  return j;
}

async function edit(body, okMsg) {
  try { const j = await post("/api/edit", body); toast(okMsg || j.summary, "ok"); return true; }
  catch (e) { toast(e.message, "err"); return false; }
}

// ---------------------------------------------------------------- render
function render(changed = new Set()) {
  const d = S.data; if (!d) return; const p = d.project;
  $("#p-title").textContent = p.title;
  $("#p-sub").textContent = d.empty ? `${d.project_path || ""}` + (S.mesh ? ` · ekspor 3D ${S.mesh.exported}` : "")
    : `Tab "${p.tab}" · model ${d.meta.model || "-"} · take-off ${d.meta.takeoff_date || "-"}` + (S.mesh ? ` · ekspor 3D ${S.mesh.exported}` : "");
  agentStatus(d.status);
  const dl = $("#design"); dl.hidden = !d.design || d.design.ok; if (d.design && !d.design.ok) dl.textContent = `Tampilan viewport berbeda dari versi resmi (${d.design.changed.join(", ")}). Pasang ulang skill serasa-3drab.`;
  document.body.classList.toggle("is-empty", !!d.empty);
  if (d.empty) {
    $("#total").textContent = "—"; ["#sheet", "#push", "#pull", "#undo", "#hist"].forEach((s) => ($(s).hidden = true));
    $("#cards").innerHTML = `<div class="stat"><div class="v">—</div><div class="k">RAB sedang disusun</div><div class="s">tabel muncul begitu input RAB ditulis</div></div>`;
    $("#babs").innerHTML = $("#kinds").innerHTML = ""; $("#files").innerHTML = "";
    $("#rows").innerHTML = `<tr><td colspan="8" class="placeholder">RAB belum ada. Model 3D sudah bisa dilihat; baris RAB muncul otomatis saat agen menulis input.</td></tr>`;
    $("#count").textContent = ""; return;
  }
  ["#pull", "#undo", "#hist"].forEach((s) => ($(s).hidden = false));
  $("#total").textContent = rp(d.total);
  const sh = $("#sheet"); sh.hidden = !p.sheet_link; if (p.sheet_link) sh.href = p.sheet_link;
  $("#push").hidden = !d.push_ready;
  if (!S.pushing) $("#push").innerHTML = d.unpushed ? `Push ke Sheet <span class="cnt">${d.unpushed}</span>` : "Push ke Sheet";
  $("#push").title = d.unpushed ? `${d.unpushed} perubahan belum dikirim ke Google Sheet` : "Sheet sudah sama dengan viewport";
  const top = d.history.log[0];
  if (top && S.lastLog !== undefined && top.id !== S.lastLog && (top.op === "model" || top.op === "ahs")) toast(top.summary, top.op === "model" && top.details && top.details.conflicts && top.details.conflicts.length ? "warn" : "ok");
  S.lastLog = top ? top.id : null;
  $("#undo").disabled = !d.history.can_undo;
  const on = d.history.open_notes; $("#hist .n").textContent = on || ""; $("#hist .n").hidden = !on;

  const L = d.luasan, lt = L.lantai.map((x) => x.items.reduce((a, b) => a + b[1], 0));
  const pend = d.rows.filter((r) => r.kind === "pending").length, manual = d.rows.filter((r) => r.manual).length;
  $("#cards").innerHTML = [
    ["Luas tapak", num(L.tanah), "m²", (L.src && L.src.tanah && L.src.tanah.calc) || ""],
    ...L.lantai.map((x, i) => [x.short, num(lt[i]), "m²", x.items.map((it) => `${it[0]} ${num(it[1])}`).join(" + ")]),
    ["Baris dari model", d.rows.filter((r) => hasHl(r) && r.kind !== "pending").length, "", "bisa ditunjuk di 3D"],
    ["Pending", pend, "", "menunggu data (belum di SKP)", "warn"],
    ...(d.estimated ? [["Volume estimasi", d.estimated, "", "kuning — isi ukuran final", "est"]] : []),
    ...(manual ? [["Koreksi manual", manual, "", "volume diubah di viewport", "edit"]] : []),
  ].map(([k, v, u, s, c]) => `<div class="stat ${c || ""}" title="${esc(s)}"><div class="v">${unitHtml(v, u)}</div><div class="k">${esc(k)}</div><div class="s">${esc(s)}</div></div>`).join("");

  $("#babs").innerHTML = `<li data-bab="" class="${S.bab ? "" : "active"}"><span>Semua bab</span><span class="n">${d.rows.filter((r) => r.kind !== "sub").length}</span></li>` +
    d.babs.map((b) => `<li data-bab="${esc(b.no)}" class="${S.bab === b.no ? "active" : ""}"><span>${esc(b.no)}. ${esc(b.title.replace(/^Pekerjaan /, ""))}</span><span class="n">${b.pending ? "⏳" : ""}</span></li>`).join("");
  $("#kinds").innerHTML = `<li data-kind="" class="${S.kind ? "" : "active"}"><span>Semua</span></li>` +
    Object.entries(d.stats).map(([k, s]) => `<li data-kind="${k}" class="${S.kind === k ? "active" : ""}"><span><i class="dot-k k-${k}"></i>${esc(s.label)}</span><span class="n">${s.rows}</span></li>`).join("") +
    (manual ? `<li data-kind="manual" class="${S.kind === "manual" ? "active" : ""}"><span><i class="dot-k k-manual"></i>Koreksi manual</span><span class="n">${manual}</span></li>` : "");
  $("#files").innerHTML = Object.entries(d.files).map(([k, f]) => `<li><b>${esc(k)}</b><br>${esc(f.path.split(/[\\/]/).slice(-2).join("/"))}<br>${f.mtime ? "diubah " + new Date(f.mtime * 1000).toLocaleTimeString("id-ID") : "belum ada"}</li>`).join("");

  const errs = (d.errors || []).filter((e) => !e.startsWith("PERINGATAN"));
  $("#errors").hidden = !errs.length; $("#errors").textContent = errs.join("\n");

  const q = S.q.toLowerCase();
  const match = (r) => !q || [r.uraian, r.uraian_group, r.ruang, r.spec, r.code, r.src && r.src.detail, r.src && (r.src.groups || []).join(" ")]
    .some((x) => String(x || "").toLowerCase().includes(q));
  const kindOk = (r) => !S.kind || (S.kind === "manual" ? !!r.manual : kindOf(r) === S.kind);
  const pickRows = S.pick ? new Set(rowsForPick(S.pick).map((r) => r.row)) : null;
  let html = "", shown = 0;
  for (const b of d.babs) {
    if (S.bab && S.bab !== b.no) continue;
    const rs = d.rows.filter((r) => r.bab === b.no && (r.kind === "sub" || (kindOk(r) && match(r) && (!pickRows || pickRows.has(r.row)))));
    if (!rs.some((r) => r.kind !== "sub")) continue;
    for (let i = rs.length - 1; i >= 0; i--)  // buang sub-judul yang tidak punya baris setelah difilter
      if (rs[i].kind === "sub" && (i === rs.length - 1 || rs[i + 1].kind === "sub")) rs.splice(i, 1);
    html += `<tr class="bab"><td class="c-row">${b.row}</td><td colspan="5">${esc(b.no)} · ${esc(b.title)}</td><td class="c-num">${rp(b.total)}</td><td></td></tr>`;
    for (const r of rs) {
      if (r.kind === "sub") { html += `<tr class="sub"><td class="c-row">${r.row}</td><td colspan="7">${esc(r.uraian)}</td></tr>`; continue; }
      shown++;
      const k = kindOf(r), cls = ["row", r.kind === "pending" ? "pending" : "", S.sel === r.row ? "sel" : "", changed.has(r.row) ? "flash" : ""].join(" ");
      const ur = r.uraian ? esc(r.uraian) : `<span class="ur-cont">↳ ${esc(r.uraian_group || "")}</span>`;
      html += `<tr class="${cls}" data-row="${r.row}"><td class="c-row">${r.row}</td><td>${ur}</td><td>${esc(r.ruang)}</td><td class="c-code">${esc(r.code)}</td>
        <td class="c-num${r.estimated ? " est" : ""}"${r.estimated ? ` title="${esc(r.quantity_note || "volume estimasi")}"` : ""}>${num(r.vol)}${r.manual ? '<i class="mk" title="koreksi manual">✎</i>' : ""}${r.conflict ? '<i class="cf" title="model berubah, bentrok dengan koreksi manual">⚠</i>' : ""}</td><td class="c-sat">${esc(r.sat)}</td><td class="c-num">${rp(r.total || null)}</td>
        <td class="c-src" title="${esc(kindLabel(k))}">${badge(k, SHORT[k] || k)}</td></tr>`;
    }
  }
  $("#rows").innerHTML = html || `<tr><td colspan="8" class="muted" style="padding:20px">Tidak ada baris yang cocok.</td></tr>`;
  $("#count").innerHTML = S.pick ? `${shown} baris memakai objek ini · <a href="#" id="clearpick">tampilkan semua</a>` : `${shown} baris`;
  inspector();
}

function inspector() {
  const keep = {}; for (const id of ["note-text", "ed-vol"]) { const el = document.getElementById(id); if (el && (id === "note-text" || el === document.activeElement)) keep[id] = el.value; }
  const was = S.inspFor; S.inspFor = S.view + "|" + S.sel + "|" + (S.pick && S.pick.key);
  inspector2();
  if (was === S.inspFor) for (const [id, v] of Object.entries(keep)) { const el = document.getElementById(id); if (el) el.value = v; }
}
function inspector2() {
  if (S.view === "hist") return history();
  if (S.sel) return detailRow(rowOf(S.sel));
  if (S.pick) return detailPick(S.pick);
  $("#detail").innerHTML = `<div class="empty">Pilih baris RAB untuk melihat bagian model yang menjadi sumber volumenya, atau klik objek di model 3D.</div>`;
}

function rowsForPick(p) {
  const part = { obj: { name: p.name, pid: p.pid }, tags: p.tags, key: p.key };
  return S.data.rows.filter((r) => r.hl && r.kind !== "sub" && viewer.match(part, r.hl));
}

function select(row, fly = true) {
  const r = rowOf(row);
  const any = r && hasHl(r) ? viewer.highlight(r.hl, fly) : (viewer.highlight(null, fly), false);
  $("#hud").innerHTML = !r ? "" : any
    ? `<b>${esc(title(r))}</b> · ${num(r.vol)} ${esc(r.sat)}<span class="r">${esc(r.ruang)}</span><span class="n">${viewer.hitCount} bagian model disorot${r.hl.room ? " · dibatasi kotak ruang" : ""}</span>`
    : `<b>${esc(title(r))}</b><span class="r">${r.kind === "pending" ? "Pending — belum ada di model" : "Tidak diambil dari geometri model (" + esc(kindLabel(kindOf(r))) + ")"}</span>`;
  return any;
}

function noteForm(row, object) {
  return `<div class="block"><h3>Catatan untuk Claude</h3>
    <textarea id="note-text" rows="2" placeholder="${object ? "Mis. objek ini harusnya masuk baris 98…" : "Mis. harga perlu analisa ulang, pakai metode lain…"}"></textarea>
    <div class="actions"><button class="btn" data-act="note" data-row="${row || ""}" data-object="${esc(object || "")}">Simpan catatan</button></div>
    <p class="hint">Catatan masuk antrean dan saya kerjakan saat menjalankan skill berikutnya.</p></div>`;
}

function detailRow(r) {
  const el = $("#detail");
  if (!r) { el.innerHTML = ""; return; }
  const s = r.src || {}, k = kindOf(r), c = r.can || {};
  let h = `<div class="i-meta"><span class="src"><i class="k-${k}"></i>${esc(kindLabel(k))}</span><span class="bar">|</span><span>Baris ${r.row} · ${esc(r.lantai)}</span></div>
    <h2>${esc(title(r))}</h2><p class="i-desc">${esc(r.ruang)}</p>
    <div class="big">${r.vol == null ? "—" : unitHtml(num(r.vol), r.sat)}</div>
    ${r.conflict ? `<div class="conflict"><b>⚠ Model berubah</b> — angka model sekarang ${num(r.conflict.model)} ${esc(r.sat)}, tapi baris ini dikoreksi manual (${num(r.vol)}).
      <div class="actions"><button class="btn" data-act="conflict" data-use="model" data-row="${r.row}">Pakai angka model</button><button class="btn ghost" data-act="conflict" data-use="manual" data-row="${r.row}">Tetap manual</button></div></div>` : ""}
    ${r.estimated ? `<div class="estbox">Volume estimasi — ${esc(r.quantity_note || "isi ukuran final")}</div>` : ""}
    ${r.manual ? `<div class="manual">✎ Koreksi manual · angka asli ${r.manual.vol_asli == null ? "—" : num(r.manual.vol_asli)} ${esc(r.sat)}${r.manual.note ? ` · ${esc(r.manual.note)}` : ""}</div>` : ""}
    <div class="block"><h3>Asal angka volume</h3><p>${esc(s.detail || (s.pick ? "Bagian model dipilih manual di viewport" : "Belum ada sumber"))}</p>
      ${s.calc ? `<div class="calc">${esc(s.calc)}</div>` : ""}
      ${s.method ? `<div class="kv">Metode: <b>${esc(s.method)}</b></div>` : ""}
      ${r.bind ? `<div class="kv">Ikut model saat SKP disimpan: <b>${{ direct: "langsung (selisih luas)", ratio: "proporsional", count: "jumlah unit" }[r.bind]}</b></div>` : (r.kind !== "pending" && kindOf(r) === "skp" ? `<div class="kv">Ikut model saat SKP disimpan: <b>tidak</b> (sumber kurang spesifik — cek manual)</div>` : "")}
      ${hasHl(r) ? `<div class="chips">${(r.hl.ids || []).map((g) => `<span>${esc(g)}</span>`).join("")}${(r.hl.tags || []).slice(0, 1).map((t) => `<span class="t">${esc(t.split("|").slice(0, 2).join(" · "))}</span>`).join("")}${(r.hl.parts || []).length ? `<span class="t">${r.hl.parts.length} bagian dipilih</span>` : ""}</div>` : ""}
    </div>`;
  if (r.kind !== "pending") h += `<div class="block"><h3>Spec & harga</h3><p><b>${esc(r.code)}</b> · ${esc(r.spec)}</p>
      <div class="kv">${esc(r.price_src || "Harga")}: <b>${rp(r.price)} / ${esc(r.sat)}</b><br>Total: <b>${rp(r.total)}</b></div></div>`;
  if (r.analysis && r.analysis.components) h += `<div class="block"><h3>Analisa ${esc(r.code)}</h3><table class="comp">${r.analysis.components.map((x) =>
      `<tr><td>${esc(x.name)}</td><td class="c-num">${num(x.koef)} ${esc(x.sat)}</td><td class="c-num">${rp(x.sub)}</td></tr>`).join("")}
      <tr><td><b>Harga satuan</b></td><td></td><td class="c-num"><b>${rp(r.analysis.price)}</b></td></tr></table></div>`;
  // ---- koreksi
  let k2 = "";
  if (c.vol) k2 += `<label class="fld"><span>Volume (${esc(r.sat)})</span><div class="row-in"><input id="ed-vol" type="text" inputmode="decimal" value="${r.vol == null ? "" : String(r.vol).replace(".", ",")}">
      <button class="btn" data-act="vol" data-row="${r.row}">Simpan</button></div></label>
      ${(r.shared || []).length ? `<p class="hint">Angka ini juga dipakai baris ${r.shared.join(", ")} (plester/aci/finishing dinding yang sama).</p>` : ""}`;
  if (c.source) k2 += `<div class="actions"><button class="btn ghost" data-act="pick-source" data-row="${r.row}">◎ Pilih sumber di model 3D</button>${s.pick ? `<button class="btn ghost" data-act="reset-source" data-row="${r.row}">Kembalikan sumber asli</button>` : ""}</div>`;
  if (c.spec) k2 += `<div class="fld"><span>Spec (AHS)</span><button class="spec-btn" data-act="spec-open" data-row="${r.row}"><b>${esc(r.code)}</b> ${esc(r.spec)}<i>Ganti…</i></button></div>`;
  if (c.pending) k2 += `<div class="actions"><button class="btn ghost" data-act="pending" data-on="${r.kind === "pending" ? 0 : 1}" data-row="${r.row}">${r.kind === "pending" ? "Batalkan pending" : "Jadikan pending"}</button></div>`;
  if (!k2) k2 = `<p class="hint">Baris ini dihitung otomatis (mis. openingan dari ukuran kusen) — koreksi lewat catatan untuk Claude.</p>`;
  h += `<div class="block edit"><h3>Koreksi</h3>${k2}</div>` + noteForm(r.row);
  el.innerHTML = h;
}

function detailPick(p) {
  const rows = rowsForPick(p);
  $("#detail").innerHTML = `<div class="i-meta"><span class="src"><i class="k-skp"></i>Objek SKP</span><span class="bar">|</span><span>pid ${p.pid}</span></div>
    <h2>${esc(p.name)}</h2><p class="i-desc">Layer ${esc(p.layer)} · bidang ini ${num(p.area)} m²</p>
    ${p.tags.length ? `<div class="chips" style="margin-bottom:18px">${p.tags.map((t) => `<span class="t">${esc(t.replaceAll("|", " · "))}</span>`).join("")}</div>` : ""}
    <div class="block"><h3>Dipakai di ${rows.length} baris RAB</h3>${rows.length ? rows.map((r) => `<div class="pr" data-row="${r.row}"><span>${r.row}</span>${esc(title(r))}<b>${num(r.vol)} ${esc(r.sat)}</b></div>`).join("") : `<p class="muted">Objek ini tidak dirujuk baris mana pun.</p>`}
    <p class="hint">Objek salah masuk baris? Pilih barisnya, lalu “Pilih sumber di model 3D”.</p></div>` + noteForm(null, p.name);
  $("#hud").innerHTML = `<b>${esc(p.name)}</b><span class="n">${rows.length} baris RAB memakai objek ini</span>`;
}

function history() {
  const h = S.data.history;
  $("#detail").innerHTML = `<div class="i-meta"><a href="#" data-act="close-hist">‹ Kembali</a></div><h2>Riwayat & catatan</h2>
    <div class="block"><h3>Catatan untuk Claude (${h.open_notes} terbuka)</h3>${h.notes.length ? h.notes.map((n) => `<div class="note ${n.status}">
      <div class="nt">${n.row ? `<a href="#" data-goto="${n.row}">Baris ${n.row}</a> · ` : ""}${n.object ? `${esc(n.object)} · ` : ""}<span class="muted">${esc(n.at)}</span></div>
      <div>${esc(n.text)}</div><button class="link" data-act="note-done" data-id="${n.id}" data-done="${n.status === "open" ? 1 : 0}">${n.status === "open" ? "Tandai selesai" : "Buka lagi"}</button></div>`).join("") : `<p class="muted">Belum ada catatan.</p>`}</div>
    <div class="block"><h3>Analisa Harga Satuan</h3><p class="kv">${S.data.ahs_state ? `Dicek ${esc(S.data.ahs_state.checked)} · ${S.data.ahs_state.count} spec` : "Belum dicek dari sheet"}</p>
      <div class="actions"><button class="btn ghost" data-act="ahs-update">Perbarui AHS dari sheet</button>${S.data.project.ahs_link ? `<a class="btn ghost" href="${esc(S.data.project.ahs_link)}" target="_blank" rel="noopener">Buka sheet AHS</a>` : ""}</div></div>
    <div class="block"><h3>Perubahan</h3>${h.log.length ? h.log.map((e) => `<div class="log ${e.undone ? "undone" : ""} op-${e.op}"><span class="muted">${esc(e.at.slice(5, 16))}</span>
      ${e.row ? `<a href="#" data-goto="${e.row}">Baris ${e.row}</a>` : ""} ${esc(e.summary)}${e.undone && e.op !== "push" ? " <i>(di-undo)</i>" : ""}${logDetails(e)}</div>`).join("") : `<p class="muted">Belum ada perubahan.</p>`}
      <p class="hint">Snapshot tiap perubahan ada di _serasa_tools/.koreksi/ — Undo mengembalikan satu langkah.</p></div>`;
}

function logDetails(e) {
  const d = e.details; if (!d) return "";
  let h = "";
  if (e.op === "model") {
    h += (d.changes || []).map((c) => `<div class="ld"><a href="#" data-goto="${c.row}">${c.row}</a> ${esc(c.uraian)} <span class="muted">${esc((c.ruang || "").slice(0, 40))}</span> <b>${num(c.old)} → ${num(c.new)}</b> ${esc(c.sat || "")}</div>`).join("");
    h += (d.conflicts || []).map((c) => `<div class="ld cf"><a href="#" data-goto="${c.row}">${c.row}</a> ⚠ bentrok: manual ${num(c.manual)}, model ${num(c.model)}</div>`).join("");
  }
  if (e.op === "ahs") h += (d.used || []).map((c) => `<div class="ld">${c.removed ? "dihapus: " : ""}${esc(c.u.slice(0, 60))}${c.old ? ` <b>${esc(c.old)} → ${esc(c.new)}</b>` : ""}</div>`).join("");
  return h ? `<div class="lds">${h}</div>` : "";
}

// ---------------------------------------------------------------- pemilih spec AHS
async function ensureAhs() {
  if (!S.ahs) S.ahs = await (await fetch("/api/ahs")).json();   // [uraian, kode, satuan, harga, kategori]
  return S.ahs;
}
async function openSpec(row) {
  const r = rowOf(row), list = await ensureAhs();
  const cats = [...new Set(list.map((a) => a[4]).filter(Boolean))];
  S.specPick = { row, q: "", cat: "", sel: null };
  const m = $("#modal");
  m.innerHTML = `<div class="sheet"><div class="sh-head"><div><b>Ganti spec · baris ${r.row}</b><span class="muted">${esc(title(r))} · ${esc((r.ruang || "").slice(0, 60))}</span></div><button class="x" data-act="spec-close">✕</button></div>
    <label class="search big-s"><svg viewBox="0 0 24 24" width="15" height="15"><circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M20 20l-3.6-3.6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
      <input id="sp-q" placeholder="Cari uraian atau kode (mis. keramik 60, PD1, cat eksterior)…" autocomplete="off"></label>
    <div class="chipbar"><button class="chip on" data-cat="">Semua (${list.length})</button>${cats.map((c) => `<button class="chip" data-cat="${esc(c)}">${esc(c)}</button>`).join("")}</div>
    <div class="sp-cur">Sekarang: <b>${esc(r.code)}</b> ${esc(r.spec)} · ${rp(r.price)} / ${esc(r.sat)}</div>
    <div class="sp-list" id="sp-list"></div>
    <div class="sh-foot" id="sp-foot"><span class="muted">Pilih spec dari daftar.</span></div></div>`;
  m.hidden = false; $("#sp-q").focus(); specList();
}
function specList() {
  const P = S.specPick, r = rowOf(P.row), words = P.q.toLowerCase().split(/\s+/).filter(Boolean);
  const hits = S.ahs.filter((a) => (!P.cat || a[4] === P.cat) && words.every((w) => (a[0] + " " + a[1]).toLowerCase().includes(w)));
  $("#sp-list").innerHTML = hits.slice(0, 250).map((a) => `<div class="sp-item ${a[0] === r.spec ? "cur" : ""} ${P.sel === a[0] ? "on" : ""}" data-spec="${esc(a[0])}">
      <span class="code">${esc(a[1])}</span><span class="u">${esc(a[0])}<small>${esc(a[4] || "")}</small></span><span class="s">${esc(a[2])}</span><span class="h">${esc(a[3])}</span></div>`).join("")
    + (hits.length > 250 ? `<div class="muted sp-more">${hits.length - 250} hasil lain — persempit pencarian</div>` : "") + (!hits.length ? `<div class="muted sp-more">Tidak ada yang cocok.</div>` : "");
}
function specChoose(u) {
  const P = S.specPick, r = rowOf(P.row), a = S.ahs.find((x) => x[0] === u); P.sel = u; specList();
  const same = (a[2] || "").toLowerCase() === (r.sat || "").toLowerCase();
  $("#sp-foot").innerHTML = `<div><b>${esc(a[1])}</b> ${esc(a[0].slice(0, 90))}<span class="muted">${esc(a[3])} / ${esc(a[2])} (harga dasar AHS, sebelum koefisien lokasi)${same ? "" : ` · <b class="warn">satuan beda dengan baris (${esc(r.sat)})</b>`}</span></div>
    <div class="actions"><button class="btn ghost" data-act="spec-close">Batal</button><button class="btn" data-act="spec-apply">Ganti spec</button></div>`;
}
function closeSpec() { $("#modal").hidden = true; S.specPick = null; S.review = null; }

// ---------------------------------------------------------------- Google Sheet: push & tarik editan
async function doPush(force, rebuild = false) {
  const b = $("#push"); b.disabled = true; S.pushing = true; b.textContent = force ? "Mengirim…" : "Mengecek Sheet…";
  try {
    const res = await fetch("/api/push", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ force, rebuild }) });
    const j = await res.json();
    if (j.review) { openReview(j, "push"); return; }
    if (j.rebuild_needed) {
      if (confirm(j.summary + "\n\nLanjut bangun ulang tab?")) { S.pushing = false; return doPush(true, true); }
      toast("Push dibatalkan — struktur berubah, perlu bangun ulang tab", "warn"); return;
    }
    if (!res.ok || j.ok === false) throw new Error(j.error || j.summary || "gagal");
    toast((j.summary.split("\n").find((l) => l.startsWith("error=")) || "Push selesai").replace("error=", "Push selesai · error="), "ok");
  } catch (err) { toast("Push gagal: " + err.message.slice(0, 300), "err"); }
  finally { b.disabled = false; S.pushing = false; load(true); }
}
const fmtv = (v, col) => v == null || v === "" ? "—" : col === "H" ? num(v) : esc(String(v).length > 70 ? String(v).slice(0, 70) + "…" : v);
function openReview(d, mode) {
  S.review = { d, mode };
  const m = $("#modal");
  m.innerHTML = `<div class="sheet rv"><div class="sh-head"><div><b>${mode === "push" ? "Ada editan langsung di Google Sheet" : "Editan di Google Sheet"}</b>
      <span class="muted">Tab "${esc(d.tab)}" dibanding push terakhir. Centang yang mau diambil ke web${mode === "push" ? "; yang tidak dicentang akan ditimpa saat push" : ""}.</span></div><button class="x" data-act="spec-close">✕</button></div>
    <div class="sp-list">${d.items.map((i) => `<label class="rv-item ${i.conflict ? "conf" : ""}"><input type="checkbox" value="${esc(i.id)}" ${i.conflict ? "" : "checked"}>
        <span class="rv-l"><b>Baris ${i.sheet_row}</b> ${esc(i.uraian)} <span class="muted">${esc((i.ruang || "").slice(0, 50))}</span>
        <span class="rv-v">${esc(i.field)}: <s>${fmtv(i.base, i.col)}</s> → <b>${fmtv(i.sheet, i.col)}</b> <span class="muted">di Sheet</span>
        ${i.conflict ? `<br><span class="warn">⚠ di web juga diubah jadi ${fmtv(i.web, i.col)} — pilih salah satu</span>` : ""}</span></span></label>`).join("")}
      ${d.struct.length ? `<div class="rv-struct"><b>Baris ditambah / dihapus di Sheet</b><span class="muted">Tidak bisa dipetakan otomatis — akan masuk catatan untuk Claude.</span>
        ${d.struct.map((s) => `<div>${s.type === "tambah" ? "＋ baris " + s.sheet_row : "－"} ${esc(s.uraian)} · ${esc(s.ruang || "")}${s.vol != null ? " · " + num(s.vol) : ""}</div>`).join("")}</div>` : ""}
    </div>
    <div class="sh-foot"><span class="muted">${d.items.length} perubahan · ${d.struct.length} baris struktur</span>
      <div class="actions"><button class="btn ghost" data-act="spec-close">Batal</button>
      ${mode === "push" ? `<button class="btn ghost" data-act="rv-overwrite">Timpa semua & push</button><button class="btn" data-act="rv-take-push">Ambil yang dicentang & push</button>`
                        : `<button class="btn" data-act="rv-take">Ambil yang dicentang</button>`}</div></div></div>`;
  m.hidden = false;
}
async function reviewApply(push) {
  const take = [...document.querySelectorAll(".rv-item input:checked")].map((x) => x.value);
  const j = await post("/api/edit", { op: "sheet_pull", take }).catch((e) => { toast(e.message, "err"); return null; });
  if (!j) return;
  closeSpec(); toast(j.summary + (j.skipped && j.skipped.length ? `\n${j.skipped.join("\n")}` : ""), j.skipped && j.skipped.length ? "warn" : "ok");
  if (push) await doPush(true);
}

// ---------------------------------------------------------------- mode pilih sumber
function startEdit(r) {
  const keys = viewer.parts.filter((p) => p.hit).map((p) => p.key);
  S.edit = { row: r.row, keys, area: 0 };
  viewer.setEdit(keys); S.edit.area = viewer.editArea(); editBar();
}
function editBar() {
  const e = S.edit, bar = $("#editbar");
  if (!e) { bar.hidden = true; return; }
  const r = rowOf(e.row);
  bar.hidden = false;
  bar.innerHTML = `<div><b>Pilih sumber · baris ${e.row}</b> ${esc(title(r))}<span class="r">Klik bagian model untuk menambah / mengeluarkan · ${e.keys.length} bagian · luas seluruh bidang terpilih ${num(e.area)} m²</span></div>
    <div class="actions"><button class="btn ghost" data-act="edit-cancel">Batal</button><button class="btn ghost" data-act="edit-save">Simpan sumber</button>
    ${r.sat === "m2" ? `<button class="btn" data-act="edit-save-area">Simpan + volume ${num(e.area)} m²</button>` : ""}</div>`;
}
function stopEdit() { S.edit = null; viewer.setEdit(null); editBar(); if (S.sel) select(S.sel, false); }

// ---------------------------------------------------------------- umum
function agentStatus(st) {
  const el = $("#agent");
  if (!st || !st.message) { el.hidden = true; return; }
  const done = /^(selesai|done)$/i.test(st.stage || "");
  el.hidden = false; el.className = "agent" + (done ? " done" : "");
  el.innerHTML = `${done ? "✓" : '<i class="spin"></i>'}<span>${esc(st.message)}</span>${st.steps ? `<small>${st.step || 0}/${st.steps}</small>` : ""}`;
}

function setLive(on, text) { const l = $("#live"); l.className = "live " + (on ? "on" : "off"); $("#live-text").textContent = text; }
let toastT;
function toast(msg, kind = "ok") { const t = $("#toast"); t.textContent = msg; t.className = "toast show " + kind; clearTimeout(toastT); toastT = setTimeout(() => (t.className = "toast"), kind === "err" ? 6000 : 2800); }
const parseNum = (s) => { s = String(s).trim(); return Number(s.includes(",") ? s.replace(/\./g, "").replace(",", ".") : s); };

document.addEventListener("click", async (e) => {
  const t = e.target;
  if (t.id === "clearpick") { e.preventDefault(); S.pick = null; viewer.highlight(null, false); render(); return; }
  const act = t.closest("[data-act]");
  if (act) {
    e.preventDefault(); const a = act.dataset.act, row = +act.dataset.row || null;
    if (a === "vol") { const v = parseNum($("#ed-vol").value); if (!isFinite(v) || $("#ed-vol").value.trim() === "") return toast("Volume tidak valid", "err"); await edit({ op: "vol", row, value: v }); }
    else if (a === "spec-open") openSpec(row);
    else if (a === "spec-close") closeSpec();
    else if (a === "spec-apply") { if (await edit({ op: "spec", row: S.specPick.row, spec: S.specPick.sel })) closeSpec(); }
    else if (a === "conflict") await edit({ op: "conflict", row, use: act.dataset.use });
    else if (a === "rv-take") await reviewApply(false);
    else if (a === "rv-take-push") await reviewApply(true);
    else if (a === "rv-overwrite") { if (confirm("Editan di Sheet akan ditimpa data web. Lanjut?")) { closeSpec(); await doPush(true); } }
    else if (a === "ahs-update") { act.disabled = true; act.textContent = "Mengecek…"; await edit({ op: "ahs_update" }); }
    else if (a === "pending") await edit({ op: "pending", row, on: act.dataset.on === "1", reason: act.dataset.on === "1" ? prompt("Alasan pending?", "menunggu data") || "dikoreksi dari viewport" : "" });
    else if (a === "pick-source") startEdit(rowOf(row));
    else if (a === "reset-source") await edit({ op: "source", row, parts: [] }, "sumber dikembalikan ke hasil take-off");
    else if (a === "edit-cancel") stopEdit();
    else if (a === "edit-save" || a === "edit-save-area") {
      const ok = await edit({ op: "source", row: S.edit.row, parts: S.edit.keys, area: S.edit.area, use_area: a === "edit-save-area" });
      if (ok) stopEdit();
    }
    else if (a === "note") { const tx = $("#note-text").value; if (await edit({ op: "note", row, object: act.dataset.object || null, text: tx })) $("#note-text").value = ""; }
    else if (a === "note-done") await edit({ op: "note_done", id: +act.dataset.id, done: act.dataset.done === "1" });
    else if (a === "close-hist") { S.view = "detail"; inspector(); }
    return;
  }
  if (t.closest("#undo")) { await edit({ op: "undo" }); return; }
  if (t.closest("#hist")) { S.view = S.view === "hist" ? "detail" : "hist"; inspector(); return; }
  if (t.closest("#push")) {
    if (!confirm(`Tulis ulang tab "${S.data.project.tab}" di Google Sheet dengan data viewport sekarang?\n(Editan langsung di Sheet dicek dulu.)`)) return;
    return doPush(false);
  }
  if (t.closest("#pull")) {
    const b = $("#pull"); b.disabled = true; b.textContent = "Membaca Sheet…";
    try { const d = await post("/api/edit", { op: "sheet_check" }); if (d.items.length || d.struct.length) openReview(d, "pull"); else toast(d.summary, "ok"); }
    catch (err) { toast("Gagal membaca Sheet: " + err.message.slice(0, 300), "err"); }
    finally { b.disabled = false; b.textContent = "Tarik dari Sheet"; }
    return;
  }
  const cat = t.closest("[data-cat]"); if (cat && S.specPick) { document.querySelectorAll("[data-cat]").forEach((x) => x.classList.toggle("on", x === cat)); S.specPick.cat = cat.dataset.cat; specList(); return; }
  const sp = t.closest("[data-spec]"); if (sp && S.specPick) { specChoose(sp.dataset.spec); return; }
  if (t.id === "modal") { closeSpec(); return; }
  const go = t.closest("[data-goto]"); if (go) { e.preventDefault(); S.view = "detail"; S.sel = +go.dataset.goto; S.pick = null; render(); select(S.sel); return; }
  if (S.edit) return;   // saat memilih sumber, klik tabel/filter tidak mengganti baris
  const b = t.closest("[data-bab]"); if (b) { S.bab = b.dataset.bab || null; render(); return; }
  const k = t.closest("[data-kind]"); if (k) { S.kind = k.dataset.kind || null; render(); return; }
  const v = t.closest("[data-view]"); if (v) { document.querySelectorAll("[data-view]").forEach((x) => x.classList.toggle("on", x === v)); viewer.view(v.dataset.view); return; }
  const m = t.closest("[data-mode]"); if (m) { document.querySelectorAll("[data-mode]").forEach((x) => x.classList.toggle("on", x === m)); viewer.setMode(m.dataset.mode); $("#legend").hidden = m.dataset.mode !== "usage"; return; }
  const c = t.closest("[data-cut]"); if (c) { document.querySelectorAll("[data-cut]").forEach((x) => x.classList.toggle("on", x === c)); viewer.setSection(c.dataset.cut ? +c.dataset.cut : null); return; }
  const tr = t.closest("[data-row]"); if (tr) { const row = +tr.dataset.row; S.sel = S.sel === row && !tr.classList.contains("pr") ? null : row; S.pick = null; S.view = "detail"; render(); select(S.sel); }
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && (S.specPick || S.review)) closeSpec();
  else if (e.key === "Escape" && S.edit) stopEdit();
  if ((e.metaKey || e.ctrlKey) && e.key === "z" && !/INPUT|TEXTAREA/.test(document.activeElement.tagName)) { e.preventDefault(); edit({ op: "undo" }); }
  if (e.key === "Enter" && document.activeElement && document.activeElement.id === "ed-vol") document.querySelector('[data-act="vol"]').click();
});
$("#q").addEventListener("input", (e) => { S.q = e.target.value; render(); });
document.addEventListener("input", (e) => { if (e.target.id === "sp-q" && S.specPick) { S.specPick.q = e.target.value; specList(); } });

function connect() {
  const es = new EventSource("/events");
  es.onopen = () => setLive(true, "Live");
  es.onmessage = (m) => {
    const ev = JSON.parse(m.data);
    if (ev.scope === "hello") { if (S.down) location.reload(); return; }  // server baru dimulai ulang
    if (ev.scope === "web" || ev.scope === "project") { location.reload(); return; }
    const l = $("#live"); l.classList.remove("pulse"); void l.offsetWidth; l.classList.add("pulse");
    setLive(true, (ev.scope === "model3d" ? "Model 3D diperbarui " : "Diperbarui ") + new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" }));
    if (ev.scope === "model3d") { S.meshMtime = null; }
    load(true);
  };
  es.onerror = () => { S.down = true; setLive(false, "Terputus · mencoba lagi…"); };
}
load(false); connect();
