"""Keep official Node binaries and the exact complete license carrier paired."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

SCRIPTS=Path(__file__).resolve().parents[1]
ROOT=SCRIPTS.parents[1]
spec=importlib.util.spec_from_file_location('preview',SCRIPTS/'prepare-preview-resources.py')
prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(prepare)
review=json.loads((SCRIPTS/'node-runtime-review.json').read_text())

def real_node():
    candidate=os.environ.get('REVIEWED_NODE_BIN') or shutil.which('node')
    if not candidate:return None
    path=Path(candidate).resolve()
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    return path if any(item['binarySha256']==digest for item in review['targets'].values()) else None

class ReviewedNodeRuntimeTests(unittest.TestCase):
    def test_canonical_carrier_is_complete_official_original_bytes(self):
        data=(ROOT/'licenses'/review['license']['file']).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(),review['license']['sha256'])
        self.assertEqual(len(data),157609)
        self.assertIn(b'merve, located at deps/merve',data)

    def test_unknown_stable_version_is_rejected_before_download(self):
        with self.assertRaisesRegex(ValueError,'Node.*reviewed.*version'):
            prepare.collect_node_license('22.23.4',fetch=lambda url:self.fail('must not download unknown version'))

    def test_unreviewed_binary_is_rejected_before_execution_or_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);binary=root/'node';binary.write_bytes(b'not reviewed')
            with mock.patch.object(prepare,'run',side_effect=AssertionError('must not execute unreviewed binary')):
                with self.assertRaisesRegex(ValueError,'Node.*reviewed'):
                    prepare.stage_node_license(binary,root/'output')
            self.assertFalse((root/'output').exists())

    def test_stage_keeps_canonical_bytes_without_network_or_rewriting_conflicts(self):
        node=real_node()
        if node is None:self.skipTest('real reviewed Node binary required')
        data=(ROOT/'licenses'/review['license']['file']).read_bytes()
        with tempfile.TemporaryDirectory() as tmp,mock.patch.object(prepare,'urlopen',side_effect=AssertionError('license must be offline')):
            root=Path(tmp)
            prepare.stage_node_license(node,root)
            self.assertEqual((root/'node.LICENSE').read_bytes(),data)
            prepare.stage_node_license(node,root)
            (root/'node.LICENSE').write_bytes(b'conflicting carrier')
            with self.assertRaisesRegex(ValueError,'Node.*license.*mismatch'):
                prepare.stage_node_license(node,root)
            self.assertEqual((root/'node.LICENSE').read_bytes(),b'conflicting carrier')

    def test_real_reviewed_binary_cannot_inherit_wrong_platform_carrier(self):
        node=real_node()
        if node is None:self.skipTest('real reviewed Node binary required')
        digest=hashlib.sha256(node.read_bytes()).hexdigest()
        other=next(key for key,value in review['targets'].items() if value['binarySha256']!=digest)
        target,arch=other.split('-')
        with self.assertRaisesRegex(ValueError,'Node.*reviewed'):
            prepare.validate_reviewed_node_binary(node,target,arch)

if __name__=='__main__':unittest.main()
