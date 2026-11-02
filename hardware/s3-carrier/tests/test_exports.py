"""Cross-check the interchange file against the actual routed design."""
import json
import math
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from source_geometry import read_archive, pads, board_geometry
from build_design import MIL, STEM, REVISION, norm


class ExportTests(unittest.TestCase):
    def test_ground_pours_have_cutouts_for_all_five_screw_heads(self):
        design=json.loads((ROOT/'output/design.json').read_text())
        docs=read_archive(ROOT/f'output/{STEM}.epro2')
        pcb=next(d for d in docs.values() if d['head']['docType']=='PCB')
        pours=[v for h,v in pcb['records'] if h['type']=='POUR']
        self.assertEqual(len(pours),2)
        for pour in pours:
            self.assertEqual(len(pour['path']),6,'Outer polygon plus five head cutouts')
            for path,hole in zip(pour['path'][1:],design['mountingHoles']):
                pts=[norm(path[0],path[1])]+[norm(path[i],path[i+1]) for i in range(3,len(path)-2,2)]
                self.assertAlmostEqual(sum(x for x,y in pts)/len(pts),hole['x'],places=4)
                self.assertAlmostEqual(sum(y for x,y in pts)/len(pts),hole['y'],places=4)
                self.assertTrue(all(math.dist((x,y),(hole['x'],hole['y']))>=3.5 for x,y in pts))

    def test_interchange_carries_ground_pours_without_filling_antenna_corner(self):
        docs=read_archive(ROOT/f'output/{STEM}.epro2')
        pcb=next(d for d in docs.values() if d['head']['docType']=='PCB')
        pours=[v for h,v in pcb['records'] if h['type']=='POUR']
        self.assertEqual({v['layerId'] for v in pours},{1,2})
        self.assertEqual(len(pours),2)
        for v in pours:
            self.assertEqual(v['netName'],'GND')
            self.assertFalse(v['keepIsland'])
            p=v['path'][0];vertices=[norm(p[0],p[1])]+[norm(p[i],p[i+1]) for i in range(3,len(p),2)]
            # The right/top antenna corner must be cut out of the source
            # polygon even before the importer re-creates its rule area.
            self.assertTrue(any(abs(x-61.73)<1e-5 and abs(y-29.294)<1e-5 for x,y in vertices))
            self.assertFalse(any(x>61.731 and y<29.293 for x,y in vertices))

    def test_interchange_has_readable_connector_and_orientation_silkscreen(self):
        docs=read_archive(ROOT/f'output/{STEM}.epro2')
        pcb=next(d for d in docs.values() if d['head']['docType']=='PCB')
        labels=[v for h,v in pcb['records'] if h['type']=='STRING' and v['layerId']==3]
        names={v['text'] for v in labels}
        self.assertTrue({'GND','VCC','SCL','SDA','RES','DC','CS','BLK',f'{REVISION} / USB LEFT','JOY RSV','1/2/8',
                         'JP1','GAIN','6dB','12dB','OPEN 9dB'}<=names)
        lcd=sorted([v for v in labels if v['text'] in {'GND','VCC','SCL','SDA','RES','DC','CS','BLK'}
                    and abs(norm(v['x'],v['y'])[1]-29.35)<.001],key=lambda v:v['x'])
        self.assertEqual([v['text'] for v in lcd],['GND','VCC','SCL','SDA','RES','DC','CS','BLK'])

    def test_export_has_all_pad_nets_and_positions(self):
        design=json.loads((ROOT/'output/design.json').read_text())
        docs=read_archive(ROOT/f'output/{STEM}.epro2')
        pcb=next(d for d in docs.values() if d['head']['docType']=='PCB')
        parts=board_geometry(pcb)['components']
        assignments={}
        for h,v in pcb['records']:
            if h['type']=='PAD_NET':
                _,component,number,source=json.loads(h['id'])
                assignments[component,source]=v['padNet']
        self.assertEqual(len(parts),9)
        self.assertEqual(len(assignments),86)
        for c in design['components']:
            p=parts[c['ref']];actual=pads(docs[p['Footprint']])
            self.assertEqual(len(actual),len(c['pads']))
            for i,(a,b) in enumerate(zip(actual,c['pads'])):
                x,y=norm(p['x']+a['centerX'],p['y']+a['centerY'])
                self.assertAlmostEqual(x,b['x'],places=5)
                self.assertAlmostEqual(y,b['y'],places=5)
                self.assertEqual(a['num'],b['number'])
                self.assertEqual(assignments[p['source_id'],f'p{i}'],b['net'])
                self.assertAlmostEqual(0 if a['hole'] is None else a['hole']['width']*MIL,b['drill'],places=5)
        lines=[v for h,v in pcb['records'] if h['type']=='LINE']
        expected=[(t,a,b) for t in design['traces'] for a,b in zip(t['points'],t['points'][1:]) if a!=b]
        self.assertEqual(len(lines),len(expected))
        for actual,(route,a,b) in zip(lines,expected):
            self.assertEqual(actual['netName'],route['net'])
            self.assertEqual(actual['layerId'],1 if route['layer']=='F.Cu' else 2)
            self.assertAlmostEqual(actual['width']*MIL,route['width'])
            self.assertLess(math.dist(norm(actual['startX'],actual['startY']),a),1e-5)
            self.assertLess(math.dist(norm(actual['endX'],actual['endY']),b),1e-5)
        self.assertEqual(sum(h['type']=='VIA' for h,v in pcb['records']),len(design['vias']))
        self.assertEqual(len(board_geometry(pcb)['outline']),10)
        self.assertEqual(len(board_geometry(pcb)['holes']),5)


if __name__=='__main__':unittest.main()
