"""Apply the approved recessed wordmark and export the new complete upper."""
import hashlib
import json
import time
from bridge_client import call,ROOT


def main():
    w=json.loads((ROOT/'working-r4.json').read_text(encoding='utf-8'))
    out=ROOT.parent/'output/r4-original-copy/hachimo-inset';out.mkdir(exist_ok=True)
    (out/'baseline-working-r4.json').write_text(json.dumps(w,indent=2),encoding='utf-8')
    call('ping',end_orbit=True);time.sleep(.6)
    result=call('new_document',template='hachimo_inset',upper_source_id=w['bodies'][0]['body_id'],screen_origin_mm=w['screen_origin_mm'])
    lower=call('copy_body',body_id=w['bodies'][1]['body_id'],to_design_id=result['design_id'],copy_appearance=True,name='Full lower SPI17 access fixed')
    result['bodies'].append(lower)
    result['review_controls']=[call('copy_body',body_id=b['body_id'],to_design_id=result['design_id'],copy_appearance=True,name=b['name']) for b in w['review_controls']]
    result['lower_assembly_minimum_mm']=lower['bounds_mm'][0]
    result['lower_sha256']=hashlib.sha256((out.parent/'a4-lower-r4-spi17-fixed.stl').read_bytes()).hexdigest()
    result['source_design_id']=w['design_id']
    (out/'working-hachimo.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    call('export_stl',body_id=result['baseline']['body_id'],path=str(out/'baseline-upper-assembly.stl'),surface_deviation_mm=.01)
    call('export_stl',body_id=result['bodies'][0]['body_id'],path=str(out/'a4-upper-hachimo-inset-assembly.stl'),surface_deviation_mm=.01)
    printdoc=call('new_document')
    ready=call('copy_body',body_id=result['bodies'][0]['body_id'],to_design_id=printdoc['design_id'])
    lo=ready['bounds_mm'][0]
    ready=call('transform',body_id=ready['body_id'],matrix_mm=[1,0,0,-lo[0],0,1,0,-lo[1],0,0,1,-lo[2],0,0,0,1])
    exported=call('export_stl',body_id=ready['body_id'],path=str(out/'a4-upper-hachimo-inset.stl'),surface_deviation_mm=.01)
    result['export']={'assembly_minimum_mm':lo,'surface_deviation_mm':exported['surface_deviation_mm'],'bytes':exported['bytes']}
    (out/'working-hachimo.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    call('snapshot',design_id=result['design_id'],show_only_ids=[b['body_id'] for b in result['bodies']+result['review_controls']],camera_mm=[[110,-180,150],[36,-30,29]],path=str(out/'hachimo-assembly.png'))
    print('Engraved upper',exported['bytes'],'bytes; design',result['design_id'],flush=True)


if __name__=='__main__':main()
