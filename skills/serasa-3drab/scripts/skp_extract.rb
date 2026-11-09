# skp_extract.rb - Serasa RAB: ekstraksi kuantitas dari model SketchUp
#
# Cara pakai:
#   * Lewat MCP SketchUp (eval_ruby): kirim isi file ini sekali, lalu panggil fungsi
#     SerasaRAB.xxx(...) di eval berikutnya. Setiap fungsi mengembalikan string JSON.
#   * Lewat Ruby Console SketchUp: load "/path/skp_extract.rb" lalu panggil fungsi yang sama.
#
# Semua satuan input/output dalam mm dan m2. Region = [xmin, xmax, ymin, ymax] (mm, koordinat dunia)
# untuk membatasi area yang dihitung (mis. area yang ditandai merah oleh user).
# Massa yang diputar terhadap sumbu dunia: pakai `angle` (derajat) -> koordinat lokal u,v.
require 'json'

module SerasaRAB
  module_function

  SKIP_LAYERS = /KONTUR|PLAN|STREET|VEGET|CAR BIKE/i
  SKIP_DEFS   = /SCF|CAY|Decid|tree|pohon|car|mobil|motor|person|people/i

  def mm(v) v.to_mm end
  def area_m2(f, tr) f.area(tr) / 1550.0031 end
  def mat_name(f) m = f.material || f.back_material; m ? m.display_name : '-' end

  def uv(x, y, ang)
    t = ang * Math::PI / 180
    [x * Math.cos(t) + y * Math.sin(t), -x * Math.sin(t) + y * Math.cos(t)]
  end

  def in_region?(b, region)
    c = b.center
    mm(c.x).between?(region[0], region[1]) && mm(c.y).between?(region[2], region[3])
  end

  # top-level groups/components dalam region (persistent_id dipakai untuk pemanggilan berikutnya)
  def roots(region, include_huge: false)
    m = Sketchup.active_model
    m.entities.select { |e|
      (e.is_a?(Sketchup::Group) || e.is_a?(Sketchup::ComponentInstance)) && e.visible? && e.layer.visible? &&
        e.layer.name !~ SKIP_LAYERS && e.definition.name !~ SKIP_DEFS && in_region?(e.bounds, region) &&
        (include_huge || (mm(e.bounds.width) < 60000 && mm(e.bounds.height) < 60000))
    }
  end

  # 1) info model + daftar entitas region
  def info(region)
    m = Sketchup.active_model
    out = { path: m.path, layers: m.layers.map(&:name), scenes: m.pages.map(&:name), roots: [] }
    roots(region, include_huge: true).each { |e|
      b = e.bounds
      out[:roots] << { pid: e.persistent_id, name: e.definition.name, layer: e.layer.name,
                       min: b.min.to_a.map { |v| mm(v).round }, max: b.max.to_a.map { |v| mm(v).round } }
    }
    out.to_json
  end

  # rekursif: kumpulkan "leaf" (group/komponen yang memuat face) beserta transform dunia
  def leaves(ent, tr = Geom::Transformation.new, acc = [], path = '')
    d = ent.definition; t = tr * ent.transformation
    fs = d.entities.grep(Sketchup::Face)
    acc << [path + '/' + d.name, t, fs] unless fs.empty?
    d.entities.each { |c|
      next unless (c.is_a?(Sketchup::Group) || c.is_a?(Sketchup::ComponentInstance)) && c.visible? && c.layer.visible?
      next if c.definition.name =~ SKIP_DEFS
      leaves(c, t, acc, path + '/' + d.name)
    }
    acc
  end

  # 2) ringkasan material (luas horizontal/vertikal) + tekstur -> untuk menebak finishing
  def materials(region)
    s = Hash.new(0); tex = {}
    roots(region).each { |e|
      leaves(e).each { |_, t, fs| fs.each { |f|
        n = f.normal.transform(t); next if n.length == 0; n.normalize!
        k = [mat_name(f), n.z.abs > 0.9 ? 'H' : 'V']; s[k] += area_m2(f, t)
        mt = f.material || f.back_material
        tex[k[0]] ||= (mt ? { color: mt.color.to_a, texture: (mt.texture ? File.basename(mt.texture.filename.to_s) : nil) } : nil)
      } }
    }
    s.sort_by { |_, v| -v }.map { |k, v| { material: k[0], orient: k[1], m2: v.round(2), info: tex[k[0]] } }.to_json
  end

  # 3) daftar leaf dengan bbox lokal (u,v) -> untuk mengenali dinding, partisi, kaca, lantai
  def leaf_table(pids, angle = 0, min_area = 0.3)
    m = Sketchup.active_model; out = []
    pids.each { |pid|
      e = m.find_entity_by_persistent_id(pid); next unless e
      leaves(e, Geom::Transformation.new, [], pid.to_s).each { |nm, t, fs|
        pts = fs.flat_map { |f| f.vertices.map { |v| v.position.transform(t) } }
        q = pts.map { |p| uv(mm(p.x), mm(p.y), angle) }; z = pts.map { |p| mm(p.z) }
        a = fs.sum { |f| area_m2(f, t) }; next if a < min_area
        hz = fs.select { |f| n = f.normal.transform(t); n.length > 0 && n.normalize.z.abs > 0.9 }.sum { |f| area_m2(f, t) }
        out << { leaf: nm, u: [q.map(&:first).min.round, q.map(&:first).max.round], v: [q.map(&:last).min.round, q.map(&:last).max.round],
                 z: [z.min.round, z.max.round], a: a.round(2), h: hz.round(2), mats: fs.map { |f| mat_name(f)[0, 14] }.uniq.first(4) }
      }
    }
    out.to_json
  end

  # rooms: [{name:, type:'uv'|'xy', rect:[u0,u1,v0,v1] (uv) | poly:[[x,y],...] (xy), z:[z0,z1]}]
  def pip(x, y, poly)
    c = false; j = poly.length - 1
    poly.each_with_index { |(xi, yi), i| xj, yj = poly[j]; c = !c if ((yi > y) != (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi); j = i }
    c
  end

  def room_of(x, y, z, rooms, angle)
    u, v = uv(x, y, angle)
    rooms.each { |r|
      next unless z.between?(r['z'][0], r['z'][1])
      if r['type'] == 'uv'
        g = r['rect']; return r['name'] if u.between?(g[0], g[1]) && v.between?(g[2], g[3])
      else
        return r['name'] if pip(x, y, r['poly'])
      end
    }
    nil
  end

  # 4) klasifikasi muka dinding per ruang & material.
  #    Hanya leaf tebal (>= min_thk mm) dan tinggi >= 250 mm (dinding pasangan), muka vertikal.
  #    Titik uji = pusat muka + normal x 200 mm -> ruang yang dihadap muka tsb.
  #    Muka yang tidak jatuh di ruang manapun = EKSTERIOR (dikelompokkan per top-group & arah).
  def classify_walls(pids, rooms_json, angle = 0, min_thk = 80)
    rooms = JSON.parse(rooms_json); m = Sketchup.active_model
    res = Hash.new(0); ext = Hash.new(0); sides = []
    pids.each { |pid|
      e = m.find_entity_by_persistent_id(pid); next unless e
      leaves(e).each { |nm, t, fs|
        pts = fs.flat_map { |f| f.vertices.map { |v| v.position.transform(t) } }
        xs = pts.map { |p| mm(p.x) }; ys = pts.map { |p| mm(p.y) }; zs = pts.map { |p| mm(p.z) }
        q = pts.map { |p| uv(mm(p.x), mm(p.y), angle) }
        thk = [[xs.max - xs.min, ys.max - ys.min].min, [q.map(&:first).max - q.map(&:first).min, q.map(&:last).max - q.map(&:last).min].min].min
        next if thk < min_thk || (zs.max - zs.min) < 250
        dirs = Hash.new(0)
        fs.each { |f|
          n = f.normal.transform(t); next if n.length == 0; n.normalize!; next if n.z.abs > 0.2
          mn = mat_name(f); next if mn =~ /GLAZ|glass|kaca/i
          a = area_m2(f, t); next if a < 0.02
          vs = f.outer_loop.vertices.map { |v| v.position.transform(t) }
          cx = vs.sum { |p| mm(p.x) } / vs.size; cy = vs.sum { |p| mm(p.y) } / vs.size; cz = vs.sum { |p| mm(p.z) } / vs.size
          r = room_of(cx + n.x * 200, cy + n.y * 200, cz, rooms, angle)
          dirs[[n.x.round(1), n.y.round(1)]] += a
          if r then res[[r, mn]] += a
          else
            ang = (Math.atan2(n.y, n.x) * 180 / Math::PI)
            d = %w[Timur Utara Barat Selatan][((ang + 45) % 360 / 90).floor]
            ext[[pid, nm.split('/')[1..2].join('/'), d, mn, zs.min.round, zs.max.round]] += a
          end
        }
        best = dirs.max_by { |_, a| a }
        sides << { pid: pid, leaf: nm, z: [zs.min.round, zs.max.round], one_side_m2: best[1].round(2) } if best && best[1] > 0.8
      }
    }
    { rooms: res.map { |k, v| { room: k[0], material: k[1], m2: v.round(2) } },
      exterior: ext.select { |_, v| v > 0.2 }.map { |k, v| { pid: k[0], leaf: k[1], arah: k[2], material: k[3], z: [k[4], k[5]], m2: v.round(2) } },
      wall_one_side: sides }.to_json
  end

  # 5) lantai/plafon: muka horizontal menghadap atas (up) atau bawah (down) per group/material/elevasi
  def horizontals(region, zmin, zmax, up = true, min_area = 0.3)
    agg = Hash.new { |h, k| h[k] = [0, [1e9, -1e9], [1e9, -1e9]] }
    walk = lambda { |ents, tr, top, d|
      return if d > 8
      ents.each { |e|
        if e.is_a?(Sketchup::Face)
          n = e.normal.transform(tr); next if n.length == 0; n.normalize!
          next unless up ? n.z > 0.9 : n.z < -0.9
          vs = e.outer_loop.vertices.map { |v| v.position.transform(tr) }; z = mm(vs[0].z); next unless z.between?(zmin, zmax)
          xs = vs.map { |p| mm(p.x) }; ys = vs.map { |p| mm(p.y) }
          next unless (xs.sum / xs.size).between?(region[0], region[1]) && (ys.sum / ys.size).between?(region[2], region[3])
          k = [top, mat_name(e)[0, 20], (z / 50).round * 50]; h = agg[k]
          h[0] += area_m2(e, tr); h[1] = [[h[1][0], xs.min].min, [h[1][1], xs.max].max]; h[2] = [[h[2][0], ys.min].min, [h[2][1], ys.max].max]
        elsif (e.is_a?(Sketchup::Group) || e.is_a?(Sketchup::ComponentInstance)) && e.visible? && e.layer.visible? && e.definition.name !~ SKIP_DEFS
          walk.call(e.definition.entities, tr * e.transformation, top, d + 1)
        end
      }
    }
    Sketchup.active_model.entities.each { |e|
      next unless (e.is_a?(Sketchup::Group) || e.is_a?(Sketchup::ComponentInstance)) && e.visible? && e.layer.visible?
      next if e.layer.name =~ /VEGET|CAR BIKE/i
      walk.call(e.definition.entities, e.transformation, "#{e.persistent_id} #{e.definition.name} [#{e.layer.name}]", 0)
    }
    agg.select { |_, v| v[0] > min_area }.sort_by { |k, _| [k[0], k[2]] }.map { |k, v|
      { group: k[0], material: k[1], z: k[2], m2: v[0].round(2), x: v[1].map(&:round), y: v[2].map(&:round) } }.to_json
  end

  # 6) bukaan: leaf berisi material kaca (GLAZ/glass) -> lebar, tinggi, luas kaca (1 sisi)
  def glazing(region)
    out = []
    scan = lambda { |ents, tr, path, d|
      return if d > 8
      ents.each { |e|
        next unless (e.is_a?(Sketchup::Group) || e.is_a?(Sketchup::ComponentInstance)) && e.visible? && e.layer.visible?
        t = tr * e.transformation; fs = e.definition.entities.grep(Sketchup::Face)
        g = fs.select { |f| mat_name(f) =~ /GLAZ|glass|kaca/i }
        unless g.empty?
          pts = fs.flat_map { |f| f.vertices.map { |v| v.position.transform(t) } }
          xs = pts.map { |p| mm(p.x) }; ys = pts.map { |p| mm(p.y) }; zs = pts.map { |p| mm(p.z) }
          out << { path: path + '/' + e.definition.name, c: [((xs.max + xs.min) / 2).round, ((ys.max + ys.min) / 2).round],
                   z: [zs.min.round, zs.max.round], w: Math.hypot(xs.max - xs.min, ys.max - ys.min).round,
                   glass_m2: (g.sum { |f| area_m2(f, t) } / 2).round(2) }
        end
        scan.call(e.definition.entities, t, path + '/' + e.definition.name, d + 1)
      }
    }
    scan.call(roots(region), Geom::Transformation.new, '', 0)
    out.to_json
  end

  # 7) atap / bidang miring: luas per material & kemiringan (ambil muka 'up' sebagai luas penutup)
  def slopes(pids)
    m = Sketchup.active_model; out = Hash.new(0)
    pids.each { |pid|
      e = m.find_entity_by_persistent_id(pid); next unless e
      leaves(e).each { |nm, t, fs| fs.each { |f|
        n = f.normal.transform(t); next if n.length == 0; n.normalize!
        sl = (Math.acos(n.z.abs) * 180 / Math::PI).round(-1)
        out[[nm.split('/')[1..2].join('/'), (f.material ? f.material.display_name : '-')[0, 16], (f.back_material ? f.back_material.display_name : '-')[0, 16], sl, n.z >= 0 ? 'up' : 'dn']] += area_m2(f, t)
      } }
    }
    out.select { |_, v| v > 0.3 }.map { |k, v| { leaf: k[0], front: k[1], back: k[2], slope: k[3], dir: k[4], m2: v.round(2) } }.to_json
  end

  # 8) hitung instance komponen (mis. bata roster, lampu, sanitair) per nama definisi di region
  def count_components(region, name_regex = '.')
    rx = Regexp.new(name_regex, Regexp::IGNORECASE); cnt = Hash.new(0)
    walk = lambda { |ents, tr, d|
      return if d > 8
      ents.each { |e|
        next unless (e.is_a?(Sketchup::Group) || e.is_a?(Sketchup::ComponentInstance)) && e.visible? && e.layer.visible?
        t = tr * e.transformation; c = e.bounds.center.transform(tr)
        if e.is_a?(Sketchup::ComponentInstance) && e.definition.name =~ rx &&
           mm(c.x).between?(region[0], region[1]) && mm(c.y).between?(region[2], region[3])
          cnt[e.definition.name] += 1
        end
        walk.call(e.definition.entities, t, d + 1)
      }
    }
    walk.call(Sketchup.active_model.entities, Geom::Transformation.new, 0)
    cnt.sort_by { |_, v| -v }.to_h.to_json
  end

  # 9) bantu visual: simpan kamera, potongan horizontal, tampak atas ortho; restore
  def save_camera
    c = Sketchup.active_model.active_view.camera
    $serasa_cam = [c.eye.to_a, c.target.to_a, c.up.to_a, c.perspective?, (c.perspective? ? c.fov : c.height)]
    'saved'
  end

  def plan_view(cx, cy, height_mm, cut_z = nil)
    m = Sketchup.active_model
    $serasa_sp.erase! if $serasa_sp && $serasa_sp.valid?
    if cut_z
      $serasa_sp = m.entities.add_section_plane([0, 0, cut_z.mm], [0, 0, -1]); $serasa_sp.activate
      m.rendering_options['DisplaySectionPlanes'] = false
    end
    cam = Sketchup::Camera.new([cx.mm, cy.mm, 100_000.mm], [cx.mm, cy.mm, 0], [0, 1, 0]); cam.perspective = false; cam.height = height_mm.mm
    m.active_view.camera = cam
    'ok - ambil screenshot sekarang (skala: tinggi gambar = ' + height_mm.to_s + ' mm)'
  end

  def restore
    m = Sketchup.active_model
    $serasa_sp.erase! if $serasa_sp && $serasa_sp.valid?
    if $serasa_cam
      c = $serasa_cam; cam = Sketchup::Camera.new(c[0], c[1], c[2]); cam.perspective = c[3]
      c[3] ? cam.fov = c[4] : cam.height = c[4]
      m.active_view.camera = cam
    end
    "restored; section planes tersisa: #{m.entities.grep(Sketchup::SectionPlane).length}"
  end
end
'SerasaRAB loaded'
