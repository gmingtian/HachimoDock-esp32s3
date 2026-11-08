import json
from pathlib import Path
from bridge_client import call, ROOT

out = ROOT.parent / 'output/r2-fusion'
doc = call('new_document')
(out/'calibration-document.json').write_text(json.dumps(doc,indent=2),encoding='utf-8')
block = call('box',design_id=doc['design_id'],min_mm=[0,0,0],max_mm=[10,20,30],name='UnitCalibration')
call('export_stl',body_id=block['body_id'],path=str(out/'calibration-10x20x30.stl'))
ref = call('import_step',path=str(ROOT.parent/'reference/original-assembly.STEP'))
(ROOT/'original-native-inspection.json').write_text(json.dumps(ref,indent=2),encoding='utf-8')
print(json.dumps({'calibration':block,'reference_design':ref['design_id'],'bodies':[{k:v for k,v in b.items() if k!='faces'} for b in ref['bodies']]},indent=2))
