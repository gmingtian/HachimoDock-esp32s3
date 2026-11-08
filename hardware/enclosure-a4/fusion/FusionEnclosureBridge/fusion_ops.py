"""Native Fusion operations; JSON supplies data, never executable code.

Only documents created by this bridge can be edited. STEP references are
read-only. Inputs and reports use mm; Fusion native geometry uses cm.
"""
import math
import importlib.util
from pathlib import Path
import adsk.core
import adsk.fusion
from bridge_protocol import mm_to_cm,point_cm,matrix_cm,within_root

def _p(values):return adsk.core.Point3D.create(*point_cm(values))
def _xyz(point):return [point.x*10,point.y*10,point.z*10]
def _box(body):return [_xyz(body.boundingBox.minPoint),_xyz(body.boundingBox.maxPoint)]

def _matrix(values):
    m=adsk.core.Matrix3D.create()
    if not m.setWithArray(matrix_cm(values)):raise RuntimeError('Fusion rejected the rigid transform')
    return m

def _document(ctx,id,edit=False):
    if id not in ctx['documents']:raise ValueError('Unknown bridge document; import or create one first')
    doc=ctx['documents'][id]
    if not doc['document'].isValid:raise RuntimeError('Document was closed')
    if edit and doc['read_only']:raise ValueError('Reference document is read-only; copy the body to a new working document')
    return doc

def _body(ctx,id,edit=False):
    if id not in ctx['bodies']:raise ValueError('Unknown body ID; inspect the document first')
    record=ctx['bodies'][id];_document(ctx,record['design_id'],edit)
    if not record['body'].isValid:raise RuntimeError('Body changed or was removed; inspect again')
    return record

def _remember(ctx,docid,body):
    token=body.entityToken
    for id,record in ctx['bodies'].items():
        if record['design_id']==docid and record.get('token')==token and record['body'].isValid:return id
    id='b'+str(len(ctx['bodies'])+1).zfill(4)
    ctx['bodies'][id]={'design_id':docid,'body':body,'token':token}
    return id

def _summary(ctx,docid,body,faces=False,edges=False):
    result={'body_id':_remember(ctx,docid,body),'name':body.name,'solid':body.isSolid,'volume_mm3':body.volume*1000,'area_mm2':body.area*100,'bounds_mm':_box(body),'face_count':body.faces.count,'edge_count':body.edges.count,'lump_count':body.lumps.count}
    if faces:
        result['faces']=[]
        for i in range(body.faces.count):
            face=body.faces.item(i);g=face.geometry
            cylinder=adsk.core.Cylinder.cast(g);plane=adsk.core.Plane.cast(g)
            if faces=='cylinders' and not cylinder:continue
            row={'index':i,'type':g.objectType,'area_mm2':face.area*100}
            if faces=='samples':row.update(bounds_mm=_box(face),sample_points_mm=[_xyz(e.pointOnEdge) for e in face.edges]+[_xyz(v.geometry) for v in face.vertices])
            if cylinder:row.update(radius_mm=cylinder.radius*10,origin_mm=_xyz(cylinder.origin),axis=[cylinder.axis.x,cylinder.axis.y,cylinder.axis.z])
            elif plane:row.update(origin_mm=_xyz(plane.origin),normal=[plane.normal.x,plane.normal.y,plane.normal.z])
            result['faces'].append(row)
    if edges:
        result['edges']=[]
        for i in range(body.edges.count):
            edge=body.edges.item(i)
            result['edges'].append({'index':i,'type':edge.geometry.objectType,'length_mm':edge.length*10,'point_mm':_xyz(edge.pointOnEdge),'bounds_mm':_box(edge)})
    return result

