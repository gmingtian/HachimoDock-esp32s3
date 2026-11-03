"""Compare a native KiCad schematic export with the audited physical PCB."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))


class SchematicTests(unittest.TestCase):
    def setUp(self):
        self.sch = ROOT / 'output/HachimoDock-S3-carrier-A4.kicad_sch'
        self.assertTrue(self.sch.is_file(), 'The editable A4 schematic has not been generated')
        self.netlist = ROOT / 'output/schematic-netlist.xml'
        self.assertTrue(self.netlist.is_file(), 'Native KiCad must export the schematic netlist')
        self.audit = json.loads((ROOT / 'output/electrical-audit.json').read_text())
        board = ROOT / 'output/HachimoDock-S3-carrier-A4.kicad_pcb'
        self.assertEqual(hashlib.sha256(board.read_bytes()).hexdigest(), self.audit['boardSha256'])

    def test_every_schematic_pin_matches_the_native_board(self):
        from schematic_audit import compare_netlist
        report = compare_netlist(ET.parse(self.netlist).getroot(), self.audit['nativeElectricalPads'])
        self.assertEqual(report['physicalPads'], 86)
        self.assertEqual(report['uniquePins'], 83)  # Four joystick tabs share pin 0.
        self.assertEqual(report['components'], 9)

    def test_export_paths_are_portable_without_changing_connections(self):
        from schematic_audit import normalize_export_paths, compare_netlist
        tree = ET.parse(self.netlist)
        tree.getroot().find('./design/source').text = '/machine/project/board.kicad_sch'
        library = tree.getroot().find('./libraries/library/uri')
        library.text = '/machine/project/S3_Carrier.kicad_sym'
        normalize_export_paths(tree.getroot())
        self.assertEqual(tree.getroot().find('./design/source').text, 'board.kicad_sch')
        self.assertEqual(library.text, 'S3_Carrier.kicad_sym')
        self.assertFalse(normalize_export_paths(tree.getroot()))
        tree.getroot().find('./design/source').text = r'C:\project\board.kicad_sch'
        library.text = r'C:\project\S3_Carrier.kicad_sym'
        self.assertTrue(normalize_export_paths(tree.getroot()))
        self.assertEqual(tree.getroot().find('./design/source').text, 'board.kicad_sch')
        self.assertEqual(library.text, 'S3_Carrier.kicad_sym')
        report = compare_netlist(tree.getroot(), self.audit['nativeElectricalPads'])
        self.assertEqual(report['connectedUniquePins'], 64)

    def test_swapped_lcd_clock_is_rejected(self):
        from schematic_audit import compare_netlist
        tree = ET.parse(self.netlist).getroot()
        node = next(n for n in tree.findall('./nets/net/node')
                    if n.get('ref') == 'J1' and n.get('pin') == '3')
        node.set('pin', '4')
        with self.assertRaises(ValueError):
            compare_netlist(tree, self.audit['nativeElectricalPads'])

    def test_gain_rail_short_is_rejected(self):
        from schematic_audit import compare_netlist
        tree = ET.parse(self.netlist).getroot()
        gain = next(n for n in tree.findall('./nets/net') if n.get('name').lstrip('/') == 'AMP_GAIN')
        ground = next(n for n in tree.findall('./nets/net') if n.get('name').lstrip('/') == 'GND')
        gain.append(copy.deepcopy(next(n for n in ground.findall('node')
                                      if n.get('ref') == 'JP1' and n.get('pin') == '3')))
        with self.assertRaises(ValueError):
            compare_netlist(tree, self.audit['nativeElectricalPads'])

    def test_usb_pin_cannot_be_attached_to_carrier_ground(self):
        from schematic_audit import compare_netlist
        tree = ET.parse(self.netlist).getroot()
        ground = next(n for n in tree.findall('./nets/net') if n.get('name').lstrip('/') == 'GND')
        ET.SubElement(ground, 'node', {'ref': 'U1', 'pin': '13'})
        with self.assertRaises(ValueError):
            compare_netlist(tree, self.audit['nativeElectricalPads'])


if __name__ == '__main__':
    unittest.main()
