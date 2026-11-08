import json,sys
from bridge_client import call,ROOT

revision=sys.argv[1] if len(sys.argv)>1 else 'r2'
out=ROOT.parent/('output/r3-original' if revision=='r3' else 'output/r2-fusion')
working=json.loads((ROOT/('working-r3.json' if revision=='r3' else 'working-native.json')).read_text(encoding='utf-8'))
original=json.loads((ROOT/'original-native-inspection.json').read_text(encoding='utf-8'))
matrix=[1,0,0,36.12495,0,0,-1,-43.69864,0,1,0,16.45525253169416,0,0,0,1]
result={}
for index,label in [(0,'upper'),(1,'lower')]:
    ref=call('copy_body',body_id=original['bodies'][index]['body_id'],to_design_id=working['design_id'],matrix_mm=matrix,name='Original '+label+' geometry comparison')
    call('export_stl',body_id=ref['body_id'],path=str(out/f'native-original-{label}.stl'))
    added=call('copy_body',body_id=working['bodies'][index]['body_id'],to_design_id=working['design_id'],name='Analytic added '+label)
    diff=call('combine',target_id=added['body_id'],tool_ids=[ref['body_id']],operation='cut')
    call('export_stl',body_id=added['body_id'],path=str(out/f'native-added-{label}.stl'))
    result[label]=diff
(out/'native-difference.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
