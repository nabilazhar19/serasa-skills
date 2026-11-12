# skp_extract.rb - Serasa RAB: ekstraksi kuantitas dari model SketchUp + jembatan ke Viewport RAB (v2.4)
#
# Pemasangan (sekali per komputer; Mac & Windows, semua versi SketchUp):
#   load "<folder skill>/scripts/skp_extract.rb"; SerasaRAB.install_plugin
#   -> menjalankan scripts/setup.py (plugin ke SEMUA versi SketchUp + viewport + library Python).
#   Tanpa Python: plugin tetap terpasang di versi SketchUp ini, viewport menyusul setelah Python ada.
#   Agen cukup cek:  defined?(SerasaRAB) ? SerasaRAB::VERSION : 'belum'
# Menu: Extensions > Serasa RAB > Buka Viewport RAB / Hentikan Viewport / Pasang ulang.
#
# Satuan mm / m2. region = [xmin, xmax, ymin, ymax] (mm, koordinat dunia).
# bands = [["Lt1", z0, z1], ["Lt2", z1, z2], ["Parapet", z2, 99999]] (mm, elevasi absolut).
# rooms = [{name:, type:'uv'|'xy', rect:[u0,u1,v0,v1] | poly:[[x,y],..], z:[z0,z1]}]
# Semua fungsi take-off mengembalikan string JSON.
require 'json'
require 'fileutils'
require 'open3'

