"""A4 engineering fit draft, derived from the original wedge STEP (mm).

Physical axes: X = PCB X, Y = -PCB drawing Y, Z up. Original geometry is
rotated, never mirrored. Read README.md and fit-report.json before printing.
"""
from pathlib import Path
import hashlib
import json
import math
import numpy as np
import trimesh
import manifold3d as mf
from explore_geometry import ROOT, OUT, load, render
OUT=ROOT/'output/r1-low-audio'
OUT.mkdir(parents=True,exist_ok=True)

D=json.loads((ROOT/'../s3-carrier/output/design.json').read_text(encoding='utf-8'))
REQ=json.loads((ROOT/'requirements.json').read_text(encoding='utf-8'))
P={
    'pcb_bottom_z':2.70525253169416,
    'support_radius':3.4,
    'locator_diameter':2.6,
    'locator_height':.8,
    'insert_bore_diameter':3.6,
    'insert_bore_depth':3.5,
    'screw_head_diameter':5.5,
    'screen_front_raise_normal':2.4,
    'screen_shift_up_plane':8.8,
    'screen_mount_post_height':6.0,
    'screen_face_to_pcb_front':4.2,
    'screen_pcb_thickness':1.6,
    'screen_pcb_fit_clearance_per_side':.4,
    'screen_bezel_thickness':2.4,
    'screen_collar_rear_depth':11.0,
    'screen_screw_pilot_diameter':1.6,
    'screen_screw_pilot_depth':5.4,
    'screen_screw_nominal_length':6.0,
    'screen_connector_rear_allowance':16,
    'mic_inlet_diameter':2.4,
    'required_adhesive_feet_height':2.0,
    'module_to_shell_clearance':2,
    'assumed_module_board_bottom_above_carrier':12.6,
    'module_board_bottom_by_ref':{'U1':12.6,'U2':4.1,'U3':4.1},
    'assumed_module_board_thickness':1.6,
    'assumed_module_electronics_above_board':3.5,
    'dual_usb_y_range':[1,30],
    'dual_usb_z_range':[14.5,24.5],
}
PARAMS=ROOT/'parameters.json'
if PARAMS.exists():P.update(json.loads(PARAMS.read_text(encoding='utf-8')))
else:PARAMS.write_text(json.dumps(P,indent=2)+'\n',encoding='utf-8')

def solid(m):
    raw=mf.Mesh(vert_properties=np.asarray(m.vertices,dtype=np.float32),tri_verts=np.asarray(m.faces,dtype=np.uint32),tolerance=.001)
    raw.merge()
    s=mf.Manifold(raw)
    assert s.status()==mf.Error.NoError,s.status()
    return s

def mesh(s):
    assert s.status()==mf.Error.NoError,s.status()
    raw=s.to_mesh()
    return trimesh.Trimesh(np.asarray(raw.vert_properties[:,:3]),np.asarray(raw.tri_verts),process=True)

def box(x0,x1,y0,y1,z0,z1):
    return mf.Manifold.cube([x1-x0,y1-y0,z1-z0]).translate([x0,y0,z0])

def pcb_box(e,z0,z1,margin=0):
    x0,y0,x1,y1=e
    return box(x0-margin,x1+margin,-y1-margin,-y0+margin,z0,z1)

def cyl(x,y,r,z0,z1):
    return mf.Manifold.cylinder(z1-z0,r,circular_segments=64).translate([x,-y,z0])

def combine(items):return mf.Manifold.batch_boolean(items,mf.OpType.Add)
def subtract(a,items):return mf.Manifold.batch_boolean([a,*items],mf.OpType.Subtract)

# Screen-local axes U horizontal, V bottom-to-top, N towards viewer/up.
q=math.sqrt(.5)
O=np.array([-4.47505,-39,21.153]) + np.array([0,-q,q])*P['screen_front_raise_normal']
O+=np.array([0,q,q])*P['screen_shift_up_plane']
def screen(s):
    return s.rotate([45,0,0]).translate(O.tolist())

def sbox(u0,u1,v0,v1,n0,n1):return screen(box(u0,u1,v0,v1,n0,n1))

def rounded_screen_plate(u0,u1,v0,v1,n0,n1,r):
    section=mf.CrossSection.square([u1-u0-2*r,v1-v0-2*r],center=True).offset(r,circular_segments=64)
    return screen(mf.Manifold.extrude(section,n1-n0).translate([(u0+u1)/2,(v0+v1)/2,n0]))

