"""Verify the complete delivered pair, rather than only Fusion viewport bodies."""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import trimesh
import manifold3d as mf

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from build_enclosure import solid,board,D,P,pcb_box,cyl
from verify_fixings import checks as fixing_checks,cylinder,HOLES
from verify_mount_access_and_controls import inner_section,samples,nearest
import verify_speaker_slot


def box(a,b):return mf.Manifold.cube((np.array(b)-a).tolist()).translate(a)


def main():
    out=ROOT/'output/r4-original-copy/full-r4.4'
    w=json.loads((out/'working-full.json').read_text())
    meshes={};solids={};files={}
    for label in ['upper','lower']:
        meta=w['exports'][label];path=out/meta['file'];m=trimesh.load_mesh(path)
        assert m.is_watertight and m.is_winding_consistent and len(m.split())==1,(label,'mesh integrity')
        m.apply_translation(meta['assembly_minimum_mm'])
        assembly=trimesh.load_mesh(out/f'{label}-assembly.stl')
        assert np.max(np.abs(m.bounds-assembly.bounds))<.001,(label,'normalization')
        meshes[label]=m;solids[label]=solid(m)
        files[label]={'file':path.name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'watertight':True,'connected_solids':1,'extents_mm':m.extents.tolist()}
    upper,lower=solids['upper'],solids['lower']
    old_upper=solid(trimesh.load_mesh(out/'baseline-upper-assembly.stl'))
    old_lower=solid(trimesh.load_mesh(out.parent/'speaker-slot/baseline-lower-assembly.stl'))
    region=box([74.87495,-64.19864,16.45525253169416],[76.19,-49.89106,20.])
    removed=old_upper-upper;added=upper-old_upper
    rim={'remaining_material_above_flat_deck_mm3':(upper^region).volume(),
        'removed_volume_mm3':removed.volume(),'added_volume_mm3':added.volume(),
        'removed_outside_repair_region_mm3':(removed-region).volume(),
        'added_outside_repair_region_mm3':(added-region).volume()}
    assert rim['remaining_material_above_flat_deck_mm3']<.01,rim
    assert .1<rim['removed_volume_mm3']<.5,rim
    assert rim['added_volume_mm3']<.025 and rim['removed_outside_repair_region_mm3']<.025,rim
    joint=((upper^lower)-(old_upper^old_lower)).volume();assert joint<.025,joint
    O=w['screen_origin_mm']
    def screen(a):return a.rotate([45,0,0]).translate(O)
    def sc(u,v,r,n0,n1):return screen(mf.Manifold.cylinder(n1-n0,r,circular_segments=96).translate([u,v,n0]))
    lcd=screen(mf.Manifold.cube([81.2,51,1.6]).translate([0,0,-6.4]))
    hardware={'carrier':board(),'lcd_pcb':lcd,
              'spi':screen(mf.Manifold.cube([3.6,22.4,17.1]).translate([.2,14.3,-23.4]))}
    for ref in ['U1','U2','U3']:
        part=next(c for c in D['components'] if c['ref']==ref);z=P['pcb_bottom_z']+P['module_board_bottom_by_ref'][ref]
        hardware[ref]=cyl(46,42.1,7,z,z+5.1) if ref=='U3' else pcb_box(part['envelope'],z,z+5.1)
    overlaps={ref:{label:(h^s).volume() for label,s in solids.items()} for ref,h in hardware.items()}
    assert all(v<.025 for row in overlaps.values() for v in row.values()),overlaps
    drivers=[]
    for u in [3,78.2]:
        for v in [3,48]:
            row={'u':u,'v':v,'driver_obstruction_mm3':(sc(u,v,2.25,-65,-6.45)^upper).volume(),
                 'head_obstruction_mm3':(sc(u,v,1.95,-8,-6.4)^(upper+lower)).volume()}
            assert row['driver_obstruction_mm3']<.025 and row['head_obstruction_mm3']<.025,row
            drivers.append(row)
    # Establish actual pilot depth and surrounding boss material for the
    # user's M2.5 thread / L4 / OD3.5 heat-set inserts, distinct from LCD M2.
    inserts={}
    for ref in ['H3','H4']:
        h=HOLES[ref];bore=cylinder(h,1.55,4.7,8.65)
        wall=cylinder(h,3.1,4.7,8.65)-cylinder(h,1.7,4.69,8.66)
        end=cylinder(h,1.5,8.9,9.2)-cylinder(h,1.4,8.89,9.21)
        inserts[ref]={'pilot_obstruction_mm3':(upper^bore).volume(),
            'boss_wall_fraction':(upper^wall).volume()/wall.volume(),
            'pilot_end_shoulder_fraction':(upper^end).volume()/end.volume()}
        assert inserts[ref]['pilot_obstruction_mm3']<.025 and inserts[ref]['boss_wall_fraction']>.995,inserts[ref]
    vectors=json.loads((out.parent/'lettering-preview/lettering-options.json').read_text())['joystick']
    word=mf.CrossSection.batch_boolean([mf.CrossSection(c,mf.FillRule.NonZero) for c in vectors['components']],mf.OpType.Add).translate(w['lettering']['offset_uv_mm'])
    empty=screen(mf.Manifold.extrude(word,.3).translate([0,0,-.4]))
    floor=screen(mf.Manifold.extrude(word,1.25).translate([0,0,-1.78]))
    logo={'groove_obstruction_mm3':(empty^upper).volume(),'floor_1p25mm_fraction':(floor^upper).volume()/floor.volume()}
    assert logo['groove_obstruction_mm3']<.025 and logo['floor_1p25mm_fraction']>.995,logo
    source=trimesh.load_mesh(out.parent/'native-original-upper.stl');controls=[]
    for z in [11.5,13.5,15.8]:
        a=inner_section(source,z);b=inner_section(meshes['upper'],z)
        row={'z':z,'max_profile_difference_mm':max(nearest(samples(a),b),nearest(samples(b),a))}
        assert row['max_profile_difference_mm']<.05,row
        controls.append(row)
    # Reuse the detailed port, wall and 54-bore tests on the actual final files.
    spec=dict(w,export=w['exports']['lower'],
              speaker_baseline_lower_assembly=str(out.parent/'speaker-slot/baseline-lower-assembly.stl'))
    verify_speaker_slot.OUT=out
    (out/'working-speaker.json').write_text(json.dumps(spec,indent=2))
    verify_speaker_slot.main()
    report={'revision':w['revision'],'physical_fit_verified':False,'files':files,'rim_cleanup':rim,
        'new_case_pair_interference_mm3':joint,'hardware_overlaps_mm3':overlaps,'lcd_screw_access':drivers,
        'heat_set_insert':{'thread':'M2.5','insert_length_mm':4,'insert_od_mm':3.5,
                           'pilot_diameter_mm':3.2,'pilot_depth_mm':4.4,'boss_diameter_mm':6.4,'checks':inserts},
        'lettering':logo,'pcb_fixings':fixing_checks(upper,lower),'original_key_profiles':controls,
        'motion_note':'Upper changes only remove material; original accepted ball-to-key limitation remains.'}
    (out/'full-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
