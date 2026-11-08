"""Predefined A4 enclosure construction, entirely in Fusion's native kernel.

All dimensions mm. Source bodies are copied out of the read-only STEP document.
"""
import json
import math
from pathlib import Path
import adsk.core as ac
import adsk.fusion as af

def build(ctx,docid,args):
    import fusion_ops as ops
    # Loaded explicitly by the dispatcher, not installed as a general evaluator.
    return _build(ctx,docid,args,ops)

def _build(ctx,docid,args,ops):
    manager=af.TemporaryBRepManager.get()
    doc=ctx['documents'][docid];root=doc['design'].rootComponent
    source=ctx['bodies'][args['upper_source_id']]['body']
    lower_source=ctx['bodies'][args['lower_source_id']]['body']
    q=math.sqrt(.5)
    O=[-4.47505,-39-q*2.4+q*8.8,21.153+q*2.4+q*8.8]
    pcb_bottom=2.70525253169416
    floor=-.29474746830584
    foot=4.45525253169416
    def p(v):return ac.Point3D.create(*[n/10 for n in v])
    def transform(body,m):
        mat=ac.Matrix3D.create();mat.setWithArray(m)
        if not manager.transform(body,mat):raise RuntimeError('Native transform failed')
        return body
    world=[1,0,0,3.612495,0,0,-1,-4.369864,0,1,0,1.645525253169416,0,0,0,1]
    upper=transform(manager.copy(source),world)
    lower=transform(manager.copy(lower_source),world)
    def box(x0,x1,y0,y1,z0,z1):
        b=ac.OrientedBoundingBox3D.create(p([(x0+x1)/2,(y0+y1)/2,(z0+z1)/2]),ac.Vector3D.create(1,0,0),ac.Vector3D.create(0,1,0),(x1-x0)/10,(y1-y0)/10,(z1-z0)/10)
        return manager.createBox(b)
    def cyl(x,y,r,z0,z1):return manager.createCylinderOrCone(p([x,y,z0]),r/10,p([x,y,z1]),r/10)
    def boolean(a,b,kind):
        if not manager.booleanOperation(a,b,kind):raise RuntimeError('Native Boolean failed')
        return a
    def cut(a,b):return boolean(a,b,af.BooleanTypes.DifferenceBooleanType)
    def join(a,b):return boolean(a,b,af.BooleanTypes.UnionBooleanType)
    def screen(s):return transform(s,[1,0,0,O[0]/10,0,q,-q,O[1]/10,0,q,q,O[2]/10,0,0,0,1])
    def sbox(u0,u1,v0,v1,n0,n1):return screen(box(u0,u1,v0,v1,n0,n1))
    def rounded(x0,x1,y0,y1,z0,z1,r):
        s=join(box(x0+r,x1-r,y0,y1,z0,z1),box(x0,x1,y0+r,y1-r,z0,z1))
        for x in [x0+r,x1-r]:
            for y in [y0+r,y1-r]:join(s,cyl(x,y,r,z0,z1))
        return s
    def pcb_box(e,z0,z1,margin=0):
        x0,y0,x1,y1=e
        return box(x0-margin,x1+margin,-y1-margin,-y0+margin,z0,z1)
    def round_front(s):
        body=root.bRepBodies.add(s)
        edges=ac.ObjectCollection.create()
        for e in body.edges:
            bounds=e.boundingBox
            if abs(bounds.minPoint.z-.24)<1e-6 and abs(bounds.maxPoint.z-.24)<1e-6:edges.add(e)
        fillets=root.features.filletFeatures;fi=fillets.createInput()
        fi.edgeSetInputs.addConstantRadiusEdgeSet(edges,ac.ValueInput.createByReal(.12),True)
        fillets.add(fi)
        result=manager.copy(body);body.deleteMe()
        return result
    data=json.loads((ctx['task_root']/'../s3-carrier/output/design.json').read_text(encoding='utf-8')) if 'task_root' in ctx else json.loads((Path(__file__).resolve().parents[2]/'../s3-carrier/output/design.json').read_text(encoding='utf-8'))
    holes={h['ref']:h for h in data['mountingHoles']}
    # Delete inherited square/front locating structures and rebuild on A4 axes.
    for ref in ['H1','H3','H4']:
        h=holes[ref];x,y=h['x'],-h['y']
        cut(lower,cyl(x,y,4.95,floor+.0001,6))
        join(lower,cyl(x,y,3.4,-.50,pcb_bottom))
        cut(upper,box(x-5.2,x+5.2,y-5.2,y+5.2,foot-.10,19.7))
        if ref=='H1':
            join(lower,cyl(x,y,1.3,pcb_bottom-.01,pcb_bottom+.8))
        else:
            join(upper,cyl(x,y,2.75,foot,21.5))
            # Drill AFTER joining: neither the inherited floor nor roof fills it.
            cut(upper,cyl(x,y,1.0,foot-.05,foot+9.5))
            cut(lower,cyl(x,y,1.35,-2.5,pcb_bottom+.1))
            cut(lower,cyl(x,y,2.8,-2.5,-1.1947474683))
    for ref in ['H2','H5']:
        h=holes[ref];cut(lower,cyl(h['x'],-h['y'],1.45,pcb_bottom+.8,6))
    usb=pcb_box([-10,1,7,30],14.5,24.5)
    cut(lower,usb);cut(upper,usb)
    # This small USB roof is disconnected by the enlarged dual-port opening.
    cut(lower,box(-3.23,-.22,-16.67,-9.57,24.49,28.05))

    # Screen shell: full-width surround replaces the old lip, later rounded
    # into the inherited body. Board fits behind the uninterrupted front face.
    cut(upper,sbox(-.4,81.6,-.4,51.4,-40,3))
    cut(lower,sbox(-.4,81.6,-.4,51.4,-8.2,-1.5))
    collar=screen(round_front(rounded(-3.65,84.85,-2.4,54,-11,2.4,6)))
    cut(collar,sbox(-.4,81.6,-.4,51.4,-11.1,0))
    cut(collar,sbox(8.6,66.2,3.9,47.1,-.1,2.5))
    for u in [3,78.2]:
        for v in [3,48]:
            join(collar,screen(cyl(u,v,3.1,-6,.6)))
            cut(collar,screen(cyl(u,v,.8,-6.01,-.61)))
    join(upper,collar)

    # The transition is a native extruded profile, sharing its edge with the
    # screen slope. Its exterior fillets are applied after the solid union.
    sketch=root.sketches.add(root.xYConstructionPlane)
    def sv(v,n):return [O[1]+q*v-q*n,O[2]+q*v+q*n]
    top=[sv(1,2.4),sv(-3,2.4),[-42.5,20.2],[-44,17.60]]
    points=top+[[a,b-2.4] for a,b in reversed(top)]
    # Exact tangent circular arcs in the section eliminate the old planar
    # ledge. The first section overlaps the bezel on the same 45 degree face.
    radii={1:2.5,2:2.0}
    starts=[];ends=[];mids={}
    for i,b in enumerate(points):
        if i not in radii:starts.append(b);ends.append(b);continue
        a=points[i-1];c=points[(i+1)%len(points)]
        def unit(v):
            d=math.hypot(*v);return [v[0]/d,v[1]/d]
        u=unit([a[0]-b[0],a[1]-b[1]]);v=unit([c[0]-b[0],c[1]-b[1]])
        angle=math.acos(max(-1,min(1,u[0]*v[0]+u[1]*v[1])))
        r=radii[i];distance=r/math.tan(angle/2)
        before=[b[j]+u[j]*distance for j in range(2)];after=[b[j]+v[j]*distance for j in range(2)]
        bisect=unit([u[0]+v[0],u[1]+v[1]])
        center=[b[j]+bisect[j]*r/math.sin(angle/2) for j in range(2)]
        middle_dir=unit([b[j]-center[j] for j in range(2)])
        mids[i]=[center[j]+middle_dir[j]*r for j in range(2)]
        starts.append(before);ends.append(after)
    for i in range(len(points)):
        if i in mids:sketch.sketchCurves.sketchArcs.addByThreePoints(p([*starts[i],0]),p([*mids[i],0]),p([*ends[i],0]))
        j=(i+1)%len(points)
        sketch.sketchCurves.sketchLines.addByTwoPoints(p([*ends[i],0]),p([*starts[j],0]))
    extrusion=root.features.extrudeFeatures.addSimple(sketch.profiles.item(0),ac.ValueInput.createByReal(8.85),af.FeatureOperations.NewBodyFeatureOperation)
    transition=manager.copy(extrusion.bodies.item(0));extrusion.bodies.item(0).deleteMe();sketch.deleteMe()
    transform(transition,[0,0,1,-.812505,1,0,0,0,0,1,0,0,0,0,0,1])
    trim_sketch=root.sketches.add(root.xYConstructionPlane)
    outline=[[-6.7,-35.2],[78.7,-35.2],[80.37495,-38],[80.37495,-45],[-8.12505,-45],[-8.12505,-38]]
    for a,b in zip(outline,outline[1:]+outline[:1]):trim_sketch.sketchCurves.sketchLines.addByTwoPoints(p([*a,0]),p([*b,0]))
    trim_feature=root.features.extrudeFeatures.addSimple(trim_sketch.profiles.item(0),ac.ValueInput.createByReal(10),af.FeatureOperations.NewBodyFeatureOperation)
    trim=manager.copy(trim_feature.bodies.item(0));trim_feature.bodies.item(0).deleteMe();trim_sketch.deleteMe()
    boolean(transition,trim,af.BooleanTypes.IntersectionBooleanType)
    join(upper,transition)
    # Side cheeks run down to the inherited sidewall, closing the two gaps
    # beneath the raised screen corners without filling the electronics bay.
    deep=manager.copy(transition)
    for drop in range(2,18,2):
        layer=manager.copy(transition)
        transform(layer,[1,0,0,0,0,1,0,0,0,0,1,-drop/10,0,0,0,1])
        join(deep,layer)
    for x0,x1 in [(-8.12505,-5.32505),(77.57495,80.37495)]:
        cheek=manager.copy(deep)
        boolean(cheek,box(x0,x1,-46,-34,5,35),af.BooleanTypes.IntersectionBooleanType)
        join(upper,cheek)

    spi=sbox(-2,6,14.3,36.7,-23.6,-7.5)
    cut(upper,spi);cut(lower,spi)
    for ref in ['U1','U2','U3']:
        c=next(c for c in data['components'] if c['ref']==ref)
        ztop=pcb_bottom+({'U1':12.6,'U2':4.1,'U3':4.1}[ref])+1.6+3.5
        clearance=cyl(46,-42.1,8,pcb_bottom+1.7,ztop+2) if ref=='U3' else pcb_box(c['envelope'],pcb_bottom+1.7,ztop+2,1)
        cut(upper,clearance)
    j=next(e for e in data['connectorMatingEnvelopes'] if e['ref']=='J1')['envelope']
    cut(upper,pcb_box(j,pcb_bottom+1.6,pcb_bottom+20.3,.5))
    cut(lower,cyl(46,-42.1,1.2,-3,0))
    ring=cut(cyl(46,-42.1,2.5,-.5,pcb_bottom-.3),cyl(46,-42.1,1.2,-.6,pcb_bottom))
    join(lower,ring)
    for sourceid in args.get('key_source_ids',[]):
        key=transform(manager.copy(ctx['bodies'][sourceid]['body']),world)
        pressed=manager.copy(key)
        transform(pressed,[1,0,0,0,0,1,0,0,0,0,1,-.4,0,0,0,1])
        cut(upper,pressed)
        b=key.boundingBox;cx=(b.minPoint.x+b.maxPoint.x)/2;cy=(b.minPoint.y+b.maxPoint.y)/2
        transform(key,[1.025,0,0,-.025*cx,0,1.025,0,-.025*cy,0,0,1,-.4,0,0,0,1])
        cut(upper,key)
    cut(upper,lower)
    upper_body=root.bRepBodies.add(upper);upper_body.name='A4 Upper R2 - Native Fusion'
    lower_body=root.bRepBodies.add(lower);lower_body.name='A4 Lower R2 - Native Fusion'
    side_edges=ac.ObjectCollection.create()
    for e in upper_body.edges:
        pt=e.pointOnEdge
        if (abs(pt.x*10+8.12505)<.01 or abs(pt.x*10-80.37495)<.01) and -42<pt.y*10<-39 and 22<pt.z*10<26:
            side_edges.add(e)
    if side_edges.count:
        fi=root.features.filletFeatures.createInput()
        fi.edgeSetInputs.addConstantRadiusEdgeSet(side_edges,ac.ValueInput.createByReal(.08),True)
        root.features.filletFeatures.add(fi)
    results=[ops._summary(ctx,docid,b,edges=True) for b in [upper_body,lower_body]]
    return {'bodies':results,'screen_origin_mm':O,'front_bearing_z_mm':foot,'pcb_bottom_z_mm':pcb_bottom}
