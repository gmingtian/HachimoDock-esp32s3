"""Package the reviewed engineering draft, never manufacturing approval."""
import csv
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
import zipfile
from build_design import REVISION, STEM
from verify_drc import validate_attestation

ROOT=Path(__file__).resolve().parents[1]


def main():
    out=ROOT/'output'
    design=json.loads((out/'design.json').read_text())
    validate_attestation(out,out/f'{STEM}.kicad_pcb')
    drc=json.loads((out/'drc.json').read_text())
    if drc['violations'] or drc['unconnected_items']:
        raise SystemExit('Native DRC is not clean; refusing to package.')
    audit=json.loads((out/'electrical-audit.json').read_text())
    if audit['result']!='PASS' or audit['boardSha256']!=hashlib.sha256((out/f'{STEM}.kicad_pcb').read_bytes()).hexdigest():
        raise SystemExit('Electrical audit is missing or stale; refusing to package.')
    if audit['designSha256']!=hashlib.sha256((out/'design.json').read_bytes()).hexdigest():
        raise SystemExit('Design changed after native pad audit; refusing to package.')
    mechanical=json.loads((out/'mechanical-audit.json').read_text())
    if mechanical['boardSha256']!=audit['boardSha256'] or mechanical['designSha256']!=audit['designSha256']:
        raise SystemExit('Mechanical audit is stale; refusing to package.')
    faults=json.loads((out/'audit-fault-checks.json').read_text())
    if faults['sourceBoardSha256']!=audit['boardSha256'] or len(faults['cases'])!=6 or not all(c['rejected'] for c in faults['cases']):
        raise SystemExit('Fault detection checks are missing or stale; refusing to package.')
    for name,digest in audit['codeSha256'].items():
        if hashlib.sha256((ROOT.parents[1]/'firmware/s3'/name).read_bytes()).hexdigest()!=digest:
            raise SystemExit('S3 code changed after electrical audit; refusing to package.')
    result=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests'),'-v'],
                          capture_output=True,text=True)
    (out/'tests.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise SystemExit(result.stdout+result.stderr)
    rows=[['U1','GOOUUU ESP32-S3 N16R8 42P',1,'2x21P 2.54mm sockets; row spacing 25.4mm'],
          ['SW1 SW2 SW3','Cherry MX compatible mechanical switch',3,'Original switch geometry'],
          ['JS1','YA13S original bare joystick',1,'Not interchangeable with a PS2 breakout PCB'],
          ['U2','MAX98357A purple module',1,'Check module pin order and supply budget'],
          ['U3','INMP441 round 14mm module',1,'Check acoustic port and orientation'],
          ['U1 sockets','1x21P female socket 2.54mm',2,'For GOOUUU 42P; 25.4mm between rows'],
          ['U2 socket','1x7P female socket 2.54mm',1,'Module VIN=3V3; no speaker-terminal carrier pads'],
          ['U3 sockets','1x3P female socket 2.54mm',2,'Separate strips; 7.62mm between rows; label side up, long pins down'],
          ['J1','1x8P header 2.54mm',1,'LCD cable; BL directly on GPIO42; mated housing max 22x3mm'],
          ['JP1','1x3P male header 2.54mm',1,'Pin1=3V3, pin2=GAIN, pin3=GND; change only with power off'],
          ['JP1 shunt','2-pin shunt cap 2.54mm',1,'One cap only; max 4x5.5mm; 1-2=6dB, open=9dB, 2-3=12dB'],
          ['H1 H4','M2.5x6 mounting screw',2,'Original case reference; confirm actual engagement; install before modules'],
          ['H1 H4 inserts','M2.5x4x3.5 heat-set insert',2,'Original case reference; confirm actual enclosure dimensions'],
          ['H3','Enclosure locating/support post',0,'PCB hole retained; no screw installed'],
          ['H2 H5','Retained mounting holes',0,'No fastener required; if H2 is used later, use a non-metallic fastener near antenna']]
    with (out/'BOM.csv').open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.writer(stream);writer.writerow(['reference','value','quantity','assembly']);writer.writerows(rows)
    report={'revision':REVISION,'status':'engineering-draft','nativeCad':'KiCad 9.0.8',
            'components':len(design['components']),
            'electricalPads':sum(len(c['pads']) for c in design['components']),
            'mountingHoles':len(design['mountingHoles']),
            'routedBranches':len(design['traces']),'vias':len(design['vias']),
            'nativeDrcViolations':len(drc['violations']),
            'nativeDrcUnconnectedItems':len(drc['unconnected_items']),
            'nativeDrcBoundToBoardAndRules':True,
            'filledGroundLayers':audit['filledGroundLayers'],
            'allNativePadPositionsVerified':audit['allNativePadPositionsVerified'],
            'addedDiscreteComponents':False,
            'mechanicalAudit':mechanical,
            'automatedTests':f"{re.search(r'Ran (\d+) tests?',result.stderr).group(1)} passed; unittest discover -s hardware/s3-carrier/tests -v",
            'easyedaDataRoundTripVerified':True,'easyedaEditorImportVerified':False,
            'easyedaNativeKeepoutConverted':False,
            'enclosureVerified':False,'screenMechanicalDimensionsVerified':False,
            'powerBudgetVerified':False,'hardwareTested':False,'fabricationApproved':False,
            'directBacklightGpio':42,'amplifierGain':'JP1: 1-2=6dB, open=9dB, 2-3=12dB; I2S; module strapping unverified',
            'gainSelector':design['gainSelector'],
            'speakerTerminalsOnCarrier':False,
            'existingFirmwareSignalAudit':audit['result'],
            'deliberateFaultsRejected':len(faults['cases']),
            'amplifierSupplyUserConfirmed':design['amplifierSupplyUserConfirmed'],
            'joystickFirmwareStatus':design['joystickFirmwareStatus'],
            'mountingSockets':design['mountingSockets'],
            'microphoneMounting':design['microphoneMounting'],
            'screenConnectorOrder':design['screenConnectorOrder'],
            'usbSide':design['usbSide'],
            'usbOpeningAlignmentVerified':design['usbOpeningAlignmentVerified'],
            'moduleRotationFromA1Deg':design['moduleRotationFromA1Deg'],
            'moduleShiftTowardUsbMm':design['moduleShiftTowardUsbMm'],
            'usbEndReferenceEnvelopeXmm':design['usbEndReferenceEnvelopeXmm'],
            'usbFaceDimensionsVerified':design['usbFaceDimensionsVerified'],
            'nylonMountingHoles':design['nylonMountingHoles'],
            'fastenerEnvelopes':design['fastenerEnvelopes'],
            'assemblyFastenerRefs':['H1','H4'],
            'locatingSupportHole':'H3; no screw installed',
            'fastenerAuditBasis':'Five conservative head envelopes retained; assembly uses two screws',
            'sourceSha256':{},'designSha256':{}}
    for p in sorted((ROOT/'reference').glob('*.epro2')):
        report['sourceSha256'][p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
    for p in sorted(out.rglob('*')):
        if p.is_file() and p.suffix not in ('.kicad_prl','.log') and p.name not in ['validation.json','SHA256SUMS']:
            report['designSha256'][str(p.relative_to(out))]=hashlib.sha256(p.read_bytes()).hexdigest()
    (out/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    files=sorted(p for p in ROOT.rglob('*') if p.is_file() and
                 '__pycache__' not in p.parts and p.suffix not in ('.kicad_prl','.log') and p.name!='SHA256SUMS')
    checksums=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(ROOT))+'\n' for p in files)
    (out/'SHA256SUMS').write_text(checksums)
    target=ROOT.parents[1]/f'artifacts/pcb/HachimoDock-S3-PCB-{REVISION}.zip'
    target.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
        for p in files+[out/'SHA256SUMS']:
            archive.write(p,Path(f'HachimoDock-S3-PCB-{REVISION}')/p.relative_to(ROOT))
    print(json.dumps({'archive':str(target),'bytes':target.stat().st_size,
                      'sha256':hashlib.sha256(target.read_bytes()).hexdigest()},indent=2))


if __name__=='__main__':main()