def export(s,name,print_rotation=None):
    m=mesh(s)
    checks={'watertight':bool(m.is_watertight),'consistent_winding':bool(m.is_winding_consistent),'connected_parts':len(s.decompose()),'volume_mm3':round(s.volume(),3),'size_mm':np.round(m.extents,4).tolist(),'triangles':len(m.faces)}
    assert checks['watertight'] and checks['consistent_winding'] and checks['connected_parts']==1 and checks['volume_mm3']>0,(name,checks)
    m.export(OUT/f'{name}-assembly.stl')
    ready=m.copy()
    if print_rotation is not None:ready.apply_transform(trimesh.transformations.rotation_matrix(math.radians(print_rotation),[1,0,0]))
    ready.apply_translation(-ready.bounds[0])
    ready.export(OUT/f'{name}-print.stl')
    reload=trimesh.load_mesh(OUT/f'{name}-print.stl')
    assert reload.is_watertight and reload.is_winding_consistent
    checks['print_size_mm']=np.round(reload.extents,4).tolist()
    checks['sha256']=hashlib.sha256((OUT/f'{name}-print.stl').read_bytes()).hexdigest()
    return m,checks

def board():
    todo=list(D['outline']);edge=todo.pop(0);points=[];cur=edge['start']
    while True:
        a,b=edge['start'],edge['end'];angle=edge['angle']
        if math.dist(cur,a)>.002:a,b=b,a;angle=-angle
        points.append([a[0],-a[1]])
        if angle:
            t=math.radians(angle);sx,sy=a;ex,ey=b
            cx=(sx+ex)/2-(ey-sy)/(2*math.tan(t/2));cy=(sy+ey)/2+(ex-sx)/(2*math.tan(t/2))
            for f in np.linspace(0,1,24)[1:]:points.append([cx+(sx-cx)*math.cos(t*f)-(sy-cy)*math.sin(t*f),-(cy+(sx-cx)*math.sin(t*f)+(sy-cy)*math.cos(t*f))])
        cur=b
        if not todo:break
        index=next(i for i,e in enumerate(todo) if min(math.dist(cur,e['start']),math.dist(cur,e['end']))<.002)
        edge=todo.pop(index)
    pcb=mf.Manifold.extrude(mf.CrossSection([points],mf.FillRule.EvenOdd),1.6).translate([0,0,P['pcb_bottom_z']])
    for h in D['mountingHoles']:pcb=pcb-cyl(h['x'],h['y'],h['diameter']/2,P['pcb_bottom_z']-.1,P['pcb_bottom_z']+1.7)
    for c in D['components']:
        for h in c.get('holes',[]):
            diameter=h.get('diameter',h.get('drill',0))
            if diameter:pcb=pcb-cyl(h['x'],h['y'],diameter/2,P['pcb_bottom_z']-.1,P['pcb_bottom_z']+1.7)
    return pcb

