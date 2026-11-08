"""Rebuild the original-copy adaptation with the measured SPI stack."""
import json
import time
from bridge_client import call, ROOT


def main():
    call('ping', end_orbit=True)
    time.sleep(.6)
    original = json.loads((ROOT / 'original-native-inspection.json').read_text(encoding='utf-8'))['bodies']
    result = call('new_document', template='enclosure_r4',
                  upper_source_id=original[0]['body_id'],
                  lower_source_id=original[1]['body_id'],
                  key_source_ids=[b['body_id'] for b in original[2:5]],
                  screen_extension_v_mm=13.5)
    out = ROOT.parent / 'output/r4-original-copy'
    # Save before subsequent exports so an interrupted queue can be resumed.
    (ROOT / 'working-r4.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    for b, label in zip(result['bodies'], ['upper', 'lower']):
        call('export_stl', body_id=b['body_id'], path=str(out / f'a4-{label}-r4-assembly.stl'))
        print(label, {k: v for k, v in b.items() if k != 'edges'}, flush=True)
    for b, label in zip(result['surface_reference_bodies'], ['upper', 'lower']):
        call('export_stl', body_id=b['body_id'], path=str(out / f'exterior-reference-{label}.stl'))
    controls = []
    transform = [1,0,0,36.12495, 0,0,-1,-43.69864, 0,1,0,16.45525253169416, 0,0,0,1]
    for b in original[2:8]:
        controls.append(call('copy_body', body_id=b['body_id'], to_design_id=result['design_id'],
                             matrix_mm=transform, copy_appearance=True, name=b['name']))
    result['review_controls'] = controls
    (ROOT / 'working-r4.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    call('snapshot', design_id=result['design_id'],
         show_only_ids=[b['body_id'] for b in result['bodies'] + controls],
         camera_mm=[[140,-185,120],[36,-28,29]], path=str(out / 'original-style-assembly.png'))
    print('Built', result['design_id'], 'screen extension', result['screen_extension_v_mm'], flush=True)


if __name__ == '__main__':
    main()
