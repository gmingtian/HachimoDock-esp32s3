"""R4: original outer BRep and controls, internally mounted LCD and SPI stack."""
import json,math
import importlib.util
from pathlib import Path
import adsk.core as ac
import adsk.fusion as af

def build(ctx,docid,args):
    import fusion_ops as ops
    manager=af.TemporaryBRepManager.get();root=ctx['documents'][docid]['design'].rootComponent
    q=math.sqrt(.5);angle=math.pi/4;c=q;sn=q
    floor=-2.2947474683058333;front=.0006311152137232;pcb_z=2.70525253169416;foot=pcb_z+1.6
    def p(v):return ac.Point3D.create(*[n/10 for n in v])
    def move(body,values):
        matrix=ac.Matrix3D.create();matrix.setWithArray(values)
        if not manager.transform(body,matrix):raise RuntimeError('Transform failed')
        return body
    world=[1,0,0,3.612495,0,0,-1,-4.369864,0,1,0,1.645525253169416,0,0,0,1]
    spec=importlib.util.spec_from_file_location('clone_baseline',Path(__file__).with_name('clone_baseline.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    base=module.build(ctx,docid,args);origin=base['screen_origin_mm'];references=base['bodies'];extra=base['screen_extension_v_mm']
    upper=manager.copy(ctx['bodies'][references[0]['body_id']]['body'])
    lower=manager.copy(ctx['bodies'][references[1]['body_id']]['body'])
    def box(x0,x1,y0,y1,z0,z1):
        b=ac.OrientedBoundingBox3D.create(p([(x0+x1)/2,(y0+y1)/2,(z0+z1)/2]),ac.Vector3D.create(1,0,0),ac.Vector3D.create(0,1,0),(x1-x0)/10,(y1-y0)/10,(z1-z0)/10)
        return manager.createBox(b)
    def cyl(x,y,r,z0,z1):return manager.createCylinderOrCone(p([x,y,z0]),r/10,p([x,y,z1]),r/10)
    def boolean(a,b,operation):
        if not manager.booleanOperation(a,b,operation):raise RuntimeError('Native Boolean failed')
        return a
    def cut(a,b):return boolean(a,b,af.BooleanTypes.DifferenceBooleanType)
    def join(a,b):return boolean(a,b,af.BooleanTypes.UnionBooleanType)
    def internal_join(a,b):return join(a,b)
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
    task=Path(__file__).resolve().parents[2]
    data=json.loads((task/'../s3-carrier/output/design.json').read_text(encoding='utf-8'))
    holes={h['ref']:h for h in data['mountingHoles']}
    # Close the original, now shifted floor counterbores completely before
    # drilling the actual carrier axes. Avoid a residual crescent at H4.
    k=91.5/88.5
    for oldx in [11.12495,61.12495]:
        x=36.12495+(oldx-36.12495)*k
        join(lower,cyl(x,-36.05186,3.7,floor,-.25))
    rail_top=16.5
    cut(upper,box(0,73.5,-42,-29,foot-.1,16.5))
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
    # Fill the original opening with a coplanar inner mask. Its outline is
    # copied from the original window and extended by the screen section.
    mask=screen(rounded(2.75,78.45,-.1942492974953,52.3057507025047+extra,-.6,front,7.5),True)
    k=91.5/88.5
    move(mask,[k,0,0,(1-k)*36.12495/10,0,1,0,0,0,0,1,0,0,0,0,1])
    join(upper,mask)
    cut(upper,manager.copy(glass_clear))
    cut(upper,window_tool())
    for u in [3,78.2]:
        for v in [3,48]:
            internal_join(upper,screen(cyl(u,v,2.6,-4.8,-.45 if u==3 else -1.8)))
            cut(upper,screen(cyl(u,v,.8,-4.81,-1.2)))
    # A standard single-row 2.54 mm DuPont housing, with 0.53 mm lateral
    # allowance on each side, rather than the previous 8 mm-wide bend box.
    # Measured: housing L14, installed PCB-back-to-tail 17 mm. Reserve a
    # further 4 mm behind the tail; turn wires right into the case (R3).
    spi=sb(.2,3.8,14.3,36.7,-23.7,-6.3)
    solder=sb(.2,3.8,14.3,36.7,-4.85,-2.6)
    for b in [upper,lower]:cut(b,spi);cut(b,solder)
    # Follow the bend rather than cutting its whole rectangular bounding box:
    # that box would needlessly breach the rounded lower side wall.
    for i in range(8):
        v=16.61+2.54*i
        route=manager.createTorus(p([5,v,-23.4]),ac.Vector3D.create(0,1,0),.3,.1)
        boolean(route,box(1,5,v-1.1,v+1.1,-27.4,-23.4),af.BooleanTypes.IntersectionBooleanType)
        join(route,manager.createSphere(p([2,v,-23.4]),.1))
        join(route,manager.createSphere(p([5,v,-26.4]),.1))
        join(route,manager.createCylinderOrCone(p([5,v,-26.4]),.1,p([8,v,-26.4]),.1))
        join(route,manager.createSphere(p([8,v,-26.4]),.1))
        route=screen(route)
        for b in [upper,lower]:cut(b,route)
    for ref in ['U1','U2','U3']:
        part=next(c for c in data['components'] if c['ref']==ref)
        top=pcb_z+({'U1':12.6,'U2':4.1,'U3':4.1}[ref])+5.1
        margin=1 if ref=='U1' else .1
        clearance=cyl(46,-42.1,7.2,pcb_z+1.7,top+1) if ref=='U3' else pb(part['envelope'],pcb_z+1.7,top+(2 if ref=='U1' else 1),margin)
        cut(upper,clearance)
    j=next(c for c in data['connectorMatingEnvelopes'] if c['ref']=='J1')['envelope']
    cut(upper,pb(j,pcb_z+1.6,pcb_z+1.6+11,.25))
    cut(upper,cyl(46,-42.1,1.2,12,35))
    cut(lower,cyl(46,-42.1,1.2,-3,pcb_z+.1))
    join(lower,cut(cyl(46,-42.1,2.5,-.5,pcb_z-.3),cyl(46,-42.1,1.2,-.6,pcb_z)))
    # LCD screws are driven before fitting the lower cover. Transfer the two
    # obstructing return-lip portions to that cover, rather than leaving open
    # holes in the assembled exterior. The small inboard web anchors each cap.
    before_access=manager.copy(upper)
    for v in [3,48]:
        access=screen(cyl(78.2,v,2.6,-65,-6.3))
        cap=boolean(manager.copy(before_access),screen(cyl(78.2,v,2.45,-65,-9.5)),af.BooleanTypes.IntersectionBooleanType)
        web=boolean(manager.copy(before_access),screen(cyl(78.2,v,1.8,-65,-9.5)),af.BooleanTypes.IntersectionBooleanType)
        move(web,[1,0,0,-.05,0,1,0,0,0,0,1,0,0,0,0,1])
        boolean(web,manager.copy(access),af.BooleanTypes.IntersectionBooleanType)
        join(lower,web);join(lower,cap);cut(upper,access)
    # Original key geometry, control recesses, vents and mating lips stay native.
    # Preserve the original coincident mating faces; inspect interference
    # on the exported solids instead of re-cutting a zero-volume contact.
    spec=importlib.util.spec_from_file_location('repair_clone_vents',Path(__file__).with_name('repair_clone_vents.py'))
    repair_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(repair_module)
    lower,roundvents=repair_module.repair(manager,lower,ctx['bodies'][args['lower_source_id']]['body'],extra)
    lettering=None
    preferences=json.loads((task/'requirements.json').read_text(encoding='utf-8'))
    speaker_mount=None
    if preferences.get('speakerMount'):
        spec=importlib.util.spec_from_file_location('speaker_slot',Path(__file__).with_name('speaker_slot.py'))
        speaker_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(speaker_module)
        lower,speaker_mount=speaker_module.apply(manager,lower,roundvents)
    if preferences.get('frontWordmark'):
        spec=importlib.util.spec_from_file_location('engrave_wordmark',Path(__file__).with_name('engrave_wordmark.py'))
        word_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(word_module)
        upper,lettering=word_module.apply(manager,root,upper,origin)
    discarded=[]
    if upper.lumps.count>1:
        lumps=list(upper.lumps);largest=max(lumps,key=lambda l:l.volume)
        discarded=[{'volume_mm3':l.volume*1000,'bounds_mm':[[v*10 for v in [l.boundingBox.minPoint.x,l.boundingBox.minPoint.y,l.boundingBox.minPoint.z]],[v*10 for v in [l.boundingBox.maxPoint.x,l.boundingBox.maxPoint.y,l.boundingBox.maxPoint.z]]]} for l in lumps if l!=largest]
        if sum(l['volume_mm3'] for l in discarded)>50:raise RuntimeError('Unexpected large disconnected component: '+json.dumps(discarded))
        if not manager.deleteFaces(list(largest.faces),False):raise RuntimeError('Could not remove obsolete disconnected mounting remnants')
    if upper.lumps.count!=1 or lower.lumps.count!=1:raise RuntimeError('Enclosure must have exactly one connected lump per part: '+json.dumps({'upper':upper.lumps.count,'lower':[{'volume_mm3':l.volume*1000,'min':[l.boundingBox.minPoint.x*10,l.boundingBox.minPoint.y*10,l.boundingBox.minPoint.z*10],'max':[l.boundingBox.maxPoint.x*10,l.boundingBox.maxPoint.y*10,l.boundingBox.maxPoint.z*10]} for l in lower.lumps]}))
    ub=root.bRepBodies.add(upper);ub.name='A4 Upper R4 - Original clone - internal LCD mounting'
    lb=root.bRepBodies.add(lower);lb.name='A4 Lower R4 - Original mating structure - dual Type-C'
    return {'rear_vent_bores_mm':roundvents,'bodies':[ops._summary(ctx,docid,b,edges=True) for b in [ub,lb]],'surface_reference_bodies':references,'original_clone':True,'original_control_geometry_and_depths':True,'original_mating_structure':True,'screen_origin_mm':origin,'screen_angle_deg':45,'external_width_mm':91.5,'screen_extension_v_mm':extra,'extension_section_v_mm':base['extension_section_v_mm'],'active_display_center_x_mm':origin[0]+37.4,'screen_pcb_front_n_mm':-4.8,'screen_glass_front_n_mm':-.6,'screen_post_radius_mm':2.6,'screen_pilot_n_mm':[-4.81,-1.2],'screen_screw_nominal_mm':5,'screen_driver_access':{'driver_diameter_mm':4.5,'upper_clearance_radius_mm':2.6,'lower_cover_tab_radius_mm':2.45,'cover_seam_radial_clearance_mm':.15,'centers_uv':[[78.2,3],[78.2,48]],'cap_n_limit_mm':-9.5,'assembly_sequence':'Fit and tighten LCD inside upper cover before installing lower cover'},'window_inner_uv':[[8.45,3.75],[66.35,47.25]],'window_outer_uv':[[7.7,3],[67.1,48]],'spi_envelope_uvn':[[.2,14.3,-23.7],[3.8,36.7,-6.3]],'spi_wire_exit':{'direction':'right into case','radius_mm':3,'clearance_radius_mm':1,'maximum_rear_extent_from_pcb_back_mm':21},'spi_stack_mm':{'housing_length':14,'installed_height_from_pcb_back':17,'additional_tail_space':4,'wire_od_assumed':1.2,'wire_bend_radius_assumed':3,'physical_route_verified':False},'microphone_inlets':['bottom','front_above_microphone'],'pcb_insert':{'thread':'M2.5','length_mm':4,'outside_diameter_mm':3.5,'pilot_diameter_mm':3.2,'pocket_depth_mm':4.4,'boss_diameter_mm':6.4,'screw_length_start_mm':8},'usb':'two Type-C sockets, original board location','removed_disconnected_remnants':discarded,'lettering':lettering,'speaker_mount':speaker_mount}
