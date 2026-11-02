"""Run native DRC and bind its result to the exact board and project rules."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from build_design import ROOT,STEM


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_attestation(directory,board):
    att=json.loads((directory/'drc-attestation.json').read_text())
    required=[board,board.with_suffix('.kicad_pro'),directory/'drc.json']
    if att.get('result')!='PASS' or set(att.get('files',{}))!={p.name for p in required}:
        raise ValueError('Missing DRC attestation inputs.')
    for path in required:
        if att['files'][path.name]!=digest(path):raise ValueError(f'Stale DRC: {path.name} changed.')
    drc=json.loads((directory/'drc.json').read_text())
    if drc['violations'] or drc['unconnected_items'] or drc.get('ignored_checks'):
        raise ValueError('Native DRC is not clean.')
    return att


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',type=Path,default=ROOT/'output')
    parser.add_argument('--kicad-cli',default='kicad-cli')
    args=parser.parse_args();out=args.directory.resolve();board=out/f'{STEM}.kicad_pcb'
    inputs={p.name:digest(p) for p in [board,board.with_suffix('.kicad_pro')]}
    att=out/'drc-attestation.json';att.unlink(missing_ok=True)
    result=subprocess.run([args.kicad_cli,'pcb','drc','--format','json','--exit-code-violations',
                           '--output',str(out/'drc.json'),str(board)],capture_output=True,text=True)
    (out/'drc-cli.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise SystemExit(result.stdout+result.stderr)
    for name,sha in inputs.items():
        if digest(out/name)!=sha:raise SystemExit('Board/rules changed while DRC was running.')
    inputs['drc.json']=digest(out/'drc.json')
    att.write_text(json.dumps({'result':'PASS','files':inputs},indent=2)+'\n')
    try:validate_attestation(out,board)
    except (KeyError,ValueError) as error:
        att.unlink(missing_ok=True);raise SystemExit(str(error))
    print('Fresh native DRC: 0 violations, 0 unconnected; board and rules hashes locked.')


if __name__=='__main__':main()
