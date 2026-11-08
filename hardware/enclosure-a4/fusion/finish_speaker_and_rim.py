"""Create a clean complete R4.4 pair, preserving original controls and lettering."""
import json
import shutil
import time
from bridge_client import call,ROOT


def main():
    out=ROOT.parent/'output/r4-original-copy/full-r4.4';out.mkdir(exist_ok=True)
    w=json.loads((ROOT/'working-r4.json').read_text(encoding='utf-8'))
    speaker=json.loads((out.parent/'speaker-slot/working-speaker.json').read_text(encoding='utf-8'))
    (out/'baseline-working-r4.3.json').write_text(json.dumps(w,indent=2),encoding='utf-8')
    shutil.copy2(out.parent/'a4-upper-r4-assembly.stl',out/'baseline-upper-assembly.stl')
    call('ping',end_orbit=True);time.sleep(.6)
    scratch=call('new_document')
    ub=call('copy_body',body_id=w['bodies'][0]['body_id'],to_design_id=scratch['design_id'])
    stock=call('box',design_id=scratch['design_id'],
        min_mm=[74.87495,-64.19864,16.45525253169416],max_mm=[76.19,-49.89106,20.],
        name='Remove scaled joystick lip remnant')
    cleaned=call('combine',target_id=ub['body_id'],tool_ids=[stock['body_id']],operation='cut',consume_tools=True)
    removed=ub['volume_mm3']-cleaned['volume_mm3']
    # Fusion's quick whole-body volume may change by a few mm3 after a
    # Boolean retessellation. Check the actual exported difference separately.
    if not 0<removed<5:raise RuntimeError('Unexpected rim cleanup volume: '+str(removed))
    doc=call('new_document');bodies=[]
    bodies.append(call('copy_body',body_id=cleaned['body_id'],to_design_id=doc['design_id'],
        copy_appearance=True,appearance_source_body_id=w['bodies'][0]['body_id'],
        name='A4 Upper R4.4 - Hachimo recessed - smooth original controls'))
    bodies.append(call('copy_body',body_id=speaker['bodies'][0]['body_id'],to_design_id=doc['design_id'],
        copy_appearance=True,name='A4 Lower R4.4 - speaker slot - dual Type-C'))
    controls=[call('copy_body',body_id=b['body_id'],to_design_id=doc['design_id'],
                   copy_appearance=True,name=b['name']) for b in w['review_controls']]
    w.update(design_id=doc['design_id'],bodies=bodies,review_controls=controls,
        revision='R4.4-speaker-and-smooth-rim',speaker_mount=speaker['speaker_mount'],
        control_rim_cleanup={'fusion_quick_volume_difference_mm3':removed,
            'region_mm':[[74.87495,-64.19864,16.45525253169416],[76.19,-49.89106,20.]],
            'original_control_geometry_unchanged':True})
    (out/'working-full.json').write_text(json.dumps(w,indent=2),encoding='utf-8')
    for label,b in zip(['upper','lower'],bodies):
        call('export_stl',body_id=b['body_id'],path=str(out/f'{label}-assembly.stl'),surface_deviation_mm=.01)
    print_doc=call('new_document');exports={}
    for label,b,name in zip(['upper','lower'],bodies,['a4-upper-r4.4-hachimo.stl','a4-lower-r4.4-speaker.stl']):
        part=call('copy_body',body_id=b['body_id'],to_design_id=print_doc['design_id'])
        lo=part['bounds_mm'][0]
        part=call('transform',body_id=part['body_id'],matrix_mm=[1,0,0,-lo[0],0,1,0,-lo[1],0,0,1,-lo[2],0,0,0,1])
        result=call('export_stl',body_id=part['body_id'],path=str(out/name),surface_deviation_mm=.01)
        exports[label]={'file':name,'assembly_minimum_mm':lo,'bytes':result['bytes']}
    w['exports']=exports
    call('export_step',design_id=doc['design_id'],path=str(out/'working-r4.4-full.step'))
    call('snapshot',design_id=doc['design_id'],show_only_ids=[b['body_id'] for b in bodies+controls],
        camera_mm=[[130,-205,140],[36,-26,28]],path=str(out/'complete-assembly.png'))
    call('snapshot',design_id=doc['design_id'],show_only_ids=[bodies[1]['body_id']],
        camera_mm=[[108,-155,123],[36,-3,29]],path=str(out/'speaker-slot-inside.png'))
    (out/'working-full.json').write_text(json.dumps(w,indent=2),encoding='utf-8')
    print(json.dumps({'design':doc['design_id'],'rim_removed_mm3':removed,'exports':exports},indent=2),flush=True)


if __name__=='__main__':main()
