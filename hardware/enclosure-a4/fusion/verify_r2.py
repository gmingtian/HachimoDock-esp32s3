import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import trimesh
import numpy as np
from build_enclosure import ROOT,P,D,board,solid,mesh,pcb_box,sbox,cyl
from explore_geometry import load
from verify_fixings import checks as fixing_checks

OUT=ROOT/'output/r2-fusion'
def main():
    upper_mesh=trimesh.load_mesh(OUT/'a4-upper-r2-assembly.stl')
    lower_mesh=trimesh.load_mesh(OUT/'a4-lower-r2-assembly.stl')
    upper=solid(upper_mesh);lower=solid(lower_mesh)
    report={'revision':'R2-Fusion','physical_fit_verified':False,'audio_installation':'U2/U3 female sockets removed; retain 2.5 mm male spacer; U1 original socket','meshes':{},'fixings':fixing_checks(upper,lower),'checks':{}}
    for label,m in [('upper',upper_mesh),('lower',lower_mesh)]:
        row=dict(watertight=bool(m.is_watertight),winding=bool(m.is_winding_consistent),parts=len(m.split()),volume_mm3=float(m.volume),extents_mm=m.extents.tolist())
        assert row['watertight'] and row['winding'] and row['parts']==1 and row['volume_mm3']>0,row
        report['meshes'][label]=row
    c=report['checks'];pcb=board()
    c['pcb_upper_overlap_mm3']=(pcb^upper).volume();c['pcb_lower_overlap_mm3']=(pcb^lower).volume()
    c['shell_overlap_mm3']=(upper^lower).volume()
    native_seam=json.loads((OUT/'native-seam-check.json').read_text(encoding='utf-8'))
    c['native_shell_overlap_mm3']=native_seam['intersection_mm3']
    assert c['native_shell_overlap_mm3']<1e-6,native_seam
    # Independently tessellated mating curves can enclose tiny slivers; retain
    # their measured volume, bounded to 0.1 mm3, and require exact native zero.
    assert c['shell_overlap_mm3']<.1,c['shell_overlap_mm3']
    modules={}
    for ref in ['U1','U2','U3']:
        part=next(v for v in D['components'] if v['ref']==ref)
        z=P['pcb_bottom_z']+P['module_board_bottom_by_ref'][ref]
        modules[ref]=cyl(46,42.1,7,z,z+5.1) if ref=='U3' else pcb_box(part['envelope'],z,z+5.1)
        c[ref+'_upper_overlap_mm3']=(modules[ref]^upper).volume()
    report['microphone_geometry']='Round INMP441 / 14mm: source PCB footprint title and user photograph; circular module envelope'
    lcd=sbox(0,81.2,0,51,-7.6,-6)
    c['lcd_upper_overlap_mm3']=(lcd^upper).volume();c['lcd_lower_overlap_mm3']=(lcd^lower).volume()
    c['lcd_module_gaps_mm']={r:lcd.min_gap(m,10) for r,m in modules.items()}
    spi=sbox(-2,6,14.3,36.7,-23.6,-7.5)
    c['spi_shell_overlap_mm3']=((upper+lower)^spi).volume()
    c['spi_u1_gap_mm']=spi.min_gap(modules['U1'],10)
    c['key_shell_overlap_mm3']={str(i):[(solid(load(i)).translate([0,0,-z])^upper).volume() for z in [0,1,2,3,4]] for i in [2,3,4]}
    # All four raised screen bosses must have a blind pilot and full bearing.
    import manifold3d as mf
    from build_enclosure import screen
    c['screen_bosses']=[]
    c['screen_corner_wall_fractions']=[]
    for u in [-.9,82.1]:
        for v in [-.9,51.9]:
            probe=sbox(u-.1,u+.1,v-.1,v+.1,-5,-2)
            fraction=(probe^upper).volume()/probe.volume()
            c['screen_corner_wall_fractions'].append(fraction)
            assert fraction>.985,('screen corner wall missing',u,v,fraction)
    for u in [3,78.2]:
        for v in [3,48]:
            hole=screen(mf.Manifold.cylinder(5.15,.74,circular_segments=64).translate([u,v,-5.95]))
            ring=screen((mf.Manifold.cylinder(.5,2.8,circular_segments=64)-mf.Manifold.cylinder(.5,.9,circular_segments=64)).translate([u,v,-5.95]))
            row=dict(u=u,v=v,hole_overlap_mm3=(hole^upper).volume(),bearing_fraction=(ring^upper).volume()/ring.volume())
            c['screen_bosses'].append(row)
            assert row['hole_overlap_mm3']<.02 and row['bearing_fraction']>.985,row
    c['mic_sound_route_overlap_mm3']=(cyl(46,42.1,1.1,-2.5,2.3)^lower).volume()
    for k,v in c.items():
        if k.endswith('_overlap_mm3') and k!='shell_overlap_mm3' and isinstance(v,(int,float)):assert v<.025,(k,v)
    assert all(v<.025 for vs in c['key_shell_overlap_mm3'].values() for v in vs),c['key_shell_overlap_mm3']
    assert all(v>=2 for v in c['lcd_module_gaps_mm'].values()),c['lcd_module_gaps_mm']
    assert c['spi_u1_gap_mm']>=2,c['spi_u1_gap_mm']
    report['source_step_sha256']=hashlib.sha256((ROOT/'reference/original-assembly.STEP').read_bytes()).hexdigest()
    report['pcb_design_sha256']=hashlib.sha256((ROOT/'../s3-carrier/output/design.json').read_bytes()).hexdigest()
    (OUT/'fit-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
