#!/usr/bin/env python3
"""Package native ESP32-S3 desktop clients and verify installed resources."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tarfile

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
    version=json.loads((ROOT/'pc/package.json').read_text(encoding='utf-8'))['version']
    installer=select_windows_installer(bundle,version)
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


def select_windows_installer(bundle,version):
    if not isinstance(version,str) or not re.fullmatch(r'\d+\.\d+\.\d+',version):
        raise ValueError('Expected exact desktop package version')
    installer=Path(bundle)/f'HachimiDock_{version}_x64-setup.exe'
    if not installer.is_file() or installer.is_symlink():
        raise ValueError(f'Expected current Windows NSIS installer: {installer.name}')
    return installer


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


def linux(output):
    """Archive the relocatable Tauri tree; system libraries/media stay external."""
    stage=ROOT/'pc/dist-linux'
    resources=stage/'usr/lib'/json.loads((ROOT/'pc/src-tauri/tauri.conf.json').read_text(encoding='utf-8'))['productName']
    verify('linux',resources,output/'Linux-resource-manifest.json')
    smoke(stage/'launch.sh',output/'Linux-startup.log')
    (stage/'LINUX-REQUIREMENTS.txt').write_text(
        'Linux x86_64; built on Ubuntu 24.04 (glibc 2.39 or newer).\n'
        'Requires WebKitGTK 4.1, GTK3, ALSA, OpenSSL, system FFmpeg with libx264, and Python 3.\n'
        'Ubuntu 24.04: sudo apt install libwebkit2gtk-4.1-0 libgtk-3-0t64 libayatana-appindicator3-1 librsvg2-2 libasound2t64 libssl3t64 libudev1 ffmpeg python3\n'
        'Extract this whole directory, then run ./launch.sh. Do not move the binary alone.\n'
        'System FFmpeg/Python and their libraries are not included or redistributed.\n'
        'No root installation required; USB serial access may require dialout group membership.\n',encoding='utf-8')
    for name in ('LICENSE','THIRD_PARTY_NOTICES.md'):
        shutil.copy2(ROOT/name,stage/name)
    dest=output/'HachimoDock-esp32s3_Linux-x64.tar.gz'
    with tarfile.open(dest,'w:gz') as archive:
        archive.add(stage,arcname='HachimoDock-Linux-x64')
    # Validate the actual compressed download, including executable mode and
    # byte-for-byte coverage of every staged file, rather than only its source.
    verify_linux_archive(dest,stage)
    return dest


def verify_linux_archive(artifact,stage):
    expected={p.relative_to(stage).as_posix():p for p in stage.rglob('*') if p.is_file()}
    with tarfile.open(artifact,'r:gz') as archive:
        files={}
        for member in archive.getmembers():
            path=PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or '\\' in member.name or ':' in member.name or member.issym() or member.islnk():
                raise ValueError('Linux archive contains unsafe path or link')
            if member.isfile():
                logical=path.relative_to('HachimoDock-Linux-x64').as_posix()
                if logical in files:raise ValueError('Linux archive contains duplicate member')
                files[logical]=member
        if set(files)!=set(expected):raise ValueError('Linux archive file inventory mismatch')
        for logical,path in expected.items():
            if archive.extractfile(files[logical]).read()!=path.read_bytes():
                raise ValueError(f'Linux archive content mismatch: {logical}')
        for executable in ('launch.sh','usr/bin/pet-manager-tauri'):
            if not files[executable].mode & 0o111:
                raise ValueError(f'Linux archive lost executable mode: {executable}')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target',required=True,choices=('windows','macos','linux'))
    parser.add_argument('--output-dir',required=True,type=Path)
    args=parser.parse_args()
    if {'win32':'windows','darwin':'macos','linux':'linux'}.get(sys.platform)!=args.target:
        parser.error('Package verification must run on its native target OS')
    output=args.output_dir.resolve();output.mkdir(parents=True,exist_ok=True)
    artifact={'windows':windows,'macos':macos,'linux':linux}[args.target](output)
    shutil.copy2(ROOT/'docs/INSTALLATION.md',output/'安装使用说明.md')
    shutil.copy2(ROOT/'docs/COMPATIBILITY.md',output/'兼容性说明.md')
    for name in ('LICENSE','THIRD_PARTY_NOTICES.md'):
        shutil.copy2(ROOT/name,output/name)
    manifest_name={'windows':'Windows','macos':'macOS','linux':'Linux'}[args.target]
    resource_manifest = json.loads((output / (manifest_name+'-resource-manifest.json')).read_text(encoding='utf-8'))
    identity={'sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'appVersion':resource_manifest['appVersion'],
              'target':args.target,'releaseChannel':'prerelease','signing':'ad-hoc-not-notarized' if args.target=='macos' else 'unsigned',
              'firmware':resource_manifest['firmware']['version'],
              'nativeUi':resource_manifest['nativeUi'],
              'nativeStartupSeconds':10,'physicalBoardTested':False,
              'artifact':artifact.name,'bytes':artifact.stat().st_size,
              'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest()}
    (output/(args.target+'-build.json')).write_text(json.dumps(identity,indent=2)+'\n',encoding='utf-8')
    (output/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(output.iterdir()) if p.is_file() and p.name!='SHA256SUMS'),encoding='utf-8')
    print(json.dumps(identity))


if __name__=='__main__':main()
