import json
from bridge_client import call,ROOT

ref=json.loads((ROOT/'original-native-inspection.json').read_text(encoding='utf-8'))
b=ref['bodies']
result=call('new_document',template='enclosure_r2',upper_source_id=b[0]['body_id'],lower_source_id=b[1]['body_id'],key_source_ids=[v['body_id'] for v in b[2:5]])
(ROOT/'working-native.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
out=ROOT.parent/'output/r2-fusion'
for row,name in zip(result['bodies'],['upper','lower']):
    call('export_stl',body_id=row['body_id'],path=str(out/f'a4-{name}-r2-assembly.stl'))
    print({k:v for k,v in row.items() if k!='edges'},flush=True)
seam=call('inspect',intersection_ids=[row['body_id'] for row in result['bodies']])
(out/'native-seam-check.json').write_text(json.dumps(seam),encoding='utf-8')
call('snapshot',design_id=result['design_id'],path=str(out/'fusion-native.png'))
