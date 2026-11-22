# Serasa RenderFlow — export scene SketchUp untuk render AI.
# Menyembunyikan anotasi sementara, export, lalu mengembalikan semuanya. Tidak menyimpan model.
require 'json'
require 'fileutils'

module SerasaRenderExport
  ANNOT = [Sketchup::Dimension, Sketchup::Text, Sketchup::SectionPlane,
           Sketchup::ConstructionLine, Sketchup::ConstructionPoint]

  def self.annotations(ents, acc = [], depth = 0)
    ents.each do |e|
      if ANNOT.any? { |k| e.is_a?(k) }
        acc << e
      elsif depth < 6 && (e.is_a?(Sketchup::Group) || e.is_a?(Sketchup::ComponentInstance))
        d = e.respond_to?(:definition) ? e.definition : e.entities.parent
        annotations(d.entities, acc, depth + 1)
      end
    end
    acc
  end

  # nama scene SKP apa adanya; hanya karakter terlarang Windows diganti '-'
  def self.safe_name(n)
    n.gsub(/[\\\/:*?"<>|]/, '-').strip.sub(/\.+\z/, '')
  end

  def self.run(dir, scenes: nil, width: 4000, hide_tags: [])
    m = Sketchup.active_model
    v = m.active_view
    FileUtils.mkdir_p(dir)
    pages = m.pages.to_a
    pages = pages.select { |p| scenes.include?(p.name) } if scenes && !scenes.empty?

    po = m.options['PageOptions']
    old_trans = po['ShowTransition']
    po['ShowTransition'] = false
    ro = m.rendering_options
    old_ro = { 'DrawSectionPlanes' => ro['DisplaySectionPlanes'], 'HideConstructionGeometry' => ro['HideConstructionGeometry'] }
    res = {}
    hidden = []
    m.start_operation('RenderFlow export (temp)', true)
    begin
      pages.each do |p|
        m.pages.selected_page = p
        # tiap scene bisa mengembalikan visibilitas; sembunyikan ulang
        ro['DisplaySectionPlanes'] = false
        ro['HideConstructionGeometry'] = true
        annotations(m.entities).each { |e| next if e.hidden?; e.hidden = true; hidden << e }
        hide_tags.each { |t| l = m.layers[t]; (hidden << l; l.visible = false) if l && l.visible? }
        v.refresh
        h = (width * v.vpheight.to_f / v.vpwidth).round
        f = File.join(dir, safe_name(p.name) + '.jpg')
        ok = v.write_image(filename: f, width: width, height: h, antialias: true, compression: 0.95, transparent: false)
        res[p.name] = { file: File.basename(f), ok: ok, w: width, h: h }
      end
    ensure
      m.abort_operation # kembalikan visibilitas & scene seperti semula
      po['ShowTransition'] = old_trans
      ro['DisplaySectionPlanes'] = old_ro['DrawSectionPlanes'] unless old_ro['DrawSectionPlanes'].nil?
      ro['HideConstructionGeometry'] = old_ro['HideConstructionGeometry'] unless old_ro['HideConstructionGeometry'].nil?
    end
    missing = scenes ? scenes - pages.map(&:name) : []
    # path dir boleh pakai '\\' (Windows) atau '/'; File.join tetap aman
    missing.each { |n| res[n] = { ok: false, error: 'scene tidak ada' } }
    File.write(File.join(dir, '_export.json'), JSON.pretty_generate(res))
    "export #{res.count { |_, r| r[:ok] }}/#{res.size} → #{dir}"
  end
end
