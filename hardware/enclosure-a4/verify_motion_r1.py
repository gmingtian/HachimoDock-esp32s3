"""Verify the unchanged original cap; retain the accepted keycap limitation."""
import json
import math
import numpy as np
import trimesh
from pathlib import Path
from explore_geometry import load
from build_enclosure import ROOT,OUT,P,solid,mesh,sbox
from check_joystick_motion import locator,positions

def main(folder=OUT,revision='r1'):
    OUT=Path(folder)
    upper=solid(trimesh.load_mesh(OUT/f'a4-upper-{revision}-assembly.stl'))
    lower=solid(trimesh.load_mesh(OUT/f'a4-lower-{revision}-assembly.stl'))
    native_difference=(OUT/'native-added-upper.stl').exists() and revision not in ['r3','r4']
    native_source=revision=='r4'
    original_upper=trimesh.load_mesh(OUT/'native-original-upper.stl') if native_difference or native_source else load(0)
    original_lower=trimesh.load_mesh(OUT/'native-original-lower.stl') if native_source else load(1)
    added=(solid(trimesh.load_mesh(OUT/'native-added-upper.stl'))+solid(trimesh.load_mesh(OUT/'native-added-lower.stl'))) if native_difference else (upper-solid(load(0)))+(lower-solid(load(1)))
    added_mesh=mesh(added)
    screen_body=sbox(0,81.2,0,51,-7.6,-1.8)
    if revision in ['r3','r4']:
        import manifold3d as mf
        params=json.loads((OUT/'fit-verification.json').read_text(encoding='utf-8'))['screen_parameters']
        screen_origin=params['screen_origin_mm']
        screen_body=mf.Manifold.cube([81.2,51,5.8]).translate([0,0,-6.4]).rotate([params.get('screen_angle_deg',45),0,0]).translate(screen_origin)
    distances={
        'new_material':locator(added_mesh),
        'original_upper':locator(original_upper),
        'new_upper':locator(mesh(upper)),
        'SW3':locator(load(4)),
        'screen_body':locator(mesh(screen_body)),
    }
    minima={name:{'gap_mm':1e9} for name in distances}
    additional_contacts=[];poses=0
    for center,pose in positions(0,step=2):
        # Difference meshes contain disconnected shells; their nearest-face
        # sign is ambiguous. Use unsigned distance for that diagnostic, while
        # the full original/new case comparison below retains signed distance.
        gaps={name:(abs(d.EvaluateFunction(center.tolist())) if name=='new_material' else d.EvaluateFunction(center.tolist()))-7.05 for name,d in distances.items()}
        for name,gap in gaps.items():
            if gap<minima[name]['gap_mm']:minima[name]={'gap_mm':float(gap),'pose':pose,'center':center.tolist()}
        if gaps['new_upper']<-.02 and gaps['new_upper']<gaps['original_upper']-.02:additional_contacts.append(pose)
        poses+=1
    # The stem is lower than the sphere; bound all its transformed vertices.
    stem=load(6);stem_bounds_min=np.full(3,np.inf);stem_bounds_max=-stem_bounds_min
    stem_added_overlap=0
    complete_case=upper+lower
    original_case=solid(original_upper)+solid(original_lower)
    local_refinement=None
    if revision=='r4' and (OUT/'analysis-fine-controls-current.stl').exists():
        import manifold3d as mf
        region=mf.Manifold.cube([37,38,32]).translate([48,-78,8])
        lower_region=(lower^region).volume()
        assert lower_region<.02,lower_region
        complete_case=solid(trimesh.load_mesh(OUT/'analysis-fine-controls-current.stl'))
        original_case=solid(trimesh.load_mesh(OUT/'analysis-fine-controls-original.stl'))
        local_refinement={'bounds_mm':[[48,-78,8],[85,-40,40]],'surface_deviation_mm':.001,'lower_case_overlap_with_region_mm3':lower_region}
    max_stem_case_overlap=0;max_original_stem_overlap=0
    c=np.array([65.62495,-59.44864,26.6])
    for arm in [12,15.1,18]:
        pivot=c-[0,0,arm]
        for theta in [0,8,16,24,32]:
            for phi in np.arange(0,360,8):
                angle=math.radians(float(phi));axis=[-math.sin(angle),math.cos(angle),0]
                rotation=trimesh.transformations.rotation_matrix(math.radians(theta),axis,pivot)
                for press in [0,1]:
                    moving=stem.copy();moving.apply_transform(rotation);moving.apply_translation([0,0,-press])
                    stem_bounds_min=np.minimum(stem_bounds_min,moving.bounds[0]);stem_bounds_max=np.maximum(stem_bounds_max,moving.bounds[1])
                    a,b=added_mesh.bounds,moving.bounds
                    if np.all(a[0]<b[1]) and np.all(b[0]<a[1]):
                        moving_solid=solid(moving)
                        overlap=(moving_solid^complete_case).volume();old_overlap=(moving_solid^original_case).volume()
                        max_stem_case_overlap=max(max_stem_case_overlap,overlap);max_original_stem_overlap=max(max_original_stem_overlap,old_overlap)
                        stem_added_overlap=max(stem_added_overlap,overlap-old_overlap)
    report={
        'original14mmCapAndStemUnchanged':True,
        'pcbAndControlLocationsUnchanged':True,
        'sphericalEnvelopeRadiusMm':7.05,
        'spherePoseCount':poses,'angleStepDeg':2,'azimuthStepDeg':2,
        'maximumTiltDeg':32,'clickTravelAssumedMm':1,
        'neutralPivotToCapCenterLengthsScannedMm':[12,15.1,18],
        'pivotMeasured':False,'physicalFullTravelVerified':False,
        'minima':minima,
        'additionalCaseContactPoseCount':len(additional_contacts),
        'newMaterialDistanceMethod':('Fusion exact BRep difference exported to STL; unsigned surface distance; paired with signed full-case comparison' if native_difference else 'unsigned nearest surface; paired with signed original/new full-case comparison'),
        'stemToNewMaterialOverlapMm3':stem_added_overlap,
        'stemToCompleteCaseOverlapMm3':max_stem_case_overlap,
        'stemToOriginalCaseOverlapMm3':max_original_stem_overlap,
        'newMaterialDistanceIsDiagnosticOnly':revision in ['r3','r4'],
        'stem_local_refinement':local_refinement,
        'stemSweepWorldBounds':[stem_bounds_min.tolist(),stem_bounds_max.tolist()],
        'knownAcceptedLimitation':'Original 14 mm cap can contact SW3. User requested keeping current PCB, controls and cap. This revision does not claim unrestricted +/-32 degree physical movement.',
        'originalCasingEnvelopeNote':'A full sphere is conservative: the actual cap has a truncated bottom. Extreme modeled sphere contact with the inherited original joystick rim is retained, not reported as a new defect.',
    }
    (OUT/'motion-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)
    assert not additional_contacts,additional_contacts[:3]
    if revision not in ['r3','r4']:assert minima['new_material']['gap_mm']>.4,minima['new_material']
    assert minima['screen_body']['gap_mm']>.4,minima['screen_body']
    assert stem_added_overlap<.02,stem_added_overlap
    (OUT/'motion-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
