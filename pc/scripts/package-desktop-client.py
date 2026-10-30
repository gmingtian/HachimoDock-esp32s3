#!/usr/bin/env python3
"""Package native ESP32-S3 desktop clients and verify installed resources."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
VERIFY = ROOT / 'pc/scripts/verify-preview-resources.py'


def run(args, **kwargs):
    return subprocess.run(list(map(str,args)),check=True,**kwargs)


def unique(paths, label):
    paths=list(paths)
    if len(paths)!=1:
        raise ValueError(f'Expected exactly one {label}, found {len(paths)}: {paths}')
    return paths[0]


def verify(target, resource, output):
    run([sys.executable,VERIFY,'--target',target,'--resource-root',resource,'--manifest',output])


def smoke(binary, log):
    """Only native startup; no USB, model calls or interactive acceptance claimed."""
    with log.open('wb') as output:
        process=subprocess.Popen([str(binary)],cwd=binary.parent,stdout=output,stderr=output)
        try:
            time.sleep(10)
            if process.poll() is not None:
                raise ValueError(f'Native startup exited ({process.returncode}); inspect {log.name}')
        finally:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill();process.wait(timeout=10)


def windows(output):
    bundle=ROOT/'pc/src-tauri/target/x86_64-pc-windows-msvc/release/bundle/nsis'
    installer=unique(bundle.glob('*.exe'),'Windows NSIS installer')
    dest=output/'HachimoDock-esp32s3_Windows-x64.exe'
    shutil.copy2(installer,dest)
    sevenzip=shutil.which('7z') or str(Path(os.environ.get('ProgramFiles','C:/Program Files'))/'7-Zip/7z.exe')
    with tempfile.TemporaryDirectory(prefix='hachimo-install-') as temp:
        temp=Path(temp)
        run([sevenzip,'x',dest,'-o'+str(temp),'-y'],stdout=subprocess.DEVNULL)
        firmware=unique(temp.rglob('esp32-s3/firmware.bin'),'installed S3 firmware')
        resources=firmware.parents[2]
        verify('windows',resources,output/'Windows-resource-manifest.json')
        candidates=[p for p in resources.glob('*.exe') if p.name.lower() in ('pet-manager-tauri.exe','hachimidock.exe','hachimodock.exe')]
        binary=unique(candidates,'installed Windows main executable')
        smoke(binary,output/'Windows-startup.log')
    return dest


def macos(output):
    if os.uname().machine!='arm64':raise ValueError('Native Apple-silicon runner required')
    bundle=ROOT/'pc/src-tauri/target/aarch64-apple-darwin/release/bundle/macos'
    app=unique(bundle.glob('*.app'),'macOS app')
    # Nested executable signatures were validated before Tauri bundling. Apply
    # stable app identity without rewriting those signed resource payloads.
    run(['node',ROOT/'pc/scripts/sign-macos-local-app.mjs',app])
    verify('macos',app/'Contents/Resources',output/'macOS-resource-manifest.json')
    info=plistlib.loads((app/'Contents/Info.plist').read_bytes())
    binary=app/'Contents/MacOS'/info['CFBundleExecutable']
    smoke(binary,output/'macOS-startup.log')
    dest=output/'HachimoDock-esp32s3_macOS-arm64.dmg'
    with tempfile.TemporaryDirectory(prefix='hachimo-dmg-stage-') as temp, tempfile.TemporaryDirectory(prefix='hachimo-dmg-mount-') as mount:
        temp=Path(temp);mount=Path(mount)
        run(['/usr/bin/ditto',app,temp/app.name])
        (temp/'Applications').symlink_to('/Applications',target_is_directory=True)
        shutil.copy2(ROOT/'docs/INSTALLATION.md',temp/'安装使用说明.md')
        shutil.copy2(ROOT/'docs/COMPATIBILITY.md',temp/'兼容性说明.md')
        run(['/usr/bin/hdiutil','create','-volname','HachimoDock ESP32-S3','-srcfolder',temp,'-ov','-format','UDZO',dest])
        attached=False
        try:
            run(['/usr/bin/hdiutil','attach','-readonly','-nobrowse','-noautoopen','-mountpoint',mount,dest])
            attached=True
            run(['/usr/bin/codesign','--verify','--deep','--strict',mount/app.name])
            verify('macos',mount/app.name/'Contents/Resources',output/'macOS-resource-manifest.json')
        finally:
            if attached:run(['/usr/bin/hdiutil','detach',mount])
    return dest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target',required=True,choices=('windows','macos'))
    parser.add_argument('--output-dir',required=True,type=Path)
    args=parser.parse_args()
    if {'win32':'windows','darwin':'macos'}.get(sys.platform)!=args.target:
        parser.error('Package verification must run on its native target OS')
    output=args.output_dir.resolve();output.mkdir(parents=True,exist_ok=True)
    artifact=windows(output) if args.target=='windows' else macos(output)
    shutil.copy2(ROOT/'docs/INSTALLATION.md',output/'安装使用说明.md')
    shutil.copy2(ROOT/'docs/COMPATIBILITY.md',output/'兼容性说明.md')
    for name in ('LICENSE','THIRD_PARTY_NOTICES.md'):
        shutil.copy2(ROOT/name,output/name)
    identity={'sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'target':args.target,'releaseChannel':'prerelease','signing':'unsigned' if args.target=='windows' else 'ad-hoc-not-notarized',
              'firmware':'0.7.103-s3-r6','nativeStartupSeconds':10,'physicalBoardTested':False,
              'artifact':artifact.name,'bytes':artifact.stat().st_size,
              'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest()}
    (output/(args.target+'-build.json')).write_text(json.dumps(identity,indent=2)+'\n',encoding='utf-8')
    (output/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(output.iterdir()) if p.is_file() and p.name!='SHA256SUMS'),encoding='utf-8')
    print(json.dumps(identity))


if __name__=='__main__':main()
