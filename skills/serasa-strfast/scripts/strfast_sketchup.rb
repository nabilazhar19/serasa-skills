require 'json'
require 'digest'

# Coordinates and dimensions in the manifest are millimeters.
module SerasaStrFast
  extend self
  TAG = 'Serasa StrFast'.freeze
  EPS = 0.01

  def label(value, field)
    raise ArgumentError, "#{field} harus berupa teks" unless value.is_a?(String) && !value.strip.empty?
    value
  end

  def number(value, field)
    raise ArgumentError, "#{field} harus berupa angka terbatas" unless value.is_a?(Numeric) && value.to_f.finite?
    value.to_f
  end

  def vector(value, field)
    raise ArgumentError, "#{field} harus berisi tiga angka" unless value.is_a?(Array) && value.size == 3
    value.map { |item| number(item, field) }
  end

  def positive(value, field)
    value = number(value, field)
    raise ArgumentError, "#{field} terlalu kecil" unless value > EPS
    value
  end

  def add(a, b)
    a.zip(b).map { |x, y| x + y }
  end

  def subtract(a, b)
    a.zip(b).map { |x, y| x - y }
  end

  def dot(a, b)
    a.zip(b).sum { |x, y| x * y }
  end

  def cross(a, b)
    [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
  end

  def shape(data)
    case data.fetch('shape')
    when 'box'
      min = vector(data.fetch('min'), 'min')
      max = vector(data.fetch('max'), 'max')
      dx, dy, dz = subtract(max, min).map { |length| positive(length, 'ukuran box') }
      offsets = [[0,0,0], [dx,0,0], [dx,dy,0], [0,dy,0]]
      [offsets.map { |offset| add(min, offset) }, [0,0,dz]]
    when 'member'
      a = vector(data.fetch('start'), 'start')
      b = vector(data.fetch('end'), 'end')
      width = positive(data.fetch('width'), 'width')
      depth = positive(data.fetch('depth'), 'depth')
      slope = number(data.fetch('cross_slope', 0), 'cross_slope')
      dx, dy = subtract(b, a)
      half = width / (2 * positive(Math.hypot(dx, dy), 'proyeksi member pada denah'))
      edge = [-dy*half, dx*half, slope*width/2]
      [[subtract(a, edge), subtract(b, edge), add(b, edge), add(a, edge)], [0,0,-depth]]
    when 'prism'
      loop = data.fetch('loop')
      raise ArgumentError, 'loop memerlukan minimal tiga titik' unless loop.is_a?(Array) && loop.size >= 3
      [loop.map { |point| vector(point, 'loop') }, vector(data.fetch('offset'), 'offset')]
    else
      raise ArgumentError, 'shape harus box, member, atau prism'
    end
  end

  def rounded(points)
    points.map { |point| point.map { |axis| (axis / EPS).round } }
  end

  def solid_faces(loop, offset)
    coords = loop.map { |point| subtract(point, loop.first) }
    normal = coords.each_with_index.reduce([0,0,0]) do |sum, (point, index)|
      add(sum, cross(point, coords[(index + 1) % coords.size]))
    end
    length = Math.sqrt(dot(normal, normal))
    raise ArgumentError, 'loop memiliki titik duplikat' unless rounded(loop).uniq.size == loop.size
    raise ArgumentError, 'luas loop mendekati nol' unless length > EPS * EPS
    normal = normal.map { |axis| axis / length }
    raise ArgumentError, 'loop tidak sebidang' unless coords.all? { |point| dot(normal, point).abs <= EPS }
    depth = dot(normal, offset)
    raise ArgumentError, 'offset tidak menghasilkan volume' unless depth.abs > EPS

    loop = loop.reverse if depth.negative?
    end_loop = loop.map { |p| add(p, offset) }
    sides = loop.each_index.map do |i|
      j = (i + 1) % loop.size
      [loop[i], loop[j], end_loop[j], end_loop[i]]
    end
    [loop.reverse, end_loop, *sides]
  end

  def read_plan(path)
    plan = JSON.parse(File.read(path))
    raise ArgumentError, 'format manifest harus objek JSON' unless plan.is_a?(Hash)
    raise ArgumentError, 'version harus 1 dan satuan harus mm' unless plan['version'] == 1 && plan['units'] == 'mm'
    %w[project scope].each { |key| label(plan.fetch(key), key) }
    origin = vector(plan.fetch('origin', [0,0,0]), 'origin')
    elements = plan.fetch('elements')
    raise ArgumentError, 'elements harus berupa daftar yang terisi' unless elements.is_a?(Array) && !elements.empty?

    ids = {}
    geometries = {}
    parts = elements.map do |element|
      raise ArgumentError, 'setiap elemen harus berupa objek JSON' unless element.is_a?(Hash)
      id = label(element.fetch('id'), 'id')
      begin
        raise ArgumentError, 'ID duplikat' if ids[id]
        ids[id] = true
        %w[system kind source].each { |key| label(element.fetch(key), key) }
        basis = element.fetch('basis')
        raise ArgumentError, 'basis harus terukur atau skematik' unless %w[terukur skematik].include?(basis)
        raise ArgumentError, 'qto harus kandidat atau overlay' unless %w[kandidat overlay].include?(element.fetch('qto'))
        loop, offset = shape(element)
        faces = solid_faces(loop, offset)
        signature = rounded(faces.first + faces[1]).sort
        raise ArgumentError, "geometri identik dengan #{geometries[signature]}" if geometries[signature]
        geometries[signature] = id
        [element, faces]
      rescue ArgumentError, KeyError => e
        raise ArgumentError, "#{id}: #{e.message}"
      end
    end
    [plan, origin, parts]
  end

  def summary(plan, parts)
    counts = parts.group_by { |data, _| data.fetch('system') }.transform_values(&:size)
    {project: plan['project'], scope: plan['scope'], elements: parts.size, systems: counts}
  end

  def check(path)
    plan, _, parts = read_plan(path)
    summary(plan, parts)
  end

  def build(path, expected_model_path:, replace_revision: nil)
    plan, origin, parts = read_plan(path)
    model = Sketchup.active_model
    unless expected_model_path.is_a?(String) && !expected_model_path.empty? && model.path == expected_model_path && !model.active_path
      raise ArgumentError, 'Aktifkan model yang dimaksud dan keluar dari mode edit grup'
    end
    project = plan.fetch('project')
    scope = plan.fetch('scope')
    root_name = "#{project} | STRUKTUR SKEMATIK"
    top_groups = model.entities.grep(Sketchup::Group)
    roots = top_groups.select { |g| g.get_attribute(TAG, 'project') == project }
    raise ArgumentError, 'Grup StrFast ganda untuk proyek ini' if roots.size > 1
    current = roots.first
    if top_groups.any? { |g| g != current && g.name == root_name }
      raise ArgumentError, 'Ada grup struktur dengan nama yang sama. Koordinasikan sebagai revisi manual.'
    end
    if current
      unless replace_revision && current.get_attribute(TAG, 'revision') == replace_revision && current.get_attribute(TAG, 'scope') == scope
        raise ArgumentError, 'Tinjau revisi dan lingkup grup aktif sebelum mengganti satu lingkup penuh'
      end
    elsif replace_revision
      raise ArgumentError, 'Grup StrFast yang akan diganti tidak ditemukan'
    end

    revision = Digest::SHA256.hexdigest(JSON.generate(plan))
    geometry = ->(p) { Geom::Point3d.new(*add(p, origin).map(&:mm)) }
    model.start_operation('Serasa StrFast · struktur skematik', true)
    begin
      root = model.entities.add_group
      root.name = root_name
      {'project'=>project, 'scope'=>scope, 'revision'=>revision}.each { |k,v| root.set_attribute(TAG, k, v) }
      systems = {}
      parts.each do |data, faces|
        system = data.fetch('system')
        system_group = systems[system] ||= root.entities.add_group
        system_group.name = system
        group = system_group.entities.add_group
        id = data.fetch('id')
        group.name = "#{id} | #{data.fetch('kind')}"
        %w[id system kind basis source qto].each { |key| group.set_attribute(TAG, key, data.fetch(key)) }
        group.set_attribute(TAG, 'manifest', JSON.generate(data))
        faces.each do |face_points|
          points = face_points.map(&geometry)
          face = group.entities.add_face(points)
          raise "Muka elemen #{id} gagal terbentuk" unless face && face.valid?
          coords = face_points.map { |point| subtract(point, face_points.first) }
          normal = coords.each_cons(2).reduce([0,0,0]) { |sum, (a, b)| add(sum, cross(a, b)) }
          face.reverse! if dot(normal, face.normal.to_a).negative?
        end
        raise "Elemen #{id} bukan solid bervolume positif" unless group.manifold? && group.volume > 0
      end
      current.erase! if current
      result = summary(plan, parts).merge(revision: revision, root_id: root.persistent_id)
      model.commit_operation
      result
    rescue StandardError
      model.abort_operation
      raise
    end
  end
end

if !defined?(Sketchup) && $PROGRAM_NAME == __FILE__
  abort 'Penggunaan: ruby strfast_sketchup.rb manifest.json' unless ARGV.size == 1
  begin
    puts JSON.pretty_generate(SerasaStrFast.check(ARGV.first))
  rescue StandardError => e
    abort e.message
  end
end
