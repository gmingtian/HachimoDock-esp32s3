"""Replace only the two shell meshes in the supplied P1S two-plate project.

Keeps original printer/material/process settings, six small-part object files,
extruders, plate membership and XY layout. Updates Z grounding and thumbnails.
Does not generate G-code, slice, upload or print.
"""
import hashlib
import io
import json
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET
import numpy as np
import trimesh
from PIL import Image
from explore_geometry import ROOT,OUT,load,render
from build_enclosure import OUT
from inspect_3mf import C,P,matrix,readmesh

ET.register_namespace('',C[1:-1])
ET.register_namespace('p',P[1:-1])
ET.register_namespace('BambuStudio','http://schemas.bambulab.com/package/2021')

def textmatrix(m):return ' '.join(f'{n:.12g}' for n in m[:3,:].T.reshape(-1))
def xml(root):return ET.tostring(root,encoding='utf-8',xml_declaration=True)

def meshxml(data,m):
    root,obj,_=readmesh(data)
    old=obj.find(C+'mesh');obj.remove(old)
    body=ET.SubElement(obj,C+'mesh');verts=ET.SubElement(body,C+'vertices');tris=ET.SubElement(body,C+'triangles')
    for v in m.vertices:ET.SubElement(verts,C+'vertex',{k:f'{v[i]:.9g}' for i,k in enumerate(['x','y','z'])})
    for f in m.faces:ET.SubElement(tris,C+'triangle',{k:str(int(f[i])) for i,k in enumerate(['v1','v2','v3'])})
    return xml(root)

