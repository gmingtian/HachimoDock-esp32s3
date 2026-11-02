"""Prove the native audit rejects deliberately incorrect temporary PCB copies."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import pcbnew
from build_design import ROOT,STEM


def main():
    source=ROOT/'output'/f'{STEM}.kicad_pcb'
    results=[]
    with tempfile.TemporaryDirectory(prefix='hachimodock-pcb-audit-') as folder:
        temp=Path(folder)
        for name,ref,num,net,error in [
            ('swapped-lcd-clock','J1','3','GPIO47','LCD_CLK'),
            ('mic-wrong-slot','U3','4','+3V3','+3V3 power/ground mapping mismatch'),
            ('amp-wrong-supply','U2','1','+5V','+3V3 power/ground mapping mismatch'),
            ('gain-tied-to-supply','U2','4','+3V3','+3V3 power/ground mapping mismatch'),
            ('jumper-wrong-center','JP1','2','GND','GND power/ground mapping mismatch'),
            ('socket-drill-too-small','U1','1',None,'Socket tail hole too small')]:
            board=pcbnew.LoadBoard(str(source))
            pad=next(p for fp in board.GetFootprints() if fp.GetReference()==ref
                     for p in fp.Pads() if p.GetNumber()==num)
            if net:pad.SetNet(board.FindNet(net))
            else:pad.SetDrillSize(pcbnew.VECTOR2I(pcbnew.FromMM(.8),pcbnew.FromMM(.8)))
            target=temp/(name+'.kicad_pcb');pcbnew.SaveBoard(str(target),board)
            run=subprocess.run([sys.executable,str(ROOT/'tools/audit_native.py'),'--board',str(target),
                                '--report',str(temp/'invalid-report.json')],capture_output=True,text=True)
            assert run.returncode!=0 and error in run.stderr,(name,run.stdout,run.stderr)
            results.append({'injectedFault':name,'rejected':True,'check':error})
            print('Rejected:',name)
    report={'sourceBoardSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'cases':results}
    (ROOT/'output/audit-fault-checks.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'{len(results)} deliberately incorrect temporary variants rejected; canonical board unchanged.')


if __name__=='__main__':main()
