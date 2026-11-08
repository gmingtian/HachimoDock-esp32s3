"""Export two full-scale inspection shells, then verify the actual STLs."""
import json
from bridge_client import call,ROOT


def main():
    w=json.loads((ROOT/'working-r4.json').read_text(encoding='utf-8'))
    out=ROOT.parent/'output/r4-original-copy/fit-trial';out.mkdir(exist_ok=True)
    result=call('new_document',template='fit_trial_r4',source_design_id=w['design_id'],
        upper_source_id=w['bodies'][0]['body_id'],lower_source_id=w['bodies'][1]['body_id'],
        screen_origin_mm=w['screen_origin_mm'])
    result['files']={}
    (out/'trial-working.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    for b,label in zip(result['bodies'],['upper','lower']):
        call('export_stl',body_id=b['body_id'],path=str(out/f'a4-{label}-fit-trial-assembly.stl'),surface_deviation_mm=.01)
    printdoc=call('new_document')
    for b,label in zip(result['bodies'],['upper','lower']):
        c=call('copy_body',body_id=b['body_id'],to_design_id=printdoc['design_id'])
        minimum=c['bounds_mm'][0]
        c=call('transform',body_id=c['body_id'],matrix_mm=[1,0,0,-minimum[0],0,1,0,-minimum[1],0,0,1,-minimum[2],0,0,0,1])
        name=f'a4-{label}-fit-trial-spi17.stl'
        exported=call('export_stl',body_id=c['body_id'],path=str(out/name),surface_deviation_mm=.01)
        result['files'][label]={'name':name,'assembly_minimum_mm':minimum,'bytes':exported['bytes']}
        print(label,exported['bytes'],flush=True)
    (out/'trial-working.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    call('snapshot',design_id=result['design_id'],show_only_ids=[b['body_id'] for b in result['bodies']],
        camera_mm=[[130,-170,125],[36,-28,29]],path=str(out/'trial-assembly.png'))
    print('Trial design',result['design_id'],flush=True)


if __name__=='__main__':main()
