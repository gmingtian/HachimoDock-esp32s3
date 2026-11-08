"""Export the original-copy R4 as two millimeter engineering-fit STLs."""
import json,hashlib
import numpy as np
import trimesh
import manifold3d as mf
from bridge_client import call,ROOT
from verify_fixings import checks

out=ROOT.parent/'output/r4-original-copy'
w=json.loads((ROOT/'working-r4.json').read_text(encoding='utf-8'))
fit=json.loads((out/'fit-verification.json').read_text(encoding='utf-8'))
view=json.loads((out/'screen-view-verification.json').read_text(encoding='utf-8'))
motion=json.loads((out/'motion-verification.json').read_text(encoding='utf-8'))
spi=json.loads((out/'spi-17mm-verification.json').read_text(encoding='utf-8'))
access=json.loads((out/'mount-access-and-controls.json').read_text(encoding='utf-8'))
assert all(r['driver_upper_obstruction_mm3']<.02 and r['installed_head_shell_overlap_mm3']<.02 for r in access['lcd_screw_access'])
assert all(max(r['original_to_current_max_mm'],r['current_to_original_max_mm'])<.05 for r in access['control_sections'])
for label,sha in spi['assembly_hashes'].items():
    assert hashlib.sha256((out/f'a4-{label}-r4-assembly.stl').read_bytes()).hexdigest()==sha
assert all(row[k]<.025 for row in spi['checks'].values() for k in row if k.endswith('_overlap_mm3'))
assert view['blocked_rays']==0
assert motion['additionalCaseContactPoseCount']==0
assert fit['checks']['active_display_axis_error_mm']<.0001
assert fit['checks']['additional_shell_interference_mm3']<.025
doc=call('new_document');meshes={}
report={'revision':'R4-original-copy','units':'mm','status':'engineering-fit-trial','physical_fit_verified':False,'files':{},'unresolved':['Physical USB cable housing, soldered module heights and assembly remain unverified.','The unmeasured-pivot conservative stem model has up to %.4f mm3 additional intersection; preserve original operation geometry and verify full travel physically.'%motion['stemToNewMaterialOverlapMm3']],'sphere_additional_contact_poses':motion['additionalCaseContactPoseCount'],'print_document_id':doc['design_id']}
for b,label in zip(w['bodies'],['upper','lower']):
    body=call('copy_body',body_id=b['body_id'],to_design_id=doc['design_id'],name='R4 '+label+' STL')
    minimum=body['bounds_mm'][0]
    body=call('transform',body_id=body['body_id'],matrix_mm=[1,0,0,-minimum[0],0,1,0,-minimum[1],0,0,1,-minimum[2],0,0,0,1])
    path=out/f'a4-{label}-r4-spi17-fixed.stl'
    exported=call('export_stl',body_id=body['body_id'],path=str(path),surface_deviation_mm=.01)
    m=trimesh.load_mesh(path);assembly=trimesh.load_mesh(out/f'a4-{label}-r4-assembly.stl')
    assert m.is_watertight and m.is_winding_consistent and len(m.split())==1 and m.volume>0
    assert abs(m.volume-assembly.volume)/assembly.volume<.001
    assert np.max(np.abs(m.extents-np.subtract(body['bounds_mm'][1],body['bounds_mm'][0])))<.02
    assert np.min(m.bounds[0])>-.01
    restored=m.copy();restored.apply_translation(minimum);meshes[label]=restored
    assert np.max(np.abs(restored.bounds-assembly.bounds))<.02
    report['files'][label]={'name':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size,'bounds_mm':m.bounds.tolist(),'extents_mm':m.extents.tolist(),'volume_mm3':float(m.volume),'single_closed_solid':True,'native_body_id':body['body_id'],'orientation':'Original assembly axes, independently translated onto the build plate; slicer orientation/support still required.','surface_deviation_mm':exported['surface_deviation_mm']}
def solid(m):return mf.Manifold(mf.Mesh(np.asarray(m.vertices,dtype=np.float32),np.asarray(m.faces,dtype=np.uint32)))
report['exported_fixings']=checks(solid(meshes['upper']),solid(meshes['lower']))
report['revision']='R4.2-original-copy-SPI17-access-and-controls-fixed'
report['spi_stack']=spi
report['lcd_driver_access_and_control_profiles']=access
(out/'delivery-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
ids=[b['body_id'] for b in w['bodies']+w.get('review_controls',[])]
call('snapshot',design_id=w['design_id'],show_only_ids=ids,camera_mm=[[140,-185,120],[36,-28,27]],path=str(out/'original-style-assembly.png'))
print(json.dumps(report,indent=2))
