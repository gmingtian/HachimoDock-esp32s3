"""Catch gain-selector miswiring, rail shorts and changes to locked mechanics."""
import copy
import json
import math
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_design import build


class GainJumperTests(unittest.TestCase):
    def test_single_shunt_selects_gain_without_shorting_supply_rails(self):
        parts={c['ref']:c for c in build()['components']}
        self.assertIn('JP1',parts,'A physical gain selector is required')
        pins={p['number']:p['net'] for p in parts['JP1']['pads']}
        self.assertEqual(pins,{'1':'+3V3','2':'AMP_GAIN','3':'GND'})
        self.assertEqual(next(p['net'] for p in parts['U2']['pads'] if p['number']=='4'),'AMP_GAIN')
        self.assertEqual([(c['ref'],p['number']) for c in parts.values() for p in c['pads']
                          if p['net']=='AMP_GAIN'],[('U2','4'),('JP1','2')])
        for shunt,target in [((),None),(('1','2'),'+3V3'),(('2','3'),'GND')]:
            linked={pins[p] for p in shunt}
            self.assertFalse({'+3V3','GND'}<=linked,'One standard shunt must not short the supply')
            if target:self.assertEqual(linked,{'AMP_GAIN',target})
            else:self.assertNotIn('AMP_GAIN',linked)

    def test_selector_accepts_standard_254mm_shunt_and_has_clearance(self):
        board=build();parts={c['ref']:c for c in board['components']}
        self.assertIn('JP1',parts)
        pins=sorted(parts['JP1']['pads'],key=lambda p:int(p['number']))
        for a,b in zip(pins,pins[1:]):self.assertAlmostEqual(math.dist((a['x'],a['y']),(b['x'],b['y'])),2.54)
        self.assertTrue(all(p['drill']>=1.0 for p in pins))
        envelope=board['gainSelector']['assemblyEnvelope']
        def gap(other):
            return math.hypot(max(envelope[0]-other[2],other[0]-envelope[2],0),
                              max(envelope[1]-other[3],other[1]-envelope[3],0))
        for ref in ['U1','U2','U3','J1']:
            self.assertGreaterEqual(gap(parts[ref]['envelope']),1.0,ref)
        for cap in board['keycapEnvelopes']:self.assertGreaterEqual(gap(cap['envelope']),1.0,cap['ref'])
        for h in board['mountingHoles']:
            self.assertGreaterEqual(gap([h['x'],h['y'],h['x'],h['y']])-3.0,1.0,h['ref'])

    def test_a3_hardware_positions_and_existing_io_are_unchanged(self):
        old=json.loads((ROOT/'reference/a3-layout-lock.json').read_text())
        board=build();parts={c['ref']:copy.deepcopy(c) for c in board['components']}
        self.assertIn('JP1',parts)
        parts.pop('JP1')
        next(p for p in parts['U2']['pads'] if p['number']=='4')['net']=''
        self.assertEqual(list(parts.values()),old['components'])
        for name in ['outline','mountingHoles','mountingSockets','connectorMatingEnvelopes',
                     'fastenerEnvelopes','keycapEnvelopes','joystickMotionReservation','antennaKeepout']:
            self.assertEqual(json.loads(json.dumps(board[name])),old[name],name)


if __name__=='__main__':unittest.main()
