"""Orient the verified native bodies for printing and verify STL round trips."""
import hashlib
import json
import math
from bridge_client import call,ROOT
import numpy as np
import trimesh
from verify_fixings import solid as mesh_solid, checks as fixing_checks

out=ROOT.parent/'output/r3-original'
working=json.loads((ROOT/'working-r3.json').read_text(encoding='utf-8'))
fit=json.loads((out/'fit-verification.json').read_text(encoding='utf-8'))
motion=json.loads((out/'motion-verification.json').read_text(encoding='utf-8'))
view=json.loads((out/'screen-view-verification.json').read_text(encoding='utf-8'))
assert view['blocked_rays']==0
assert motion['additionalCaseContactPoseCount']==0
assert motion['stemToNewMaterialOverlapMm3']<.02
assert motion['minima']['new_material']['gap_mm']>.4
doc=call('new_document')
manifest={'revision':'R3-Fusion','units':'mm','files':{},'working_design_id':working['design_id'],'print_design_id':doc['design_id'],'physical_fit_verified':False}
inverse_meshes={}
for i,label in [(0,'upper'),(1,'lower')]:
    angle=math.radians(180-working['screen_angle_deg'] if label=='upper' else 0);c,s=math.cos(angle),math.sin(angle)
    matrix=[1,0,0,0,0,c,-s,0,0,s,c,0,0,0,0,1]
    body=call('copy_body',body_id=working['bodies'][i]['body_id'],to_design_id=doc['design_id'],matrix_mm=matrix,name='A4 '+label+' R3 print')
    minimum=body['bounds_mm'][0]
    body=call('transform',body_id=body['body_id'],matrix_mm=[1,0,0,-minimum[0],0,1,0,-minimum[1],0,0,1,-minimum[2],0,0,0,1])
    destination=out/f'a4-{label}-r3-print.stl'
    call('export_stl',body_id=body['body_id'],path=str(destination))
    mesh=trimesh.load_mesh(destination)
    assembly=trimesh.load_mesh(out/f'a4-{label}-r3-assembly.stl')
    assert mesh.is_watertight and mesh.is_winding_consistent and len(mesh.split())==1
    assert mesh.volume>0 and abs(mesh.volume-assembly.volume)/assembly.volume<.001
    expected=np.subtract(body['bounds_mm'][1],body['bounds_mm'][0])
    assert np.max(np.abs(mesh.extents-expected))<.02,(label,mesh.extents,expected)
    assert np.min(mesh.bounds[0])>-.01
    inverse=mesh.copy();inverse.apply_translation(minimum)
    inverse.apply_transform(trimesh.transformations.rotation_matrix(-angle,[1,0,0]))
    assert np.max(np.abs(inverse.bounds-assembly.bounds))<.02
    inverse_meshes[label]=inverse
    manifest['files'][label]={'file':destination.name,'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'bytes':destination.stat().st_size,'extents_mm':mesh.extents.tolist(),'volume_mm3':float(mesh.volume),'watertight':True,'single_solid':True,'native_body_id':body['body_id'],'rotation_x_deg':180-working['screen_angle_deg'] if label=='upper' else 0}
import manifold3d as mf
def native_mesh_solid(m):
    return mf.Manifold(mf.Mesh(np.asarray(m.vertices,dtype=np.float32),np.asarray(m.faces,dtype=np.uint32)))
manifest['print_round_trip_fixings']=fixing_checks(native_mesh_solid(inverse_meshes['upper']),native_mesh_solid(inverse_meshes['lower']))
manifest['assembly_sha256']={label:hashlib.sha256((out/f'a4-{label}-r3-assembly.stl').read_bytes()).hexdigest() for label in ['upper','lower']}
manifest['screen_view']=view
manifest['model_parameters']={k:v for k,v in working.items() if k not in ['bodies','surface_reference_bodies']}
ids=[b['body_id'] for b in working['bodies']]
call('snapshot',design_id=working['design_id'],show_only_ids=ids,camera_mm=[[145,-190,125],[36,-28,27]],path=str(out/'fusion-final-exterior.png'))
call('snapshot',design_id=working['design_id'],show_only_ids=ids[:1],camera_mm=[[40,-90,-140],[36,-28,27]],path=str(out/'fusion-final-inside.png'))
call('snapshot',design_id=working['design_id'],show_only_ids=ids,camera_mm=[[145,-190,125],[36,-28,27]],path=str(out/'fusion-final-exterior.png'))
(out/'delivery-verification.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps(manifest,indent=2))
