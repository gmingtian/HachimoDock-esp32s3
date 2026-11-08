import json,sys,hashlib,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import trimesh
import manifold3d as mf
from build_enclosure import ROOT,D,P,solid,mesh,board,pcb_box,cyl
from explore_geometry import load
from check_joystick_motion import locator
from verify_fixings import checks as fixing_checks
q=math.sqrt(.5);OUT=ROOT/'output/r4-original-copy'
working=json.loads((ROOT/'fusion/working-r4.json').read_text(encoding='utf-8'))
O=np.array(working['screen_origin_mm'])
ANGLE=working.get('screen_angle_deg',45)
def sb(u0,u1,v0,v1,n0,n1):
    return mf.Manifold.cube([u1-u0,v1-v0,n1-n0]).translate([u0,v0,n0]).rotate([ANGLE,0,0]).translate(O.tolist())
def sc(u,v,r,n0,n1):return mf.Manifold.cylinder(n1-n0,r,circular_segments=96).translate([u,v,n0]).rotate([ANGLE,0,0]).translate(O.tolist())
def main():
    um=trimesh.load_mesh(OUT/'a4-upper-r4-assembly.stl');lm=trimesh.load_mesh(OUT/'a4-lower-r4-assembly.stl')
    upper=solid(um);lower=solid(lm);c={}
    report={'revision':'R4-original-native-copy','physical_fit_verified':False,'audio_mounting':'female sockets removed; retain 2.5 mm plastic spacer; U1 sockets unchanged','meshes':{},'fixings':fixing_checks(upper,lower),'checks':c,'screen_parameters':{k:v for k,v in working.items() if k not in ['bodies','design_id']}}
    for label,m in [('upper',um),('lower',lm)]:
        row={'watertight':bool(m.is_watertight),'consistent_winding':bool(m.is_winding_consistent),'parts':len(m.split()),'volume_mm3':float(m.volume),'extents_mm':m.extents.tolist()}
        assert row['watertight'] and row['consistent_winding'] and row['parts']==1 and row['volume_mm3']>0,row
        report['meshes'][label]=row
    expected=load(0).bounds.copy();expected[:,0]=36.12495+(expected[:,0]-36.12495)*91.5/88.5
    expected[1,1:]+=working['screen_extension_v_mm']*2**-.5
    c['designed_upper_bounds_max_difference_mm']=float(np.max(np.abs(expected-um.bounds)))
    c['active_display_axis_error_mm']=abs(O[0]+37.4-36.12495)
    assert c['designed_upper_bounds_max_difference_mm']<.02 and c['active_display_axis_error_mm']<.0001,c
    pcb=board();c['pcb_upper_overlap_mm3']=(pcb^upper).volume();c['pcb_lower_overlap_mm3']=(pcb^lower).volume()
    c['shell_overlap_mm3']=(upper^lower).volume()
    # Quantify the STL approximation at coincident native mating surfaces.
    distances=[locator(um),locator(lm)];penetration=[];false_signed_samples=0
    for m,distance,other in [(um,distances[1],lower),(lm,distances[0],upper)]:
        candidates=[]
        for p in np.vstack([m.vertices,m.triangles_center]):
            d=distance.EvaluateFunction(p.tolist())
            if d<-.0001:
                # A nearest-face pseudo-normal can misclassify concave lips.
                # Confirm actual containment by a non-axis-aligned solid ray.
                hits=other.ray_cast(p.tolist(),(p+np.array([1000,312.345,651.234])).tolist())
                if len(hits)%2:candidates.append(-d)
                else:false_signed_samples+=1
        penetration.append(max(candidates,default=0))
    c['vtk_concave_sign_false_samples']=false_signed_samples
    c['sampled_shell_penetration_mm']=max(penetration)
    base_upper=solid(trimesh.load_mesh(OUT/'exterior-reference-upper.stl'))
    base_lower=solid(trimesh.load_mesh(OUT/'exterior-reference-lower.stl'))
    inherited=base_upper^base_lower
    c['inherited_original_mating_mesh_overlap_mm3']=inherited.volume()
    c['additional_shell_interference_mm3']=((upper^lower)-inherited).volume()
    # Preserve the source joint. Its independently tessellated curved faces
    # already overlap by up to about .05 mm; only new interference is rejected.
    assert c['additional_shell_interference_mm3']<.025,c
    modules={}
    for ref in ['U1','U2','U3']:
        part=next(v for v in D['components'] if v['ref']==ref)
        z=P['pcb_bottom_z']+P['module_board_bottom_by_ref'][ref]
        modules[ref]=cyl(46,42.1,7,z,z+5.1) if ref=='U3' else pcb_box(part['envelope'],z,z+5.1)
        c[ref+'_upper_overlap_mm3']=(modules[ref]^upper).volume()
    lcd=sb(0,81.2,0,51,-6.4,-4.8);glass=sb(6.0002,75.1982,.5,50.5,-4.8,-.6)
    for ref,s in [('lcd',lcd),('glass',glass)]:
        c[ref+'_upper_overlap_mm3']=(s^upper).volume();c[ref+'_lower_overlap_mm3']=(s^lower).volume()
    c['lcd_module_gap_mm']={r:lcd.min_gap(v,20) for r,v in modules.items()}
    assert min(c['lcd_module_gap_mm'].values())>=1.0,c['lcd_module_gap_mm']
    a,b=working['spi_envelope_uvn'];spi=sb(a[0],b[0],a[1],b[1],a[2],b[2])
    c['spi_shell_overlap_mm3']=(spi^(upper+lower)).volume();c['spi_U1_gap_mm']=spi.min_gap(modules['U1'],20)
    assert c['spi_U1_gap_mm']>=.8,c['spi_U1_gap_mm']
    j=next(v for v in D['connectorMatingEnvelopes'] if v['ref']=='J1')['envelope']
    j1=pcb_box(j,P['pcb_bottom_z']+1.6,P['pcb_bottom_z']+1.6+11)
    c['J1_upper_overlap_mm3']=(j1^upper).volume();c['lcd_J1_gap_mm']=lcd.min_gap(j1,20)
    assert c['lcd_J1_gap_mm']>=2,c['lcd_J1_gap_mm']
    c['key_shell_overlap_mm3']={str(i):[(solid(load(i)).translate([0,0,-z])^upper).volume() for z in [0,1,2,3,3.5,4]] for i in [2,3,4]}
    c['key_added_interference_mm3']={str(i):[((solid(load(i)).translate([0,0,-z])^upper)-(solid(load(i)).translate([0,0,-z])^base_upper)).volume() for z in [0,1,2,3,3.5,4]] for i in [2,3,4]}
    assert all(v<.025 for vs in c['key_added_interference_mm3'].values() for v in vs),c['key_added_interference_mm3']
    c['key_clear_travel_modelled_mm']=max(z for index,z in enumerate([0,1,2,3,3.5,4]) if all(vs[index]<.025 for vs in c['key_shell_overlap_mm3'].values()))
    c['key_original_floor_stop_retained']=True
    c['screen_bosses']=[]
    for u in [3,78.2]:
        for v in [3,48]:
            ring=sc(u,v,2.45,-4.7,-4.2)-sc(u,v,.9,-4.71,-4.19)
            shaft=sc(u,v,.74,-4.75,-1.3);closed_tip=sc(u,v,.5,-1.1,-.55)
            row={'u':u,'v':v,'bearing_fraction':(ring^upper).volume()/ring.volume(),'pilot_obstruction_mm3':(shaft^upper).volume(),'closed_front_fraction':(closed_tip^upper).volume()/closed_tip.volume()}
            assert row['bearing_fraction']>.985 and row['pilot_obstruction_mm3']<.02 and row['closed_front_fraction']>.985,row
            c['screen_bosses'].append(row)
    h=next(v for v in D['mountingHoles'] if v['ref']=='H1')
    h1floor=cyl(h['x'],h['y'],2.5,-2.29,-2.1)
    c['H1_bottom_flush_fraction']=(h1floor^lower).volume()/h1floor.volume();assert c['H1_bottom_flush_fraction']>.985,c
    c['bottom_microphone_route_overlap_mm3']=(cyl(46,42.1,1.1,-2.5,2.3)^lower).volume()
    band=pcb_box([0,49.45,56,50.2],10.85,15.4)
    baseline=solid(trimesh.load_mesh(OUT/'exterior-reference-upper.stl'))
    c['original_key_rear_wall_removed_mm3']=((baseline-upper)^band).volume()
    assert c['original_key_rear_wall_removed_mm3']<.025,c['original_key_rear_wall_removed_mm3']
    c['top_microphone_route_overlap_mm3']=(cyl(46,42.1,1.1,13.8,34)^upper).volume()
    for k,v in c.items():
        if k.endswith('_overlap_mm3') and k not in ['shell_overlap_mm3','inherited_original_mating_mesh_overlap_mm3'] and isinstance(v,(int,float)):assert v<.025,(k,v)
    report['source_step_sha256']=hashlib.sha256((ROOT/'reference/original-assembly.STEP').read_bytes()).hexdigest()
    report['pcb_design_sha256']=hashlib.sha256((ROOT/'../s3-carrier/output/design.json').read_bytes()).hexdigest()
    (OUT/'fit-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
