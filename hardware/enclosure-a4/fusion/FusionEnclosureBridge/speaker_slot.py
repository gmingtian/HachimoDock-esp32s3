"""Simple 1.5 mm speaker locating frame on the inside of the rear vent grid."""
import math
import adsk.core as ac
import adsk.fusion as af


def apply(manager,lower,vents):
    columns=sorted(set(round(v[0],4) for v in vents))
    if len(columns)!=18:raise RuntimeError('Expected the original 18-column vent grid')
    cx=sum(v[0] for v in vents if abs(v[0]-columns[11])<.001)/3
    cz=(min(v[1] for v in vents)+max(v[1] for v in vents))/2
    grid_x=sum(v[0] for v in vents)/len(vents)
    planes=[]
    for face in lower.faces:
        plane=ac.Plane.cast(face.geometry);b=face.boundingBox
        if plane and abs(plane.normal.y)>.999 and b.minPoint.x*10<cx<b.maxPoint.x*10 and b.minPoint.z*10<cz<b.maxPoint.z*10:
            planes.append(plane.origin.y*10)
    if len(planes)<2:raise RuntimeError('Rear speaker mounting plane not found')
    y=min(planes);front=y-4.6
    def p(a):return ac.Point3D.create(*[v/10 for v in a])
    def box(a,b):
        v=ac.OrientedBoundingBox3D.create(p([(a[i]+b[i])/2 for i in range(3)]),ac.Vector3D.create(1,0,0),ac.Vector3D.create(0,1,0),*[(b[i]-a[i])/10 for i in range(3)])
        return manager.createBox(v)
    def boolean(a,b,kind):
        if not manager.booleanOperation(a,b,kind):raise RuntimeError('Speaker frame Boolean failed')
        return a
    # Hollow the separate frame completely before attaching it: a thin back
    # skin would fill the existing vent bores even though they looked open.
    frame=box([cx-11.7,front,cz-7.2],[cx+11.7,y+.2,cz+7.2])
    hollow=box([cx-10.2,front-.1,cz-5.7],[cx+10.2,y+.3,cz+5.7])
    boolean(frame,hollow,af.BooleanTypes.DifferenceBooleanType)
    port=box([cx+10.19,front-.1,cz],[cx+11.8,y+.3,cz+4])
    boolean(frame,port,af.BooleanTypes.DifferenceBooleanType)
    boolean(lower,frame,af.BooleanTypes.UnionBooleanType)
    # The vent panel is flat outside, with a small inner bend below the last
    # row. Flatten just the seat to a 1.995 mm back wall so the 11 mm body fits.
    pocket=box([cx-10.2,front-.1,cz-5.7],[cx+10.2,y+.005,cz+5.7])
    boolean(lower,pocket,af.BooleanTypes.DifferenceBooleanType)
    if lower.lumps.count!=1:raise RuntimeError('Speaker slot must be connected to lower case')
    return lower,{'speaker_mm':[20,11,4.35],'cavity_mm':[20.4,11.4,4.605],
        'wall_mm':1.5,'center_xz_mm':[cx,cz],'rear_inner_y_mm':y,
        'grid_center_x_mm':grid_x,'grid_right_shift_mm':cx-grid_x,
        'wire_port_mm':4,'wire_port_position':'right short side, upper half',
        'outer_xz_mm':[23.4,14.4],'rear_wall_minimum_mm':1.995,
        'retention':'locating slot only; no additional snap details requested'}


def build(ctx,docid,args):
    import fusion_ops as ops
    manager=af.TemporaryBRepManager.get();root=ctx['documents'][docid]['design'].rootComponent
    source=ctx['bodies'][args['lower_source_id']]['body']
    baseline=root.bRepBodies.add(manager.copy(source));baseline.name='Lower before speaker slot'
    lower,spec=apply(manager,manager.copy(source),args['rear_vent_bores_mm'])
    actual=root.bRepBodies.add(lower);actual.name='Full lower - speaker 20x11 - 1.5mm locating slot'
    actual.appearance=ctx['documents'][docid]['design'].appearances.addByCopy(source.appearance,'Speaker lower appearance')
    return {'bodies':[ops._summary(ctx,docid,actual)],'baseline':ops._summary(ctx,docid,baseline),'speaker_mount':spec}
