// viewer3d.js - tampilan 3D model SKP + sorotan sumber volume + pilih per bidang + garis potong interaktif.
// Hanya urusan gambar: data RAB & logika sorotan datang dari app.js / core/model.py.
// Hemat: geometri sekali per definisi SketchUp (core/mesh.py) dirangkai di sini per objek, material dipakai bersama,
// layar hanya digambar ulang bila ada perubahan.
import * as THREE from "three";
import { OrbitControls } from "/vendor/OrbitControls.js";

const DS = THREE.DoubleSide;
const lam = (o) => new THREE.MeshLambertMaterial({ side: DS, ...o });
const line = (color, opacity) => new THREE.LineBasicMaterial({ color, transparent: true, opacity });
const DEFAULT_RGBA = [238, 236, 230, 255];
const CAP = 0x48484a;   // isian bidang potong: abu gelap seperti gambar kerja

export class Viewer3D {
  constructor(el, { onPick, onEdit, onSection } = {}) {
    this.el = el; this.onPick = onPick; this.onEdit = onEdit; this.onSection = onSection;
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, stencil: true, powerPreference: "low-power" });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.setClearColor(0x000000, 0); this.renderer.localClippingEnabled = true;
    el.appendChild(this.renderer.domElement);
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(40, 1, 0.05, 2000);
    this.camera.up.set(0, 0, 1); // Z ke atas, sama dengan SketchUp
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true; this.controls.dampingFactor = 0.14;
    this.controls.addEventListener("change", () => this.redraw());
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0xb9b2a6, 1.15));
    const sun = new THREE.DirectionalLight(0xffffff, 1.1); sun.position.set(-6, -9, 14); this.scene.add(sun);
    this.root = new THREE.Group(); this.scene.add(this.root);
    this.roomsGroup = new THREE.Group(); this.scene.add(this.roomsGroup);
    this.capGroup = new THREE.Group(); this.scene.add(this.capGroup);
    this.handleGroup = new THREE.Group(); this.scene.add(this.handleGroup);
    this.parts = []; this.objEdges = []; this.mode = "material"; this.hl = null; this.anim = null; this.picked = null; this.editSel = null;
    this.clip = []; this.sec = { mode: "none", caps: true };
    // material bersama (tidak dibuat ulang setiap klik); semua ikut bidang potong (this.clip)
    this.M = {
      base: lam({ vertexColors: true, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 }),
      glass: lam({ vertexColors: true, transparent: true, opacity: 0.35, depthWrite: false }),
      hl: lam({ color: 0xff9f0a, emissive: 0x7a4500, polygonOffset: true, polygonOffsetFactor: -1 }),
      ghost: lam({ color: 0xd2d2d7, transparent: true, opacity: 0.12, depthWrite: false }),
      used: lam({ color: 0x0071e3 }), unused: lam({ color: 0xc7c7cc, transparent: true, opacity: 0.35, depthWrite: false }),
      pickSelf: lam({ color: 0x0071e3, emissive: 0x00346b, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 }),   // bidang yang diklik
      pickObj: lam({ color: 0xe8e8ed, emissive: 0x111114, polygonOffset: true, polygonOffsetFactor: -1 }),                               // objek induknya: abu netral
      edit: lam({ color: 0x34c759, emissive: 0x0d4a1c, polygonOffset: true, polygonOffsetFactor: -1 }),
      dim: lam({ vertexColors: true, transparent: true, opacity: 0.55, depthWrite: false }),
    };
    this.E = { normal: line(0x48484a, 0.45), ghost: line(0x8a857c, 0.07), hl: line(0xb86e00, 0.9), pick: line(0x6e6e73, 0.7), face: line(0x002a5c, 1), edit: line(0x1b7a35, 0.95) };
    for (const m of [...Object.values(this.M), ...Object.values(this.E)]) m.clippingPlanes = this.clip;
    this.clipMats = {};
    this.ray = new THREE.Raycaster(); this.ray.params.Line.threshold = 0;
    new ResizeObserver(() => this.resize()).observe(el); this.resize();
    let down = null;
    const cv = this.renderer.domElement;
    cv.addEventListener("pointerdown", (e) => { down = [e.clientX, e.clientY]; this.dragStart(e); });
    cv.addEventListener("pointermove", (e) => this.dragMove(e));
    cv.addEventListener("pointerup", (e) => {
      if (this.drag) { this.dragEnd(); down = null; return; }
      if (down && Math.hypot(e.clientX - down[0], e.clientY - down[1]) < 4) this.pick(e);
    });
    const loop = () => {
      requestAnimationFrame(loop);
      const moving = this.tick() | this.controls.update();
      if (moving || this.dirty) { this.dirty = false; this.renderer.render(this.scene, this.camera); }
    };
    loop();
  }

  redraw() { this.dirty = true; }

  resize() {
    const w = this.el.clientWidth, h = this.el.clientHeight || 400;
    this.renderer.setSize(w, h); this.camera.aspect = w / h; this.camera.updateProjectionMatrix(); this.redraw();
  }

  // ------------------------------------------------------------------ muat model
  // buf: ArrayBuffer dari /api/model3d -> [uint32 len][meta json][Float32 V][Uint32 T][Float32 E]  (core/mesh.py)
  load(buf) {
    const n = new DataView(buf).getUint32(0, true);
    const meta = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 4, n)));
    let off = 4 + n;
    const len = (k) => meta.defs.reduce((a, d) => Math.max(a, d[k][0] + d[k][1]), 0);
    const V = new Float32Array(buf, off, len("v")); off += V.byteLength;
    const T = new Uint32Array(buf, off, len("t")); off += T.byteLength;
    const Ed = new Float32Array(buf, off, len("e"));
    for (const p of this.parts) { p.mesh.geometry.dispose(); if (p.edges) p.edges.geometry.dispose(); }
    for (const o of this.objEdges || []) o.geometry.dispose();
    this.root.clear(); this.roomsGroup.clear(); this.clearCaps(); if (this.capSrc) this.capSrc.dispose();
    this.parts = []; this.objEdges = []; this.meta = meta; this.capSrc = null; this.picked = null;
    const o0 = meta.origin; this.origin = o0;
    const mats = meta.materials.map((m) => ({ name: m[0], c: new THREE.Color(`rgb(${m[1]},${m[2]},${m[3]})`), glass: m[4] < 200 }));
    const dflt = { name: "(tanpa material)", c: new THREE.Color(`rgb(${DEFAULT_RGBA[0]},${DEFAULT_RGBA[1]},${DEFAULT_RGBA[2]})`), glass: false };
    let capTris = 0; const capPlan = [];
    meta.objects.forEach((obj, oi) => {
      // lintasan 1: hitung segitiga per part (tagset x kaca) dan rencana muka
      const plan = [], cnt = new Map(); let rle = 0, rleLeft = obj.ft.length ? obj.ft[0][1] : 0, fid = 0;
      const nextTs = () => { while (rleLeft === 0 && rle < obj.ft.length - 1) { rle++; rleLeft = obj.ft[rle][1]; } rleLeft--; return obj.ft.length ? obj.ft[rle][0] : 0; };
      obj.leaves.forEach(([di, m, inh], li) => {
        const d = meta.defs[di]; let t0 = 0;
        for (const [mi, nt] of d.f) {
          const ts = nextTs(), mat = mi >= 0 ? mats[mi] : inh >= 0 ? mats[inh] : dflt;
          const key = ts + "|" + (mat.glass ? 1 : 0);
          cnt.set(key, (cnt.get(key) || 0) + nt);
          plan.push({ key, li, t0, nt, mat, fid: fid++ });
          if (d.c && !mat.glass) { capTris += nt; capPlan.push([oi, li, t0, nt]); }
          t0 += nt;
        }
      });
      // lintasan 2: isi buffer
      const P = new Map();
      for (const [key, c] of cnt) P.set(key, { pos: new Float32Array(c * 9), col: new Float32Array(c * 9), n: 0, faces: [], area: 0 });
      const W = this.worldFn(obj, o0);
      for (const f of plan) {
        const p = P.get(f.key), [di, m] = obj.leaves[f.li], d = meta.defs[di], tb = d.t[0], vb = d.v[0], c = f.mat.c;
        const start = p.n; let a = 0;
        for (let k = 0; k < f.nt; k++) {
          const j = p.n * 9;
          for (let q = 0; q < 3; q++) {
            const vi = vb + T[tb + (f.t0 + k) * 3 + q] * 3;
            W(m, V[vi], V[vi + 1], V[vi + 2], p.pos, j + q * 3);
            p.col[j + q * 3] = c.r; p.col[j + q * 3 + 1] = c.g; p.col[j + q * 3 + 2] = c.b;
          }
          a += triArea(p.pos, j); p.n++;
        }
        p.faces.push({ fid: f.fid, start, n: f.nt, mat: f.mat.name, area: a }); p.area += a;
      }
      for (const [key, p] of P) {
        const [ts, gl] = key.split("|"), tags = meta.tagsets[+ts] ? meta.tagsets[+ts].split(";") : [];
        const g = new THREE.BufferGeometry();
        g.setAttribute("position", new THREE.BufferAttribute(p.pos, 3)); g.setAttribute("color", new THREE.BufferAttribute(p.col, 3)); g.computeVertexNormals();
        const tagStr = meta.tagsets[+ts] || "";
        const part = { obj, oi, tags, glass: gl === "1", area: p.area, key: `${obj.name}::${tagStr}`, faces: p.faces, faceStart: Int32Array.from(p.faces.map((f) => f.start)) };
        part.base = part.glass ? this.M.glass : this.M.base;
        part.mesh = new THREE.Mesh(g, part.base); part.mesh.userData.part = part;
        if (obj.edges_auto) { part.edges = new THREE.LineSegments(new THREE.EdgesGeometry(g, 25), this.E.normal); this.root.add(part.edges); }
        this.root.add(part.mesh); this.parts.push(part);
      }
      // garis tepi asli SketchUp, satu LineSegments per objek
      if (!obj.edges_auto) {
        const ne = obj.leaves.reduce((a, [di]) => a + meta.defs[di].e[1], 0);
        if (ne) {
          const ep = new Float32Array(ne); let j = 0;
          for (const [di, m] of obj.leaves) { const d = meta.defs[di]; for (let i = d.e[0]; i < d.e[0] + d.e[1]; i += 3) { W(m, Ed[i], Ed[i + 1], Ed[i + 2], ep, j); j += 3; } }
          const eg = new THREE.BufferGeometry(); eg.setAttribute("position", new THREE.BufferAttribute(ep, 3));
          const ls = new THREE.LineSegments(eg, this.E.normal); ls.userData.oi = oi; this.root.add(ls); this.objEdges.push(ls);
        }
      }
    });
    this.capPlan = { tris: capTris, plan: capPlan, V, T };
    for (const r of meta.rooms || []) {
      const [x0, x1, y0, y1] = r.rect || polyRect(r.poly), [z0, z1] = r.z, o = this.origin;
      const box = new THREE.Box3(new THREE.Vector3((x0 - o[0]) / 1000, (y0 - o[1]) / 1000, (z0 - o[2]) / 1000), new THREE.Vector3((x1 - o[0]) / 1000, (y1 - o[1]) / 1000, (z1 - o[2]) / 1000));
      const h = new THREE.Box3Helper(box, 0x2f8f7a); h.userData.box = box; h.material.transparent = true; h.material.opacity = 0.0; h.userData.room = r.name;
      this.roomsGroup.add(h);
    }
    this.clipMats = {};
    this.box = new THREE.Box3().setFromObject(this.root);
    if (!this.loaded) { this.fit(this.box, false); this.loaded = true; }
    this.applySection();
    this.apply();
    return meta;
  }

  // fungsi transformasi lokal (mm) -> dunia viewport (m, relatif origin)
  worldFn(obj, o0) {
    return (m, x, y, z, out, j) => {
      out[j] = (m[0] * x + m[3] * y + m[6] * z + m[9] - o0[0]) / 1000;
      out[j + 1] = (m[1] * x + m[4] * y + m[7] * z + m[10] - o0[1]) / 1000;
      out[j + 2] = (m[2] * x + m[5] * y + m[8] * z + m[11] - o0[2]) / 1000;
    };
  }

  // ------------------------------------------------------------------ sorotan
  // hl: {ids:[...], tags:[...], tag_ids_only, room, parts:[objek::tag]}  (null = tidak ada sorotan)
  match(part, hl) {
    if (!hl) return false;
    if (hl.parts && hl.parts.length) return hl.parts.includes(part.key);
    const idHit = hl.ids && hl.ids.length && (hl.ids.includes(part.obj.name) || hl.ids.includes(String(part.obj.pid)));
    if (hl.tags && hl.tags.length) {
      if (hl.tag_ids_only && !idHit) return false;
      return part.tags.some((t) => hl.tags.some((q) => q === t || tagLike(q, t)));
    }
    return !!idHit;
  }

  setUsage(used) { this.used = used; this.apply(); }
  setMode(m) { this.mode = m; this.apply(); }

  roomPlanes(name) {
    const h = this.roomsGroup.children.find((x) => x.userData.room === name); if (!h) return null;
    const b = h.userData.box, e = 0.3;  // sedikit lebih besar dari ruang: muka dinding ada di tepinya
    return [new THREE.Plane(new THREE.Vector3(1, 0, 0), -(b.min.x - e)), new THREE.Plane(new THREE.Vector3(-1, 0, 0), b.max.x + e),
      new THREE.Plane(new THREE.Vector3(0, 1, 0), -(b.min.y - e)), new THREE.Plane(new THREE.Vector3(0, -1, 0), b.max.y + e),
      new THREE.Plane(new THREE.Vector3(0, 0, 1), -(b.min.z - 0.02)), new THREE.Plane(new THREE.Vector3(0, 0, -1), b.max.z + 0.02)];
  }

  hlMat(room) {
    if (!room) return this.M.hl;
    if (!this.clipMats[room]) { const m = this.M.hl.clone(); m.clippingPlanes = (this.roomPlanes(room) || []).concat(this.clip); this.clipMats[room] = m; }
    return this.clipMats[room];
  }

  set(p, mat, edge, order) { p.mesh.material = mat; if (p.edges) p.edges.material = edge; p.mesh.renderOrder = order; }
  edgesFor(oi, mat) { for (const l of this.objEdges) l.material = oi === undefined || l.userData.oi === oi ? mat : this.E.ghost; }

  apply() {
    const hl = this.hl; let any = false;
    for (const h of this.roomsGroup.children) h.material.opacity = 0;
    this.setFaceOverlay(null);
    if (this.editSel) {                          // mode pilih sumber: hijau = dipilih
      for (const p of this.parts) { p.hit = this.editSel.has(p.key); this.set(p, p.hit ? this.M.edit : p.glass ? p.base : this.M.dim, p.hit ? this.E.edit : this.E.normal, p.hit ? 2 : 1); }
      this.edgesFor(undefined, this.E.normal);
      this.hitCount = this.parts.filter((p) => p.hit).length; this.redraw(); return true;
    }
    if (this.picked && !hl) {                    // bidang hasil klik (biru tua) di dalam objeknya (biru muda)
      const pk = this.picked;
      for (const p of this.parts) { const inObj = p.oi === pk.oi; p.hit = inObj; this.set(p, inObj ? (pk.whole || p === pk.part ? this.M.pickSelf : this.M.pickObj) : this.M.ghost, inObj ? this.E.pick : this.E.ghost, inObj ? 2 : 1); }
      this.edgesFor(pk.oi, this.E.pick);
      if (!pk.whole && pk.face) this.setFaceOverlay(pk.part, pk.face);
      if (!pk.whole && pk.face) pk.part.mesh.material = this.M.pickObj;
      this.hitCount = this.parts.filter((p) => p.hit).length; this.redraw(); return true;
    }
    for (const p of this.parts) { p.hit = this.match(p, hl); any = any || p.hit; }
    const hm = this.hlMat(hl && hl.room);
    for (const p of this.parts) {
      if (hl && any) this.set(p, p.hit ? hm : this.M.ghost, p.hit ? this.E.hl : this.E.ghost, p.hit ? 2 : 1);
      else if (this.mode === "usage" && this.used) {
        const u = this.used.has(p.obj.name) || this.used.has(String(p.obj.pid)) || this.used.has(p.key) || p.tags.some((t) => this.used.has(t));
        this.set(p, u ? this.M.used : this.M.unused, this.E.normal, u ? 2 : 1);
      } else this.set(p, p.base, this.E.normal, 0);
    }
    if (hl && any) { const hitObj = new Set(this.parts.filter((p) => p.hit).map((p) => p.oi)); for (const l of this.objEdges) l.material = hitObj.has(l.userData.oi) ? this.E.normal : this.E.ghost; }
    else this.edgesFor(undefined, this.E.normal);
    for (const h of this.roomsGroup.children) h.material.opacity = hl && hl.room === h.userData.room ? 0.95 : 0;
    this.hitCount = this.parts.filter((p) => p.hit).length; this.redraw();
    return any;
  }

  // lapisan sorot satu bidang (segitiga bidang itu saja, di atas part-nya)
  setFaceOverlay(part, face) {
    if (this.faceMesh) { this.scene.remove(this.faceMesh, this.faceLine); this.faceMesh.geometry.dispose(); this.faceLine.geometry.dispose(); this.faceMesh = this.faceLine = null; }
    if (!part) return;
    const src = part.mesh.geometry.attributes.position.array;
    const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(src.slice(face.start * 9, (face.start + face.n) * 9), 3)); g.computeVertexNormals();
    this.faceMesh = new THREE.Mesh(g, this.M.pickSelf); this.faceMesh.renderOrder = 3;
    this.faceLine = new THREE.LineSegments(new THREE.EdgesGeometry(g, 1), this.E.face); this.faceLine.renderOrder = 4;   // garis tepi bidang
    this.scene.add(this.faceMesh, this.faceLine);
  }

  highlight(hl, fly = true) {
    this.hl = hl; this.picked = null; const any = this.apply();
    const DIR = { Barat: [-1, -0.35, 0.45], Timur: [1, -0.35, 0.45], Utara: [0.35, 1, 0.45], Selatan: [0.35, -1, 0.45] };
    const ext = hl && (hl.tags || []).map((t) => t.split("|")).find((t) => t[0] === "E" && DIR[t[1]]);
    this.prefDir = ext ? new THREE.Vector3(...DIR[ext[1]]) : hl && hl.room ? new THREE.Vector3(0.6, -0.8, 1.6) : null;
    if (fly) {
      const b = new THREE.Box3();
      if (any) for (const p of this.parts) if (p.hit) b.expandByObject(p.mesh);
      for (const h of this.roomsGroup.children) if (hl && hl.room === h.userData.room) b.union(h.userData.box);
      this.fit(b.isEmpty() ? this.box : b, true);
    }
    return any;
  }

  // mode pilih sumber untuk koreksi: keys = Set("objek::tag"), null = keluar
  setEdit(keys) { this.editSel = keys ? new Set(keys) : null; this.picked = null; this.apply(); }
  editArea() { return this.parts.filter((p) => this.editSel && this.editSel.has(p.key)).reduce((a, p) => a + p.area, 0); }

  // pilih seluruh objek dari bidang yang sedang dipilih
  pickWhole(on = true) { if (this.picked) { this.picked.whole = on; this.apply(); } }

  // ------------------------------------------------------------------ kamera
  fit(box, animate) {
    if (!box || box.isEmpty()) return;
    const c = box.getCenter(new THREE.Vector3()), s = box.getSize(new THREE.Vector3());
    const r = Math.max(s.length() / 2, 1.2), d = r / Math.sin((this.camera.fov * Math.PI) / 360) * 1.05;
    const dir = this.prefDir ? this.prefDir.clone() : this.camera.position.clone().sub(this.controls.target);
    if (dir.length() < 1e-3 || !animate) dir.set(1.1, -1.4, 0.9);
    dir.normalize();
    const pos = c.clone().add(dir.multiplyScalar(d));
    if (!animate) { this.camera.position.copy(pos); this.controls.target.copy(c); this.redraw(); return; }
    this.anim = { t: 0, p0: this.camera.position.clone(), p1: pos, c0: this.controls.target.clone(), c1: c };
  }

  view(name) {
    const b = this.box, c = b.getCenter(new THREE.Vector3()), s = b.getSize(new THREE.Vector3()), d = s.length() * 1.25;
    const dirs = { iso: [1.1, -1.4, 0.9], atas: [0.0001, -0.0001, 1], depan: [0, -1, 0.15], timur: [1, 0, 0.15], barat: [-1, 0, 0.15], belakang: [0, 1, 0.15] };
    const v = new THREE.Vector3(...dirs[name]).normalize().multiplyScalar(d);
    this.anim = { t: 0, p0: this.camera.position.clone(), p1: c.clone().add(v), c0: this.controls.target.clone(), c1: c };
  }

  tick() {
    const a = this.anim; if (!a) return false;
    a.t = Math.min(1, a.t + 0.06); const k = 1 - Math.pow(1 - a.t, 3);
    this.camera.position.lerpVectors(a.p0, a.p1, k); this.controls.target.lerpVectors(a.c0, a.c1, k);
    if (a.t >= 1) this.anim = null;
    return true;
  }

  // ------------------------------------------------------------------ garis potong
  // mode: "none" | "plan" (denah, simpan di bawah z) | "cut" (potongan vertikal, sumbu x/y) | "box" (kotak 6 sisi)
  // nilai posisi dalam mm dunia (sama dengan SketchUp) supaya UI bisa menampilkan elevasi asli.
  bounds() {   // batas model dalam mm dunia
    const b = this.box, o = this.origin;
    return { x: [b.min.x * 1000 + o[0], b.max.x * 1000 + o[0]], y: [b.min.y * 1000 + o[1], b.max.y * 1000 + o[1]], z: [b.min.z * 1000 + o[2], b.max.z * 1000 + o[2]] };
  }
  setSection(s) {   // s: {mode, z, axis, pos, flip, box:{x:[a,b],y:[..],z:[..]}, caps}
    this.sec = { ...this.sec, ...s };
    if (this.sec.mode === "box" && !this.sec.box) { const b = this.bounds(); this.sec.box = { x: [...b.x], y: [...b.y], z: [...b.z] }; }
    this.applySection();
  }
  planes() {
    const s = this.sec, o = this.origin || [0, 0, 0], k = { x: 0, y: 1, z: 2 };
    const P = (axis, dir, mm) => { const n = new THREE.Vector3(); n.setComponent(k[axis], dir); return new THREE.Plane(n, -dir * (mm - o[k[axis]]) / 1000); };
    // Plane(n, c): titik p disimpan bila n·p + c >= 0
    if (s.mode === "plan" && s.z != null) return [P("z", -1, s.z)];
    if (s.mode === "cut" && s.pos != null) return [P(s.axis || "y", s.flip ? -1 : 1, s.pos)];
    if (s.mode === "box" && s.box) return ["x", "y", "z"].flatMap((a) => [P(a, 1, s.box[a][0]), P(a, -1, s.box[a][1])]);
    return [];
  }
  applySection() {
    const ps = this.planes(), countChanged = ps.length !== this.clip.length;
    this.clip.length = 0; ps.forEach((p) => this.clip.push(p));
    if (countChanged) { for (const m of [...Object.values(this.M), ...Object.values(this.E)]) m.needsUpdate = true; this.clipMats = {}; }
    this.buildCaps(); this.buildHandles(); this.redraw();
  }

  // isian bidang potong: teknik stencil paritas (jumlah permukaan di belakang bidang ganjil = di dalam solid).
  // Hanya geometri definisi yang tertutup (solid) yang dipakai, jadi muka tunggal/terbuka tidak membuat bercak.
  clearCaps() { for (const c of this.capGroup.children) { if (c.geometry !== this.capSrc) c.geometry.dispose(); c.material.dispose(); } this.capGroup.clear(); }

  // garis potong: perpotongan semua segitiga dengan bidang potong (seperti section cut SketchUp), untuk geometri apa pun
  sectionLines(ps) {
    const out = [], a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
    ps.forEach((plane, i) => {
      const seg = [], others = ps.filter((_, k) => k !== i), n = plane.normal, d0 = plane.constant;
      for (const p of this.parts) {
        const arr = p.mesh.geometry.attributes.position.array, sp = p.mesh.geometry.boundingSphere || (p.mesh.geometry.computeBoundingSphere(), p.mesh.geometry.boundingSphere);
        if (Math.abs(plane.distanceToPoint(sp.center)) > sp.radius) continue;
        for (let j = 0; j < arr.length; j += 9) {
          const da = n.x * arr[j] + n.y * arr[j + 1] + n.z * arr[j + 2] + d0, db = n.x * arr[j + 3] + n.y * arr[j + 4] + n.z * arr[j + 5] + d0, dc = n.x * arr[j + 6] + n.y * arr[j + 7] + n.z * arr[j + 8] + d0;
          if ((da > 0 && db > 0 && dc > 0) || (da < 0 && db < 0 && dc < 0)) continue;
          a.fromArray(arr, j); b.fromArray(arr, j + 3); c.fromArray(arr, j + 6);
          const pts = [];
          const cut = (u, v, du, dv) => { if ((du > 0) !== (dv > 0)) { const t = du / (du - dv); pts.push(u.x + (v.x - u.x) * t, u.y + (v.y - u.y) * t, u.z + (v.z - u.z) * t); } };
          cut(a, b, da, db); cut(b, c, db, dc); cut(c, a, dc, da);
          if (pts.length === 6) seg.push(...pts);
        }
      }
      if (!seg.length) return;
      const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(seg), 3));
      const m = new THREE.LineBasicMaterial({ color: 0x1d1d1f, clippingPlanes: others, depthTest: true });
      const l = new THREE.LineSegments(g, m); l.renderOrder = 30; out.push(l);
    });
    return out;
  }
  capSource() {
    if (this.capSrc || !this.capPlan || !this.capPlan.tris) return this.capSrc;
    const { plan, tris, V, T } = this.capPlan, pos = new Float32Array(tris * 9), meta = this.meta; let j = 0;
    for (const [oi, li, t0, nt] of plan) {
      const obj = meta.objects[oi], [di, m] = obj.leaves[li], d = meta.defs[di], W = this.worldFn(obj, this.origin);
      for (let k = 0; k < nt; k++) for (let q = 0; q < 3; q++) { const vi = d.v[0] + T[d.t[0] + (t0 + k) * 3 + q] * 3; W(m, V[vi], V[vi + 1], V[vi + 2], pos, j); j += 3; }
    }
    const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(pos, 3)); g.computeBoundingSphere();
    return (this.capSrc = g);
  }
  buildCaps(lines = true) {
    this.clearCaps();
    const ps = this.clip; if (!ps.length || !this.box) return;
    if (lines) for (const l of this.sectionLines(ps)) this.capGroup.add(l);
    if (!this.sec.caps) return;
    const src = this.capSource(); if (!src) return;
    const size = this.box.getSize(new THREE.Vector3()).length() * 2, c = this.box.getCenter(new THREE.Vector3());
    ps.forEach((plane, i) => {
      const st = new THREE.MeshBasicMaterial({ side: DS, colorWrite: false, depthWrite: false, depthTest: false, clippingPlanes: [plane],
        stencilWrite: true, stencilFunc: THREE.AlwaysStencilFunc, stencilZPass: THREE.InvertStencilOp, stencilFail: THREE.InvertStencilOp, stencilZFail: THREE.InvertStencilOp });
      const sm = new THREE.Mesh(src, st); sm.renderOrder = 10 + i * 2; sm.frustumCulled = false;
      const others = ps.filter((_, k) => k !== i);
      const cm = new THREE.MeshBasicMaterial({ color: CAP, side: DS, clippingPlanes: others, polygonOffset: true, polygonOffsetFactor: 1,
        stencilWrite: true, stencilRef: 0, stencilFunc: THREE.NotEqualStencilFunc, stencilZPass: THREE.ReplaceStencilOp, stencilFail: THREE.ReplaceStencilOp, stencilZFail: THREE.ReplaceStencilOp });
      const q = new THREE.Mesh(new THREE.PlaneGeometry(size, size), cm); q.renderOrder = 11 + i * 2;
      plane.coplanarPoint(q.position); q.lookAt(q.position.clone().sub(plane.normal));
      q.position.addScaledVector(plane.normal, 0); q.onAfterRender = (r) => r.clearStencil();
      // pusatkan kuad di proyeksi tengah model supaya cukup menutup
      const cp = plane.projectPoint(c, new THREE.Vector3()); q.position.copy(cp);
      this.capGroup.add(sm, q);
    });
  }

  // pegangan: titik biru yang bisa ditarik sepanjang normal bidang
  buildHandles() {
    for (const h of this.handleGroup.children) { h.geometry.dispose(); h.children.forEach((c) => c.geometry.dispose()); }
    this.handleGroup.clear();
    const s = this.sec; if (!this.box || s.mode === "none") return;
    const c = this.box.getCenter(new THREE.Vector3()), o = this.origin, r = Math.max(this.box.getSize(new THREE.Vector3()).length() / 90, 0.12);
    const mk = (axis, idx, mm) => {
      const p = c.clone(); p.setComponent({ x: 0, y: 1, z: 2 }[axis], (mm - o[{ x: 0, y: 1, z: 2 }[axis]]) / 1000);
      const m = new THREE.Mesh(new THREE.SphereGeometry(r, 20, 14), new THREE.MeshBasicMaterial({ color: 0x0071e3, depthTest: false, transparent: true, opacity: 0.95 }));
      m.position.copy(p); m.renderOrder = 50; m.userData.h = { axis, idx };
      const rim = new THREE.Mesh(new THREE.SphereGeometry(r * 1.35, 20, 14), new THREE.MeshBasicMaterial({ color: 0xffffff, depthTest: false, side: THREE.BackSide }));
      rim.renderOrder = 49; m.add(rim); this.handleGroup.add(m);
    };
    if (s.mode === "plan") mk("z", 0, s.z);
    else if (s.mode === "cut") mk(s.axis || "y", 0, s.pos);
    else if (s.mode === "box") for (const a of ["x", "y", "z"]) { mk(a, 0, s.box[a][0]); mk(a, 1, s.box[a][1]); }
  }

  ndc(e) { const r = this.renderer.domElement.getBoundingClientRect(); return new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1); }
  dragStart(e) {
    if (!this.handleGroup.children.length) return;
    this.ray.setFromCamera(this.ndc(e), this.camera);
    const h = this.ray.intersectObjects(this.handleGroup.children, false)[0]; if (!h) return;
    const { axis, idx } = h.object.userData.h, ax = new THREE.Vector3(); ax.setComponent({ x: 0, y: 1, z: 2 }[axis], 1);
    // bidang bantu: memuat sumbu tarik, menghadap kamera
    const view = this.camera.position.clone().sub(h.object.position), n = view.clone().sub(ax.clone().multiplyScalar(view.dot(ax))).normalize();
    this.drag = { axis, idx, ax, obj: h.object, plane: new THREE.Plane().setFromNormalAndCoplanarPoint(n, h.object.position), p0: h.object.position.clone() };
    this.controls.enabled = false;
  }
  dragMove(e) {
    const d = this.drag; if (!d) return;
    this.ray.setFromCamera(this.ndc(e), this.camera);
    const hit = this.ray.ray.intersectPlane(d.plane, new THREE.Vector3()); if (!hit) return;
    const k = { x: 0, y: 1, z: 2 }[d.axis], b = this.bounds()[d.axis], o = this.origin[k];
    let mm = Math.round(hit.getComponent(k) * 1000 + o);
    mm = Math.max(b[0] - 500, Math.min(b[1] + 500, mm));
    const s = this.sec;
    if (s.mode === "plan") s.z = mm; else if (s.mode === "cut") s.pos = mm;
    else if (s.mode === "box") { const r = s.box[d.axis]; r[d.idx] = d.idx === 0 ? Math.min(mm, r[1] - 100) : Math.max(mm, r[0] + 100); }
    d.obj.position.setComponent(k, ((s.mode === "box" ? s.box[d.axis][d.idx] : mm) - o) / 1000);
    const ps = this.planes(); ps.forEach((p, i) => this.clip[i] && this.clip[i].copy(p));
    if (!this.capT) this.capT = requestAnimationFrame(() => { this.capT = null; this.buildCaps(false); this.redraw(); });   // garis potong dihitung saat dilepas
    this.redraw();
    if (this.onSection) this.onSection(this.sec);
  }
  dragEnd() { this.drag = null; this.controls.enabled = true; this.applySection(); }

  // ------------------------------------------------------------------ klik
  pick(e) {
    this.ray.setFromCamera(this.ndc(e), this.camera);
    let hits = this.ray.intersectObjects(this.parts.map((p) => p.mesh), false);
    if (this.clip.length) hits = hits.filter((h) => this.clip.every((pl) => pl.distanceToPoint(h.point) >= -1e-4));   // bagian terpotong tidak bisa diklik
    if (this.editSel) {                          // toggle bagian untuk sumber baris
      const p = hits.length ? hits[0].object.userData.part : null; if (!p) return;
      this.editSel.has(p.key) ? this.editSel.delete(p.key) : this.editSel.add(p.key);
      this.apply(); if (this.onEdit) this.onEdit([...this.editSel], this.editArea(), p);
      return;
    }
    const h = hits.find((x) => x.object.userData.part.hit && !this.picked) || hits[0];
    const p = h ? h.object.userData.part : null;
    let face = null;
    if (p) { const tri = h.faceIndex, fs = p.faceStart; let lo = 0, hi = fs.length - 1; while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (fs[mid] <= tri) lo = mid; else hi = mid - 1; } face = p.faces[lo]; }
    this.picked = p ? { oi: p.oi, part: p, face, whole: false } : null; if (p) this.hl = null;
    this.apply();
    if (this.onPick) this.onPick(p ? { pid: p.obj.pid, name: p.obj.name, layer: p.obj.layer, tags: p.tags, key: p.key, area: face ? face.area : p.area,
      partArea: p.area, material: face && face.mat, objArea: this.parts.filter((q) => q.oi === p.oi).reduce((a, q) => a + q.area, 0) } : null);
  }
}

function tagLike(q, t) {   // "R|Toko 1|*" cocok dengan "R|Toko 1|putih"
  if (!q.includes("*")) return false;
  const a = q.split("|"), b = t.split("|");
  return a.length === b.length && a.every((x, i) => x === "*" || x === b[i]);
}
function triArea(p, j) {
  const ax = p[j + 3] - p[j], ay = p[j + 4] - p[j + 1], az = p[j + 5] - p[j + 2], bx = p[j + 6] - p[j], by = p[j + 7] - p[j + 1], bz = p[j + 8] - p[j + 2];
  const cx = ay * bz - az * by, cy = az * bx - ax * bz, cz = ax * by - ay * bx;
  return 0.5 * Math.sqrt(cx * cx + cy * cy + cz * cz);
}
function polyRect(poly) {
  const xs = (poly || []).map((p) => p[0]), ys = (poly || []).map((p) => p[1]);
  return xs.length ? [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)] : [0, 0, 0, 0];
}