module SerasaRAB
  VERSION = '2.4'
  SRC = File.expand_path(__FILE__) rescue nil
  WIN = (Sketchup.platform == :platform_win rescue RUBY_PLATFORM =~ /mswin|mingw/)
  module_function

  # ---------- instalasi & lingkungan ----------
  # folder bersama (viewport + builder + env.json), sama untuk semua versi SketchUp & semua agen
  def home_shared
    WIN ? File.join(ENV['APPDATA'].to_s.tr('\\', '/'), 'SerasaRAB') : File.expand_path('~/Library/Application Support/SerasaRAB')
  end

  # folder skill bila file ini dimuat dari <skill>/scripts/
  def skill_dir
    d = File.expand_path('..', File.dirname(SRC.to_s))
    File.file?(File.join(d, 'viewport', 'tools.py')) ? d : nil
  end

  def home
    File.file?(File.join(home_shared, 'viewport', 'tools.py')) ? home_shared : skill_dir
  end

  def env
    JSON.parse(File.read(File.join(home_shared, 'env.json'))) rescue {}
  end

  def py_ok?(exe)
    return false unless exe && File.file?(exe)
    out, st = Open3.capture2e(exe, '-c', 'import sys; print(sys.version_info >= (3, 8))')
    st.success? && out.include?('True')
  rescue StandardError
    false
  end

  # Python untuk viewport: env.json (dicatat setup.py) -> lokasi umum. Path absolut supaya tidak bergantung PATH.
  def python
    c = [env['python']]
    if WIN
      la = ENV['LOCALAPPDATA'].to_s.tr('\\', '/')
      c += Dir.glob("#{la}/Programs/Python/Python3*/python.exe").sort.reverse
      c += Dir.glob('C:/Program Files/Python3*/python.exe').sort.reverse + Dir.glob('C:/Python3*/python.exe').sort.reverse
      c += ENV['PATH'].to_s.split(';').map { |d| File.join(d.tr('\\', '/'), 'python.exe') }.reject { |p| p =~ /WindowsApps/i }
    else
      c += %w[/opt/homebrew/bin/python3 /usr/local/bin/python3 /Library/Frameworks/Python.framework/Versions/Current/bin/python3]
      c << '/usr/bin/python3' if File.directory?('/Library/Developer/CommandLineTools') || File.directory?('/Applications/Xcode.app')
    end
    c.compact.uniq.find { |p| py_ok?(p) }
  end

  # python tanpa jendela konsol (Windows)
  def python_bg
    py = python or return nil
    w = File.join(File.dirname(py), 'pythonw.exe')
    WIN && File.file?(w) ? w : py
  end

  # Pasang/perbarui: setup.py (semua versi SketchUp, viewport, library Python). Fallback: salin plugin ke versi ini.
  def install_plugin
    return 'gagal: script tidak dimuat dari file (pakai load "<path>")' unless SRC && File.file?(SRC)
    setup = [skill_dir, home_shared].compact.map { |d| File.join(d, 'scripts', 'setup.py') }.find { |f| File.file?(f) }
    py = python
    if setup && py
      out, st = Open3.capture2e(py, setup)
      return "Serasa RAB #{VERSION}: #{st.success? ? 'terpasang' : 'sebagian gagal'}\n#{out}"
    end
    dir = Sketchup.find_support_file('Plugins')
    dest = File.join(dir, 'serasa_skp_extract.rb')
    FileUtils.cp(SRC, dest) unless File.expand_path(dest) == SRC
    msg = "plugin terpasang #{VERSION}: #{dest}"
    msg += py ? '' : ' · Python 3 belum ada -> viewport belum bisa jalan. ' +
                     (WIN ? 'Klik dua kali setup.bat di folder skill (memasang Python lewat winget).' : 'Klik dua kali setup.command di folder skill.')
    msg
  end

  # ---------- viewport ----------
  def tools_py
    h = home or return nil
    f = File.join(h, 'viewport', 'tools.py'); File.file?(f) ? f : nil
  end

  def project_dir(m = Sketchup.active_model)
    m && !m.path.to_s.empty? ? File.dirname(m.path) : nil
  end

  def run_tools(args, wait: false)
    t = tools_py or return 'viewport belum terpasang -> SerasaRAB.install_plugin'
    py = wait ? python : python_bg
    return 'Python 3 belum ada -> jalankan setup' + (WIN ? '.bat' : '.command') + ' di folder skill' unless py
    if wait
      out, = Open3.capture2e(py, t, *args); return out.strip
    end
    log = File.join(File.dirname(t), 'server.log')
    opt = { [:out, :err] => [log, 'a'], in: (WIN ? 'NUL' : '/dev/null') }
    if WIN then opt[:new_pgroup] = true else opt[:pgroup] = true end
    Process.detach(Process.spawn(py, t, *args, opt)); 'ok'
  rescue StandardError => e
    "gagal menjalankan viewport: #{e}"
  end

  # Buka viewport untuk model aktif (proyek = folder file .skp). Belum ada viewport.json -> dibuat (judul = nama model).
  def viewport(dir = nil)
    dir ||= project_dir
    if dir && !File.file?(File.join(dir, '_serasa_tools', 'viewport.json'))
      run_tools(['init', '--project', dir, '--title', File.basename(Sketchup.active_model.path.to_s, '.skp')], wait: true)
    end
    run_tools(dir ? ['open', '--project', dir] : ['open'])
  end

  # dipanggil saat model dibuka: nyalakan server di belakang layar (tanpa browser) bila proyek punya viewport.json
  def ensure_viewport(m)
    dir = project_dir(m); return unless dir && File.file?(File.join(dir, '_serasa_tools', 'viewport.json'))
    run_tools(['ensure', '--project', dir])
  end

  def stop_viewport
    run_tools(['stop'], wait: true)
  end

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

  # 11) EXPORT 3D untuk viewport (v2.3): geometri root di region -> JSON (segitiga, mm dunia) + luas per tag.
  #   objects: [{pid, name, layer, bbox, qty: {tag: mm2}, parts: [{c: [r,g,b,a], t: tags, p: [x,y,z, ...]}]}]
  #   tag muka (sampel 400 mm, logika sama dengan walls_sampled):
  #     dinding  "R|<ruang>|<tipe>" (menghadap ruang) · "E|<arah>|<tipe>" (muka luar)
  #     lantai   "F|<ruang>|<tipe>" (muka atas di dalam ruang) · plafon "C|<ruang>|<tipe>" (muka bawah)
  #   qty = luas muka (mm², setelah transformasi) dibagi ke tiap tag sesuai porsi sampel -> dipakai viewport
  #   untuk menghitung ulang volume RAB tiap model disimpan. rooms/bands/angle = sama seperti takeoff.
  def sample_tags(f, t, inv, rooms, angle, walllike, step = 400)
    n = f.normal.transform(t); return {} if n.length == 0
    n.normalize!
    mt = f.material || f.back_material; g = fin_guess(mt); return {} if g == 'kaca'
    fpts = f.vertices.map { |v| v.position.transform(t) }
    out = Hash.new(0)
    if n.z.abs > 0.9                      # bidang datar -> lantai / plafon per ruang
      xs = fpts.map { |p| mm(p.x) }; ys = fpts.map { |p| mm(p.y) }; z = mm(fpts[0].z)
      sx = [(xs.max - xs.min) / 2.0, step / 2.0].min; sy = [(ys.max - ys.min) / 2.0, step / 2.0].min
      x = xs.min + sx
      while x < xs.max
        y = ys.min + sy
        while y < ys.max
          wp = Geom::Point3d.new(x.mm, y.mm, z.mm)
          c = f.classify_point(wp.transform(inv))
          if c == Sketchup::Face::PointInside || c == Sketchup::Face::PointOnEdge
            r = room_of(x, y, z + (n.z > 0 ? 50 : -50), rooms, angle)
            out[r ? "#{n.z > 0 ? 'F' : 'C'}|#{r}|#{g}" : ''] += 1
          end
          y += step
        end
        x += step
      end
      return out
    end
    return {} if !walllike || n.z.abs > 0.2
    h = Geom::Vector3d.new(-n.y, n.x, 0); h.normalize!
    ref = fpts[0]; rs = mm(ref.x) * h.x + mm(ref.y) * h.y
    s = fpts.map { |p| mm(p.x) * h.x + mm(p.y) * h.y }; fz = fpts.map { |p| mm(p.z) }
    d = ARAH[((Math.atan2(n.y, n.x) * 180 / Math::PI + 45) % 360 / 90).floor]
    su = [(s.max - s.min) / 2.0, step / 2.0].min; sz = [(fz.max - fz.min) / 2.0, step / 2.0].min
    u = s.min + su
    while u < s.max
      z = fz.min + sz
      while z < fz.max
        dd = u - rs
        wp = Geom::Point3d.new(ref.x + (h.x * dd).mm, ref.y + (h.y * dd).mm, z.mm)
        c = f.classify_point(wp.transform(inv))
        if c == Sketchup::Face::PointInside || c == Sketchup::Face::PointOnEdge
          r = room_of(mm(wp.x) + n.x * 200, mm(wp.y) + n.y * 200, z, rooms, angle)
          out[r ? "R|#{r}|#{g}" : "E|#{d}|#{g}"] += 1
        end
        z += step
      end
      u += step
    end
    out
  end

  def export_mesh(region, path, rooms_json = '[]', bands = [], angle = 0, model = nil)
    rooms = rooms_json.is_a?(String) ? JSON.parse(rooms_json) : JSON.parse(rooms_json.to_json)
    m = model || Sketchup.active_model; tri = 0; t0 = Time.now
    out = { model: m.path, exported: Time.now.strftime('%Y-%m-%d %H:%M:%S'), region: region, bands: bands,
            rooms: rooms, angle: angle, objects: [] }
    roots(region, include_huge: true).each { |r|
      parts = Hash.new { |hh, k| hh[k] = [] }; qty = Hash.new(0.0); bb = Geom::BoundingBox.new
      leaves(r).each { |_, t, fs|
        pts = fs.flat_map { |f| f.vertices.map { |v| v.position.transform(t) } }
        next if pts.empty?
        pts.each { |p| bb.add(p) }
        xs = pts.map { |p| mm(p.x) }; ys = pts.map { |p| mm(p.y) }; zs = pts.map { |p| mm(p.z) }
        q = pts.map { |p| uv(mm(p.x), mm(p.y), angle) }
        thk = [[xs.max - xs.min, ys.max - ys.min].min, [q.map(&:first).max - q.map(&:first).min, q.map(&:last).max - q.map(&:last).min].min].min
        walllike = thk >= 80 && (zs.max - zs.min) >= 250
        inv = t.inverse
        fs.each { |f|
          mt = f.material || f.back_material
          col = mt ? [mt.color.red, mt.color.green, mt.color.blue, (mt.alpha * 255).round] : [238, 236, 230, 255]
          cnt = sample_tags(f, t, inv, rooms, angle, walllike)
          tags = cnt.keys.reject(&:empty?).sort
          me = f.mesh(0); arr = parts[[col, tags.join(';')]]; area = 0.0
          me.polygons.each { |poly|
            a = poly.map { |i| me.point_at(i.abs).transform(t) }
            a.each { |p| arr << mm(p.x).round << mm(p.y).round << mm(p.z).round }
            if a.size == 3
              v1 = a[1] - a[0]; v2 = a[2] - a[0]; area += (v1 * v2).length.to_mm.to_f * 1.0
            end
            tri += 1
          }
          # luas segitiga: |v1 x v2| (inch^2 -> mm^2), lalu dibagi 2
          area = area * 25.4 / 2.0
          tot = cnt.values.sum
          if tot > 0 then cnt.each { |k, c| qty[k] += area * c / tot } else qty[''] += area end
        }
      }
      out[:objects] << { pid: r.persistent_id, name: r.definition.name, layer: r.layer.name,
                         bbox: [mm(bb.min.x).round, mm(bb.min.y).round, mm(bb.min.z).round, mm(bb.max.x).round, mm(bb.max.y).round, mm(bb.max.z).round],
                         qty: qty.transform_values { |v| v.round }, parts: parts.map { |(c, tg), p| { c: c, t: tg, p: p } } }
    }
    tmp = path + '.tmp'; File.write(tmp, JSON.generate(out)); File.rename(tmp, path)  # atomik
    "ok #{out[:objects].size} objek, #{tri} segitiga, #{(Time.now - t0).round(1)} dtk -> #{path}"
  end

  # Ekspor ulang otomatis setiap model disimpan (Cmd+S). Setelan disimpan di <folder model>/_serasa_tools/serasa_watch.json,
  # jadi tetap aktif setelah SketchUp ditutup-buka (plugin memasang ulang observer saat model dibuka).
  class ExportOnSave < Sketchup::ModelObserver
    def initialize(args) @args = args end
    def onPostSaveModel(m)
      SerasaRAB.export_mesh(*@args, m)
    rescue => e
      puts "SerasaRAB export gagal: #{e}"
    end
  end

  class AutoWatch < Sketchup::AppObserver
    def onOpenModel(m) SerasaRAB.attach_watch(m); SerasaRAB.ensure_viewport(m) end
    def onActivateModel(m) SerasaRAB.attach_watch(m) end
  end

  def watch_file(m) m.path.to_s.empty? ? nil : File.join(File.dirname(m.path), '_serasa_tools', 'serasa_watch.json') end

  def attach_watch(m)
    f = watch_file(m); return nil unless f && File.file?(f)
    cfg = JSON.parse(File.read(f))
    return nil unless cfg['model'] == File.basename(m.path)
    $serasa_obs ||= {}
    return 'sudah aktif' if $serasa_obs[m.guid]
    o = ExportOnSave.new([cfg['region'], cfg['path'], cfg['rooms'].to_json, cfg['bands'], cfg['angle'] || 0])
    m.add_observer(o); $serasa_obs[m.guid] = o
    'aktif'
  rescue => e
    puts "SerasaRAB watch gagal: #{e}"; nil
  end

  def watch_export(region, path, rooms_json = '[]', bands = [], angle = 0)
    m = Sketchup.active_model
    rooms = rooms_json.is_a?(String) ? JSON.parse(rooms_json) : JSON.parse(rooms_json.to_json)
    f = watch_file(m) or return 'simpan model dulu (belum punya path)'
    FileUtils.mkdir_p(File.dirname(f))
    File.write(f, JSON.pretty_generate({ model: File.basename(m.path), region: region, path: path, rooms: rooms, bands: bands, angle: angle }))
    $serasa_obs ||= {}
    m.remove_observer($serasa_obs.delete(m.guid)) if $serasa_obs[m.guid]
    attach_watch(m)
    export_mesh(region, path, rooms, bands, angle, m) + ' · ekspor ulang otomatis tiap model disimpan (tetap aktif setelah SketchUp dibuka ulang)'
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

