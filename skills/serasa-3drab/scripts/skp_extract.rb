# skp_extract.rb - Serasa RAB: ekstraksi kuantitas dari model SketchUp (v2)
#
# Pemasangan (sekali per komputer, paling hemat token):
#   Salin file ini ke folder Plugins SketchUp supaya termuat otomatis:
#     macOS  : ~/Library/Application Support/SketchUp 20xx/SketchUp/Plugins/
#     Windows: %APPDATA%\SketchUp\SketchUp 20xx\SketchUp\Plugins\
#   Agen cukup cek:  defined?(SerasaRAB) ? SerasaRAB::VERSION : 'belum'
#   Kalau belum: load "/path/skp_extract.rb"  (satu baris, jangan tempel isi file).
#
# Satuan mm / m2. region = [xmin, xmax, ymin, ymax] (mm, koordinat dunia).
# bands = [["Lt1", z0, z1], ["Lt2", z1, z2], ["Parapet", z2, 99999]] (mm, elevasi absolut).
# rooms = [{name:, type:'uv'|'xy', rect:[u0,u1,v0,v1] | poly:[[x,y],..], z:[z0,z1]}]
# Semua fungsi mengembalikan string JSON.
require 'json'

module SerasaRAB
  VERSION = '2.0'
  module_function

  SKIP_LAYERS = /KONTUR|PLAN|STREET|VEGET|CAR BIKE|AMBIENCE/i
  SKIP_DEFS   = /SCF|CAY|Decid|tree|pohon|car|mobil|motor|person|people/i

  def mm(v) v.to_mm end
  def area_m2(f, tr) f.area(tr) / 1550.0031 end
  def mat_name(f) m = f.material || f.back_material; m ? m.display_name : '-' end
  def r2(x) x.round(2) end

  def uv(x, y, ang)
    t = ang * Math::PI / 180
    [x * Math.cos(t) + y * Math.sin(t), -x * Math.sin(t) + y * Math.cos(t)]
  end

  def in_region?(b, region)
    c = b.center
    mm(c.x).between?(region[0], region[1]) && mm(c.y).between?(region[2], region[3])
  end

  def roots(region, include_huge: false)
    Sketchup.active_model.entities.select { |e|
      (e.is_a?(Sketchup::Group) || e.is_a?(Sketchup::ComponentInstance)) && e.visible? && e.layer.visible? &&
        e.layer.name !~ SKIP_LAYERS && e.definition.name !~ SKIP_DEFS && in_region?(e.bounds, region) &&
        (include_huge || (mm(e.bounds.width) < 60000 && mm(e.bounds.height) < 60000))
    }
  end

  # tebakan tipe finishing dari material (nama + warna + nama tekstur)
  def fin_guess(mt)
    return 'putih' unless mt
    n = (mt.display_name + ' ' + (mt.texture ? mt.texture.filename.to_s : '')).downcase
    r, g, b = mt.color.red, mt.color.green, mt.color.blue
    return 'kaca' if n =~ /glaz|glass|kaca/ || mt.alpha < 0.6
    return 'kayu' if n =~ /wood|kayu|timber|oak|teak|images/ && r > b + 30
    return 'terracotta' if r > g + 30 && r > b + 50
    return 'ekspos' if (r - g).abs < 15 && (g - b).abs < 15 && r < 235
    return 'putih' if r >= 235 && g >= 235 && b >= 235
    'lain'
  end

  def info(region)
    m = Sketchup.active_model
    out = { path: m.path, roots: [] }
    roots(region, include_huge: true).each { |e|
      b = e.bounds
      out[:roots] << { pid: e.persistent_id, name: e.definition.name, layer: e.layer.name,
                       min: b.min.to_a.map { |v| mm(v).round }, max: b.max.to_a.map { |v| mm(v).round } }
    }
    out.to_json
  end

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

  # 2) ringkasan material + tebakan finishing
  def materials(region, min_m2 = 0.5)
    s = Hash.new(0); mats = {}
    roots(region).each { |e|
      leaves(e).each { |_, t, fs| fs.each { |f|
        n = f.normal.transform(t); next if n.length == 0; n.normalize!
        mt = f.material || f.back_material; k = [mat_name(f), n.z.abs > 0.9 ? 'H' : 'V']
        s[k] += area_m2(f, t); mats[k[0]] ||= mt
      } }
    }
    s.select { |_, v| v >= min_m2 }.sort_by { |_, v| -v }.map { |k, v|
      { material: k[0][0, 30], orient: k[1], m2: r2(v), guess: fin_guess(mats[k[0]]) } }.to_json
  end

  # 3) leaf dengan bbox lokal (u,v)
  def leaf_table(pids, angle = 0, min_area = 0.3)
    m = Sketchup.active_model; out = []
    pids.each { |pid|
      e = m.find_entity_by_persistent_id(pid); next unless e
      leaves(e, Geom::Transformation.new, [], pid.to_s).each { |nm, t, fs|
        pts = fs.flat_map { |f| f.vertices.map { |v| v.position.transform(t) } }
        q = pts.map { |p| uv(mm(p.x), mm(p.y), angle) }; z = pts.map { |p| mm(p.z) }
        a = fs.sum { |f| area_m2(f, t) }; next if a < min_area
        out << { leaf: nm, u: [q.map(&:first).min.round, q.map(&:first).max.round], v: [q.map(&:last).min.round, q.map(&:last).max.round],
                 z: [z.min.round, z.max.round], a: r2(a), mats: fs.map { |f| mat_name(f)[0, 14] }.uniq.first(4) }
      }
    }
    out.to_json
  end

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

  def band_of(z, bands)
    b = bands.find { |_, z0, z1| z >= z0 && z < z1 }
    b ? b[0] : 'lain'
  end

  ARAH = %w[Timur Utara Barat Selatan]

  # 4) DINDING (v2, sampling grid). Akurat untuk muka yang menerus >1 lantai: tiap titik
  #    sampel (default 100 mm) dikelompokkan per pita z (bands) dan per ruang yang dihadap.
  #    Hasil: rooms (ruang x tipe finishing), exterior (pita x arah x tipe), one_side (pasangan per pita).
  def walls_sampled(pids, rooms_json, bands, angle = 0, step = 100, min_thk = 80)
    rooms = rooms_json.is_a?(String) ? JSON.parse(rooms_json) : JSON.parse(rooms_json.to_json)
    m = Sketchup.active_model; cell = (step * step) / 1e6
    res = Hash.new(0); ext = Hash.new(0); side = Hash.new(0)
    pids.each { |pid|
      e = m.find_entity_by_persistent_id(pid); next unless e
      leaves(e).each { |_, t, fs|
        pts = fs.flat_map { |f| f.vertices.map { |v| v.position.transform(t) } }
        next if pts.empty?
        xs = pts.map { |p| mm(p.x) }; ys = pts.map { |p| mm(p.y) }; zs = pts.map { |p| mm(p.z) }
        q = pts.map { |p| uv(mm(p.x), mm(p.y), angle) }
        thk = [[xs.max - xs.min, ys.max - ys.min].min, [q.map(&:first).max - q.map(&:first).min, q.map(&:last).max - q.map(&:last).min].min].min
        next if thk < min_thk || (zs.max - zs.min) < 250
        dir_band = Hash.new(0)
        inv = t.inverse
        fs.each { |f|
          n = f.normal.transform(t); next if n.length == 0; n.normalize!; next if n.z.abs > 0.2
          mt = f.material || f.back_material; g = fin_guess(mt); next if g == 'kaca'
          fpts = f.vertices.map { |v| v.position.transform(t) }
          h = Geom::Vector3d.new(-n.y, n.x, 0); h.normalize!
          ref = fpts[0]; rs = mm(ref.x) * h.x + mm(ref.y) * h.y
          s = fpts.map { |p| mm(p.x) * h.x + mm(p.y) * h.y }
          fz = fpts.map { |p| mm(p.z) }
          d = ARAH[((Math.atan2(n.y, n.x) * 180 / Math::PI + 45) % 360 / 90).floor]
          u = s.min + step / 2.0
          while u < s.max
            z = fz.min + step / 2.0
            while z < fz.max
              dd = u - rs
              wp = Geom::Point3d.new(ref.x + (h.x * dd).mm, ref.y + (h.y * dd).mm, z.mm)
              c = f.classify_point(wp.transform(inv))
              if c == Sketchup::Face::PointInside || c == Sketchup::Face::PointOnEdge
                bd = band_of(z, bands)
                r = room_of(mm(wp.x) + n.x * 200, mm(wp.y) + n.y * 200, z, rooms, angle)
                if r then res[[r, g]] += cell else ext[[bd, d, g]] += cell end
                dir_band[[bd, n.x.round(1), n.y.round(1)]] += cell
              end
              z += step
            end
            u += step
          end
        }
        per = Hash.new(0)
        dir_band.each { |(bd, _, _), a| per[bd] = [per[bd], a].max }
        per.each { |bd, a| side[[pid, bd]] += a }
      }
    }
    { rooms: res.select { |_, v| v >= 0.2 }.map { |k, v| [k[0], k[1], r2(v)] },
      exterior: ext.select { |_, v| v >= 0.3 }.sort.map { |k, v| [k[0], k[1], k[2], r2(v)] },
      one_side: side.select { |_, v| v >= 0.5 }.map { |k, v| [k[0], k[1], r2(v)] },
      cols: { rooms: %w[ruang tipe m2], exterior: %w[pita arah tipe m2], one_side: %w[pid pita m2] } }.to_json
  end

  # versi lama (titik tengah muka) - dipertahankan untuk kompatibilitas
  def classify_walls(pids, rooms_json, angle = 0, min_thk = 80)
    walls_sampled(pids, rooms_json, [['all', -1e9, 1e9]], angle, 100, min_thk)
  end

  # 5) lantai/plafon (v2): muka horizontal per group/material/elevasi; muka kecil (< min_area)
  #    tidak dibuang tapi dirangkum per group sebagai 'kecil' (mis. anak tangga).
  def horizontals(region, zmin, zmax, up = true, min_area = 1.0)
    agg = Hash.new { |h, k| h[k] = [0, [1e9, -1e9], [1e9, -1e9], 0] }
    walk = lambda { |ents, tr, top, d|
      return if d > 8
      ents.each { |e|
        if e.is_a?(Sketchup::Face)
          n = e.normal.transform(tr); next if n.length == 0; n.normalize!
          next unless up ? n.z > 0.9 : n.z < -0.9
          vs = e.outer_loop.vertices.map { |v| v.position.transform(tr) }; z = mm(vs[0].z); next unless z.between?(zmin, zmax)
          xs = vs.map { |p| mm(p.x) }; ys = vs.map { |p| mm(p.y) }
          next unless (xs.sum / xs.size).between?(region[0], region[1]) && (ys.sum / ys.size).between?(region[2], region[3])
          a = area_m2(e, tr)
          k = a < min_area ? [top, 'kecil', nil] : [top, mat_name(e)[0, 20], (z / 50).round * 50]
          h = agg[k]; h[0] += a; h[3] += 1
          h[1] = [[h[1][0], xs.min].min, [h[1][1], xs.max].max]; h[2] = [[h[2][0], ys.min].min, [h[2][1], ys.max].max]
        elsif (e.is_a?(Sketchup::Group) || e.is_a?(Sketchup::ComponentInstance)) && e.visible? && e.layer.visible? && e.definition.name !~ SKIP_DEFS
          walk.call(e.definition.entities, tr * e.transformation, top, d + 1)
        end
      }
    }
    Sketchup.active_model.entities.each { |e|
      next unless (e.is_a?(Sketchup::Group) || e.is_a?(Sketchup::ComponentInstance)) && e.visible? && e.layer.visible?
      next if e.layer.name =~ SKIP_LAYERS || e.definition.name =~ SKIP_DEFS
      walk.call(e.definition.entities, e.transformation, "#{e.persistent_id} #{e.definition.name[0, 14]} [#{e.layer.name[0, 18]}]", 0)
    }
    agg.select { |k, v| v[0] >= (k[1] == 'kecil' ? 1.0 : min_area) }.sort_by { |k, _| [k[0], k[2].to_i] }.map { |k, v|
      { g: k[0], mat: k[1], z: k[2], m2: r2(v[0]), n: v[3], x: v[1].map(&:round), y: v[2].map(&:round) } }.to_json
  end

  # 6) bukaan (v2): panel kaca dikelompokkan per unit. Root kecil (< 6 m, mis. komponen pintu atau
  #    group kusen) = 1 unit, frame_xyz = ukuran bbox root (pakai untuk lebar x tinggi kusen);
  #    root besar (massa) -> tiap anak tingkat-1 = 1 unit. w = bentang panel kaca (daun terbuka bisa miring).
  def glazing(region)
    units = Hash.new { |h, k| h[k] = { glass: 0, pts: [], panels: 0 } }
    scan = lambda { |ents, tr, key, d|
      return if d > 8
      ents.each { |e|
        next unless (e.is_a?(Sketchup::Group) || e.is_a?(Sketchup::ComponentInstance)) && e.visible? && e.layer.visible?
        t = tr * e.transformation; fs = e.definition.entities.grep(Sketchup::Face)
        k = key || "#{e.persistent_id} #{e.definition.name[0, 26]}"
        g = fs.select { |f| fin_guess(f.material || f.back_material) == 'kaca' }
        if g.sum { |f| area_m2(f, t) } >= 0.1
          u = units[k]; u[:glass] += g.sum { |f| area_m2(f, t) } / 2; u[:panels] += 1
          u[:pts] += fs.flat_map { |f| f.vertices.map { |v| v.position.transform(t) } }
        end
        scan.call(e.definition.entities, t, k, d + 1)
      }
    }
    roots(region).each { |r|
      small = [mm(r.bounds.width), mm(r.bounds.height)].max < 6000
      k = small ? "#{r.persistent_id} #{r.definition.name[0, 26]}" : nil
      units[k][:frame] = [r.bounds.width, r.bounds.height, r.bounds.depth].map { |v| mm(v).round } if k
      scan.call(r.definition.entities, r.transformation, k, 0)
    }
    units.select { |_, u| u[:glass] >= 0.1 && !u[:pts].empty? }.map { |k, u|
      xs = u[:pts].map { |p| mm(p.x) }; ys = u[:pts].map { |p| mm(p.y) }; zs = u[:pts].map { |p| mm(p.z) }
      { unit: k, c: [((xs.max + xs.min) / 2).round, ((ys.max + ys.min) / 2).round], w: Math.hypot(xs.max - xs.min, ys.max - ys.min).round,
        z: [zs.min.round, zs.max.round], glass_m2: r2(u[:glass]), leaves: u[:panels], frame_xyz: u[:frame] }.compact }.to_json
  end

  # 7) atap / bidang miring
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
    out.select { |_, v| v > 0.3 }.map { |k, v| { leaf: k[0], front: k[1], back: k[2], slope: k[3], dir: k[4], m2: r2(v) } }.to_json
  end

  # 8) hitung instance komponen per nama definisi di region
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

  # 9) TAKEOFF satu panggilan: dinding (sampling per pita), lantai (up), plafon/sisi bawah (dn), bukaan.
  #    wall_pids nil -> semua root di region. Output ringkas siap dipetakan ke input JSON.
  def takeoff(region, rooms_json, bands, angle = 0, wall_pids = nil)
    pids = wall_pids || roots(region).map(&:persistent_id)
    zlo = bands.map { |b| b[1] }.min - 500; zhi = [bands.map { |b| b[2] }.max, 20000].min
    { walls: JSON.parse(walls_sampled(pids, rooms_json, bands, angle)),
      floors: JSON.parse(horizontals(region, zlo, zhi, true)),
      under: JSON.parse(horizontals(region, zlo, zhi, false)),
      openings: JSON.parse(glazing(region)) }.to_json
  end

  # 10) bantu visual
  def save_camera
    m = Sketchup.active_model; c = m.active_view.camera
    $serasa_cam = [c.eye.to_a, c.target.to_a, c.up.to_a, c.perspective?, (c.perspective? ? c.fov : c.height)]
    $serasa_dsc = m.rendering_options['DisplaySectionCuts']
    'saved'
  end

  def plan_view(cx, cy, height_mm, cut_z = nil)
    m = Sketchup.active_model
    $serasa_sp.erase! if $serasa_sp && $serasa_sp.valid?
    if cut_z
      $serasa_sp = m.entities.add_section_plane([0, 0, cut_z.mm], [0, 0, -1]); $serasa_sp.activate
      m.rendering_options['DisplaySectionPlanes'] = false
      m.rendering_options['DisplaySectionCuts'] = true
    end
    cam = Sketchup::Camera.new([cx.mm, cy.mm, 100_000.mm], [cx.mm, cy.mm, 0], [0, 1, 0]); cam.perspective = false; cam.height = height_mm.mm
    m.active_view.camera = cam
    'ok - screenshot (tinggi gambar = ' + height_mm.to_s + ' mm, utara = atas)'
  end

  # kamera perspektif cepat: dari titik mata ke target (mm)
  def persp(eye, target, fov = 45)
    cam = Sketchup::Camera.new(eye.map(&:mm), target.map(&:mm), [0, 0, 1]); cam.fov = fov
    Sketchup.active_model.active_view.camera = cam; 'ok'
  end

  def restore
    m = Sketchup.active_model
    $serasa_sp.erase! if $serasa_sp && $serasa_sp.valid?
    m.rendering_options['DisplaySectionCuts'] = $serasa_dsc unless $serasa_dsc.nil?
    if $serasa_cam
      c = $serasa_cam; cam = Sketchup::Camera.new(c[0], c[1], c[2]); cam.perspective = c[3]
      c[3] ? cam.fov = c[4] : cam.height = c[4]
      m.active_view.camera = cam
    end
    "restored; section planes tersisa: #{m.entities.grep(Sketchup::SectionPlane).length}"
  end
end
'SerasaRAB ' + SerasaRAB::VERSION + ' loaded'
