"""A single rounded wedge envelope; original controls restored without scaling."""
import math
import adsk.core as ac
import adsk.fusion as af

FLOOR=-2.2947474683058333
WIDTH=91.5
CENTER=36.12495

def profile(manager,root,vertices,radii,x,width,side_radius):
    def p(v):return ac.Point3D.create(x/10,v[0]/10,v[1]/10)
    corners=[]
    for i,b in enumerate(vertices):
        a=vertices[i-1];d=vertices[(i+1)%len(vertices)]
        incoming=[b[j]-a[j] for j in [0,1]];outgoing=[d[j]-b[j] for j in [0,1]]
        li=math.hypot(*incoming);lo=math.hypot(*outgoing)
        incoming=[v/li for v in incoming];outgoing=[v/lo for v in outgoing]
        turn=math.atan2(incoming[0]*outgoing[1]-incoming[1]*outgoing[0],sum(incoming[j]*outgoing[j] for j in [0,1]))
        radius=radii[i];distance=radius*math.tan(abs(turn)/2)
        if distance>min(li,lo)*.9:raise RuntimeError('Side profile fillet too large')
        start=[b[j]-incoming[j]*distance for j in [0,1]];end=[b[j]+outgoing[j]*distance for j in [0,1]]
        sign=1 if turn>0 else -1
        center=[start[0]-incoming[1]*radius*sign,start[1]+incoming[0]*radius*sign]
        vec=[start[j]-center[j] for j in [0,1]];half=turn/2
        mid=[center[0]+vec[0]*math.cos(half)-vec[1]*math.sin(half),center[1]+vec[0]*math.sin(half)+vec[1]*math.cos(half)]
        corners.append((start,mid,end))
    curves=[]
    for i,(start,mid,end) in enumerate(corners):
        curves.append(ac.Arc3D.createByThreePoints(p(start),p(mid),p(end)))
        curves.append(ac.Line3D.create(p(end),p(corners[(i+1)%len(corners)][0])))
    wire,_=manager.createWireFromCurves(curves)
    sheet=root.bRepBodies.add(manager.createFaceFromPlanarWires([wire]))
    feature=root.features.extrudeFeatures.addSimple(sheet.faces.item(0),ac.ValueInput.createByReal(width/10),af.FeatureOperations.NewBodyFeatureOperation)
    body=feature.bodies.item(0);sheet.deleteMe()
    # Face orientation is not assumed by the planar-wire API.
    shift=ac.Matrix3D.create();shift.translation=ac.Vector3D.create(x/10-body.boundingBox.minPoint.x,0,0)
    temporary=manager.copy(body);manager.transform(temporary,shift);body.deleteMe();body=root.bRepBodies.add(temporary)
    edges=ac.ObjectCollection.create()
    for edge in body.edges:
        bb=edge.boundingBox
        if abs(bb.maxPoint.x-bb.minPoint.x)<1e-7 and (abs(bb.minPoint.x*10-x)<.001 or abs(bb.minPoint.x*10-x-width)<.001):edges.add(edge)
    input=root.features.filletFeatures.createInput();input.edgeSetInputs.addConstantRadiusEdgeSet(edges,ac.ValueInput.createByReal(side_radius/10),False)
    root.features.filletFeatures.add(input)
    result=manager.copy(body);body.deleteMe();return result

def inset(vertices,amount):
    result=[]
    for i,b in enumerate(vertices):
        a=vertices[i-1];d=vertices[(i+1)%len(vertices)]
        u=[b[j]-a[j] for j in [0,1]];v=[d[j]-b[j] for j in [0,1]]
        lu=math.hypot(*u);lv=math.hypot(*v);u=[t/lu for t in u];v=[t/lv for t in v]
        p=[b[0]-u[1]*amount,b[1]+u[0]*amount];q=[b[0]-v[1]*amount,b[1]+v[0]*amount]
        cross=u[0]*v[1]-u[1]*v[0]
        t=((q[0]-p[0])*v[1]-(q[1]-p[1])*v[0])/cross
        result.append([p[j]+u[j]*t for j in [0,1]])
    return result

