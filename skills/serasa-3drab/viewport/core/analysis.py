"""
core/analysis.py - koefisien komponen analisa yang bergantung ukuran (resep ukuran kusen/paket).

Analisa di input (audit[i]) boleh punya:
  dimension_recipe {kind: strip|frameless|fixed|slide, params: {panels, frame, glazed, overlap, leaf_w_override}}
  komponen {formula: "frame_m*1.05", name_template: "Kaca {glass_w_mm:.0f} x {glass_h_mm:.0f} mm", ...}
Saat ukuran bukaan berubah (core/sync.resize_opening) semua koef komponen dihitung ulang dari rumusnya;
harga tetap milik komponen (bisa diedit). Parameter tersedia: w, h, area, frame_m, seal_m, panels, leaf_w/h, leaf_m,
glass_w/h(_mm), glass_area, glass_m, bill_glass_area (min. 0,5 m2 per lembar), glass_panels, infill_area/_m.
Rumus hanya boleh + - * / min max ceil (dievaluasi aman, tanpa eval Python).
"""
import ast, math, operator


def evaluate(expression, params):
    ops={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv}
    def run(n):
        if isinstance(n,ast.Constant) and type(n.value) in (int,float):return n.value
        if isinstance(n,ast.Name):return params[n.id]
        if isinstance(n,ast.BinOp) and type(n.op) in ops:return ops[type(n.op)](run(n.left),run(n.right))
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -run(n.operand)
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in ('min','max','ceil') and not n.keywords:
            return {'min':min,'max':max,'ceil':math.ceil}[n.func.id](*[run(x) for x in n.args])
        raise ValueError('Unsupported quantity formula')
    value=float(run(ast.parse(expression,mode='eval').body))
    if not math.isfinite(value) or value<0:raise ValueError('Quantity must be finite and nonnegative')
    return round(value,6)


def parameters(width,height,recipe):
    p=dict(recipe.get('params',{}),w=width,h=height)
    n=p.get('panels',1);kind=recipe['kind'];frame=p.get('frame',.04)
    p.update(area=width*height,frame_m=2*(width+height),seal_m=2*(width+height),panels=n)
    if kind=='strip':
        lw=max(width-2*frame,.001);lh=max(height-frame,.001)
        mid=0 if p.get('glazed') else 1
        cw=max(lw-.16,.001);ch=max(lh-.16-mid*.08,.001)
        p.update(frame_m=width+2*height,leaf_w=lw,leaf_h=lh,leaf_m=2*(lw+lh)+mid*lw,
                 infill_area=cw*ch,infill_m=2*(cw+ch)+2*mid*cw,
                 glass_area=cw*ch if p.get('glazed') else 0,glass_m=2*(cw+ch) if p.get('glazed') else 0,
                 glass_w=cw,glass_h=ch)
    elif kind=='frameless':
        gw=width;gh=max(height-.007,.001)
        p.update(glass_area=gw*gh,glass_m=2*(gw+gh),glass_w=gw,glass_h=gh,leaf_m=0)
    elif kind=='fixed':
        gw=max(width-2*frame,.001);gh=max(height-2*frame,.001)
        p.update(glass_area=gw*gh,glass_m=2*(gw+gh),glass_w=gw,glass_h=gh,leaf_m=0)
    elif kind=='slide':
        lw=p.get('leaf_w_override') or max((width-2*frame+(n-1)*p.get('overlap',.025))/n,.001)
        lh=max(height-2*frame,.001);gw=max(lw-.10,.001);gh=max(lh-.06,.001)
        fixed_w=max(width-2*lw-.04,0) if p.get('leaf_w_override') else 0
        fixed_area=fixed_w*gh
        p.update(frame_m=2*height,leaf_w=lw,leaf_h=lh,leaf_m=n*2*(lw+lh),glass_w=gw,glass_h=gh,
                 glass_area=n*gw*gh+fixed_area,glass_m=n*2*(gw+gh)+(2*(fixed_w+gh) if fixed_w else 0),
                 fixed_glass_area=fixed_area,fixed_glass_w=fixed_w)
    else:raise ValueError('Unknown opening construction')
    if kind!='strip' or p.get('glazed'):
        p['bill_glass_area']=(n*max(.5,p['glass_w']*p['glass_h']) + (max(.5,p.get('fixed_glass_area',0)) if p.get('fixed_glass_area',0)>0 else 0))
    p['glass_panels']=n+(1 if p.get('fixed_glass_area',0)>0 else 0)
    for k in ('glass_w','glass_h','leaf_w','leaf_h','fixed_glass_w'):
        if k in p:p[k+'_mm']=p[k]*1000
    return p


def recalculate(analysis,width=None,height=None,extra=None):
    recipe=analysis.get('dimension_recipe')
    params=parameters(width,height,recipe) if recipe else dict(analysis.get('metric_params',{}))
    params.update(extra or {})
    for c in analysis.get('components',[]):
        if c.get('formula'):c['koef']=evaluate(c['formula'],params)
        if c.get('name_template'):c['name']=c['name_template'].format(**params)
    if recipe:analysis['dimensions']={'w':width,'h':height}
    if extra:analysis.setdefault('metric_params',{}).update(extra)
    return params
