"""Retain the actual SPI17 mating interfaces in two open inspection shells."""
import math
import adsk.core as ac
import adsk.fusion as af


def build(ctx,docid,args):
    import fusion_ops as ops
    manager=af.TemporaryBRepManager.get()
    root=ctx['documents'][docid]['design'].rootComponent
    origin=args['screen_origin_mm'];q=math.sqrt(.5)
    def p(a):return ac.Point3D.create(*[v/10 for v in a])
    def box(a,b):
        dims=[(b[i]-a[i])/10 for i in range(3)]
        bounds=ac.OrientedBoundingBox3D.create(p([(a[i]+b[i])/2 for i in range(3)]),
            ac.Vector3D.create(1,0,0),ac.Vector3D.create(0,1,0),*dims)
        return manager.createBox(bounds)
    def screen(body):
        m=ac.Matrix3D.create();m.setWithArray([1,0,0,origin[0]/10,0,q,-q,origin[1]/10,0,q,q,origin[2]/10,0,0,0,1])
        if not manager.transform(body,m):raise RuntimeError('Trial mask transform failed')
        return body
    def sb(a,b):return screen(box(a,b))
    def join(a,b):
        if not manager.booleanOperation(a,b,af.BooleanTypes.UnionBooleanType):raise RuntimeError('Trial mask union failed')
        return a
    upper_masks=[
        box([-20,-90,-10],[90,-30,80]),
        box([-20,-90,-10],[-4.62505,30,80]),
        box([76.87495,-90,-10],[90,30,80]),
        box([-20,10,54],[90,30,80]),
        sb([5.45,.75,-1.8],[69.35,50.25,1]),
        sb([-7,-.3,-1.8],[87,6.3,1]),
        sb([-7,44.7,-1.8],[87,51.3,1]),
        sb([-6,11,-45],[12,41,-6]),
        box([-12,-31,12],[10,2,27]),
    ]
    for u in [3,78.2]:
        for v in [3,48]:
            upper_masks.append(screen(manager.createCylinderOrCone(p([u,v,-6.5]),.33,p([u,v,1.5]),.33)))
    lower_masks=[
        box([-10,-80,-5],[.55,30,65]),box([71.7,-80,-5],[85,30,65]),
        box([-10,-73,-5],[85,-65,7]),box([-10,5.4,-5],[85,11,6]),
        box([-10,-40.4,-5],[85,-31.7,7]),box([-10,-16.4,-5],[85,-7.6,7]),
        box([32.5,-73,-5],[39.6,11,7]),box([42.8,-46,-5],[49.2,-31,7]),
        box([-10,0,53],[85,25,65]),sb([-6,11,-45],[12,41,-6]),
        box([-12,-31,12],[10,2,27]),
    ]
    result=[]
    for key,label,masks in [('upper_source_id','upper',upper_masks),('lower_source_id','lower',lower_masks)]:
        source=ctx['bodies'][args[key]]['body']
        keep=masks[0]
        for b in masks[1:]:join(keep,b)
        body=manager.copy(source)
        if not manager.booleanOperation(body,keep,af.BooleanTypes.IntersectionBooleanType):raise RuntimeError('Trial crop failed '+label)
        if body.lumps.count!=1:raise RuntimeError('Trial must remain connected '+label+': '+str(body.lumps.count))
        actual=root.bRepBodies.add(body);actual.name='SPI17 fit trial '+label+' - inspection openings'
        actual.appearance=ctx['documents'][docid]['design'].appearances.addByCopy(source.appearance,'Trial '+label)
        result.append(ops._summary(ctx,docid,actual))
    return {'bodies':result,'source_design_id':args['source_design_id'],
            'screen_origin_mm':origin,'nominal_interfaces_unchanged':True,
            'inspection_openings_intentional':True,'physical_fit_verified':False}