def restore_controls(manager,root,target,original,exterior_limit):
    loops=[]
    for face in original.faces:
        plane=ac.Plane.cast(face.geometry)
        if not plane or abs(abs(plane.normal.z)-1)>.0001:continue
        z=plane.origin.z*10
        if abs(z-10.75609)<.005 and face.loops.count==4:loops.extend(l for l in face.loops if l.isOuter)
        if abs(z-16.45525253169416)<.0001 and 190<face.area*100<210:loops.extend(l for l in face.loops if l.isOuter)
    if len(loops)!=2:raise RuntimeError('Original control contours not found')
    for loop in loops:
        wire,_=manager.createWireFromCurves([edge.geometry for edge in loop.edges]);face=manager.createFaceFromPlanarWires([wire])
        matrix=ac.Matrix3D.create();matrix.translation=ac.Vector3D.create(0,0,-face.boundingBox.minPoint.z);manager.transform(face,matrix)
        sheet=root.bRepBodies.add(face)
        feature=root.features.extrudeFeatures.addSimple(sheet.faces.item(0),ac.ValueInput.createByReal(3.3),af.FeatureOperations.NewBodyFeatureOperation)
        stock=manager.copy(feature.bodies.item(0));feature.bodies.item(0).deleteMe();sheet.deleteMe()
        matrix.translation=ac.Vector3D.create(0,0,-stock.boundingBox.minPoint.z);manager.transform(stock,matrix)
        positive=manager.copy(stock)
        if not manager.booleanOperation(positive,manager.copy(original),af.BooleanTypes.IntersectionBooleanType):raise RuntimeError('Original control copy failed')
        allowed=manager.copy(positive)
        limits=ac.OrientedBoundingBox3D.create(ac.Point3D.create(6.6,-6,2.4),ac.Vector3D.create(1,0,0),ac.Vector3D.create(0,1,0),2.4,2.6,1.509)
        if not manager.booleanOperation(allowed,manager.createBox(limits),af.BooleanTypes.IntersectionBooleanType):raise RuntimeError('Original joystick rim extraction failed')
        if allowed.lumps.count and not manager.booleanOperation(exterior_limit,allowed,af.BooleanTypes.UnionBooleanType):raise RuntimeError('Original control rim envelope failed')
        # Fill the pocket stock, then remove the original negative space.
        # This keeps substantial overlap throughout the Boolean operation;
        # joining thin copied walls onto coincident outer fillets is fragile.
        filled=manager.copy(stock)
        if not manager.booleanOperation(filled,manager.copy(exterior_limit),af.BooleanTypes.IntersectionBooleanType):raise RuntimeError('Control stock envelope trim failed')
        if not manager.booleanOperation(target,filled,af.BooleanTypes.UnionBooleanType):raise RuntimeError('Control stock fill failed')
        if not manager.booleanOperation(stock,manager.copy(original),af.BooleanTypes.DifferenceBooleanType):raise RuntimeError('Original control void failed')
        if not manager.booleanOperation(target,stock,af.BooleanTypes.DifferenceBooleanType):raise RuntimeError('Control opening restoration failed')
    return target

def envelope(manager,root,original,origin,angle):
    slope=math.tan(angle);deck=16.45525253169416;top=71.07348450357591
    intercept=origin[2]-slope*origin[1]
    front=-76.19864;rear=11.759990946220142
    vertices=[[front,FLOOR],[rear,FLOOR],[rear,top],[(top-intercept)/slope,top],[(deck-intercept)/slope,deck],[front,deck]]
    radii=[7,7,7,7,8,7]
    outer=profile(manager,root,vertices,radii,CENTER-WIDTH/2,WIDTH,6.5)
    untouched_outer=manager.copy(outer)
    inside=inset(vertices,2)
    inner=profile(manager,root,inside,[5,5,5,5,10,5],CENTER-WIDTH/2+2,WIDTH-4,4.5)
    def offset_solid(amount):
        return profile(manager,root,inset(vertices,amount),[7-amount]*4+[8+amount,7-amount],CENTER-WIDTH/2+amount,WIDTH-2*amount,6.5-amount)
    tongue=offset_solid(1.8)
    if not manager.booleanOperation(tongue,offset_solid(3.1),af.BooleanTypes.DifferenceBooleanType):raise RuntimeError('Mating tongue section failed')
    groove=offset_solid(1.5)
    if not manager.booleanOperation(groove,offset_solid(3.4),af.BooleanTypes.DifferenceBooleanType):raise RuntimeError('Mating groove section failed')
    if not manager.booleanOperation(outer,inner,af.BooleanTypes.DifferenceBooleanType):raise RuntimeError('Continuous shell hollowing failed')
    return restore_controls(manager,root,outer,original,untouched_outer),untouched_outer,tongue,groove

def control_pocket(manager,root,original):
    for face in original.faces:
        plane=ac.Plane.cast(face.geometry)
        if plane and abs(abs(plane.normal.z)-1)<.0001 and abs(plane.origin.z*10-10.75609)<.005 and face.loops.count==4:
            loop=next(l for l in face.loops if l.isOuter)
            wire,_=manager.createWireFromCurves([edge.geometry for edge in loop.edges])
            sheet=root.bRepBodies.add(manager.createFaceFromPlanarWires([wire]))
            feature=root.features.extrudeFeatures.addSimple(sheet.faces.item(0),ac.ValueInput.createByReal(3),af.FeatureOperations.NewBodyFeatureOperation)
            body=feature.bodies.item(0);tool=manager.copy(body);body.deleteMe();sheet.deleteMe()
            shift=ac.Matrix3D.create();shift.translation=ac.Vector3D.create(0,0,(10.78/10)-tool.boundingBox.minPoint.z);manager.transform(tool,shift)
            return tool
    raise RuntimeError('Original key trough floor not found')
