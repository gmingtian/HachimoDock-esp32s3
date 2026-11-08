import json,time
from bridge_client import call,ROOT
call('ping',end_orbit=True);time.sleep(.5)
reference=json.loads((ROOT/'original-native-inspection.json').read_text(encoding='utf-8'))['bodies']
result=call('new_document',template='enclosure_r3',upper_source_id=reference[0]['body_id'],lower_source_id=reference[1]['body_id'],key_source_ids=[b['body_id'] for b in reference[2:5]])
(ROOT/'working-r3.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
out=ROOT.parent/'output/r3-original'
for b,name in zip(result['bodies'],['upper','lower']):
    call('export_stl',body_id=b['body_id'],path=str(out/f'a4-{name}-r3-assembly.stl'))
    print({k:v for k,v in b.items() if k!='edges'},flush=True)
for b,label in zip(result['surface_reference_bodies'],['upper','lower']):
    call('export_stl',body_id=b['body_id'],path=str(out/f'exterior-reference-{label}.stl'))
seam=call('inspect',interference_ids=[b['body_id'] for b in result['bodies']])
(out/'native-seam-check.json').write_text(json.dumps(seam),encoding='utf-8')
call('snapshot',design_id=result['design_id'],show_only_ids=[b['body_id'] for b in result['bodies']],camera_mm=[[145,-190,125],[36,-28,27]],path=str(out/'native-exterior.png'))
