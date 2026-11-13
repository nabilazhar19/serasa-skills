# skp_extract.rb - Serasa RAB: ekstraksi kuantitas dari model SketchUp + jembatan ke Viewport RAB (v2.5)
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
  VERSION = '2.5'
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

  # 11) EKSPOR 3D untuk Viewport RAB (format 4, v2.5) -----------------------------------------------
  # Setelan ekspor = <proyek>/_serasa_tools/serasa_watch.json (ditulis watch_export, boleh diedit agen):
  #   model, path, region, rooms, bands, angle
  #   skip_layers    regex layer yang tidak ikut (default SKIP_LAYERS)
  #   display_layers regex layer yang ikut tampil walau di skip_layers (default KONTUR = tapak); null = tidak ada
  #   measures       {pid: {resep}}  ukuran tambahan per objek, hanya dihitung bila diminta:
  #                  solid (volume m3), bands [[nama,z0,z1]] (volume per pita), masonry_include/exclude (regex path leaf),
  #                  roof_materials [nama material], perimeter, roster (true | regex definisi modul),
  #                  seat_name (nama leaf dudukan), steel_materials [..], inclined_envelope
  # Isi file ekspor:
  #   materials [[nama, r, g, b, a]] · tagsets ["", "R|Toko 1|putih", ...]
  #   defs [{name, f: [[mat, ntri], ..], v: [x,y,z mm lokal ..], t: [i,j,k ..], e: [x,y,z,x,y,z ..]}]   (geometri sekali per definisi)
  #   objects [{pid, name, layer, bbox, qty {tag: mm2}, measures {}, leaves [[def, m12, mat_warisan]], ft [[tagset, jumlah_muka] ..]}]
  #   tag muka: dinding "R|ruang|tipe" / "E|arah|tipe" (+ "Q|pita|E|arah|tipe" di qty), lantai "F|ruang|tipe", plafon "C|ruang|tipe".
  # Ekspor bertahap: hanya objek yang berubah sejak ekspor terakhir yang dihitung ulang (konservatif: ragu = hitung ulang).
  EXPORT_FORMAT = 4
  DISPLAY_EXTRA = 'KONTUR'
  MIN_FLOOR_M2 = 0.1          # muka datar lebih kecil dari ini tidak ditandai lantai/plafon (mis. dudukan kecil, anak tangga roster)

  def r1(x) y = (x * 10).round; y % 10 == 0 ? y / 10 : y / 10.0 end
  def pjson(x) x.is_a?(String) ? JSON.parse(x) : JSON.parse(x.to_json) end
  def instance?(e) (e.is_a?(Sketchup::Group) || e.is_a?(Sketchup::ComponentInstance)) && e.visible? && e.layer.visible? end

  def export_roots(m, cfg)
    region = cfg['region']
    skip = cfg['skip_layers'] ? Regexp.new(cfg['skip_layers'], Regexp::IGNORECASE) : SKIP_LAYERS
    extra = cfg.key?('display_layers') ? cfg['display_layers'] : DISPLAY_EXTRA
    extra = extra ? Regexp.new(extra, Regexp::IGNORECASE) : nil
    m.entities.select { |e|
      next false unless instance?(e) && in_region?(e.bounds, region) && e.definition.name !~ SKIP_DEFS
      e.layer.name !~ skip || (extra && e.layer.name =~ extra)
    }
  end

  # --- penanda perubahan (murah: hanya menaikkan angka; dipasang saat model dibuka) ---
  def rev() @rev ||= Hash.new(0) end
  def touch(key) rev[key] += 1 end
  def ekey(es) p = es.parent; p.is_a?(Sketchup::Model) ? 0 : p.entityID end

  class ChangeMark < Sketchup::EntitiesObserver
    def onElementAdded(es, e) SerasaRAB.touch(SerasaRAB.ekey(es)) end
    def onElementModified(es, e) SerasaRAB.touch(SerasaRAB.ekey(es)) end
    def onElementRemoved(es, id) SerasaRAB.touch(SerasaRAB.ekey(es)) end
    def onEraseEntities(es) SerasaRAB.touch(SerasaRAB.ekey(es)) end
  end
  class DefMark < Sketchup::DefinitionsObserver
    def onComponentAdded(defs, d) d.entities.add_observer(SerasaRAB.change_mark) rescue nil end
  end
  class MatMark < Sketchup::MaterialsObserver
    def onMaterialChange(ms, mt) SerasaRAB.touch("mat:#{mt.name}") end
    def onMaterialRemove(ms, mt) SerasaRAB.touch("mat:#{mt.name}") end
  end
  class LayerMark < Sketchup::LayersObserver
    def onLayerChanged(ls, l) SerasaRAB.touch(:layers) end
    def onLayerRemoved(ls, l) SerasaRAB.touch(:layers) end
  end

  def change_mark() @change_mark ||= ChangeMark.new end

  def mark_model(m)
    @marked ||= {}
    return if @marked[m.guid]
    o = change_mark
    m.entities.add_observer(o)
    m.definitions.each { |d| d.entities.add_observer(o) }
    m.definitions.add_observer(DefMark.new); m.materials.add_observer(MatMark.new); m.layers.add_observer(LayerMark.new)
    @marked[m.guid] = true
  end

  # tanda tangan objek: transformasi + material + layer + angka perubahan semua definisi di dalamnya
  def signature(r, mats_used)
    keys = []
    walk = lambda { |e, d| return if d > 12; keys << e.definition.entityID; e.definition.entities.each { |c| walk.call(c, d + 1) if c.is_a?(Sketchup::Group) || c.is_a?(Sketchup::ComponentInstance) } }
    walk.call(r, 0)
    [r.transformation.to_a, r.material && r.material.name, r.layer.name, r.layer.visible?, rev[:layers],
     keys.map { |k| [k, rev[k]] }, (mats_used || []).map { |n| rev["mat:#{n}"] }].hash
  end

  # --- geometri per definisi (lokal, mm), dipakai bersama semua instance ---
  def def_geo(d)
    @geo ||= {}
    k = d.entityID; c = @geo[k]
    return c if c && c[:rev] == rev[k]
    f_out = []; v = []; t = []; e = []; faces = []; fn = []
    d.entities.each { |f|
      next unless f.is_a?(Sketchup::Face) && f.visible? && f.layer.visible?
      me = f.mesh(0); pts = me.points; base = v.length / 3
      pts.each { |p| v << r1(p.x.to_mm) << r1(p.y.to_mm) << r1(p.z.to_mm) }
      n = 0
      me.polygons.each { |poly| next unless poly.length == 3; poly.each { |i| t << base + i.abs - 1 }; n += 1 }
      mt = f.material || f.back_material
      f_out << [mt ? mt.name : nil, n]; faces << f; fn << f.normal
    }
    d.entities.each { |ed|
      next unless ed.is_a?(Sketchup::Edge) && ed.visible? && ed.layer.visible? && !ed.soft? && !ed.smooth? && !ed.hidden?
      [ed.start.position, ed.end.position].each { |p| e << r1(p.x.to_mm) << r1(p.y.to_mm) << r1(p.z.to_mm) }
    }
    use = Hash.new(0); faces.each { |f| f.edges.each { |ed| use[ed.entityID] += 1 } }
    @geo[k] = { rev: rev[k], name: d.name, f: f_out, v: v, t: t, e: e, faces: faces, fn: fn, empty: f_out.empty? && e.empty?,
                closed: !use.empty? && use.values.all? { |n| n == 2 } }
  end

  def walk_leaves(ent, tr, inh, path, out, depth = 0)
    return if depth > 12
    d = ent.definition; t = tr * ent.transformation; inh = ent.material || inh; path = path + '/' + d.name
    out << [d, t, inh, path]
    d.entities.each { |c| walk_leaves(c, t, inh, path, out, depth + 1) if instance?(c) && c.definition.name !~ SKIP_DEFS }
    out
  end

  def m12(t)
    a = t.to_a; w = a[15].to_f; w = 1.0 if w == 0
    [a[0], a[1], a[2], a[4], a[5], a[6], a[8], a[9], a[10]].map { |x| (x / w).round(7) } + [a[12], a[13], a[14]].map { |x| r1(x / w * 25.4) }
  end

  # tag muka untuk volume per ruang (logika sama dengan walls_sampled; sampel 400 mm)
  def face_tags(f, t, inv, rooms, angle, walllike, qbands, step = 400)
    n = f.normal.transform(t); return {} if n.length == 0
    n.normalize!
    g = fin_guess(f.material || f.back_material); return {} if g == 'kaca'
    fpts = f.vertices.map { |vx| vx.position.transform(t) }
    out = Hash.new(0)
    if n.z.abs > 0.9
      return {} if f.area(t) / 1550.0031 < MIN_FLOOR_M2
      xs = fpts.map { |p| mm(p.x) }; ys = fpts.map { |p| mm(p.y) }; z = mm(fpts[0].z)
      sx = [(xs.max - xs.min) / 2.0, step / 2.0].min; sy = [(ys.max - ys.min) / 2.0, step / 2.0].min
      x = xs.min + sx
      while x < xs.max
        y = ys.min + sy
        while y < ys.max
          c = f.classify_point(Geom::Point3d.new(x.mm, y.mm, z.mm).transform(inv))
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
          out["Q|#{band_of(z, qbands)}|E|#{d}|#{g}"] += 1 if !r && !qbands.empty?
        end
        z += step
      end
      u += step
    end
    out
  end

  # --- ukuran tambahan (hanya objek yang punya resep) ---
  def volume_above_triangle(points, z_mm)
    z = z_mm.mm; poly = []
    points.each_with_index { |a, i|
      b = points[(i + 1) % points.size]; ina = a.z >= z; inb = b.z >= z
      poly << a if ina
      if ina != inb
        f = (z - a.z) / (b.z - a.z); poly << Geom::Point3d.new(a.x + (b.x - a.x) * f, a.y + (b.y - a.y) * f, z)
      end
    }
    return 0.0 if poly.size < 3
    tot = 0.0
    (1...poly.size - 1).each { |i| a, b, c = poly[0], poly[i], poly[i + 1]; tot += ((b - a) * (c - a)).z / 2.0 * ((a.z + b.z + c.z) / 3.0 - z) * 25.4**3 }
    tot
  end

  def minimum_rectangle(points)
    ps = points.map { |p| [mm(p.x).round(3), mm(p.y).round(3)] }.uniq.sort
    return [0.0, 0.0] if ps.size < 3
    cross = lambda { |a, b, c| (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) }
    lo = []; ps.each { |p| lo.pop while lo.size >= 2 && cross.call(lo[-2], lo[-1], p) <= 0; lo << p }
    hi = []; ps.reverse_each { |p| hi.pop while hi.size >= 2 && cross.call(hi[-2], hi[-1], p) <= 0; hi << p }
    hull = lo[0...-1] + hi[0...-1]; best = nil
    hull.each_with_index { |a, i|
      b = hull[(i + 1) % hull.size]; dx = b[0] - a[0]; dy = b[1] - a[1]; ln = Math.hypot(dx, dy); next if ln == 0
      u = hull.map { |x, y| (x * dx + y * dy) / ln }; v = hull.map { |x, y| (-x * dy + y * dx) / ln }
      dims = [u.max - u.min, v.max - v.min]
      best = dims if best.nil? || dims.inject(:*) < best.inject(:*)
    }
    best || [0.0, 0.0]
  end

  def world_tris(d, t)
    g = def_geo(d); v = g[:v]; out = []
    g[:t].each_slice(3) { |a| out << a.map { |i| Geom::Point3d.new((v[i * 3] / 25.4), (v[i * 3 + 1] / 25.4), (v[i * 3 + 2] / 25.4)).transform(t) } }
    out
  end

  # roster: luas = lebar x tinggi tiap modul. Modul = regex resep, atau otomatis: potongan (definisi) yang paling sering muncul;
  # bila induknya berisi tepat satu potongan itu, induk = modul (modul tersusun dari beberapa potongan), selain itu potongan = modul.
  def roster_area(r, rule)
    cnt = Hash.new(0); mind = Hash.new(99); insts = []
    walk = lambda { |e, tr, dd, par|
      next if dd > 12
      tw = tr * e.transformation
      e.definition.entities.each { |c|
        next unless instance?(c)
        k = c.definition.entityID; cnt[k] += 1; mind[k] = dd if dd < mind[k]
        insts << [c, tw, par]; walk.call(c, tw, dd + 1, [c, tw])
      } }
    walk.call(r, Geom::Transformation.new, 0, nil)
    return 0.0 if insts.empty?
    mods = if rule.is_a?(String)
             rx = Regexp.new(rule, Regexp::IGNORECASE); insts.select { |c, _, _| c.definition.name =~ rx }.map { |c, tw, _| [c, tw] }
           else
             most = cnt.values.max
             piece = cnt.select { |_, n| n == most }.keys.max_by { |k| mind[k] }
             occ = insts.select { |c, _, _| c.definition.entityID == piece }
             par = occ.first[2]
             once = par && par[0].definition.entities.count { |x| instance?(x) && x.definition.entityID == piece } == 1
             once ? occ.map { |_, _, pp| [pp[0], pp[1]] } : occ.map { |c, tw, _| [c, tw] }
           end
    mods.sum { |c, tw|
      ps = walk_leaves(c, tw, nil, '', []).flat_map { |dd, tt, _, _| dd.bounds.empty? ? [] : (0..7).map { |i| dd.bounds.corner(i).transform(tt) } }
      next 0.0 if ps.empty?
      zs = ps.map { |q| mm(q.z) }; minimum_rectangle(ps).max * (zs.max - zs.min) / 1e6
    }
  end

  def measures_for(r, leaves, recipe)
    out = {}
    need_solid = recipe['solid'] || recipe['bands'] || recipe['seat_name'] || recipe['masonry_include'] || recipe['masonry_exclude']
    if need_solid || recipe['roof_materials'] || recipe['inclined_envelope']
      solid = 0.0; top = 0.0; band = Hash.new(0.0); roof = 0.0; roof_xy = 0.0; seat = 0.0; conc = 0.0; steel = 0.0; normals = Hash.new(0.0)
      mi = recipe['masonry_include'] && Regexp.new(recipe['masonry_include']); mx = recipe['masonry_exclude'] && Regexp.new(recipe['masonry_exclude'])
      leaves.each { |d, t, inh, path|
        g = def_geo(d); next if g[:f].empty?
        tris = world_tris(d, t); next if tris.empty?
        o = tris[0][0]; vol = 0.0; flux = Geom::Vector3d.new(0, 0, 0); surf = 0.0; lb = Hash.new(0.0)
        masonry = (!mi || mi.match?(path)) && (!mx || !mx.match?(path))
        steel_leaf = !((g[:f].map(&:first).compact + [inh && inh.name].compact) & (recipe['steel_materials'] || [])).empty?
        seat_leaf = recipe['seat_name'] && path.end_with?('/' + recipe['seat_name'])
        fi = 0; left = g[:f][0] ? g[:f][0][1] : 0
        tris.each { |a|
          while left == 0 && fi < g[:f].length - 1 do fi += 1; left = g[:f][fi][1] end
          left -= 1
          mname = g[:f][fi][0] || (inh && inh.name)
          nz = g[:fn][fi].transform(t); nz.normalize! if nz.length > 0
          v1 = a[1] - a[0]; v2 = a[2] - a[0]; cr = v1 * v2
          vol += (a[0] - o).dot((a[1] - o) * (a[2] - o)) * 25.4**3 / 6.0
          flux += cr; surf += cr.length
          (recipe['bands'] || []).each { |b, z0, z1| lb[b] += volume_above_triangle(a, z0) - volume_above_triangle(a, z1) } if masonry
          ar = cr.length * 25.4**2 / 2.0
          if recipe['roof_materials'] && recipe['roof_materials'].include?(mname) && nz.z > 0.1
            roof += ar; roof_xy += cr.z.abs * 25.4**2 / 2.0
          end
          if nz.z > 0.9
            top += ar; seat += ar if seat_leaf
            normals[nz.to_a.map { |x| x.round(4) }] += ar if recipe['inclined_envelope']
          end
        }
        closed = g[:closed] || (surf > 0 && flux.length / surf < 1e-7 && vol.abs > 1e-6)
        next unless closed
        solid += vol.abs
        if steel_leaf then steel += vol.abs else conc += vol.abs end
        lb.each { |b, x| band[b] += x.abs }
      }
      out[:solid_m3] = solid / 1e9; out[:top_m2] = top / 1e6
      band.each { |b, x| out["solid_m3:#{b}"] = x / 1e9 }
      if recipe['roof_materials'] then out[:roof_m2] = roof / 1e6; out[:roof_xy_m2] = roof_xy / 1e6 end
      if recipe['seat_name'] then out[:seat_m2] = seat / 1e6; out[:concrete_m3] = conc / 1e9; out[:steel_m3] = steel / 1e9 end
      if recipe['inclined_envelope'] && !normals.empty?
        n = Geom::Vector3d.new(normals.max_by { |_, x| x }[0]); n.normalize!
        u = Geom::Vector3d.new(1, 0, 0); u = Geom::Vector3d.new(0, 1, 0) if n.parallel?(u)
        v = n * u; v.normalize!; u = v * n; u.normalize!
        ps = leaves.flat_map { |d, t, _, _| world_tris(d, t).flatten }.map { |q| Geom::Point3d.new(q.x * u.x + q.y * u.y + q.z * u.z, q.x * v.x + q.y * v.y + q.z * v.z, 0) }
        out[:envelope_m2] = minimum_rectangle(ps).inject(:*) / 1e6
      end
    end
    if recipe['perimeter']
      ps = leaves.flat_map { |d, t, _, _| d.bounds.empty? ? [] : (0..7).map { |i| d.bounds.corner(i).transform(t) } }
      out[:perimeter_m] = 2 * minimum_rectangle(ps).sum / 1000.0
    end
    out[:roster_m2] = roster_area(r, recipe['roster']) if recipe['roster']
    out
  end

  # --- satu objek (root) -> data ekspor ---
  def export_object(r, cfg, rooms)
    angle = cfg['angle'] || 0
    recipe = (cfg['measures'] || {})[r.persistent_id.to_s] || {}
    qbands = recipe['bands'] || cfg['bands'] || []
    leaves = walk_leaves(r, Geom::Transformation.new, nil, '', [])
    qty = Hash.new(0.0); ft = []; lv = []; mats_used = []; tris = 0
    leaves.each { |d, t, inh, _|
      g = def_geo(d); next if g[:empty]
      mats_used.concat(g[:f].map(&:first).compact); mats_used << inh.name if inh
      lv << [d, m12(t), inh && inh.name]
      next if g[:faces].empty?
      b = d.bounds
      cs = b.empty? ? [] : (0..7).map { |i| b.corner(i).transform(t) }
      xs = cs.map { |p| mm(p.x) }; ys = cs.map { |p| mm(p.y) }; zs = cs.map { |p| mm(p.z) }
      q = cs.map { |p| uv(mm(p.x), mm(p.y), angle) }
      thk = cs.empty? ? 0 : [[xs.max - xs.min, ys.max - ys.min].min, [q.map(&:first).max - q.map(&:first).min, q.map(&:last).max - q.map(&:last).min].min].min
      walllike = thk >= 80 && !zs.empty? && (zs.max - zs.min) >= 250
      inv = t.inverse
      g[:faces].each_with_index { |f, i|
        area = f.area(t) * 645.16
        cnt = face_tags(f, t, inv, rooms, angle, walllike, qbands)
        tot = cnt.reject { |k, _| k.start_with?('Q|') }.values.sum
        if tot > 0 then cnt.each { |k, c| qty[k] += area * c / tot } else qty[''] += area end
        ts = cnt.keys.reject { |k| k.empty? || k.start_with?('Q|') }.sort.join(';')
        if ft.last && ft.last[0] == ts then ft.last[1] += 1 else ft << [ts, 1] end
        tris += g[:f][i][1]
      }
    }
    bb = r.bounds
    obj = { pid: r.persistent_id, name: r.definition.name, layer: r.layer.name,
            bbox: [mm(bb.min.x).round, mm(bb.min.y).round, mm(bb.min.z).round, mm(bb.max.x).round, mm(bb.max.y).round, mm(bb.max.z).round],
            qty: qty.reject { |_, v| v < 1 }.transform_values(&:round), leaves: lv, ft: ft, tris: tris }
    ms = measures_for(r, leaves, recipe) unless recipe.empty?
    obj[:measures] = ms if ms && !ms.empty?
    [obj, mats_used.uniq]
  end

  # --- pekerjaan ekspor (bertahap, bisa dicicil per tick timer agar SketchUp tidak membeku) ---
  # objek netral (definisi & nama material) -> indeks tabel ekspor ini
  def serialize(o, ctx)
    o.merge(leaves: o[:leaves].map { |d, m, inh| [(ctx[:def_index][d.entityID] ||= (ctx[:defs] << d; ctx[:defs].length - 1)), m, inh ? ctx[:mat].call(inh, nil) : -1] },
            ft: o[:ft].map { |ts, n| [ctx[:tagset].call(ts), n] })
  end

  class ExportJob
    attr_reader :done, :total, :rebuilt, :result
    def initialize(m, cfg, full: false)
      @m, @cfg = m, cfg
      @roots = SerasaRAB.export_roots(m, cfg); @i = 0; @total = @roots.length; @rebuilt = 0; @t0 = Time.now
      @cache = SerasaRAB.cache_for(m, cfg); @cache.clear if full
      @ctx = SerasaRAB.export_ctx; @objects = []
    end
    def done() @i end
    # kerjakan objek sampai jatah waktu habis; true = semua objek selesai
    def step(budget = 0.12)
      t = Time.now
      while @i < @roots.length && Time.now - t < budget
        r = @roots[@i]; @i += 1
        c = @cache[r.persistent_id]
        unless c && c[:sig] == SerasaRAB.signature(r, c[:mats])
          obj, mats = SerasaRAB.export_object(r, @cfg, @cfg['rooms'] || [])
          c = @cache[r.persistent_id] = { sig: SerasaRAB.signature(r, mats), obj: obj, mats: mats }; @rebuilt += 1
        end
        @objects << SerasaRAB.serialize(c[:obj], @ctx)
      end
      @i >= @roots.length
    end
    def finish(path)
      step(1e9) until @i >= @roots.length
      ids = @roots.map(&:persistent_id); @cache.keep_if { |pid, _| ids.include?(pid) }
      defs = @ctx[:defs].map { |d|
        g = SerasaRAB.def_geo(d)
        { name: g[:name], f: g[:f].map { |mn, n| [mn ? @ctx[:mat].call(mn, nil) : -1, n] }, v: g[:v], t: g[:t], e: g[:e], c: g[:closed] ? 1 : 0 }
      }
      tris = @objects.sum { |o| o[:tris] || 0 }
      out = { format: EXPORT_FORMAT, plugin: VERSION, model: @m.path, model_mtime: (File.mtime(@m.path).to_f rescue nil),
              exported: Time.now.strftime('%Y-%m-%d %H:%M:%S'), revision: Time.now.to_f.to_s, region: @cfg['region'], bands: @cfg['bands'] || [],
              rooms: @cfg['rooms'] || [], angle: @cfg['angle'] || 0, materials: @ctx[:mats], tagsets: @ctx[:tagsets], defs: defs, objects: @objects,
              stats: { objects: @objects.length, rebuilt: @rebuilt, defs: defs.length, tris: tris, seconds: (Time.now - @t0).round(2) } }
      tmp = path + '.tmp'; File.write(tmp, JSON.generate(out)); File.rename(tmp, path)
      @result = "ok #{@objects.length} objek (#{@rebuilt} dihitung ulang), #{defs.length} definisi, #{tris} segitiga, #{(Time.now - @t0).round(1)} dtk -> #{path}"
    end
  end

  def cache_for(m, cfg)
    @ecache ||= {}
    key = [m.guid, cfg['region'], cfg['rooms'], cfg['bands'], cfg['angle'], cfg['measures'], cfg['skip_layers'], cfg['display_layers']].hash
    @ecache[key] ||= {}
  end

  def export_ctx
    mats = []; mat_idx = {}; tagsets = ['']; ts_idx = { '' => 0 }; m = Sketchup.active_model
    mat = lambda { |name, obj|
      mat_idx[name] ||= begin
        mt = obj || m.materials[name]
        mats << (mt ? [mt.display_name, mt.color.red, mt.color.green, mt.color.blue, (mt.alpha * 255).round] : [name, 238, 236, 230, 255]); mats.length - 1
      end
    }
    tagset = lambda { |s| ts_idx[s] ||= (tagsets << s; tagsets.length - 1) }
    { defs: [], def_index: {}, mats: mats, mat: mat, tagsets: tagsets, tagset: tagset }
  end

  def export_config(m)
    f = watch_file(m); return nil unless f && File.file?(f)
    JSON.parse(File.read(f))
  end

  def status_file(m) m.path.to_s.empty? ? nil : File.join(File.dirname(m.path), '_serasa_tools', 'export_status.json') end
  def write_status(m, h)
    f = status_file(m) or return
    File.write(f, JSON.generate(h.merge(at: Time.now.strftime('%Y-%m-%d %H:%M:%S')))) rescue nil
  end

  # Ekspor langsung (memblok sampai selesai) - dipakai agen / watch_export. Signature lama dipertahankan.
  def export_mesh(region, path, rooms_json = '[]', bands = [], angle = 0, model = nil, full: false)
    m = model || Sketchup.active_model
    cfg = (export_config(m) || {}).merge('region' => region, 'rooms' => pjson(rooms_json), 'bands' => bands, 'angle' => angle)
    mark_model(m)
    job = ExportJob.new(m, cfg, full: full)
    job.finish(path)
  end

  # Ekspor setelah Save: dicicil per tick timer (SketchUp tetap bisa dipakai), status ke export_status.json.
  def export_async(m, full: false)
    cfg = export_config(m) or return
    if @job_timer then @again = [m, full]; return end
    job = ExportJob.new(m, cfg, full: full)
    write_status(m, state: 'running', done: 0, total: job.total)
    @job_timer = UI.start_timer(0.05, true) {
      begin
        fin = job.step
        write_status(m, state: 'running', done: job.done, total: job.total) if job.done % 20 == 0
        if fin
          UI.stop_timer(@job_timer); @job_timer = nil
          write_status(m, state: 'writing', done: job.total, total: job.total)
          job.finish(cfg['path'])
          write_status(m, state: 'done', done: job.total, total: job.total, rebuilt: job.rebuilt, result: job.result)
          if @again then mm_, fl = @again; @again = nil; export_async(mm_, full: fl) end
        end
      rescue => e
        UI.stop_timer(@job_timer) if @job_timer; @job_timer = nil
        write_status(m, state: 'error', error: "#{e.class}: #{e.message}")
        puts "SerasaRAB ekspor gagal: #{e.class}: #{e.message}\n#{e.backtrace.first(3).join("\n")}"
      end
    }
  end

  def export_full
    m = Sketchup.active_model
    return 'model ini belum diatur ekspornya (watch_export)' unless export_config(m)
    export_async(m, full: true); 'ekspor penuh dimulai — lihat status di viewport'
  end

  # Ekspor ulang otomatis setiap model disimpan. Setelan: <folder model>/_serasa_tools/serasa_watch.json
  # (tetap aktif setelah SketchUp ditutup-buka; plugin memasang ulang saat model dibuka).
  class SaveWatch < Sketchup::ModelObserver
    def onPostSaveModel(m) UI.start_timer(0.2, false) { SerasaRAB.export_async(m) } end
  end

  class AutoWatch < Sketchup::AppObserver
    def onOpenModel(m) SerasaRAB.attach_watch(m); SerasaRAB.ensure_viewport(m) end
    def onActivateModel(m) SerasaRAB.attach_watch(m) end
  end

  def watch_file(m) m.path.to_s.empty? ? nil : File.join(File.dirname(m.path), '_serasa_tools', 'serasa_watch.json') end

  def attach_watch(m)
    cfg = export_config(m); return nil unless cfg && cfg['model'] == File.basename(m.path)
    $serasa_obs ||= {}
    old = $serasa_obs[m.guid]
    return 'sudah aktif' if old.is_a?(SaveWatch)
    if old
      old.detach if old.respond_to?(:detach)
      m.remove_observer(old) rescue nil
    end
    mark_model(m)
    o = SaveWatch.new; m.add_observer(o); $serasa_obs[m.guid] = o
    'aktif'
  rescue => e
    puts "SerasaRAB watch gagal: #{e}"; nil
  end

  def watch_export(region, path, rooms_json = '[]', bands = [], angle = 0, extra = {})
    m = Sketchup.active_model
    f = watch_file(m) or return 'simpan model dulu (belum punya path)'
    FileUtils.mkdir_p(File.dirname(f))
    cfg = (export_config(m) || {}).merge('model' => File.basename(m.path), 'region' => region, 'path' => path,
                                        'rooms' => pjson(rooms_json), 'bands' => bands, 'angle' => angle).merge(pjson(extra))
    File.write(f, JSON.pretty_generate(cfg))
    attach_watch(m)
    export_mesh(region, path, rooms_json, bands, angle, m, full: true) + ' · ekspor ulang otomatis setelah model disimpan (hanya objek yang berubah)'
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
  sub.add_item('Ekspor penuh model 3D') { UI.messagebox(SerasaRAB.export_full) }
  sub.add_separator
  sub.add_item('Pasang ulang / perbarui') { UI.messagebox(SerasaRAB.install_plugin) }
  sub.add_item("Tentang (v#{SerasaRAB::VERSION})") {
    UI.messagebox("Serasa RAB #{SerasaRAB::VERSION}\nviewport: #{SerasaRAB.home || '-'}\nPython: #{SerasaRAB.python || 'belum ada'}")
  }
end
SerasaRAB.ensure_viewport(Sketchup.active_model) if Sketchup.active_model && !$serasa_vp_started
$serasa_vp_started = true
'SerasaRAB ' + SerasaRAB::VERSION + ' loaded'
