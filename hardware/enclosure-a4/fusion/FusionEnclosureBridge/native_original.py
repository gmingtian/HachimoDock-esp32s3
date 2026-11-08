"""R3: retain the original external BRep; fit the LCD behind its existing face."""
import json,math
import importlib.util
from pathlib import Path
import adsk.core as ac
import adsk.fusion as af

def build(ctx,docid,args):
    import fusion_ops as ops
    manager=af.TemporaryBRepManager.get();root=ctx['documents'][docid]['design'].rootComponent
    height_scale=1.16;floor=-2.2947474683058333
    q=math.sqrt(.5);angle=math.atan(height_scale);c=math.cos(angle);sn=math.sin(angle)
    vscale=math.sqrt((1+height_scale**2)/2);vshift=(vscale-1)*25.5
    origin=[-1.27505,-39+c*vshift,floor+(21.153-floor)*height_scale+sn*vshift]
    front=0;pcb_z=2.70525253169416;foot=pcb_z+1.6
    def p(v):return ac.Point3D.create(*[n/10 for n in v])
    def move(body,values):
        matrix=ac.Matrix3D.create();matrix.setWithArray(values)
        if not manager.transform(body,matrix):raise RuntimeError('Transform failed')
        return body
    world=[1,0,0,3.612495,0,0,-1,-4.369864,0,1,0,1.645525253169416,0,0,0,1]
    upper=move(manager.copy(ctx['bodies'][args['upper_source_id']]['body']),world)
    spec=importlib.util.spec_from_file_location('clean_profile',Path(__file__).with_name('clean_profile.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    control_source=manager.copy(upper)
    upper,exterior_limit,tongue_section,groove_section=module.envelope(manager,root,upper,origin,angle);widening_tolerance=.005
    def box(x0,x1,y0,y1,z0,z1):
        b=ac.OrientedBoundingBox3D.create(p([(x0+x1)/2,(y0+y1)/2,(z0+z1)/2]),ac.Vector3D.create(1,0,0),ac.Vector3D.create(0,1,0),(x1-x0)/10,(y1-y0)/10,(z1-z0)/10)
        return manager.createBox(b)
    def cyl(x,y,r,z0,z1):return manager.createCylinderOrCone(p([x,y,z0]),r/10,p([x,y,z1]),r/10)
    def boolean(a,b,operation):
        if not manager.booleanOperation(a,b,operation):raise RuntimeError('Native Boolean failed')
        return a
    def cut(a,b):return boolean(a,b,af.BooleanTypes.DifferenceBooleanType)
    def join(a,b):return boolean(a,b,af.BooleanTypes.UnionBooleanType)
    def internal_join(a,b):
        boolean(b,manager.copy(exterior_limit),af.BooleanTypes.IntersectionBooleanType)
        return join(a,b)
    def screen(s,original=False):
        o=[-4.47505,-39,21.153] if original else origin
        co,si=(q,q) if original else (c,sn)
        return move(s,[1,0,0,o[0]/10,0,co,-si,o[1]/10,0,si,co,o[2]/10,0,0,0,1])
    def sb(u0,u1,v0,v1,n0,n1):return screen(box(u0,u1,v0,v1,n0,n1))
    def rounded(x0,x1,y0,y1,z0,z1,r):
        s=join(box(x0+r,x1-r,y0,y1,z0,z1),box(x0,x1,y0+r,y1-r,z0,z1))
        for x in [x0+r,x1-r]:
            for y in [y0+r,y1-r]:join(s,cyl(x,y,r,z0,z1))
        return s
    def window_tool():
        sheets=[]
        for u0,u1,v0,v1,n in [(8.45,66.35,3.75,47.25,-.61),(7.7,67.1,3.0,48.0,.1)]:
            points=[p(t) for t in [(u0,v0,n),(u1,v0,n),(u1,v1,n),(u0,v1,n)]]
            curves=[ac.Line3D.create(points[i],points[(i+1)%4]) for i in range(4)]
            wire,_=manager.createWireFromCurves(curves)
            sheets.append(root.bRepBodies.add(manager.createFaceFromPlanarWires([wire])))
        input=root.features.loftFeatures.createInput(af.FeatureOperations.NewBodyFeatureOperation)
        for sheet in sheets:input.loftSections.add(sheet.faces.item(0))
        input.isSolid=True
        feature=root.features.loftFeatures.add(input);body=feature.bodies.item(0)
        tool=manager.copy(body);body.deleteMe()
        for sheet in sheets:sheet.deleteMe()
        return screen(tool)
    def pb(e,z0,z1,m=0):
        x0,y0,x1,y1=e;return box(x0-m,x1+m,-y1-m,-y0+m,z0,z1)
    lower_mask=join(box(-30,120,-100,100,-10,.95525253169416),sb(-40,130,-120,150,-150,-15.5))
    lower=boolean(manager.copy(upper),manager.copy(lower_mask),af.BooleanTypes.IntersectionBooleanType)
    cut(upper,lower_mask)
    def seam_mask(vertical,normal):
        return join(box(-30,120,-100,100,-10,vertical),sb(-40,130,-120,150,-150,normal))
    tongue_zone=cut(seam_mask(2.15525253169416,-14.3),seam_mask(.45525253169416,-16))
    groove_zone=cut(seam_mask(2.40525253169416,-14.05),seam_mask(.90525253169416,-15.55))
    boolean(tongue_section,tongue_zone,af.BooleanTypes.IntersectionBooleanType)
    boolean(groove_section,groove_zone,af.BooleanTypes.IntersectionBooleanType)
    join(lower,tongue_section);cut(upper,groove_section)
    references=[]
    for shape,label in [(upper,'upper'),(lower,'lower')]:
        b=root.bRepBodies.add(manager.copy(shape));b.name='Uncut continuous exterior reference '+label
        references.append(ops._summary(ctx,docid,b))
    task=Path(__file__).resolve().parents[2]
    data=json.loads((task/'../s3-carrier/output/design.json').read_text(encoding='utf-8'))
    holes={h['ref']:h for h in data['mountingHoles']}
    # A continuous rear wall for the original key trough. The previous
    # 1 mm audio keep-out margin cut a long slot through this thin web.
    join(upper,box(-1.7,55.4,-51,-49.35,10.7,16.45525253169416))
    # Remove the whole obsolete internal mounting rail, safely below the
    # original outer skin. Rebuild only the two required round supports.
    rail_top=27
    # Raising the shell must not raise its old pegs into the fixed carrier.
    # Clear the carrier layer first; rebuild only its actual locating points.
    cut(lower,pb([-.15,-.15,73.6247,69.6247],pcb_z,foot+.2))
    for ref in ['H1','H3','H4']:
        h=holes[ref];x,y=h['x'],-h['y']
        cut(lower,cyl(x,y,4.95,-.2946474683,6))
        join(lower,cyl(x,y,3.4,-2.2947474683058333 if ref=='H1' else -.5,pcb_z))
        if ref=='H1':join(lower,cyl(x,y,1.3,pcb_z-.01,pcb_z+.8))
        else:
            internal_join(upper,cyl(x,y,3.2,foot,rail_top+.3))
            # M2.5 x L4 x OD3.5 heat-set inserts, installed from the PCB side.
            # Starting pilot OD3.2; a short OD3.7 entry guides the iron/insert.
            cut(upper,cyl(x,y,1.6,foot-.05,foot+4.4))
            cut(upper,cyl(x,y,1.85,foot-.05,foot+.35))
            cut(upper,cyl(x,y,1.35,foot+4.35,foot+6))
            cut(lower,cyl(x,y,1.35,-2.5,pcb_z+.1))
            cut(lower,cyl(x,y,2.8,-2.5,.70525253169416))
    for ref in ['H2','H5']:
        h=holes[ref];x,y=h['x'],-h['y']
        cut(lower,cyl(x,y,4.95,pcb_z,6))
        join(lower,cyl(x,y,3.4,-.5,pcb_z))
        join(lower,cyl(x,y,1.3,pcb_z-.01,pcb_z+.8))
    usb=pb([-10,1,7,30],14.5,24.5)
    cut(upper,usb);cut(lower,usb)

    # All clearance is internal. Keep the original rounded front/side blend.
    cut(upper,sb(-.4,81.6,-.4,51.4,-11,-4.75))
    cut(lower,sb(-.4,81.6,-.4,51.4,-7,-4.75))
    glass_clear=sb(5.6,75.6,.1,50.9,-4.85,-.6)
    cut(upper,glass_clear);cut(lower,glass_clear)
    # The front is one native face; there is no separate mask or patch seam.
    cut(upper,window_tool())
    for u in [3,78.2]:
        for v in [3,48]:
            internal_join(upper,screen(cyl(u,v,2.6,-4.8,-.45)))
            cut(upper,screen(cyl(u,v,.8,-4.81,-1.2)))
    # A standard single-row 2.54 mm DuPont housing, with 0.53 mm lateral
    # allowance on each side, rather than the previous 8 mm-wide bend box.
    spi=sb(.2,3.8,14.3,36.7,-22.4,-6.3)
    solder=sb(.2,3.8,14.3,36.7,-4.85,-2.6)
    for b in [upper,lower]:cut(b,spi);cut(b,solder)
    for ref in ['U1','U2','U3']:
        part=next(c for c in data['components'] if c['ref']==ref)
        top=pcb_z+({'U1':12.6,'U2':4.1,'U3':4.1}[ref])+5.1
        margin=1 if ref=='U1' else .2
        clearance=cyl(46,-42.1,7.2,pcb_z+1.7,top+1) if ref=='U3' else pb(part['envelope'],pcb_z+1.7,top+(2 if ref=='U1' else 1),margin)
        cut(upper,clearance)
    j=next(c for c in data['connectorMatingEnvelopes'] if c['ref']=='J1')['envelope']
    cut(upper,pb(j,pcb_z+1.6,pcb_z+1.6+11,.25))
    cut(upper,cyl(46,-42.1,1.2,12,35))
    cut(lower,cyl(46,-42.1,1.2,-3,pcb_z+.1))
    join(lower,cut(cyl(46,-42.1,2.5,-.5,pcb_z-.3),cyl(46,-42.1,1.2,-.6,pcb_z)))
    # Reuse the original vent positions and bore diameters on the rear wall.
    rear_vents=[]
    source_lower=ctx['bodies'][args['lower_source_id']]['body']
    for face in source_lower.faces:
        cylinder=ac.Cylinder.cast(face.geometry)
        if not cylinder or abs(cylinder.axis.z)<.99 or cylinder.radius*10>1.5:continue
        o=cylinder.origin;x=o.x*10+36.12495;z=floor+(o.y*10+16.45525253169416-floor)*height_scale
        if z<25:continue
        rear_vents.append([x,z,cylinder.radius*10])
        vent=manager.createCylinderOrCone(p([x,5,z]),cylinder.radius,p([x,15,z]),cylinder.radius)
        cut(lower,manager.copy(vent));cut(upper,vent)
    for source in args.get('key_source_ids',[]):
        key=move(manager.copy(ctx['bodies'][source]['body']),world)
        b=key.boundingBox;cx=(b.minPoint.x+b.maxPoint.x)/2;cy=(b.minPoint.y+b.maxPoint.y)/2
        unscaled=manager.copy(key)
        move(key,[1.025,0,0,-.025*cx,0,1.025,0,-.025*cy,0,0,1,0,0,0,0,1])
        for press in [0,.5,1,1.5,2,2.5,3,3.5,4]:
            for cap in [unscaled,key]:
                moving=manager.copy(cap);move(moving,[1,0,0,0,0,1,0,0,0,0,1,-press/10,0,0,0,1]);cut(upper,moving)
    pocket=module.control_pocket(manager,root,control_source)
    boolean(pocket,box(-20,100,-100,-50.2,0,50),af.BooleanTypes.IntersectionBooleanType)
    cut(upper,pocket)
    cut(upper,lower)
    discarded=[]
    if upper.lumps.count>1:
        lumps=list(upper.lumps);largest=max(lumps,key=lambda l:l.volume)
        discarded=[{'volume_mm3':l.volume*1000,'bounds_mm':[[v*10 for v in [l.boundingBox.minPoint.x,l.boundingBox.minPoint.y,l.boundingBox.minPoint.z]],[v*10 for v in [l.boundingBox.maxPoint.x,l.boundingBox.maxPoint.y,l.boundingBox.maxPoint.z]]]} for l in lumps if l!=largest]
        if sum(l['volume_mm3'] for l in discarded)>50:raise RuntimeError('Unexpected large disconnected component: '+json.dumps(discarded))
        if not manager.deleteFaces(list(largest.faces),False):raise RuntimeError('Could not remove obsolete disconnected mounting remnants')
    if upper.lumps.count!=1 or lower.lumps.count!=1:raise RuntimeError('Enclosure must have exactly one connected lump per part: '+json.dumps({'upper':upper.lumps.count,'lower':[{'volume_mm3':l.volume*1000,'min':[l.boundingBox.minPoint.x*10,l.boundingBox.minPoint.y*10,l.boundingBox.minPoint.z*10],'max':[l.boundingBox.maxPoint.x*10,l.boundingBox.maxPoint.y*10,l.boundingBox.maxPoint.z*10]} for l in lower.lumps]}))
    ub=root.bRepBodies.add(upper);ub.name='A4 Upper R3 - Centered LCD - M2.5 heat inserts'
    lb=root.bRepBodies.add(lower);lb.name='A4 Lower R3 - Raised rear - dual microphone inlet'
    return {'outer_corner_radii_mm':{'side':6.5,'profile':7,'hinge':8},'mating_joint':{'type':'concealed tongue and groove','tongue_height_mm':1.2,'tongue_wall_thickness_mm':1.3,'lateral_clearance_mm':.3,'height_clearance_mm':.25},'rear_vent_bores_mm':rear_vents,'surface_reference_bodies':references,'bodies':[ops._summary(ctx,docid,b,edges=True) for b in [ub,lb]],'screen_origin_mm':origin,'screen_angle_deg':math.degrees(angle),'rear_height_scale':height_scale,'total_height_increase_mm':(60.953728369523255-floor)*(height_scale-1),'pcb_insert':{'thread':'M2.5','length_mm':4,'outside_diameter_mm':3.5,'pilot_diameter_mm':3.2,'entry_diameter_mm':3.7,'pocket_depth_mm':4.4,'boss_diameter_mm':6.4,'installed_from':'inside, PCB side of upper shell','bottom_screw_head_seat_z_mm':.70525253169416,'screw_length_start_mm':8},'screen_origin_mm':origin,'external_width_mm':91.5,'active_display_center_x_mm':origin[0]+37.4,'control_coordinates_unchanged':True,'widening_boolean_tolerance_mm':widening_tolerance,'screen_pcb_front_n_mm':-4.8,'screen_glass_front_n_mm':-.6,'window_inner_uv':[[8.45,3.75],[66.35,47.25]],'window_outer_uv':[[7.7,3.0],[67.1,48.0]],'window_flared_for_unobstructed_view':True,'screen_post_radius_mm':2.6,'screen_pilot_n_mm':[-4.81,-1.2],'screen_screw_nominal_mm':5,'front_plane_n_original_mm':front,'J1_hard_connector_height_above_carrier_top_mm':11,'spi_envelope_uvn':[[.2,14.3,-22.4],[3.8,36.7,-6.3]],'microphone_inlets':['bottom','front_above_microphone'],'removed_disconnected_remnants':discarded,'exterior':'continuous rounded wedge, 91.5 mm uniform width; original control recesses and dimensions; internal screw bosses clipped to outer skin'}
