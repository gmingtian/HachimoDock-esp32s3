import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'FusionEnclosureBridge'))
from bridge_protocol import validate_request,mm_to_cm,point_cm,matrix_cm,within_root,atomic_json

class ProtocolTests(unittest.TestCase):
    def test_mm_are_converted_to_fusion_centimeters(self):
        self.assertEqual(mm_to_cm(25.4),2.54)
        for actual,expected in zip(point_cm([36.044,-36.060,4.455]),[3.6044,-3.606,0.4455]):
            self.assertAlmostEqual(actual,expected,places=12)

    def test_non_finite_and_boolean_dimensions_are_rejected(self):
        for value in [True,False,math.nan,math.inf,-math.inf,'3.5']:
            with self.subTest(value=value),self.assertRaises(ValueError):mm_to_cm(value)

    def test_point_has_exactly_three_dimensions(self):
        for value in [[1,2],[1,2,3,4],None]:
            with self.subTest(value=value),self.assertRaises(ValueError):point_cm(value)

    def test_affine_translation_is_scaled_but_rotation_is_not(self):
        result=matrix_cm([1,0,0,25.4,0,0,-1,40,0,1,0,6,0,0,0,1])
        self.assertEqual(result,[1,0,0,2.54,0,0,-1,4,0,1,0,.6,0,0,0,1])

    def test_mirror_and_non_affine_transform_are_rejected(self):
        for values in [[-1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],[1,0,0,0,0,1,0,0,0,0,1,0,1,0,0,1]]:
            with self.assertRaises(ValueError):matrix_cm(values)

    def test_known_request_retains_its_session_and_identifier(self):
        request={'id':'inspect-001','session_id':'s123','op':'inspect','args':{'design_id':'d1'}}
        self.assertEqual(validate_request(request),request)

    def test_request_cannot_select_python_or_shell_execution(self):
        for op in ['exec','eval','shell','powershell','load_module']:
            with self.assertRaises(ValueError):validate_request({'id':'x','session_id':'s','op':op,'args':{}})

    def test_request_id_cannot_escape_response_folder(self):
        for id in ['../x','x/y','x\\y','', 'x'*97]:
            with self.assertRaises(ValueError):validate_request({'id':id,'session_id':'s','op':'ping','args':{}})

    def test_missing_session_and_wrong_args_shape_are_rejected(self):
        for request in [{'id':'x','op':'ping','args':{}},{'id':'x','session_id':'s','op':'ping','args':[]}]:
            with self.assertRaises(ValueError):validate_request(request)

    def test_output_is_confined_to_its_declared_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'output';root.mkdir()
            self.assertEqual(within_root(root/'part.stl',root),root/'part.stl')
            with self.assertRaises(ValueError):within_root(root/'..'/'elsewhere.stl',root)

    def test_json_response_preserves_real_newlines_and_unicode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'reply.json';payload={'message':'中间固定\n已读取','values':[2.54]}
            atomic_json(path,payload)
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')),payload)
            self.assertFalse(list(Path(tmp).glob('*.tmp')))

if __name__=='__main__':unittest.main()