# saat plugin dimuat (SketchUp start / load): pantau model yang dibuka, dan model yang sedang terbuka
unless $serasa_app_obs
  $serasa_app_obs = SerasaRAB::AutoWatch.new
  Sketchup.add_observer($serasa_app_obs)
end
SerasaRAB.attach_watch(Sketchup.active_model) if Sketchup.active_model

# menu Extensions > Serasa RAB (sekali per sesi SketchUp)
unless $serasa_menu
  $serasa_menu = true
  sub = UI.menu(Sketchup.version.to_i >= 16 ? 'Extensions' : 'Plugins').add_submenu('Serasa RAB')
  sub.add_item('Buka Viewport RAB') {
    r = SerasaRAB.viewport
    UI.messagebox(r) unless r == 'ok'
  }
  sub.add_item('Hentikan Viewport') { UI.messagebox(SerasaRAB.stop_viewport) }
  sub.add_separator
  sub.add_item('Pasang ulang / perbarui') { UI.messagebox(SerasaRAB.install_plugin) }
  sub.add_item("Tentang (v#{SerasaRAB::VERSION})") {
    UI.messagebox("Serasa RAB #{SerasaRAB::VERSION}\nviewport: #{SerasaRAB.home || '-'}\nPython: #{SerasaRAB.python || 'belum ada'}")
  }
end
SerasaRAB.ensure_viewport(Sketchup.active_model) if Sketchup.active_model && !$serasa_vp_started
$serasa_vp_started = true
'SerasaRAB ' + SerasaRAB::VERSION + ' loaded'
