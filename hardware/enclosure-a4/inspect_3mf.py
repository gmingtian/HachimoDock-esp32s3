from pathlib import Path
import json
import zipfile
import xml.etree.ElementTree as ET
import numpy as np
import trimesh

ROOT=Path(__file__).resolve().parent
C='{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}'
P='{http://schemas.microsoft.com/3dmanufacturing/production/2015/06}'

def matrix(text):
    a=np.array([float(v) for v in text.split()]).reshape(4,3)
    m=np.eye(4);m[:3,:]=a.T
    return m

def readmesh(data):
    root=ET.fromstring(data)
    obj=root.find(f'{C}resources/{C}object')
    m=obj.find(f'{C}mesh')
    vertices=np.array([[float(v.get(k)) for k in ['x','y','z']] for v in m.find(f'{C}vertices')])
    faces=np.array([[int(t.get(k)) for k in ['v1','v2','v3']] for t in m.find(f'{C}triangles')])
    return root,obj,trimesh.Trimesh(vertices,faces,process=True)

if __name__=='__main__':
    src=ROOT/'reference/user-p1s-white-orange-two-plates.3mf'
    out=ROOT/'reference/user-3mf-inspection';out.mkdir(exist_ok=True)
    report={}
    with zipfile.ZipFile(src) as z:
        main=ET.fromstring(z.read('3D/3dmodel.model'))
        settings=ET.fromstring(z.read('Metadata/model_settings.config'))
        project=json.loads(z.read('Metadata/project_settings.config'))
        report['project']={k:project.get(k) for k in ['printer_model','printer_settings_id','print_settings_id','filament_colour','filament_type','filament_settings_id','nozzle_diameter','layer_height']}
        for obj in main.find(f'{C}resources'):
            id=obj.get('id');comp=obj.find(f'{C}components/{C}component');path=comp.get(P+'path').lstrip('/')
            _,_,m=readmesh(z.read(path))
            source_bounds=m.bounds.tolist()
            mc=m.copy();mc.apply_transform(matrix(comp.get('transform')))
            item=next(i for i in main.find(f'{C}build') if i.get('objectid')==id)
            mc.apply_transform(matrix(item.get('transform')))
            name=next(o for o in settings.findall('object') if o.get('id')==id).find("metadata[@key='name']").get('value')
            report[id]={'name':name,'path':path,'raw_bounds':source_bounds,'placed_bounds':mc.bounds.tolist(),'source_volume':m.volume,'triangles':len(m.faces),'watertight':m.is_watertight}
            m.export(out/f'object-{id}.stl')
        for p in ['Metadata/plate_1.png','Metadata/plate_2.png']:(out/Path(p).name).write_bytes(z.read(p))
    (out/'inspection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