def thumb(path,size):
    with Image.open(path) as im:
        im.thumbnail(size)
        canvas=Image.new('RGB',size,(240,242,247));canvas.paste(im,((size[0]-im.width)//2,(size[1]-im.height)//2))
        b=io.BytesIO();canvas.save(b,format='PNG');return b.getvalue()

def main():
    source=ROOT/'reference/user-p1s-white-orange-two-plates.3mf'
    target=OUT/'HachimoDock-A4-R1-P1S-white-orange-two-plates.3mf'
    with zipfile.ZipFile(source) as z:data={name:z.read(name) for name in z.namelist()}
    originals=dict(data)
    main=ET.fromstring(data['3D/3dmodel.model'])
    settings=ET.fromstring(data['Metadata/model_settings.config'])
    refs={obj.get('id'):obj for obj in main.find(C+'resources')}
    build={item.get('objectid'):item for item in main.find(C+'build')}
    counts={};positions={}
    for objid,solidindex,filename in [('2',0,'a4-upper-r1-assembly.stl'),('4',1,'a4-lower-r1-assembly.stl')]:
        comp=refs[objid].find(f'{C}components/{C}component');path=comp.get(P+'path').lstrip('/')
        physical=trimesh.load_mesh(OUT/filename)
        # Restore the original, centered source axes before retaining its component rotation.
        center=load(solidindex).bounds.mean(axis=0)
        inverse=np.array([[1,0,0,-center[0]],[0,0,1,-center[2]],[0,-1,0,center[1]],[0,0,0,1]],float)
        raw=physical.copy();raw.apply_transform(inverse)
        data[path]=meshxml(data[path],raw)
        placed=raw.copy();placed.apply_transform(matrix(comp.get('transform')))
        item=build[objid];placement=matrix(item.get('transform'));placed.apply_transform(placement)
        dz=-float(placed.bounds[0,2]);placement[2,3]+=dz
        item.set('transform',textmatrix(placement))
        placed.apply_translation([0,0,dz]);positions[objid]=placed.bounds.tolist()
        counts[objid]=len(raw.faces)
        setting=next(o for o in settings.findall('object') if o.get('id')==objid)
        name=setting.find("metadata[@key='name']");name.set('value',name.get('value')+' A4 R1')
        part=setting.find('part');part.find("metadata[@key='source_file']").set('value',filename)
        for element in setting.iter():
            if 'face_count' in element.attrib:element.set('face_count',str(len(raw.faces)))
        for assembled in settings.findall('assemble/assemble_item'):
            if assembled.get('object_id')==objid and assembled.get('instance_id')=='0':assembled.set('transform',textmatrix(placement))
    for meta in main.findall(C+'metadata'):
        if meta.get('name')=='ModificationDate':meta.text='2026-11-07'
        if meta.get('name')=='Title':meta.text='HachimoDock A4 R1 engineering fit draft'
        if meta.get('name')=='Description':meta.text='A4 carrier fit draft. Re-slice and inspect. Not physically verified.'

    # Drop obsolete slicer picking maps. Recreate photographic thumbnails from actual meshes.
    for plate in settings.findall('plate'):
        for meta in list(plate.findall('metadata')):
            if meta.get('key') in ['top_file','pick_file']:plate.remove(meta)
            if meta.get('key')=='plater_name':meta.set('value',meta.get('value')+' - A4 R1 试装')
    for name in list(data):
        if name.startswith('Metadata/top_') or name.startswith('Metadata/pick_'):del data[name]
    data['3D/3dmodel.model']=xml(main)
    data['Metadata/model_settings.config']=xml(settings)
    scenes={1:[],2:[]};placed_meshes={}
    for id,obj in refs.items():
        comp=obj.find(f'{C}components/{C}component');path=comp.get(P+'path').lstrip('/')
        _,_,m=readmesh(data[path]);m.apply_transform(matrix(comp.get('transform')));m.apply_transform(matrix(build[id].get('transform')))
        assert m.is_watertight and m.is_winding_consistent and m.bounds[0,2]>-.0001,(id,m.bounds.tolist())
        placed_meshes[id]=m
        plate=1 if id=='2' else 2
        display=m.copy();display.apply_translation([-(0 if plate==1 else 307.2),0,0])
        color=(.94,.94,.91) if id in ['2','4','12'] else (.97,.35,.075)
        scenes[plate].append((display,color))
    for p,scene in scenes.items():
        path=OUT/f'p1s-plate-{p}-r1.png';render(scene,path,camera=(170,-180,160))
        for name in [f'Metadata/plate_{p}.png',f'Metadata/plate_{p}_small.png',f'Metadata/plate_no_light_{p}.png']:
            old=Image.open(io.BytesIO(originals[name]));data[name]=thumb(path,old.size)
    assert data['Metadata/project_settings.config']==originals['Metadata/project_settings.config']
    preserved=[p for p in originals if p.startswith('3D/Objects/') and p not in [refs[i].find(f'{C}components/{C}component').get(P+'path').lstrip('/') for i in ['2','4']]]
    assert all(data[p]==originals[p] for p in preserved)
    # No overlap between separate items on the same plate. Bounds are only a broad phase.
    clashes=[]
    from build_enclosure import solid
    ids=list(placed_meshes)
    for aidx,a in enumerate(ids):
        for b in ids[aidx+1:]:
            if ('2' in [a,b]):continue
            ma,mb=placed_meshes[a],placed_meshes[b]
            if np.all(ma.bounds[0]<mb.bounds[1]) and np.all(mb.bounds[0]<ma.bounds[1]):
                overlap=(solid(ma)^solid(mb)).volume()
                if overlap>.02:clashes.append([a,b,overlap])
    assert not clashes,clashes
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,content in data.items():z.writestr(name,content)
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        for name in ['3D/3dmodel.model','Metadata/model_settings.config']:ET.fromstring(z.read(name))
    report={
        'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'outputSha256':hashlib.sha256(target.read_bytes()).hexdigest(),
        'changedShellObjectIds':['2','4'],'shellFaceCounts':counts,
        'printerAndMaterialProcessSettingsByteIdentical':True,
        'preservedSmallPartFilesByteIdentical':preserved,
        'plateCount':2,'allObjectsOnBed':True,'samePlateObjectClashes':clashes,
        'updatedShellWorldBounds':positions,
        'bambuStudioOpened':False,'sliced':False,'sentToPrinter':False,
        'note':'Unsliced engineering fit draft; printer/settings preserved from supplied project.'
    }
    (OUT/'3mf-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
