#!/usr/bin/env python3
"""Stage only the pinned upstream LGPL runtime for native preview packaging.

The ordinary prepare-desktop-resources.mjs preflight must still run afterwards;
this script neither substitutes nor weakens its architecture/licensing checks.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
RELEASE = 'https://github.com/YizhengWw/HachimoDock/releases/download/v0.1.167/'
ARCHIVES = {
    'windows': ('HachimiDock_0.1.167_Windows-x64-setup.exe',
                '5a79d40e3212ca74ba5844e9a06f1dc0f3febb9645ed62faa23fc3ba0d0a298e'),
    'macos': ('HachimiDock_0.1.167_macOS-arm64.dmg',
              '845adc85834e9e23cbd6790e3e511598db47ad80e683d7eb8ef9dd3f10ac00e5'),
}
SOURCE_NAME = 'ffmpeg-8.1.2.tar.xz'
SOURCE_URL = 'https://ffmpeg.org/releases/' + SOURCE_NAME
SOURCE_SHA = '464beb5e7bf0c311e68b45ae2f04e9cc2af88851abb4082231742a74d97b524c'
BINARY_SHA = {
    'windows': '1cefca14ea713d5d7e7a1b948299142831185487f5efb14914d049ba9090d95f',
    'macos': 'e340c148c720888a528e7bd2e7867da3b4bea91d1f6e508c9526111257ee0468',
}
NODE_LICENSE_MARKERS = (
    'Node.js is licensed for use as follows:',
    'Copyright Node.js contributors. All rights reserved.',
    'Permission is hereby granted, free of charge',
    'THE SOFTWARE IS PROVIDED "AS IS"',
    'libuv, located at deps/uv', 'OpenSSL, located at deps/openssl',
    'V8, located at deps/v8', 'zlib, located at deps/zlib',
    'nghttp2, located at deps/nghttp2', 'brotli, located at deps/brotli',
    'uvwasi, located at deps/uvwasi',
)


def validate_node_license(data):
    try:
        text = data.decode('utf-8')
    except UnicodeError as error:
        raise ValueError('Node license is incomplete or not UTF-8') from error
    if len(data) < 16384 or any(marker not in text for marker in NODE_LICENSE_MARKERS):
        raise ValueError('Node license is incomplete; full bundled third-party notices are required')
    return data


def download_notice(url):
    with urlopen(url, timeout=60) as response:
        data = response.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise ValueError('Node license download exceeds 2 MiB')
    return data


def collect_node_license(version, fetch=download_notice):
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError(f'Node license requires an exact stable runtime version: {version}')
    url = f'https://raw.githubusercontent.com/nodejs/node/v{version}/LICENSE'
    data = validate_node_license(fetch(url))
    return data, {'version':version, 'source':url, 'sha256':hashlib.sha256(data).hexdigest()}


def stage_node_license(node_bin, output_dir):
    version = run([node_bin, '-p', 'process.versions.node']).stdout.strip()
    data, metadata = collect_node_license(version)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'node.LICENSE').write_bytes(data)
    return metadata


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def require_hash(path, expected):
    actual = sha256(path)
    if actual != expected:
        raise ValueError(f'SHA-256 mismatch for {Path(path).name}: expected {expected}, got {actual}')


def download(url, path, expected):
    """Cache only complete, verified downloads; never reuse an unverified cache."""
    path = Path(path)
    if path.exists():
        require_hash(path, expected)
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.part')
    try:
        with urlopen(url, timeout=120) as response, temporary.open('wb') as output:
            shutil.copyfileobj(response, output)
        require_hash(temporary, expected)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def select_members(names, target):
    """Require one unambiguous file per resource; never extract installer code."""
    wanted = ['ffmpeg.exe' if target == 'windows' else 'ffmpeg',
              'ffmpeg.README', 'ffmpeg.LICENSE', 'ffmpeg.SOURCE.txt', SOURCE_NAME]
    if target == 'windows':
        wanted.append('zlib.LICENSE')
    matches = {name: [] for name in wanted}
    for name in names:
        normalized = name.replace('\\', '/')
        path = PurePosixPath(normalized)
        if path.name not in matches:
            continue
        if path.is_absolute() or '..' in path.parts or ':' in normalized or '\n' in normalized or '\r' in normalized:
            raise ValueError(f'unsafe archive member: {name}')
        matches[path.name].append(name)
    result = {}
    for name, found in matches.items():
        if len(found) > 1:
            raise ValueError(f'ambiguous archive resource {name}: {found}')
        if not found and name != SOURCE_NAME:
            raise ValueError(f'upstream archive resource missing: {name}')
        if found:
            result[name] = found[0]
    return result


def run(command):
    return subprocess.run(list(map(str, command)), check=True, capture_output=True,
                          text=True, timeout=180)


@contextmanager
def mounted_dmg(archive):
    if sys.platform != 'darwin':
        raise ValueError('macOS DMG extraction requires a native macOS host')
    with tempfile.TemporaryDirectory(prefix='hachimo-preview-mount-') as temporary:
        mount = Path(temporary) / 'volume'
        mount.mkdir()
        attached = False
        try:
            run(['hdiutil', 'attach', '-readonly', '-nobrowse', '-noautoopen',
                 '-mountpoint', mount, archive])
            attached = True
            yield mount
        finally:
            if attached:
                run(['hdiutil', 'detach', mount])


def extract_windows(archive, destination):
    seven_zip = shutil.which('7z') or shutil.which('7zz')
    if not seven_zip:
        raise ValueError('7z is required to extract the pinned Windows installer')
    listing = run([seven_zip, 'l', '-slt', archive]).stdout
    # The first Path record describes the archive itself; subsequent records
    # describe entries. The separator prevents treating that header as a file.
    entries = listing.split('----------', 1)
    if len(entries) != 2:
        raise ValueError('7z did not return an archive member listing')
    names = [line[7:] for line in entries[1].splitlines() if line.startswith('Path = ')]
    members = select_members(names, 'windows')
    # Exact member arguments with wildcard expansion disabled, only these six
    # media resources are extracted. No installer program is ever executed.
    run([seven_zip, 'x', '-y', '-spd', f'-o{destination}', archive, *members.values()])
    return {name: destination.joinpath(*member.replace('\\', '/').split('/'))
            for name, member in members.items()}


def validate_staged(resources, target):
    for name, path in resources.items():
        if not path.is_file() or path.is_symlink():
            raise ValueError(f'upstream resource is not a regular file: {name}')
    require_hash(resources['ffmpeg.exe' if target == 'windows' else 'ffmpeg'], BINARY_SHA[target])
    require_hash(resources[SOURCE_NAME], SOURCE_SHA)
    readme = resources['ffmpeg.README'].read_text(encoding='utf-8')
    for flag in ('--disable-gpl', '--disable-nonfree',
                 'h264_mf' if target == 'windows' else 'h264_videotoolbox'):
        if flag not in readme:
            raise ValueError(f'LGPL README missing {flag}')
    for flag in ('--enable-gpl', '--enable-nonfree', '--enable-libx264', '--enable-libopenh264'):
        if flag in readme:
            raise ValueError(f'LGPL README contains forbidden {flag}')
    if 'GNU LESSER GENERAL PUBLIC LICENSE' not in resources['ffmpeg.LICENSE'].read_text(encoding='utf-8'):
        raise ValueError('FFmpeg LGPL license text missing')


def prepare(target, cache_dir, output_dir, archive=None, node_bin=None):
    filename, archive_sha = ARCHIVES[target]
    archive = Path(archive) if archive else download(RELEASE + filename, Path(cache_dir) / filename, archive_sha)
    require_hash(archive, archive_sha)  # Always before extraction or output writes.
    with tempfile.TemporaryDirectory(prefix='hachimo-preview-extract-') as temporary:
        staging = Path(temporary)
        if target == 'windows':
            resources = extract_windows(archive, staging)
            stage_resources(resources, target, cache_dir, output_dir)
        else:
            with mounted_dmg(archive) as mount:
                files = [path.relative_to(mount).as_posix() for path in mount.rglob('*') if path.is_file()]
                members = select_members(files, target)
                resources = {name: mount / member for name, member in members.items()}
                # Copies only the selected resources while the read-only volume
                # is mounted. Nothing else from the app is reused.
                stage_resources(resources, target, cache_dir, output_dir)
    node_bin = node_bin or os.environ.get('PET_MANAGER_NODE_BIN') or shutil.which('node')
    if not node_bin:
        raise ValueError('Native Node executable required; set --node-bin or PET_MANAGER_NODE_BIN')
    node_license = stage_node_license(node_bin, output_dir)
    return {'upstreamVersion': '0.1.167', 'archive': filename, 'sha256': archive_sha,
            'target': target + ('-x64' if target == 'windows' else '-arm64'),
            'nodeLicense':node_license}


def stage_resources(resources, target, cache_dir, output_dir):
    if SOURCE_NAME not in resources:
        resources[SOURCE_NAME] = download(SOURCE_URL, Path(cache_dir) / SOURCE_NAME, SOURCE_SHA)
    validate_staged(resources, target)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, path in resources.items():
        shutil.copy2(path, output_dir / name)
    if target != 'windows':
        (output_dir / 'ffmpeg').chmod(0o755)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True, choices=ARCHIVES)
    parser.add_argument('--cache-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'pc/src-tauri/generated-runtime')
    parser.add_argument('--archive', type=Path, help='Offline pinned upstream installer; its digest is still required')
    parser.add_argument('--node-bin', type=Path, help='Native Node executable (defaults to PET_MANAGER_NODE_BIN or PATH node)')
    args = parser.parse_args()
    result = prepare(args.target, args.cache_dir.resolve(), args.output_dir.resolve(), args.archive, args.node_bin)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