def _inspect(ctx,id,faces=False,edges=False):
    doc=_document(ctx,id);root=doc['design'].rootComponent;bodies=[]
    for i in range(root.bRepBodies.count):bodies.append(_summary(ctx,id,root.bRepBodies.item(i),faces,edges))
    for i in range(root.allOccurrences.count):
        occ=root.allOccurrences.item(i)
        for j in range(occ.bRepBodies.count):
            row=_summary(ctx,id,occ.bRepBodies.item(j),faces,edges);row['occurrence']=occ.fullPathName;bodies.append(row)
    return {'design_id':id,'document':doc['document'].name,'read_only':doc['read_only'],'bodies':bodies}

def _register_document(ctx,doc,read_only):
    design=adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
    if not design:raise RuntimeError('Fusion did not return a design product')
    id='d'+str(len(ctx['documents'])+1).zfill(4)
    ctx['documents'][id]={'document':doc,'design':design,'read_only':read_only}
    return id

def _add(ctx,docid,temporary,name):
    doc=_document(ctx,docid,True)
    if not temporary or not temporary.isSolid:raise RuntimeError('Native operation did not produce a closed solid')
    body=doc['design'].rootComponent.bRepBodies.add(temporary)
    if not body:raise RuntimeError('Could not add native body')
    body.name=str(name)
    return _summary(ctx,docid,body)

def _replace(ctx,id,temporary):
    old=_body(ctx,id,True);doc=_document(ctx,old['design_id'],True)
    if not temporary or not temporary.isSolid:raise RuntimeError('Result is not a closed solid; original body retained')
    original=old['body'];name=original.name
    new=doc['design'].rootComponent.bRepBodies.add(temporary)
    if not new:raise RuntimeError('Failed to add result; original body retained')
    new.name=name
    if not original.deleteMe():
        new.deleteMe();raise RuntimeError('Could not replace original body')
    old.update(body=new,token=new.entityToken)
    return _summary(ctx,old['design_id'],new)

