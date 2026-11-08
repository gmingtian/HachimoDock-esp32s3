"""Package the verified R1 draft only; keep intermediate R0 files out."""
import hashlib
import json
import zipfile
from pathlib import Path
from build_enclosure import ROOT,OUT

def main():
    fit=json.loads((OUT/'fit-report.json').read_text())
    motion=json.loads((OUT/'motion-verification.json').read_text())
    three=json.loads((OUT/'3mf-verification.json').read_text())
    assert motion['additionalCaseContactPoseCount']==0
    assert motion['stemToNewMaterialOverlapMm3']<.02
    assert three['printerAndMaterialProcessSettingsByteIdentical'] and not three['samePlateObjectClashes']
    for name,file in [('upper','a4-upper-r1-print.stl'),('lower','a4-lower-r1-print.stl'),('support_coupon','support-coupon-r1-print.stl'),('m2_boss_coupon','m2-boss-coupon-r1-print.stl')]:
        assert hashlib.sha256((OUT/file).read_bytes()).hexdigest()==fit['meshes'][name]['sha256']
        assert fit['meshes'][name]['watertight'] and fit['meshes'][name]['connected_parts']==1
    project=OUT/'HachimoDock-A4-R1-P1S-white-orange-two-plates.3mf'
    assert hashlib.sha256(project.read_bytes()).hexdigest()==three['outputSha256']
    pcb=ROOT/'../s3-carrier/output/HachimoDock-S3-carrier-A4.kicad_pcb'
    assert hashlib.sha256(pcb.read_bytes()).hexdigest()=='3ea5f653f6bf27bdb09c90290e1f22ae493803e0c346911ff89b9b5f40b8624e'
    entries={project.name:project,'README.md':ROOT/'README.md'}
    for file in OUT.glob('*-print.stl'):entries['print-stl/'+file.name]=file
    for file in [OUT/'a4-upper-r1-assembly.stl',OUT/'a4-lower-r1-assembly.stl']:entries['assembly-cad/'+file.name]=file
    for name in ['a4-enclosure-r1.png','a4-lower-supports-r1.png','a4-lower-layout-r1.png','layout-and-height-r1.png','layout-and-height-r1.svg','p1s-plate-1-r1.png','p1s-plate-2-r1.png']:
        entries['preview/'+name]=OUT/name
    for name in ['fit-report.json','motion-verification.json','3mf-verification.json']:entries['reports/'+name]=OUT/name
    for name in ['build_enclosure.py','inspect_original.py','explore_geometry.py','package_3mf.py','inspect_3mf.py','check_joystick_motion.py','verify_motion_r1.py','make_layout_sheet.py','make_delivery.py','parameters.json','parameters-standard-socket-r0.json','requirements.json','requirements-cad.txt','README.md']:
        entries['source/enclosure-a4/'+name]=ROOT/name
    for name in ['original-assembly.STEP','user-p1s-white-orange-two-plates.3mf','screen-user-drawing.jpg','original-inspection.json']:
        entries['source/enclosure-a4/reference/'+name]=ROOT/'reference'/name
    entries['source/s3-carrier/output/design.json']=ROOT/'../s3-carrier/output/design.json'
    manifest={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in sorted(entries.items())}
    archive=OUT/'HachimoDock-A4-R1-Fit-Draft.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,path in entries.items():z.write(path,name)
        z.writestr('SHA256SUMS.txt','\n'.join(f'{sha}  {name}' for name,sha in manifest.items())+'\n')
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert all(hashlib.sha256(z.read(name)).hexdigest()==sha for name,sha in manifest.items())
    summary={'archive':archive.name,'sizeBytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'files':len(entries)+1,'modelChecksPassed':True,'physicalFitVerified':False,'bambuStudioOpened':False,'pcbUnchanged':True}
    (OUT/'delivery-verification.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
