import json
import time
from bridge_client import call,ROOT


def main():
    w=json.loads((ROOT/'working-r4.json').read_text(encoding='utf-8'))
    out=ROOT.parent/'output/r4-original-copy/speaker-slot';out.mkdir(exist_ok=True)
    (out/'baseline-working.json').write_text(json.dumps(w,indent=2),encoding='utf-8')
    call('ping',end_orbit=True);time.sleep(.6)
    result=call('new_document',template='speaker_slot',lower_source_id=w['bodies'][1]['body_id'],rear_vent_bores_mm=w['rear_vent_bores_mm'])
    result.update(screen_origin_mm=w['screen_origin_mm'],rear_vent_bores_mm=w['rear_vent_bores_mm'])
    (out/'working-speaker.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    call('export_stl',body_id=result['baseline']['body_id'],path=str(out/'baseline-lower-assembly.stl'),surface_deviation_mm=.01)
    call('export_stl',body_id=result['bodies'][0]['body_id'],path=str(out/'a4-lower-speaker-slot-assembly.stl'),surface_deviation_mm=.01)
    call('export_stl',body_id=w['bodies'][0]['body_id'],path=str(out/'upper-assembly.stl'),surface_deviation_mm=.01)
    d=call('new_document');b=call('copy_body',body_id=result['bodies'][0]['body_id'],to_design_id=d['design_id']);lo=b['bounds_mm'][0]
    b=call('transform',body_id=b['body_id'],matrix_mm=[1,0,0,-lo[0],0,1,0,-lo[1],0,0,1,-lo[2],0,0,0,1])
    exported=call('export_stl',body_id=b['body_id'],path=str(out/'a4-lower-speaker-slot.stl'),surface_deviation_mm=.01)
    result['export']={'assembly_minimum_mm':lo,'bytes':exported['bytes']}
    (out/'working-speaker.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    call('snapshot',design_id=result['design_id'],show_only_ids=[result['bodies'][0]['body_id']],camera_mm=[[115,-160,125],[36,-10,25]],path=str(out/'speaker-slot-inside.png'))
    print('Speaker slot',result['speaker_mount'],'design',result['design_id'],flush=True)


if __name__=='__main__':main()
