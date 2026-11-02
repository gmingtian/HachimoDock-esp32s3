"""Packaging must reject DRC results from a different PCB or rule set."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))


class DrcGuardTests(unittest.TestCase):
    def test_changed_board_rules_or_report_invalidates_clean_drc(self):
        from verify_drc import validate_attestation
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            contents={'board.kicad_pcb':b'original pcb','board.kicad_pro':b'original rules',
                      'drc.json':json.dumps({'violations':[],'unconnected_items':[]}).encode()}
            for name,data in contents.items():(root/name).write_bytes(data)
            att={'result':'PASS','files':{name:hashlib.sha256(data).hexdigest() for name,data in contents.items()}}
            (root/'drc-attestation.json').write_text(json.dumps(att))
            validate_attestation(root,root/'board.kicad_pcb')
            for name,original in contents.items():
                with self.subTest(changed=name):
                    (root/name).write_bytes(original+b' ')
                    with self.assertRaises(ValueError):validate_attestation(root,root/'board.kicad_pcb')
                    (root/name).write_bytes(original)

    def test_attested_but_unclean_report_is_rejected(self):
        from verify_drc import validate_attestation
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in ['board.kicad_pcb','board.kicad_pro']:(root/name).write_text('fixture')
            (root/'drc.json').write_text(json.dumps({'violations':[{'type':'shorting_items'}],'unconnected_items':[]}))
            (root/'drc-attestation.json').write_text(json.dumps({'result':'PASS','files':{
                p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()}}))
            with self.assertRaises(ValueError):validate_attestation(root,root/'board.kicad_pcb')


if __name__=='__main__':unittest.main()
