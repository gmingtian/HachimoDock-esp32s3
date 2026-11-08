"""Point local working records at the verified complete STL pair."""
import hashlib
import json
import shutil
import time
from bridge_client import ROOT,call

out=ROOT.parent/'output/r4-original-copy/full-r4.4'
w=json.loads((out/'working-full.json').read_text())
report=json.loads((out/'full-verification.json').read_text())
for label,meta in report['files'].items():
    assert hashlib.sha256((out/meta['file']).read_bytes()).hexdigest()==meta['sha256']
    shutil.copy2(out/f'{label}-assembly.stl',out.parent/f'a4-{label}-r4-assembly.stl')
w['control_rim_cleanup']['mesh_removed_mm3']=report['rim_cleanup']['removed_volume_mm3']
w['control_rim_cleanup']['mesh_added_mm3']=report['rim_cleanup']['added_volume_mm3']
(out/'working-full.json').write_text(json.dumps(w,indent=2),encoding='utf-8')
(ROOT/'working-r4.json').write_text(json.dumps(w,indent=2),encoding='utf-8')
requirements=ROOT.parent/'requirements.json';r=json.loads(requirements.read_text(encoding='utf-8'))
r['revision']=w['revision']
r['speakerMount']={**w['speaker_mount'],'dimension_source':'user supplied measurements',
                   'physical_fit_verified':False,'acoustic_performance_verified':False}
r['unresolved']=[s for s in r['unresolved'] if 'Speaker diameter' not in s]
r['unresolved'].append('Speaker slot printed fit and retention; actual wire routing and acoustic performance')
requirements.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
# Include the speaker metadata in future native rebuild results as well.
source=ROOT/'FusionEnclosureBridge/native_clone.py';s=source.read_text(encoding='utf-8')
old="'lettering':lettering}"
if old in s:
    assert s.count(old)==1
    source.write_text(s.replace(old,"'lettering':lettering,'speaker_mount':speaker_mount}"),encoding='utf-8')
delivery={'revision':w['revision'],'upper':'full-r4.4/'+w['exports']['upper']['file'],
    'lower':'full-r4.4/'+w['exports']['lower']['file'],'preview':'full-r4.4/complete-assembly.png',
    'inside_preview':'full-r4.4/speaker-slot-inside.png','native_checkpoint':'full-r4.4/working-r4.4-full.step',
    'verification':'full-r4.4/full-verification.json','physical_fit_verified':False}
(out.parent/'current-delivery.json').write_text(json.dumps(delivery,indent=2),encoding='utf-8')
call('ping',end_orbit=True);time.sleep(.6)
closed=call('ping',close_unused_bridge_documents=True,keep_design_ids=[w['design_id']])
call('snapshot',design_id=w['design_id'],show_only_ids=[b['body_id'] for b in w['bodies']+w['review_controls']],
    camera_mm=[[105,-205,140],[36,-27,28]],path=str(out/'complete-assembly.png'))
print(json.dumps({'current':delivery,'closed_scratch':closed},indent=2))
