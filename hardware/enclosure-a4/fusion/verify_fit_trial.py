"""Read back the fit-trial STLs and verify the retained mechanical interfaces."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build_enclosure import solid, board, pcb_box, cyl, D, P
from verify_fixings import checks as fixing_checks
from verify_r4 import sb, sc

OUT = ROOT / 'output/r4-original-copy/fit-trial'


def main():
    names = {n: f'a4-{n}-fit-trial-spi17.stl' for n in ['upper', 'lower']}
    for name in names.values():
        assert (OUT/name).is_file(), 'Fit-trial STL not generated yet: '+name
    info = json.loads((OUT/'trial-working.json').read_text(encoding='utf-8'))
    full = {}; trial = {}; result = {'files': {}, 'checks': {}, 'physical_fit_verified': False}
    for n in ['upper', 'lower']:
        path = OUT/names[n]
        m = trimesh.load_mesh(path)
        assert m.is_watertight and m.is_winding_consistent and len(m.split()) == 1, n
        original_minimum = info['files'][n]['assembly_minimum_mm']
        assert np.min(m.bounds[0]) > -.01
        m.apply_translation(original_minimum)
        assembly = trimesh.load_mesh(OUT/f'a4-{n}-fit-trial-assembly.stl')
        assert np.max(np.abs(m.bounds-assembly.bounds)) < .02
        assert abs(m.volume-assembly.volume)/assembly.volume < .001
        trial[n] = solid(m)
        full[n] = solid(trimesh.load_mesh(OUT.parent/f'a4-{n}-r4-assembly.stl'))
        result['files'][n] = dict(name=path.name, bytes=path.stat().st_size,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(), watertight=True,
            connected_solids=1, volume_mm3=float(m.volume), extents_mm=m.extents.tolist(),
            full_case_volume_fraction=trial[n].volume()/full[n].volume())
    ratio = sum(s.volume() for s in trial.values())/sum(s.volume() for s in full.values())
    result['solid_material_reduction_fraction'] = 1-ratio
    assert ratio < .8, ratio
    assert result['files']['lower']['full_case_volume_fraction'] < .55
    result['checks']['pcb_fixings'] = fixing_checks(trial['upper'], trial['lower'])

    # Actual support/locating rings remain at all five PCB hole axes.
    rows = {}
    for h in D['mountingHoles']:
        ring = cyl(h['x'],h['y'],3.2,2.1,2.65)-cyl(h['x'],h['y'],2.85,2.09,2.66)
        rows[h['ref']] = (ring ^ trial['lower']).volume()/ring.volume()
        assert rows[h['ref']] > .985, (h['ref'], rows[h['ref']])
    result['checks']['pcb_support_ring_fractions'] = rows
    result['checks']['screen_bosses'] = []
    for u in [3,78.2]:
        for v in [3,48]:
            bearing = sc(u,v,2.45,-4.7,-4.2)-sc(u,v,.9,-4.71,-4.19)
            pilot = sc(u,v,.74,-4.75,-1.3)
            closed = sc(u,v,.5,-1.1,-.55)
            row = dict(u=u,v=v,bearing_fraction=(bearing ^ trial['upper']).volume()/bearing.volume(),
                       pilot_obstruction_mm3=(pilot ^ trial['upper']).volume(),
                       blind_front_fraction=(closed ^ trial['upper']).volume()/closed.volume())
            assert row['bearing_fraction'] > .985 and row['pilot_obstruction_mm3'] < .02 and row['blind_front_fraction'] > .985, row
            result['checks']['screen_bosses'].append(row)

    import manifold3d as mf
    def box(a,b):
        return mf.Manifold.cube((np.array(b)-a).tolist()).translate(a)
    regions = {
        'complete_controls_and_audio_roof': ('upper',box([-20,-90,-10],[90,-30,80])),
        'upper_spi_chamber': ('upper',sb(-3,10,13,38,-40,-6)),
        'lower_spi_chamber': ('lower',sb(-3,10,13,38,-40,-6)),
        'upper_dual_usb': ('upper',box([-12,-30.5,12.5],[9,1.5,26.5])),
        'lower_dual_usb': ('lower',box([-12,-30.5,12.5],[9,1.5,26.5])),
        'active_window_rim': ('upper',sb(5.6,69.2,.9,50.1,-1.7,.5)),
    }
    preserved = {}
    for label,(part,region) in regions.items():
        original = full[part] ^ region
        removed = (original-trial[part]).volume()
        fraction = removed/max(original.volume(),1)
        assert removed < .03 or fraction < .001, (label, removed, fraction)
        preserved[label] = dict(original_volume_mm3=original.volume(),removed_volume_mm3=removed,
                                retained_fraction=1-fraction)
    result['checks']['retained_interfaces'] = preserved
    hardware = {
        'lcd':sb(0,81.2,0,51,-6.4,-4.8),
        'glass':sb(6.0002,75.1982,.5,50.5,-4.8,-.6),
        'installed_spi':sb(.2,3.8,14.3,36.7,-23.4,-6.3),
        'carrier':board(),
    }
    for ref in ['U2','U3']:
        p = next(c for c in D['components'] if c['ref']==ref)
        z = P['pcb_bottom_z']+4.1
        hardware[ref] = cyl(46,42.1,7,z,z+5.1) if ref=='U3' else pcb_box(p['envelope'],z,z+5.1)
    contacts = {}
    for name,body in hardware.items():
        for part,s in trial.items():
            v = (body ^ s).volume(); assert v < .025, (name,part,v)
            contacts[name+'_'+part+'_mm3'] = v
    result['checks']['hardware_overlaps'] = contacts
    result['limitations'] = [
        'Same nominal interfaces as SPI17; actual solder heights and cable bending remain unverified.',
        'The conservative original-control stem model still has a small extreme-position overlap; verify physically.',
        'Open inspection windows are intentional. Trial rigidity and acoustics do not represent the closed final enclosure.',
        'Material reduction counts solid volumes only; slicer supports, brim and print time are not measured.',
    ]
    (OUT/'trial-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
