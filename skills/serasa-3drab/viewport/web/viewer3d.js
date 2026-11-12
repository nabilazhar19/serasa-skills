// viewer3d.js - tampilan 3D model SKP + sorotan sumber volume + mode pilih sumber (koreksi).
// Hanya urusan gambar: data RAB & logika sorotan datang dari app.js / core/model.py.
// Hemat: geometri biner (core/mesh.py), material dipakai bersama, dan layar hanya digambar ulang bila ada perubahan.
import * as THREE from "three";
import { OrbitControls } from "/vendor/OrbitControls.js";

const DS = THREE.DoubleSide;
const lam = (o) => new THREE.MeshLambertMaterial({ side: DS, ...o });
const line = (color, opacity) => new THREE.LineBasicMaterial({ color, transparent: true, opacity });

export class Viewer3D {
  constructor(el, { onPick, onEdit } = {}) {
    this.el = el; this.onPick = onPick; this.onEdit = onEdit;
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.setClearColor(0x000000, 0); this.renderer.localClippingEnabled = true;
    el.appendChild(this.renderer.domElement);
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(40, 1, 0.05, 500);
    this.camera.up.set(0, 0, 1); // Z ke atas, sama dengan SketchUp
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true; this.controls.dampingFactor = 0.14;
    this.controls.addEventListener("change", () => this.redraw());
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0xb9b2a6, 1.15));
    const sun = new THREE.DirectionalLight(0xffffff, 1.1); sun.position.set(-6, -9, 14); this.scene.add(sun);
    this.root = new THREE.Group(); this.scene.add(this.root);
    this.roomsGroup = new THREE.Group(); this.scene.add(this.roomsGroup);
    this.parts = []; this.mode = "material"; this.hl = null; this.anim = null; this.picked = null; this.editSel = null;
    // material bersama (tidak dibuat ulang setiap klik)
    this.M = {
      base: lam({ vertexColors: true, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 }),
      glass: lam({ vertexColors: true, transparent: true, opacity: 0.35, depthWrite: false }),
      hl: lam({ color: 0xff9f0a, emissive: 0x7a4500, polygonOffset: true, polygonOffsetFactor: -1 }),
      ghost: lam({ color: 0xd2d2d7, transparent: true, opacity: 0.12, depthWrite: false }),
      used: lam({ color: 0x0071e3 }), unused: lam({ color: 0xc7c7cc, transparent: true, opacity: 0.35, depthWrite: false }),
      pickSelf: lam({ color: 0x0058b9, emissive: 0x002a5c, polygonOffset: true, polygonOffsetFactor: -1 }),
      pickObj: lam({ color: 0x0071e3, emissive: 0x001f44, polygonOffset: true, polygonOffsetFactor: -1 }),
      edit: lam({ color: 0x34c759, emissive: 0x0d4a1c, polygonOffset: true, polygonOffsetFactor: -1 }),
      dim: lam({ vertexColors: true, transparent: true, opacity: 0.55, depthWrite: false }),
    };
    this.E = { normal: line(0x48484a, 0.45), ghost: line(0x8a857c, 0.07), hl: line(0xb86e00, 0.9), pick: line(0x1e3a8a, 0.95), edit: line(0x1b7a35, 0.95) };
    this.clipMats = {};
    this.ray = new THREE.Raycaster();
    new ResizeObserver(() => this.resize()).observe(el); this.resize();
    let down = null;
    this.renderer.domElement.addEventListener("pointerdown", (e) => (down = [e.clientX, e.clientY]));
    this.renderer.domElement.addEventListener("pointerup", (e) => {
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

  // buf: ArrayBuffer dari /api/model3d -> [uint32 len][meta json][Int16 xyz]
  load(buf) {
    const n = new DataView(buf).getUint32(0, true);
    const meta = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 4, n)));
    const xyz = new Int16Array(buf, 4 + n);
    for (const p of this.parts) { p.mesh.geometry.dispose(); p.edges.geometry.dispose(); }
    this.root.clear(); this.roomsGroup.clear(); this.parts = []; this.meta = meta;
    const sc = meta.scale / 1000;
    this.origin = meta.origin;
    for (const p of meta.parts) {
      const pos = new Float32Array(p.count * 3), col = new Float32Array(p.count * 3);
      for (let i = 0, j = p.start * 3; i < pos.length; i++, j++) pos[i] = xyz[j] * sc;
      let v = 0;
      for (const [cnt, r, g, b] of p.runs) {
        const c = new THREE.Color(`rgb(${r},${g},${b})`);  // sRGB -> linear sesuai warna SketchUp
        for (let k = 0; k < cnt; k++, v++) { col[v * 3] = c.r; col[v * 3 + 1] = c.g; col[v * 3 + 2] = c.b; }
      }
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.BufferAttribute(pos, 3)); g.setAttribute("color", new THREE.BufferAttribute(col, 3)); g.computeVertexNormals();
      const obj = meta.objects[p.o];
      const part = { obj, oi: p.o, tags: p.t ? p.t.split(";") : [], glass: p.glass, area: p.area, key: `${obj.name}::${p.t}` };
      part.base = p.glass ? this.M.glass : this.M.base;
      part.mesh = new THREE.Mesh(g, part.base); part.mesh.userData.part = part;
      part.edges = new THREE.LineSegments(new THREE.EdgesGeometry(g, 25), this.E.normal);
      this.root.add(part.mesh, part.edges); this.parts.push(part);
    }
    const O = [0, 0, 0];
    for (const r of meta.rooms || []) {
      const [x0, x1, y0, y1] = r.rect, [z0, z1] = r.z, o = this.origin;
      const box = new THREE.Box3(new THREE.Vector3((x0 - o[0]) / 1000, (y0 - o[1]) / 1000, (z0 - o[2]) / 1000), new THREE.Vector3((x1 - o[0]) / 1000, (y1 - o[1]) / 1000, (z1 - o[2]) / 1000));
      const h = new THREE.Box3Helper(box, 0x2f8f7a); h.userData.box = box; h.material.transparent = true; h.material.opacity = 0.0; h.userData.room = r.name;
      this.roomsGroup.add(h);
    }
    this.clipMats = {};
    this.box = new THREE.Box3().setFromObject(this.root);
    if (!this.loaded) { this.fit(this.box, false); this.loaded = true; }
    this.apply();
    return meta;
  }

  // hl: {ids:[...], tags:[...], tag_ids_only, room, parts:[objek::tag]}  (null = tidak ada sorotan)
  match(part, hl) {
    if (!hl) return false;
    if (hl.parts && hl.parts.length) return hl.parts.includes(part.key);
    const idHit = hl.ids && hl.ids.length && (hl.ids.includes(part.obj.name) || hl.ids.includes(String(part.obj.pid)));
    if (hl.tags && hl.tags.length) {
      if (hl.tag_ids_only && !idHit) return false;
      return part.tags.some((t) => hl.tags.some((q) => q === t || (q.startsWith("E|*|") && t.startsWith("E|") && t.endsWith("|" + q.split("|")[2]))));
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
    if (!this.clipMats[room]) { const m = this.M.hl.clone(); m.clippingPlanes = this.roomPlanes(room); this.clipMats[room] = m; }
    return this.clipMats[room];
  }

  set(p, mat, edge, order) { p.mesh.material = mat; p.edges.material = edge; p.mesh.renderOrder = order; }

  apply() {
    const hl = this.hl; let any = false;
    for (const h of this.roomsGroup.children) h.material.opacity = 0;
    if (this.editSel) {                          // mode pilih sumber: hijau = dipilih
      for (const p of this.parts) { p.hit = this.editSel.has(p.key); this.set(p, p.hit ? this.M.edit : p.glass ? p.base : this.M.dim, p.hit ? this.E.edit : this.E.normal, p.hit ? 2 : 1); }
      this.hitCount = this.parts.filter((p) => p.hit).length; this.redraw(); return true;
    }
    if (this.picked && !hl) {                    // objek hasil klik
      const pk = this.picked;
      for (const p of this.parts) { const inObj = p.oi === pk.oi; p.hit = inObj; this.set(p, inObj ? (p === pk.part ? this.M.pickSelf : this.M.pickObj) : this.M.ghost, inObj ? this.E.pick : this.E.ghost, inObj ? 2 : 1); }
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
    for (const h of this.roomsGroup.children) h.material.opacity = hl && hl.room === h.userData.room ? 0.95 : 0;
    this.hitCount = this.parts.filter((p) => p.hit).length; this.redraw();
    return any;
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

  // potongan horizontal: tampilkan geometri di bawah elevasi z (mm absolut); null = tanpa potongan
  setSection(zmm) {
    this.renderer.clippingPlanes = zmm == null ? [] : [new THREE.Plane(new THREE.Vector3(0, 0, -1), (zmm - this.origin[2]) / 1000)];
    this.redraw();
  }

  tick() {
    const a = this.anim; if (!a) return false;
    a.t = Math.min(1, a.t + 0.06); const k = 1 - Math.pow(1 - a.t, 3);
    this.camera.position.lerpVectors(a.p0, a.p1, k); this.controls.target.lerpVectors(a.c0, a.c1, k);
    if (a.t >= 1) this.anim = null;
    return true;
  }

  pick(e) {
    const r = this.renderer.domElement.getBoundingClientRect();
    this.ray.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), this.camera);
    const hits = this.ray.intersectObjects(this.parts.map((p) => p.mesh), false);
    if (this.editSel) {                          // toggle bagian untuk sumber baris
      const p = hits.length ? hits[0].object.userData.part : null; if (!p) return;
      this.editSel.has(p.key) ? this.editSel.delete(p.key) : this.editSel.add(p.key);
      this.apply(); if (this.onEdit) this.onEdit([...this.editSel], this.editArea(), p);
      return;
    }
    const h = hits.find((x) => x.object.userData.part.hit) || hits[0];
    const p = h ? h.object.userData.part : null;
    this.picked = p ? { oi: p.oi, part: p } : null; if (p) this.hl = null;
    this.apply();
    if (this.onPick) this.onPick(p ? { pid: p.obj.pid, name: p.obj.name, layer: p.obj.layer, tags: p.tags, key: p.key, area: p.area } : null);
  }
}
