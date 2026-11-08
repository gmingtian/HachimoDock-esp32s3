"""Native recessed Hachimo wordmark with a reinforced inner face."""
import json
import math
from pathlib import Path
import adsk.core as ac
import adsk.fusion as af


def apply(manager,root,upper,origin):
    task=Path(__file__).resolve().parents[2]
    design=json.loads((task/'fusion/assets/hachimo-joystick-vectors.json').read_text(encoding='utf-8'))
    x0,y0,x1,y1=design['bounds_mm'];dx=37.4-(x0+x1)/2;dy=-5.6-(y0+y1)/2
    q=math.sqrt(.5)
    def p(a):return ac.Point3D.create(*[v/10 for v in a])
    def boolean(a,b,kind):
        if not manager.booleanOperation(a,b,kind):raise RuntimeError('Wordmark Boolean failed')
        return a
    def screen(body,du=0,dv=0,dn=0):
        ox,oy,oz=origin;m=ac.Matrix3D.create()
        m.setWithArray([1,0,0,(ox+du)/10,0,q,-q,(oy+q*(dv-dn))/10,0,q,q,(oz+q*(dv+dn))/10,0,0,0,1])
        if not manager.transform(body,m):raise RuntimeError('Wordmark transform failed')
        return body
    def box(a,b):
        bounds=ac.OrientedBoundingBox3D.create(p([(a[i]+b[i])/2 for i in range(3)]),ac.Vector3D.create(1,0,0),ac.Vector3D.create(0,1,0),*[(b[i]-a[i])/10 for i in range(3)])
        return manager.createBox(bounds)
    # The existing face is only 0.6 mm thick here. Reinforce inside the case;
    # it stays below the LCD PCB footprint and clear of the main-board modules.
    r=1.2
    backing=box([19+r,-10.25,-1.8],[55.8-r,-.9,-.45])
    boolean(backing,box([19,-10.25+r,-1.8],[55.8,-.9-r,-.45]),af.BooleanTypes.UnionBooleanType)
    for u in [19+r,55.8-r]:
        for v in [-10.25+r,-.9-r]:
            c=manager.createCylinderOrCone(p([u,v,-1.8]),r/10,p([u,v,-.45]),r/10)
            boolean(backing,c,af.BooleanTypes.UnionBooleanType)
    boolean(upper,screen(backing),af.BooleanTypes.UnionBooleanType)
    stages=[{'stage':'backing','lumps':upper.lumps.count,'volume_mm3':upper.volume*1000}]
    for index,contours in enumerate(design['components']):
        wires=[]
        for loop in contours:
            points=[p([a[0],a[1],0]) for a in loop]
            curves=[ac.Line3D.create(points[i],points[(i+1)%len(points)]) for i in range(len(points))]
            wire,_=manager.createWireFromCurves(curves);wires.append(wire)
        face=manager.createFaceFromPlanarWires(wires)
        if not face:raise RuntimeError('Invalid wordmark face')
        sheet=root.bRepBodies.add(face)
        feature=root.features.extrudeFeatures.addSimple(sheet.faces.item(0),ac.ValueInput.createByReal(.058),af.FeatureOperations.NewBodyFeatureOperation)
        # In direct-design documents Fusion may also enumerate pre-existing
        # base-feature bodies here. Only the new local 0..0.58 mm extrusion is
        # a text cutter; never transform/delete the baseline casing as a tool.
        generated=[b for b in feature.bodies if b.isSolid and
            abs(b.boundingBox.minPoint.z)<1e-6 and abs(b.boundingBox.maxPoint.z-.058)<1e-6]
        if not generated:raise RuntimeError('Text extrusion did not create a cutter')
        tools=[manager.copy(b) for b in generated]
        for b in generated:b.deleteMe()
        sheet.deleteMe()
        bounds=[[t.boundingBox.minPoint.z*10,t.boundingBox.maxPoint.z*10] for t in tools]
        for tool in tools:boolean(upper,screen(tool,dx,dy,-.5),af.BooleanTypes.DifferenceBooleanType)
        stages.append({'component':index,'tool_z_mm':bounds,'lumps':upper.lumps.count,'volume_mm3':upper.volume*1000})
    if upper.lumps.count!=1:raise RuntimeError('Lettering disconnected the shell: '+json.dumps(stages))
    return upper,{'text':'Hachimo','style':'C joystick wordmark','effect':'recessed',
        'offset_uv_mm':[dx,dy],'center_uv_mm':[37.4,-5.6],
        'bounds_uv_mm':[x0+dx,y0+dy,x1+dx,y1+dy],
        'recess_depth_mm':.5006311152,'backing_n_mm':[-1.8,-.45],
        'nominal_remaining_floor_mm':1.3,'vector_source':'fusion/assets/hachimo-joystick-vectors.json'}


def build(ctx,docid,args):
    import fusion_ops as ops
    manager=af.TemporaryBRepManager.get();root=ctx['documents'][docid]['design'].rootComponent
    source=ctx['bodies'][args['upper_source_id']]['body']
    baseline=root.bRepBodies.add(manager.copy(source));baseline.name='Baseline upper before Hachimo'
    upper,spec=apply(manager,root,manager.copy(source),args['screen_origin_mm'])
    actual=root.bRepBodies.add(upper);actual.name='Full upper - Hachimo recessed joystick wordmark'
    actual.appearance=ctx['documents'][docid]['design'].appearances.addByCopy(source.appearance,'Hachimo upper appearance')
    return {'bodies':[ops._summary(ctx,docid,actual)],'baseline':ops._summary(ctx,docid,baseline),
        'lettering':spec,'screen_origin_mm':args['screen_origin_mm']}