def dispatch(ctx,op,args):
    app=ctx['app'];manager=adsk.fusion.TemporaryBRepManager.get()
    if op=='ping':
        if args.get('close_unused_bridge_documents'):
            keep=set(args.get('keep_design_ids',[]));closed=[]
            if not keep:raise ValueError('At least the current working design must be retained')
            for docid,record in list(ctx['documents'].items()):
                doc=record['document']
                if docid in keep or record['read_only'] or not doc.isValid:continue
                name=doc.name
                if not doc.close(False):raise RuntimeError('Could not close bridge scratch document '+docid)
                closed.append({'design_id':docid,'name':name})
            return {'closed_bridge_scratch_documents':closed,'kept_design_ids':list(keep),'remaining_document_count':app.documents.count}
        if args.get('end_orbit') and app.userInterface.activeCommand=='OrbitCommand':
            app.userInterface.commandDefinitions.itemById('SelectCommand').execute()
        return {'connected':True,'session_id':ctx['session'],'fusion_version':app.version,'document_count':app.documents.count,'active_document':app.activeDocument.name if app.activeDocument else None,'active_command':app.userInterface.activeCommand,'internal_length_unit':'cm','interface_length_unit':'mm'}
    if op=='import_step':
        path=within_root(args['path'],ctx['workspace'])
        if path.suffix.lower() not in ['.step','.stp'] or not path.is_file():raise ValueError('Expected an existing workspace STEP file')
        options=app.importManager.createSTEPImportOptions(str(path));options.isViewFit=True
        doc=app.importManager.importToNewDocument(options)
        if not doc:raise RuntimeError('STEP import failed')
        return _inspect(ctx,_register_document(ctx,doc,True),faces='cylinders')
    if op=='new_document':
        doc=app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        id=_register_document(ctx,doc,False)
        design=ctx['documents'][id]['design'];design.designType=adsk.fusion.DesignTypes.DirectDesignType
        design.unitsManager.distanceDisplayUnits=adsk.fusion.DistanceUnits.MillimeterDistanceUnits
        if args.get('template'):
            templates={'enclosure_r2':'native_enclosure.py','enclosure_r3':'native_original.py','original_clone':'clone_baseline.py','enclosure_r4':'native_clone.py','repair_clone_vents':'repair_clone_vents.py','fit_trial_r4':'fit_trial.py','hachimo_inset':'engrave_wordmark.py','speaker_slot':'speaker_slot.py'}
            if args['template'] not in templates:raise ValueError('Unknown document template')
            if args['template'] in ['enclosure_r3','enclosure_r4']:
                ctx['output']=Path(__file__).resolve().parents[2]/('output/r4-original-copy' if args['template']=='enclosure_r4' else 'output/r3-original')
                ctx['output'].mkdir(parents=True,exist_ok=True)
                from bridge_protocol import atomic_json
                status_path=Path(__file__).resolve().parents[1]/'io/status.json'
                import json
                status=json.loads(status_path.read_text(encoding='utf-8'));status['output_directory']=str(ctx['output']);atomic_json(status_path,status)
            spec=importlib.util.spec_from_file_location('native_enclosure',Path(__file__).with_name(templates[args['template']]))
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            result=module.build(ctx,id,args)
            result['design_id']=id
            return result
        return _inspect(ctx,id)
    if op=='inspect':
        if args.get('interference_ids'):
            records=[_body(ctx,i) for i in args['interference_ids']]
            if len({r['design_id'] for r in records})!=1:raise ValueError('Interference bodies must share a document')
            design=_document(ctx,records[0]['design_id'])['design'];collection=adsk.core.ObjectCollection.create()
            for record in records:collection.add(record['body'])
            input=design.createInterferenceInput(collection);input.areCoincidentFacesIncluded=False
            results=design.analyzeInterference(input)
            if results is None:return {'method':'Fusion analyzeInterference','coincident_faces_included':False,'returned_none':True,'count':None,'intersection_mm3':None}
            return {'method':'Fusion analyzeInterference','coincident_faces_included':False,'count':results.count,'intersection_mm3':sum(results.item(i).interferenceBody.volume*1000 for i in range(results.count))}
        if args.get('face_index') is not None:
            body=_body(ctx,args['body_id'])['body'];face=body.faces.item(args['face_index'])
            return {'index':args['face_index'],'bounds_mm':_box(face),'loops':[{'outer':loop.isOuter,'edges':[{'type':e.geometry.objectType,'start_mm':_xyz(e.startVertex.geometry),'end_mm':_xyz(e.endVertex.geometry),'mid_mm':_xyz(e.pointOnEdge),'bounds_mm':_box(e)} for e in loop.edges]} for loop in face.loops]}
        if args.get('intersection_ids'):
            one,two=[_body(ctx,i)['body'] for i in args['intersection_ids']]
            temporary=manager.copy(one)
            if not manager.booleanOperation(temporary,manager.copy(two),adsk.fusion.BooleanTypes.IntersectionBooleanType):raise RuntimeError('Intersection inspection failed')
            return {'intersection_mm3':temporary.volume*1000,'lump_count':temporary.lumps.count}
        if args.get('body_id'):
            record=_body(ctx,args['body_id'])
            return _summary(ctx,record['design_id'],record['body'],args.get('faces',False),args.get('edges',False))
        return _inspect(ctx,args['design_id'],args.get('faces',False),args.get('edges',False))
    if op=='copy_body':
        source=_body(ctx,args['body_id']);target=_document(ctx,args['to_design_id'],True)
        temporary=manager.copy(source['body'])
        if args.get('matrix_mm') and not manager.transform(temporary,_matrix(args['matrix_mm'])):raise RuntimeError('Copy transform failed')
        result=_add(ctx,args['to_design_id'],temporary,args.get('name',source['body'].name))
        if args.get('copy_appearance'):
            appearance_source=_body(ctx,args.get('appearance_source_body_id',args['body_id']))
            appearance=target['design'].appearances.addByCopy(appearance_source['body'].appearance,'Original appearance '+result['body_id'])
            _body(ctx,result['body_id'])['body'].appearance=appearance
        return result
    if op=='cylinder':
        _document(ctx,args['design_id'],True)
        radius=mm_to_cm(args['radius_mm']);radius2=mm_to_cm(args.get('radius2_mm',args['radius_mm']))
        if radius<=0 or radius2<0:raise ValueError('Invalid cylinder/cone radius')
        one,two=_p(args['start_mm']),_p(args['end_mm'])
        if one.distanceTo(two)<1e-6:raise ValueError('Cylinder axis must have length')
        return _add(ctx,args['design_id'],manager.createCylinderOrCone(one,radius,two,radius2),args.get('name','RoundPost'))
    if op=='box':
        _document(ctx,args['design_id'],True)
        lo,hi=point_cm(args['min_mm']),point_cm(args['max_mm']);size=[hi[i]-lo[i] for i in range(3)]
        if min(size)<=0:raise ValueError('Box dimensions must be positive')
        center=adsk.core.Point3D.create(*[(lo[i]+hi[i])/2 for i in range(3)])
        bounds=adsk.core.OrientedBoundingBox3D.create(center,adsk.core.Vector3D.create(1,0,0),adsk.core.Vector3D.create(0,1,0),*size)
        return _add(ctx,args['design_id'],manager.createBox(bounds),args.get('name','ConstructionBox'))
    if op=='combine':
        record=_body(ctx,args['target_id'],True)
        kinds={'join':adsk.fusion.BooleanTypes.UnionBooleanType,'cut':adsk.fusion.BooleanTypes.DifferenceBooleanType,'intersect':adsk.fusion.BooleanTypes.IntersectionBooleanType}
        if args.get('operation') not in kinds:raise ValueError('Invalid Boolean operation')
        tools=args.get('tool_ids',[])
        if not tools or args['target_id'] in tools:raise ValueError('Expected distinct tool bodies')
        if args.get('consume_tools',False):
            for id in tools:
                tool=_body(ctx,id,True)
                if tool['design_id']!=record['design_id']:raise ValueError('Cannot consume a tool from another document')
        temporary=manager.copy(record['body'])
        for id in tools:
            tool=_body(ctx,id)
            if not manager.booleanOperation(temporary,manager.copy(tool['body']),kinds[args['operation']]):raise RuntimeError('Native Boolean failed; original target retained')
        result=_replace(ctx,args['target_id'],temporary)
        if args.get('consume_tools',False):
            for id in tools:
                tool=_body(ctx,id,True)
                tool['body'].deleteMe()
        return result
    if op=='transform':
        if args.get('face_indices'):
            record=_body(ctx,args['body_id'],True);doc=_document(ctx,record['design_id'],True);doc['document'].activate()
            collection=adsk.core.ObjectCollection.create()
            for index in args['face_indices']:
                if isinstance(index,bool) or not isinstance(index,int) or not 0<=index<record['body'].faces.count:raise ValueError('Invalid face index')
                collection.add(record['body'].faces.item(index))
            input=doc['design'].rootComponent.features.moveFeatures.createInput2(collection)
            if not input.defineAsFreeMove(_matrix(args['matrix_mm'])):raise RuntimeError('Could not define face move')
            doc['design'].rootComponent.features.moveFeatures.add(input)
            return _summary(ctx,record['design_id'],record['body'],faces=True)
        record=_body(ctx,args['body_id'],True);temporary=manager.copy(record['body'])
        if not manager.transform(temporary,_matrix(args['matrix_mm'])):raise RuntimeError('Rigid transform failed')
        return _replace(ctx,args['body_id'],temporary)
    if op=='fillet':
        record=_body(ctx,args['body_id'],True);doc=_document(ctx,record['design_id'],True);doc['document'].activate()
        body=record['body'];collection=adsk.core.ObjectCollection.create()
        for index in args['edge_indices']:
            if isinstance(index,bool) or not isinstance(index,int) or not 0<=index<body.edges.count:raise ValueError('Invalid edge index; inspect the current body first')
            collection.add(body.edges.item(index))
        if not collection.count:raise ValueError('Fillet requires edges')
        radius=mm_to_cm(args['radius_mm'])
        if radius<=0:raise ValueError('Fillet radius must be positive')
        fillets=doc['design'].rootComponent.features.filletFeatures;input=fillets.createInput()
        input.edgeSetInputs.addConstantRadiusEdgeSet(collection,adsk.core.ValueInput.createByReal(radius),bool(args.get('tangent_chain',True)))
        feature=fillets.add(input)
        if not feature:raise RuntimeError('Fusion could not build this fillet')
        return _summary(ctx,record['design_id'],body,edges=True)
    if op=='export_stl':
        record=_body(ctx,args['body_id']);doc=_document(ctx,record['design_id'])
        path=within_root(args['path'],ctx['output'])
        if path.suffix.lower()!='.stl':raise ValueError('Expected an STL destination')
        path.parent.mkdir(parents=True,exist_ok=True)
        doc['document'].activate()
        was_visible=record['body'].isLightBulbOn;record['body'].isLightBulbOn=True
        app.activeViewport.refresh()
        options=doc['design'].exportManager.createSTLExportOptions(record['body'],str(path))
        options.isBinaryFormat=True;options.sendToPrintUtility=False
        options.unitType=adsk.fusion.DistanceUnits.MillimeterDistanceUnits
        options.meshRefinement=adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
        if args.get('surface_deviation_mm') is not None:
            deviation=mm_to_cm(args['surface_deviation_mm'])
            if not .00001<=deviation<=.01:raise ValueError('Surface deviation must be between .0001 and .1 mm')
            options.surfaceDeviation=deviation
            if args.get('normal_deviation_deg') is not None:
                normal_degrees=float(args['normal_deviation_deg'])
                if not 1<=normal_degrees<=45:raise ValueError('Normal deviation must be 1 to 45 degrees')
                options.normalDeviation=math.radians(normal_degrees)
        if not doc['design'].exportManager.execute(options):raise RuntimeError('STL export failed')
        record['body'].isLightBulbOn=was_visible
        return {'path':str(path),'units':'mm','bytes':path.stat().st_size,'bounds_mm':_box(record['body']),'surface_deviation_mm':options.surfaceDeviation*10,'normal_deviation_api_value':options.normalDeviation}
    if op=='export_step':
        doc=_document(ctx,args['design_id']);path=within_root(args['path'],ctx['output'])
        if path.suffix.lower() not in ['.step','.stp']:raise ValueError('Expected STEP destination')
        path.parent.mkdir(parents=True,exist_ok=True)
        options=doc['design'].exportManager.createSTEPExportOptions(str(path),doc['design'].rootComponent)
        if not doc['design'].exportManager.execute(options):raise RuntimeError('STEP export failed')
        return {'path':str(path),'bytes':path.stat().st_size}
    if op=='snapshot':
        doc=_document(ctx,args['design_id']);doc['document'].activate()
        if 'show_only_ids' in args:
            wanted=set(args['show_only_ids'])
            for id,record in ctx['bodies'].items():
                if record['design_id']==args['design_id'] and record['body'].isValid:record['body'].isLightBulbOn=id in wanted
        if args.get('camera_mm'):
            eye,target=args['camera_mm'];camera=app.activeViewport.camera
            camera.eye=_p(eye);camera.target=_p(target)
            camera.upVector=adsk.core.Vector3D.create(0,0,1)
            camera.cameraType=adsk.core.CameraTypes.OrthographicCameraType
            camera.isSmoothTransition=False;app.activeViewport.camera=camera
        app.activeViewport.fit()
        path=within_root(args['path'],ctx['output'])
        if path.suffix.lower()!='.png':raise ValueError('Expected PNG destination')
        path.parent.mkdir(parents=True,exist_ok=True)
        if not app.activeViewport.saveAsImageFile(str(path),1600,1000):raise RuntimeError('Viewport capture failed')
        return {'path':str(path)}
    raise ValueError('Unsupported operation')