def main():
    lower0=solid(load(1));upper0=solid(load(0))
    lower=lower0
    holes={h['ref']:h for h in D['mountingHoles']}
    # Preserve the floor, replace H1/H3/H4 with round, exactly coaxial supports.
    for ref in ['H1','H3','H4']:
        h=holes[ref];x,y=h['x'],h['y']
        lower=lower-cyl(x,y,4.9,-.2946,6)
        boss=cyl(x,y,P['support_radius'],-.5,P['pcb_bottom_z'])
        if ref=='H1':
            boss=boss+cyl(x,y,P['locator_diameter']/2,P['pcb_bottom_z']-.01,P['pcb_bottom_z']+P['locator_height'])
        else:
            # Blind insert pilot; actual insert OD is a user-measured parameter.
            boss=boss-cyl(x,y,P['insert_bore_diameter']/2,P['pcb_bottom_z']-P['insert_bore_depth'],P['pcb_bottom_z']+.1)
        lower=lower+boss
    # Existing H2/H5 are plastic supports only; keep their tips below PCB top.
    for ref in ['H2','H5']:
        h=holes[ref]
        lower=lower-cyl(h['x'],h['y'],1.45,P['pcb_bottom_z']+P['locator_height'],6)

    usb=pcb_box([-10,P['dual_usb_y_range'][0],7,P['dual_usb_y_range'][1]],*P['dual_usb_z_range'])
    lower=lower-usb;upper=upper0-usb

    # Replace original screen screw pattern with a raised, fitted bezel.
    clear=P['screen_pcb_fit_clearance_per_side']
    # Clear the obsolete original LCD mounting pillars all the way to the rear.
    body_clear=sbox(-clear,81.2+clear,-clear,51+clear,-40,3)
    upper=upper-body_clear
    lower=lower-sbox(-clear,81.2+clear,-clear,51+clear,-8.2,-1.5)
    collar=rounded_screen_plate(-2.4,83.6,-3,54,-P['screen_collar_rear_depth'],2.4,6)
    # Rear clearance accepts full PCB body. The front lip reveals active area.
    collar=collar-sbox(-clear,81.2+clear,-clear,51+clear,-P['screen_collar_rear_depth']-.1,0)
    collar=collar-sbox(8.6,66.2,3.9,47.1,-.1,2.5)
    # Four bosses: exact 75.2 x 45 screen-hole pitch.
    pilots=[]
    for u in [3,78.2]:
        for v in [3,48]:
            post=mf.Manifold.cylinder(P['screen_mount_post_height']+.6,3.1,circular_segments=48).translate([u,v,-P['screen_mount_post_height']])
            collar=collar+screen(post)
            pilots.append(screen(mf.Manifold.cylinder(P['screen_screw_pilot_depth'],P['screen_screw_pilot_diameter']/2,circular_segments=48).translate([u,v,-P['screen_mount_post_height']-.01])))
    collar=subtract(collar,pilots)
    upper=upper+collar
    # Close the obsolete display opening below the relocated bezel. This
    # shallow transition hides all PCB/old mounting features from the front.
    transition_section=mf.CrossSection([[[-38,28.8],[-42.5,20.2],[-42.5,17.8],[-38,26.4]]],mf.FillRule.EvenOdd)
    transition=mf.Manifold.extrude(transition_section,80).transform([[0,0,1,-4],[1,0,0,0],[0,1,0,0]])
    upper=upper+transition

    # Left-hand SPI pins: connector body and a bending chamber behind the LCD.
    screen_rear=-P['screen_mount_post_height']-P['screen_pcb_thickness']
    connector_clear=sbox(-2,6,14.3,36.7,screen_rear-P['screen_connector_rear_allowance'],screen_rear+.1)
    upper=upper-connector_clear;lower=lower-connector_clear

    # Existing soldered modules stay at current-style socket heights in R1.
    # These are explicit envelope assumptions, not measured components.
    envelopes={}
    cuts=[]
    for ref in ['U1','U2','U3']:
        zmod=P['pcb_bottom_z']+P['module_board_bottom_by_ref'].get(ref,P['assumed_module_board_bottom_above_carrier'])
        zmax=zmod+P['assumed_module_board_thickness']+P['assumed_module_electronics_above_board']
        c=next(c for c in D['components'] if c['ref']==ref)
        e=c['envelope']
        nominal=pcb_box(e,zmod,zmax)
        envelopes[ref]=nominal
        cuts.append(pcb_box(e,P['pcb_bottom_z']+1.7,zmax+P['module_to_shell_clearance'],margin=1))
    j=next(e for e in D['connectorMatingEnvelopes'] if e['ref']=='J1')['envelope']
    cuts.append(pcb_box(j,P['pcb_bottom_z']+1.6,P['pcb_bottom_z']+20.3,margin=1))
    upper=subtract(upper,cuts)

    # Acoustic entry aligned to the existing PCB microphone via-hole.
    lower=lower-cyl(46,42.1,P['mic_inlet_diameter']/2,-3,0)
    acoustic_ring=cyl(46,42.1,2.5,-.5,P['pcb_bottom_z']-.3)-cyl(46,42.1,P['mic_inlet_diameter']/2,-.6,P['pcb_bottom_z'])
    lower=lower+acoustic_ring
    # Relieve the original key wells for a conservative 4 mm press. The carrier
    # locates the switches; the shell must not act as an unintended travel stop.
    key_reliefs=[]
    for i in [2,3,4]:
        key=solid(load(i));center=mesh(key).bounds.mean(axis=0)
        relief=key.translate((-center).tolist()).scale([1.025,1.025,1]).translate(center.tolist()).translate([0,0,-4])
        key_reliefs.extend([relief,key.translate([0,0,-4])])
    upper=subtract(upper,key_reliefs)
    # Remove tiny tessellation slivers at the inherited upper/lower seam.
    upper=upper-lower
    lower_fragments=sorted(lower.decompose(),key=lambda s:s.volume(),reverse=True)
    lower_usb_roof_removed=0
    for fragment in lower_fragments[1:]:
        bounds=mesh(fragment).bounds
        assert bounds[1,0]<0 and bounds[0,2]>=24.4 and fragment.volume()<25, bounds
        lower_usb_roof_removed+=fragment.volume()
    lower=lower_fragments[0]
    fragments=sorted(upper.decompose(),key=lambda s:s.volume(),reverse=True)
    print('Upper connected fragments:',[(round(s.volume(),8),np.round(mesh(s).bounds,3).tolist()) for s in fragments],flush=True)
    print('Lower connected fragments:',[(round(s.volume(),8),np.round(mesh(s).bounds,3).tolist()) for s in lower.decompose()],flush=True)
    discarded_volume=sum(s.volume() for s in fragments[1:])
    if len(fragments)>1 and discarded_volume<1:
        upper=fragments[0]

    OUT.mkdir(exist_ok=True)
    report={
        'revision':'A4-enclosure-R1','status':'engineering-fit-draft','fabricationApproved':False,
        'pcbModified':False,'screenBodyFromUserDrawing':True,
        'originalStepSha256':hashlib.sha256((ROOT/'reference/original-assembly.STEP').read_bytes()).hexdigest(),
        'pcbDesignSha256':hashlib.sha256((ROOT/'../s3-carrier/output/design.json').read_bytes()).hexdigest(),
        'coordinateTransform':'Proper rotation: X=STEP.X+36.12495; Y=-STEP.Z-43.69864; Z=STEP.Y+16.45525253',
        'originalWidthMm':88.5,'screenAngleDeg':45,
        'discarded_boolean_sliver_volume_mm3':discarded_volume,
        'removed_detached_usb_roof_mm3':lower_usb_roof_removed,
        'parameters':P,'fixings':{r:holes[r] for r in ['H1','H3','H4']},
        'leftH1':'plastic short locating pin; no metal screw',
        'centerH3':'round screw boss, coaxial to original 3 mm PCB hole',
        'rightH4':'round screw boss',
        'closedTransitionBelowScreen':True,
        'audioInstallation':'R1 assumes U2/U3 female sockets removed; keep 2.5 mm male header spacer height above carrier top. U1 keeps original female sockets.',
        'meshes':{},'checks':{},'unverified':REQ['unresolved']
    }
    lm,report['meshes']['lower']=export(lower,'a4-lower-r1')
    um,report['meshes']['upper']=export(upper,'a4-upper-r1',135)
    coupon=lower ^ pcb_box([3,30,67,42],-3,6)
    cm,report['meshes']['support_coupon']=export(coupon,'support-coupon-r1')
    m2coupon=box(-6,6,-6,6,0,2.4)+mf.Manifold.cylinder(6.1,3.1,circular_segments=64).translate([0,0,2.3])
    m2coupon=m2coupon-mf.Manifold.cylinder(P['screen_screw_pilot_depth'],P['screen_screw_pilot_diameter']/2,circular_segments=64).translate([0,0,8.41-P['screen_screw_pilot_depth']])
    _,report['meshes']['m2_boss_coupon']=export(m2coupon,'m2-boss-coupon-r1')
    pcb=board()
    # Checking the actual booleans, not scalar parameter values alone.
    report['checks']['pcb_to_lower_overlap_mm3']=(pcb^lower).volume()
    report['checks']['pcb_to_upper_overlap_mm3']=(pcb^upper).volume()
    report['checks']['upper_lower_overlap_mm3']=(upper^lower).volume()
    report['checks']['module_to_upper_overlap_mm3']={r:(s^upper).volume() for r,s in envelopes.items()}
    lcd=sbox(0,81.2,0,51,screen_rear,-P['screen_mount_post_height'])
    report['checks']['screen_pcb_to_upper_overlap_mm3']=(lcd^upper).volume()
    report['checks']['screen_pcb_to_lower_overlap_mm3']=(lcd^lower).volume()
    report['checks']['screen_pcb_to_modules_overlap_mm3']={r:(lcd^s).volume() for r,s in envelopes.items()}
    report['checks']['screen_pcb_to_module_min_gap_mm']={r:round(lcd.min_gap(s,10),3) for r,s in envelopes.items()}
    report['checks']['left_spi_chamber_to_shell_overlap_mm3']=((upper+lower)^connector_clear).volume()
    report['checks']['left_spi_chamber_to_devkit_min_gap_mm']=round(connector_clear.min_gap(envelopes['U1'],10),3)
    # Head clearance to the connector uses its full body, not pin-center distance.
    h=holes['H3'];head=cyl(h['x'],h['y'],P['screw_head_diameter']/2,P['pcb_bottom_z']+1.6,P['pcb_bottom_z']+4.1)
    report['checks']['h3_head_to_j1_overlap_mm3']=(head^pcb_box(j,P['pcb_bottom_z']+1.6,P['pcb_bottom_z']+20.3)).volume()
    report['checks']['locator_tip_below_pcb_top_mm']=1.6-P['locator_height']
    report['checks']['h1_radial_pin_to_pcb_hole_clearance_mm']=(holes['H1']['diameter']-P['locator_diameter'])/2
    report['checks']['nominal_modules_measured']=False
    report['checks']['speaker_fit_checked']=False
    report['checks']['physical_fit_checked']=False
    report['checks']['neutral_printed_cap_to_upper_overlap_mm3']={str(i):(solid(load(i))^upper).volume() for i in range(2,7)}
    report['checks']['key_press_travel_assumed_mm']=4
    report['checks']['key_press_samples_to_shell_overlap_mm3']={str(i):[round((solid(load(i)).translate([0,0,-d])^upper).volume(),6) for d in [0,1,2,3,4]] for i in [2,3,4]}
    report['checks']['key_press_samples_to_modules_overlap_mm3']={str(i):[round((solid(load(i)).translate([0,0,-d])^combine(list(envelopes.values()))).volume(),6) for d in [0,1,2,3,4]] for i in [2,3,4]}
    report['microphone']={'pcb_center':[46,42.1],'external_location':'base underside, coaxial with PCB sound hole','inlet_diameter_mm':P['mic_inlet_diameter'],'required_feet_height_mm':P['required_adhesive_feet_height'],'gasket_and_acoustics_verified':False}
    print(json.dumps(report['checks'],indent=2),flush=True)
    (OUT/'fit-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    for key in ['pcb_to_lower_overlap_mm3','pcb_to_upper_overlap_mm3','upper_lower_overlap_mm3','screen_pcb_to_upper_overlap_mm3','screen_pcb_to_lower_overlap_mm3','left_spi_chamber_to_shell_overlap_mm3','h3_head_to_j1_overlap_mm3']:
        assert report['checks'][key]<.02,(key,report['checks'][key])
    assert all(v<.02 for v in report['checks']['module_to_upper_overlap_mm3'].values())
    assert all(v<.02 for v in report['checks']['screen_pcb_to_modules_overlap_mm3'].values())
    assert all(v>=P['module_to_shell_clearance'] for v in report['checks']['screen_pcb_to_module_min_gap_mm'].values()),report['checks']['screen_pcb_to_module_min_gap_mm']
    assert report['checks']['left_spi_chamber_to_devkit_min_gap_mm']>=2
    assert all(v<.02 for v in report['checks']['neutral_printed_cap_to_upper_overlap_mm3'].values())
    assert all(v<.02 for values in report['checks']['key_press_samples_to_shell_overlap_mm3'].values() for v in values),report['checks']['key_press_samples_to_shell_overlap_mm3']
    assert all(v<.02 for values in report['checks']['key_press_samples_to_modules_overlap_mm3'].values() for v in values)
    (OUT/'fit-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')

    # Native CAD geometry previews, including deliberately visible assumptions.
    parts=[(lm,(.80,.81,.79)),(um,(.94,.94,.91))]
    caps=[(load(i),(.97,.35,.075)) for i in [2,3,4,5,6]]+[(load(7),(.94,.94,.91))]
    glass_n=P['screen_face_to_pcb_front']-P['screen_mount_post_height']
    # Inactive black glass extends behind the aperture, as in the user's BL drawing.
    glass=sbox(6.0002,75.1982,.5,50.5,glass_n-.05,glass_n)
    render(parts+[(mesh(glass),(.045,.09,.12))]+caps,OUT/'a4-enclosure-r1.png',camera=(145,-190,125))
    render([(lm,(.2,.23,.27)),(mesh(pcb),(.035,.30,.19))]+[(mesh(s),(.25,.2,.35)) for s in envelopes.values()],OUT/'a4-lower-layout-r1.png',camera=(-95,-155,180))
    render([(lm,(.23,.26,.3))],OUT/'a4-lower-supports-r1.png',camera=(115,-145,170))
    render([(cm,(.65,.67,.7))],OUT/'support-coupon-r1.png')
    print(json.dumps({'meshes':report['meshes'],'checks':report['checks']},indent=2))

if __name__=='__main__':main()
