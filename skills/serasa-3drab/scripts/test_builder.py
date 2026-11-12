"""Offline checks for quantity provenance; no credentials or Sheet writes."""
import copy
import unittest
from build_rab import Ahs, Builder, DS, EST_BG, PEND_BG, build_audit, plan_patch, rab_requests

class QuantityProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.spec = {
            'project': {'title': 'Offline', 'tab': 'RAB'},
            'walls': [], 'openings': [],
            'audit': [{'code': 'OPK', 'name': 'Perapihan bukaan', 'sat': 'm1', 'components': []},
                      {'code': 'P1', 'group': 'kusen', 'name': 'Pintu', 'sat': 'unit', 'components': []}],
            'wall_specs': {'plester': 'Plester', 'aci': {'putih': 'Acian'},
                           'finish': {'interior': {'putih': 'Cat'}}},
            'bab': [{'no': 'IV', 'title': 'Dinding', 'rows': []}],
        }
        self.ahs = Ahs([{'u': u, 's': 'm2', 'h': 1, 'c': u} for u in ['Plester', 'Acian', 'Cat']])

    def render(self, spec):
        b = Builder(spec, self.ahs).build()
        self.assertFalse(b.errors)
        audit, prices = build_audit(spec, b, 'RAB')
        reqs = rab_requests(1, b, [], 'Audit', prices)
        cells = next(r['updateCells']['rows'] for r in reqs if r.get('updateCells', {}).get('range', {}).get('startRowIndex') == DS-1)
        return b, audit, cells

    def test_layer_areas_and_estimates_propagate_without_changing_numbers(self):
        self.spec['walls'] = [{'room': 'WC', 'lantai': 'Lantai 1', 'parts': {'putih': 12.4},
            'layer_parts': {'aci': {'putih': 1.0}, 'finish': {}},
            'estimated': True, 'quantity_note': 'Ukuran WC dari denah.'}]
        self.spec['bab'][0]['rows'] = [{'type': 'wall_plaster'}, {'type': 'wall_aci'}, {'type': 'wall_finish'}]
        b, audit, cells = self.render(self.spec)
        data = [(r,c) for r,c in zip(b.rows,cells) if r['k']=='ahs']
        self.assertEqual([r['c'][7] for r,c in data], [12.4,1.0])
        for r,c in data:
            self.assertEqual(c['values'][7]['userEnteredFormat']['backgroundColor'], EST_BG)
            self.assertNotIn('backgroundColor',c['values'][8]['userEnteredFormat'])
            self.assertIn('formulaValue',c['values'][9]['userEnteredValue'])
            self.assertIn('dataValidation',c['values'][5])
        self.assertEqual(sum('Ukuran WC dari denah.' in r for r in audit),2)

    def test_confirmed_and_pending_are_not_estimates(self):
        rows = self.spec['bab'][0]['rows']
        rows.extend([{'type':'ahs','spec':'Plester','vol':5},
                     {'type':'pending','uraian':'Kolom','reason':'Detail belum tersedia.'}])
        b, audit, cells = self.render(self.spec)
        for r,c in zip(b.rows,cells):
            if r['k']=='ahs': self.assertNotIn('backgroundColor',c['values'][7]['userEnteredFormat'])
            if r['k']=='pending':
                self.assertEqual(r['c'][7:10],['','',''])
                self.assertTrue(all(v['userEnteredFormat']['backgroundColor']==PEND_BG for v in c['values']))

    def test_opening_count_affects_perimeter_and_estimated_aggregate(self):
        self.spec['openings']=[{'code':'P1','jenis':'Pintu','ruang':'Teras > Toko 1',
            'lantai':'Lantai 1','w':.8,'h':2.3,'vol':2,'spec':'Pintu 80 x 230 cm','estimated':True}]
        self.spec['bab'][0]['rows']=[{'type':'openingan'}, {'type':'openings'}]
        b, audit, cells = self.render(self.spec)
        items=[r for r in b.rows if r['k'] in ('audit','kusen')]
        self.assertEqual([r['c'][7] for r in items],[10.8,2])
        self.assertTrue(all(r['estimated'] for r in items))
        legacy=copy.deepcopy(self.spec); legacy['openings'][0].pop('estimated')
        b2, _, _=self.render(legacy)
        self.assertEqual([r['c'] for r in b.rows],[r['c'] for r in b2.rows])
        self.assertFalse(any(r.get('estimated') for r in b2.rows))

    def test_patch_plan_writes_only_changed_rows(self):
        self.spec['walls'] = [{'room': 'WC', 'lantai': 'Lantai 1', 'parts': {'putih': 12.4}}]
        self.spec['bab'][0]['rows'] = [{'type': 'wall_plaster'}, {'type': 'wall_finish'}]
        b = Builder(copy.deepcopy(self.spec), self.ahs).build()
        _, prices = build_audit(self.spec, b, 'RAB')
        same, changed, want = plan_patch(b, [], 'Audit', prices)
        live = [[str(v).replace(',', ';') if isinstance(v, str) else v for v in r] for r in want]   # locale ; di Sheet
        self.assertEqual(plan_patch(b, live, 'Audit', prices)[:2], (True, []))
        spec2 = copy.deepcopy(self.spec); spec2['walls'][0]['parts']['putih'] = 13.0
        b2 = Builder(spec2, self.ahs).build()
        same, changed, _ = plan_patch(b2, live, 'Audit', prices)
        self.assertTrue(same)
        self.assertTrue(changed and all(b2.rows[i]['k'] not in ('bab', 'total') for i in changed))

if __name__=='__main__': unittest.main()
