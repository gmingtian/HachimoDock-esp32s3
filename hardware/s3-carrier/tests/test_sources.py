"""Checks against real downloaded PCB libraries, not inferred screenshots."""
import importlib.util
from pathlib import Path
import unittest
import re
import sys
import math

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_design
spec = importlib.util.spec_from_file_location('source_geometry', ROOT / 'tools/source_geometry.py')
geometry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geometry)


class SourceGeometryTests(unittest.TestCase):
    def test_mated_screen_plug_leaves_room_for_screw_heads(self):
        board=build_design.build()
        plug=board['connectorMatingEnvelopes'][0]['envelope']
        for hole in board['mountingHoles']:
            x,y=hole['x'],hole['y']
            nearest=math.hypot(max(plug[0]-x,0,x-plug[2]),max(plug[1]-y,0,y-plug[3]))
            self.assertGreaterEqual(nearest-3.0,.5,hole['ref']+' 6mm head versus plug')

    def test_added_modules_keep_out_of_joystick_motion_reservation(self):
        board=build_design.build()
        motion=board.get('joystickMotionReservation')
        self.assertIsNotNone(motion,'Static body outline alone does not reserve lever motion')
        x,y=motion['center'];r=motion['radiusMm']
        bodies=[(c['ref'],c['envelope']) for c in board['components'] if c['ref'] in ['U1','U2','U3','J1','JP1']]
        bodies += [(p['ref']+' plug',p['envelope']) for p in board['connectorMatingEnvelopes']]
        for name,(left,top,right,bottom) in bodies:
            distance=math.hypot(max(left-x,0,x-right),max(top-y,0,y-bottom))
            self.assertGreaterEqual(distance-r,1.0,name)

    def test_screen_connector_matches_user_screen_pin_order(self):
        board=build_design.build()
        self.assertEqual(board.get('screenConnectorOrder'),['GND','VCC','SCL','SDA','RES','DC','CS','BLK'])
        lcd=next(c for c in board['components'] if c['ref']=='J1')
        self.assertEqual([p['net'] for p in sorted(lcd['pads'],key=lambda p:p['x'])],
                         ['GND','+3V3','GPIO21','GPIO47','GPIO45','GPIO40','GPIO41','GPIO42'])

    def test_modules_mount_on_separate_standard_socket_strips(self):
        board=build_design.build()
        sockets=board.get('mountingSockets',[])
        self.assertEqual(sorted(s['pins'] for s in sockets if s['parent']=='U1'),[21,21])
        self.assertEqual(sorted(s['pins'] for s in sockets if s['parent']=='U2'),[7])
        self.assertEqual(sorted(s['pins'] for s in sockets if s['parent']=='U3'),[3,3])
        mic=[s for s in sockets if s['parent']=='U3']
        self.assertAlmostEqual(abs(mic[0]['centerX']-mic[1]['centerX']),7.62)
        self.assertEqual({s['pitch'] for s in sockets},{2.54})
        for c in board['components']:
            if c['ref'] in ['U1','U2','U3']:
                self.assertTrue(all(p['drill']>=1.19 for p in c['pads']))

    def test_round_mic_pre_soldered_top_label_view_matches_user_photo(self):
        mic=next(c for c in build_design.build()['components'] if c['ref']=='U3')
        left=sorted([p for p in mic['pads'] if p['x']<47],key=lambda p:p['y'])
        right=sorted([p for p in mic['pads'] if p['x']>47],key=lambda p:p['y'])
        self.assertEqual([p['net'] for p in left],['GPIO6','+3V3','GND'])
        self.assertEqual([p['net'] for p in right],['GPIO5','GPIO4','GND'])
        self.assertEqual([p['number'] for p in left],['3','2','1'])
        self.assertEqual([p['number'] for p in right],['6','5','4'])
        self.assertEqual(mic['envelope'],[39,35.1,53,49.1])

    def test_plug_and_keycap_bodies_have_explicit_clearance(self):
        board=build_design.build()
        mating=board.get('connectorMatingEnvelopes',[])
        self.assertEqual(len(mating),1)
        plug=mating[0]['envelope']
        self.assertEqual(mating[0]['maximumPlugBodyMm'],[22,3])
        lower=max(s['bodyEnvelope'][3] for s in board['mountingSockets'] if s['parent']=='U1')
        self.assertGreaterEqual(plug[1]-lower,.5)
        mic=next(c for c in board['components'] if c['ref']=='U3')['envelope']
        self.assertGreaterEqual(mic[1]-plug[3],1.0)
        caps=board.get('keycapEnvelopes',[])
        self.assertEqual(len(caps),3)
        self.assertGreaterEqual(min(c['envelope'][1] for c in caps)-mic[3],1.0)

    def test_board_outline_holes_and_controls_match_original(self):
        design=build_design.build()
        source=geometry.read_archive(ROOT/'reference/upstream-pcb-v1.2.epro2')
        original=geometry.board_geometry(source['1ecf9d019d074243'])
        self.assertEqual(len(design['outline']),len(original['outline']))
        for actual,path in zip(design['outline'],original['outline']):
            self.assertEqual(tuple(actual['start']),build_design.norm(path[0],path[1]))
            self.assertEqual(tuple(actual['end']),build_design.norm(path[-2],path[-1]))
            self.assertEqual(actual['angle'],-path[3] if path[2]=='ARC' else 0)
        self.assertEqual(len(design['mountingHoles']),5)
        for actual,hole in zip(design['mountingHoles'],original['holes']):
            self.assertEqual((actual['x'],actual['y']),build_design.norm(hole['x'],hole['y']))
            self.assertAlmostEqual(actual['diameter'],hole['diameter']*.0254)
        for ref,original_ref in [('SW1','SW1'),('SW2','SW2'),('SW3','SW3'),('JS1','U2')]:
            actual=next(c for c in design['components'] if c['ref']==ref)
            component=original['components'][original_ref]
            self.assertEqual((actual['x'],actual['y']),build_design.norm(component['x'],component['y']))
            for actual_pad,original_pad in zip(actual['pads'],geometry.pads(source[component['Footprint']])):
                self.assertEqual(actual_pad['number'],original_pad['num'])
                self.assertEqual((actual_pad['x'],actual_pad['y']),build_design.transform(component,original_pad['centerX'],original_pad['centerY']))

    def test_a2_reverses_devkit_pads_without_changing_the_gpio_map(self):
        board=build_design.build()
        devkit=next(c for c in board['components'] if c['ref']=='U1')
        indexed={p['number']:p for p in devkit['pads']}
        # Rotate around the existing 67.78 x 28 mm module envelope centre.
        # GPIO labels travel with the physical numbered pins, never mirror nets.
        # Move 3mm toward USB after rotation, bringing the USB end to the edge.
        for number,x,y in [('1',57.73,2.294),('21',6.93,2.294),
                           ('22',57.73,27.694),('42',6.93,27.694)]:
            self.assertAlmostEqual(indexed[number]['x'],x,places=5)
            self.assertAlmostEqual(indexed[number]['y'],y,places=5)
        docs=geometry.read_archive(ROOT/'reference/goouuu-reference-carrier.epro2')
        pins=geometry.symbol_pins(docs['dec5ecc4336c40cd976d9e8e08c16bd8'])
        active={f'GPIO{n}' for n in build_design.FIXED_IO.values()}|{'GPIO1','GPIO2','GPIO8','GND'}
        for number,name in pins.items():
            expected='+3V3' if name=='3V3' else '+5V' if name=='5V+' else name if name in active else ''
            self.assertEqual(indexed[number]['net'],expected)
        self.assertEqual(devkit['envelope'],[-.525,.897,67.255,28.897])
        self.assertEqual(board['usbSide'],'left')
        self.assertFalse(board['usbOpeningAlignmentVerified'])
        self.assertGreater(board['antennaKeepout'][0],60)
        self.assertGreaterEqual(board['antennaKeepout'][2],73.4747)
        self.assertEqual(board['nylonMountingHoles'],['H2'])
        self.assertFalse(board['usbFaceDimensionsVerified'])

    def test_existing_firmware_gpio_assignments_remain_exact(self):
        header=(ROOT.parents[1]/'firmware/s3/pet_s3_board.h').read_text()
        actual={key:int(value) for key,value in re.findall(r'^#define PET_S3_(\w+) (\d+)$',header,re.M)}
        for key,value in build_design.FIXED_IO.items():self.assertEqual(actual[key],value)

    def test_module_pin_nets_and_direct_gpio_backlight(self):
        board=build_design.build();c={c['ref']:c for c in board['components']}
        def nets(ref):return {p['number']:p['net'] for p in c[ref]['pads']}
        self.assertEqual(nets('U3'),{'1':'GND','2':'+3V3','3':'GPIO6','4':'GND','5':'GPIO4','6':'GPIO5'})
        self.assertEqual(nets('U2')['5'],'GPIO7')
        self.assertEqual(nets('U2')['6'],'GPIO15')
        self.assertEqual(nets('U2')['7'],'GPIO16')
        self.assertEqual(set(nets('U2')),{'1','2','3','4','5','6','7'})
        self.assertFalse({'SPK+','SPK-'} &
                         {p['net'] for part in c.values() for p in part['pads']})
        self.assertEqual(nets('J1')['8'],'GPIO42')
        self.assertEqual(nets('U1')['27'],'GPIO42')
        self.assertEqual(nets('U2')['4'],'AMP_GAIN')
        self.assertEqual(set(c),{'U1','U2','U3','SW1','SW2','SW3','JS1','J1','JP1'})
        self.assertFalse({'BL_GATE','BL_BASE','LCD_BL_POWER'} &
                         {p['net'] for part in c.values() for p in part['pads']})
        self.assertTrue(all(p['net']=='' for p in c['U1']['pads'] if p['number'] in ['13','14','32','33','34']))
        self.assertFalse(board['fabricationApproved'])

    def test_module_envelopes_do_not_overlap(self):
        components=build_design.build()['components']
        for i,a in enumerate(components):
            for b in components[i+1:]:
                x1,y1,x2,y2=a['envelope'];u1,v1,u2,v2=b['envelope']
                self.assertTrue(min(x2,u2)<=max(x1,u1) or min(y2,v2)<=max(y1,v1),
                                f'{a["ref"]} interferes with {b["ref"]}')

    def test_joystick_retains_drill_and_pad_locations(self):
        board=build_design.build();j=next(c for c in board['components'] if c['ref']=='JS1')
        for p in j['pads']:
            if p['number']=='0':
                self.assertAlmostEqual(p['drill'],1.2,places=4)
                self.assertGreaterEqual((p['width']-p['drill'])/2,.29)

    def test_goouuu_symbol_and_footprint_agree_on_42_pins(self):
        docs = geometry.read_archive(ROOT / 'reference/goouuu-reference-carrier.epro2')
        pads = geometry.pads(docs['e7f74316ee0e465e9b94fc43b531cec9'])
        pins = geometry.symbol_pins(docs['dec5ecc4336c40cd976d9e8e08c16bd8'])
        self.assertEqual(set(pins), {str(i) for i in range(1, 43)})
        self.assertEqual({p['num'] for p in pads}, set(pins))
        self.assertEqual(pins['23'], 'GPIO1')
        self.assertEqual(pins['24'], 'GPIO2')
        self.assertEqual(pins['42'], '5V+')
        self.assertAlmostEqual((pads[21]['centerX'] - pads[0]['centerX']) * .0254, 25.4)

    def test_original_switch_spacing_is_preserved_from_source(self):
        docs = geometry.read_archive(ROOT / 'reference/upstream-pcb-v1.2.epro2')
        board = geometry.board_geometry(docs['1ecf9d019d074243'])
        sw = [board['components'][f'SW{i}'] for i in [1, 2, 3]]
        self.assertAlmostEqual(sw[1]['x'] - sw[0]['x'], 748.5)
        self.assertAlmostEqual(sw[2]['x'] - sw[1]['x'], 748.5)
        self.assertEqual(len(board['holes']), 5)
        self.assertEqual(len(board['outline']), 10)
        self.assertEqual(board['components']['U2']['angle'], -90)


if __name__ == '__main__':
    unittest.main()
