"""Restore round source vents after inserting the original screen section."""
import math
import adsk.core as ac
import adsk.fusion as af

def repair(manager,lower,source,extra=13.5,section=38):
    q=math.sqrt(.5)
    def p(a):return ac.Point3D.create(*[v/10 for v in a])
    def box(x0,x1,y0,y1,z0,z1):
        b=ac.OrientedBoundingBox3D.create(p([(x0+x1)/2,(y0+y1)/2,(z0+z1)/2]),ac.Vector3D.create(1,0,0),ac.Vector3D.create(0,1,0),(x1-x0)/10,(y1-y0)/10,(z1-z0)/10)
        return manager.createBox(b)
    def boolean(a,b,operation):
        if not manager.booleanOperation(a,b,operation):raise RuntimeError('Source vent repair Boolean failed')
        return a
    def screen(b):
        m=ac.Matrix3D.create();m.setWithArray([1,0,0,-.447505,0,q,-q,-3.9,0,q,q,2.1153,0,0,0,1]);manager.transform(b,m);return b
    def slab(v0,v1):return screen(box(-50,140,v0,v1,-100,100))
    outer_y=10.428062731907062;inner_y=outer_y-2
    n0=section-math.sqrt(2)*(outer_y+39);n1=section-math.sqrt(2)*(inner_y+39)
    a=boolean(box(8,65,inner_y,outer_y,0,70),slab(section-4,section),af.BooleanTypes.IntersectionBooleanType)
    b=screen(box(12.47505,69.47505,section,section+extra,n0,n1))
    c=boolean(box(8,65,inner_y+extra*q,outer_y+extra*q,0,75),slab(section+extra,section+extra+5.5),af.BooleanTypes.IntersectionBooleanType)
    for patch in [a,b,c]:boolean(lower,patch,af.BooleanTypes.UnionBooleanType)
    vents=[];seen=set()
    for face in source.faces:
        cylinder=ac.Cylinder.cast(face.geometry)
        if not cylinder or abs(cylinder.axis.z)<.99 or not .5<cylinder.radius*10<.7:continue
        o=cylinder.origin;x0=o.x*10+36.12495;z=o.y*10+16.45525253169416
        if not 25<z<40:continue
        x=36.12495+(x0-36.12495)*91.5/88.5
        if q*(outer_y+39+z-21.153)>section:z+=extra*q
        key=(round(x,4),round(z,4))
        if key in seen:continue
        seen.add(key);vents.append([x,z,cylinder.radius*10])
        tool=manager.createCylinderOrCone(p([x,6,z]),cylinder.radius,p([x,outer_y+extra*q+1,z]),cylinder.radius)
        boolean(lower,tool,af.BooleanTypes.DifferenceBooleanType)
    if lower.lumps.count!=1:raise RuntimeError('Source lower vent repair disconnected')
    return lower,vents

def build(ctx,docid,args):
    import fusion_ops as ops
    manager=af.TemporaryBRepManager.get();root=ctx['documents'][docid]['design'].rootComponent
    source=ctx['bodies'][args['original_lower_source_id']]['body']
    lower,vents=repair(manager,manager.copy(ctx['bodies'][args['lower_source_id']]['body']),source,float(args.get('screen_extension_v_mm',13.5)))
    body=root.bRepBodies.add(lower);body.name='A4 Lower R4 - original joint and round vents'
    body.appearance=ctx['documents'][docid]['design'].appearances.addByCopy(source.appearance,'Original lower appearance')
    return {'bodies':[ops._summary(ctx,docid,body)],'round_vent_bores_mm':vents,'vent_count':len(vents),'original_source_pattern':True}
