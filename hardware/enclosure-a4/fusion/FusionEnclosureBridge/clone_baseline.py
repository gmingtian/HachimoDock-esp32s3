"""Extend the original native case by inserting an unchanged cross section."""
import math,importlib.util
from pathlib import Path
import adsk.core as ac
import adsk.fusion as af

def build(ctx,docid,args):
    import fusion_ops as ops
    manager=af.TemporaryBRepManager.get();root=ctx['documents'][docid]['design'].rootComponent;q=math.sqrt(.5)
    def p(v):return ac.Point3D.create(*[t/10 for t in v])
    def move(b,a):
        m=ac.Matrix3D.create();m.setWithArray(a)
        if not manager.transform(b,m):raise RuntimeError('Original copy transform failed')
        return b
    def boolean(a,b,op):
        if not manager.booleanOperation(a,b,op):raise RuntimeError('Original copy Boolean failed')
        return a
    def v(point):return q*(point.y*10+39)+q*(point.z*10-21.153)
    world=[1,0,0,3.612495,0,0,-1,-4.369864,0,1,0,1.645525253169416,0,0,0,1]
    originals=[move(manager.copy(ctx['bodies'][args[k]]['body']),world) for k in ['upper_source_id','lower_source_id']]
    spec=importlib.util.spec_from_file_location('widen_case',Path(__file__).with_name('widen_case.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    upper,_=module.widen(manager,root,originals[0],3,1)
    lower=manager.copy(originals[1]);k=91.5/88.5
    move(lower,[k,0,0,(1-k)*3.612495,0,1,0,0,0,0,1,0,0,0,0,1])
    extra=float(args.get('screen_extension_v_mm',13.5));section=38;result=[]
    for case,label in [(upper,'upper'),(lower,'lower')]:
        # Insert below the original vents. This gives actual rear depth for
        # the 17 mm SPI connector and wire bend, not just a taller window.
        middle=(section+200)/2
        bounds=ac.OrientedBoundingBox3D.create(p([36,-39+q*middle,21.153+q*middle]),ac.Vector3D.create(1,0,0),ac.Vector3D.create(0,q,q),20,(200-section)/10,40)
        half=manager.createBox(bounds)
        top=boolean(manager.copy(case),manager.copy(half),af.BooleanTypes.IntersectionBooleanType)
        bottom=boolean(manager.copy(case),half,af.BooleanTypes.DifferenceBooleanType)
        temporary=root.bRepBodies.add(manager.copy(top));faces=[]
        for face in temporary.faces:
            plane=ac.Plane.cast(face.geometry)
            if plane and abs(v(plane.origin)-section)<.001 and abs(abs(plane.normal.y*q+plane.normal.z*q)-1)<.001:faces.append(face)
        if not faces:raise RuntimeError('Original section faces missing '+label)
        bridges=[]
        for face in faces:
            feature=root.features.extrudeFeatures.addSimple(face,ac.ValueInput.createByReal((extra+.01)/10),af.FeatureOperations.NewBodyFeatureOperation)
            body=feature.bodies.item(0);bridge=manager.copy(body);body.deleteMe()
            minimum=min(v(vertex.geometry) for vertex in bridge.vertices)
            delta=(section-.005-minimum)/10
            move(bridge,[1,0,0,0,0,1,0,q*delta,0,0,1,q*delta,0,0,0,1]);bridges.append(bridge)
        temporary.deleteMe()
        for bridge in bridges:boolean(bottom,bridge,af.BooleanTypes.UnionBooleanType)
        move(top,[1,0,0,0,0,1,0,q*extra/10,0,0,1,q*extra/10,0,0,0,1])
        boolean(bottom,top,af.BooleanTypes.UnionBooleanType)
        if bottom.lumps.count!=1:raise RuntimeError('Original copy disconnected '+label)
        body=root.bRepBodies.add(bottom);body.name='Original clone '+label+' - screen extended only'
        body.appearance=ctx['documents'][docid]['design'].appearances.addByCopy(ctx['bodies'][args['upper_source_id' if label=='upper' else 'lower_source_id']]['body'].appearance,'Original '+label)
        result.append(ops._summary(ctx,docid,body))
    return {'bodies':result,'original_source_geometry':True,'control_dimensions_and_depths_unchanged':True,'width_mm':91.5,'screen_extension_v_mm':extra,'extension_section_v_mm':section,'screen_origin_mm':[-1.27505,-39+extra*q,21.153+extra*q],'screen_angle_deg':45}
