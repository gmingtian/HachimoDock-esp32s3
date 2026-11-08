"""Widen the original rounded outer body while restoring fixed control voids."""
import adsk.core as ac
import adsk.fusion as af

def trim_scaled_joystick_lip(manager,body):
    """Remove only the raised, scaled lip beyond the original right mouth.

    The restored native outline ends at X74.87495. Nonuniform scaling leaves
    a 0.24 mm-high remnant outside that outline, on the otherwise flat deck.
    This stock is wholly above the original surface; it cannot alter the
    native joystick opening, its floor, or the widened outer side fillet.
    """
    lo=[74.87495,-64.19864,16.45525253169416]
    hi=[76.19,-49.89106,20.]
    box=ac.OrientedBoundingBox3D.create(
        ac.Point3D.create(*[(lo[i]+hi[i])/20 for i in range(3)]),
        ac.Vector3D.create(1,0,0),ac.Vector3D.create(0,1,0),
        *[(hi[i]-lo[i])/10 for i in range(3)])
    before=body.volume
    if not manager.booleanOperation(body,manager.createBox(box),af.BooleanTypes.DifferenceBooleanType):
        raise RuntimeError('Scaled joystick lip cleanup failed')
    return (before-body.volume)*1000

def widen(manager,root,original,extra_mm=3,height_scale=1):
    scale=(88.5+extra_mm)/88.5;center=36.12495
    scaled=manager.copy(original);matrix=ac.Matrix3D.create()
    matrix.setWithArray([scale,0,0,(1-scale)*center/10,0,1,0,0,0,0,height_scale,(1-height_scale)*(-2.2947474683058333)/10,0,0,0,1])
    try:success=manager.transform(scaled,matrix)
    except RuntimeError:success=False
    if not success:
        body=root.bRepBodies.add(manager.copy(original));entities=ac.ObjectCollection.create();entities.add(body)
        point_input=root.constructionPoints.createInput();point_input.setByPoint(ac.Point3D.create(center/10,0,0))
        point=root.constructionPoints.add(point_input)
        input=root.features.scaleFeatures.createInput(entities,point,ac.ValueInput.createByReal(1))
        if height_scale!=1:raise RuntimeError('Temporary affine transform required for raised screen')
        if not input.setToNonUniform(ac.ValueInput.createByReal(scale),ac.ValueInput.createByReal(1),ac.ValueInput.createByReal(1)):raise RuntimeError('Nonuniform body scale failed')
        root.features.scaleFeatures.add(input);scaled=manager.copy(body);body.deleteMe();point.deleteMe()
    if abs((scaled.boundingBox.maxPoint.x-scaled.boundingBox.minPoint.x)*10-(88.5+extra_mm))>.001:raise RuntimeError('Unexpected widened width')
    boolean_tolerance=.005

    loops=[]
    for face in original.faces:
        plane=ac.Plane.cast(face.geometry)
        if not plane or abs(abs(plane.normal.z)-1)>.0001:continue
        z=plane.origin.z*10
        if abs(z-10.75609)<.005 and face.loops.count==4:
            loops.extend(l for l in face.loops if l.isOuter)
        if abs(z-16.45525253169416)<.0001 and 190<face.area*100<210:
            loops.extend(l for l in face.loops if l.isOuter)
    if len(loops)!=2:raise RuntimeError('Expected original keyboard and joystick void outlines')
    for loop in loops:
        curves=[edge.geometry for edge in loop.edges]
        wire,_=manager.createWireFromCurves(curves)
        face_body=manager.createFaceFromPlanarWires([wire])
        bounds=face_body.boundingBox;cx=(bounds.minPoint.x+bounds.maxPoint.x)/2;cy=(bounds.minPoint.y+bounds.maxPoint.y)/2
        # The keyboard floor outline is narrower than its upper mouth.
        # Restore across BOTH mouths: a 0.2% margin left scaled cavity slivers
        # and a duplicate latch notch outside the replacement footprint.
        keyboard=abs(face_body.boundingBox.minPoint.z*10-10.75609)<.005
        sx,sy=(1.13,1.08) if keyboard else (1.002,1.002)
        expand=ac.Matrix3D.create();expand.setWithArray([sx,0,0,(1-sx)*cx,0,sy,0,(1-sy)*cy,0,0,1,0,0,0,0,1]);manager.transform(face_body,expand)
        z=face_body.boundingBox.minPoint.z
        shift=ac.Matrix3D.create();shift.translation=ac.Vector3D.create(0,0,-z)
        manager.transform(face_body,shift)
        surface=root.bRepBodies.add(face_body)
        feature=root.features.extrudeFeatures.addSimple(surface.faces.item(0),ac.ValueInput.createByReal(3),af.FeatureOperations.NewBodyFeatureOperation)
        stock=manager.copy(feature.bodies.item(0));feature.bodies.item(0).deleteMe();surface.deleteMe()
        lo=stock.boundingBox.minPoint.z
        shift.translation=ac.Vector3D.create(0,0,-lo);manager.transform(stock,shift)
        positive=manager.copy(stock)
        if not manager.booleanOperation(positive,manager.copy(original),af.BooleanTypes.IntersectionBooleanType):raise RuntimeError('Original control extraction failed')
        inset=manager.copy(stock);bounds=stock.boundingBox;cx=(bounds.minPoint.x+bounds.maxPoint.x)/2;cy=(bounds.minPoint.y+bounds.maxPoint.y)/2
        shrink=ac.Matrix3D.create();shrink.setWithArray([.9999,0,0,.0001*cx,0,.9999,0,.0001*cy,0,0,1,0,0,0,0,1]);manager.transform(inset,shrink)
        if not manager.booleanOperation(scaled,manager.copy(stock),af.BooleanTypes.UnionBooleanType):raise RuntimeError('Control region fill failed')
        if not manager.booleanOperation(stock,manager.copy(original),af.BooleanTypes.DifferenceBooleanType):raise RuntimeError('Original void extraction failed')
        if not manager.booleanOperation(scaled,stock,af.BooleanTypes.DifferenceBooleanType):raise RuntimeError('Original control void restoration failed')
    if abs(extra_mm-3)<.0001:
        trim_scaled_joystick_lip(manager,scaled)
    if height_scale!=1:
        # The screen may rise; the complete control deck and its outer rim
        # must stay at the original height, including material outside the
        # circular joystick hole. Keep the join behind the full cap sweep.
        flat=manager.copy(original)
        def stock(ymax):
            bounds=ac.OrientedBoundingBox3D.create(ac.Point3D.create(4,(-100+ymax)/20,1.75),ac.Vector3D.create(1,0,0),ac.Vector3D.create(0,1,0),12,(ymax+100)/10,4.5)
            return manager.createBox(bounds)
        positive=stock(-41.995)
        if not manager.booleanOperation(positive,flat,af.BooleanTypes.IntersectionBooleanType):raise RuntimeError('Control deck extraction failed')
        if not manager.booleanOperation(scaled,stock(-42),af.BooleanTypes.DifferenceBooleanType):raise RuntimeError('Raised control deck removal failed')
        if not manager.booleanOperation(scaled,positive,af.BooleanTypes.UnionBooleanType):raise RuntimeError('Original deck height restoration failed')
        # Blend the screen/deck join before acoustic holes divide its edge.
        body=root.bRepBodies.add(scaled)
        for label,radius,high in [('upper',2.5,True),('lower',.8,False)]:
            candidates=[]
            for edge in body.edges:
                b=edge.boundingBox
                if abs(b.minPoint.y*10+42)<.02 and abs(b.maxPoint.y*10+42)<.02 and edge.length*10>65 and abs(b.maxPoint.z-b.minPoint.z)<.0001:
                    candidates.append(edge)
            if not candidates:raise RuntimeError('Screen/deck blend edge not found: '+label)
            edge=(max if high else min)(candidates,key=lambda e:e.pointOnEdge.z)
            collection=ac.ObjectCollection.create();collection.add(edge)
            input=root.features.filletFeatures.createInput()
            input.edgeSetInputs.addConstantRadiusEdgeSet(collection,ac.ValueInput.createByReal(radius/10),True)
            root.features.filletFeatures.add(input)
        scaled=manager.copy(body);body.deleteMe()
    return scaled,boolean_tolerance
