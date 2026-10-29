#!/usr/bin/env python3
"""Verify staged or installed native S3 preview resources without USB/services.

Produces a portable resource manifest plus SHA256SUMS covering every shipped
runtime/tool file, the real S3 firmware, and the actual converter smoke result.
Importing this module performs no downloads, filesystem writes, or subprocesses.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
FIRMWARE_SHA = 'e37a62e63b6a5590d400449c2c4514a83676e91987233e6692bd9dea7aa9a320'


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def validate_firmware(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError(f'S3 firmware is missing: {path}')
    data = path.read_bytes()
    if len(data) < 288 or data[0] != 0xe9 or struct.unpack_from('<H', data, 12)[0] != 9:
        raise ValueError('S3 firmware must be a real ESP-IDF chip9 application image')
    if struct.unpack_from('<I', data, 32)[0] != 0xabcd5432:
        raise ValueError('S3 firmware app descriptor is missing')
    version = data[48:80].split(b'\0', 1)[0].decode('utf-8')
    project = data[80:112].split(b'\0', 1)[0].decode('utf-8')
    if project != 'pet_manager_s3_runtime' or version != '0.7.103-s3-r1':
        raise ValueError(f'S3 firmware identity mismatch: {project} {version}')
    actual = sha256(path)
    if actual != FIRMWARE_SHA:
        raise ValueError(f'S3 firmware SHA-256 mismatch: {actual}')
    return {'chipId':9, 'projectName':project, 'version':version,
            'bytes':len(data), 'sha256':actual}


def validate_executable(path, target):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError(f'executable missing or symlink: {path}')
    with path.open('rb') as stream:
        header = stream.read(4096)
    if target == 'windows':
        offset = struct.unpack_from('<I', header, 0x3c)[0] if len(header) >= 64 else 0
        if not header.startswith(b'MZ') or offset < 64 or offset + 6 > len(header) or header[offset:offset+4] != b'PE\0\0' or struct.unpack_from('<H', header, offset + 4)[0] != 0x8664:
            raise ValueError(f'{path.name} is not a Windows x64 executable')
    else:
        # Native arm64 Mach-O only; a fat/universal binary needs its slices
        # inspected explicitly rather than being accepted on magic alone.
        if len(header) < 8 or header[:4] != b'\xcf\xfa\xed\xfe' or struct.unpack_from('<I', header, 4)[0] != 0x0100000c:
            raise ValueError(f'{path.name} is not a macOS arm64 executable')
        libraries = run(['/usr/bin/otool', '-L', path]).stdout.splitlines()[1:]
        external = [line.strip().split(' (compatibility version')[0] for line in libraries
                    if line.strip() and not line.strip().startswith(('/usr/lib/', '/System/Library/'))]
        if external:
            raise ValueError(f'{path.name} depends on unbundled libraries: {external}')


def run(command, timeout=180):
    result = subprocess.run(list(map(str, command)), capture_output=True, text=True,
                            timeout=timeout)
    if result.returncode:
        raise ValueError(f'{Path(str(command[0])).name} failed ({result.returncode}): {result.stderr[-6000:]}')
    return result


def safe_pack_file(root, logical):
    if not isinstance(logical, str):
        raise ValueError('fixture stream path missing')
    name = PurePosixPath(logical)
    if name.is_absolute() or '..' in name.parts or '\\' in logical or ':' in logical:
        raise ValueError('fixture stream path escapes pack root')
    path = root.joinpath(*name.parts)
    if not path.resolve().is_relative_to(root.resolve()) or not path.is_file() or path.is_symlink():
        raise ValueError(f'fixture stream path missing/unsafe: {logical}')
    return path


def validate_pack(manifest, root):
    if manifest.get('target') != 'esp32s3':
        raise ValueError('fixture manifest target must be esp32s3')
    for key, expected in (('format','p4-h264-v1'), ('codec','h264'), ('container','annex-b'), ('width',240), ('height',180)):
        if manifest.get(key) != expected:
            raise ValueError(f'fixture manifest {key} mismatch')
    fps = manifest.get('fps', 0)
    families = manifest.get('families', [])
    if not isinstance(fps, int) or not 1 <= fps <= 10 or not 1 <= len(families) <= 24:
        raise ValueError('fixture manifest family/fps bounds violated')
    files = {}
    streams = []
    for family in families:
        logical = family.get('path')
        path = safe_pack_file(root, logical)
        data = path.read_bytes()
        actual_sha = hashlib.sha256(data).hexdigest()
        if logical != 'p4/families/sha256-' + actual_sha[:24] + '.h264':
            raise ValueError('fixture stream SHA-256 filename mismatch')
        if not 0 < len(data) <= 384 * 1024 or family.get('streamBytes') != len(data):
            raise ValueError('fixture stream byte bounds mismatch')
        nals = [nal for nal in re.split(b'\x00\x00\x00?\x01', data) if nal]
        frames = [nal for nal in nals if nal[0] & 31 in (1,5)]
        # Canonical SPS for 240x180 constrained-baseline tinyh264 profile,
        # independently fixed here rather than accepting converter self-report.
        expected_sps = bytes.fromhex('6742c01eda0f1979d0')
        sps = [nal for nal in nals if nal[0] & 31 == 7]
        if not sps or any(nal != expected_sps for nal in sps):
            raise ValueError('fixture stream canonical SPS mismatch')
        if not 1 <= len(frames) <= 300 or any(len(nal) < 2 or not nal[1] & 0x80 for nal in frames):
            raise ValueError('fixture stream single-slice/frame bounds violated')
        family_fps = family.get('fps', fps)
        if not isinstance(family_fps, int) or not 1 <= family_fps <= 10 or len(frames) > 30 * family_fps or family.get('frames') != len(frames):
            raise ValueError('fixture stream timing/frame count mismatch')
        files[logical] = path
        if family.get('audioPath'):
            raise ValueError('video-only smoke fixture unexpectedly contains audio')
        streams.append({'path':logical, 'frames':len(frames), 'bytes':len(data), 'sha256':actual_sha})
    if sum(path.stat().st_size + 3 for path in files.values()) + 4096 > 3 * 1024 * 1024:
        raise ValueError('fixture exceeds S3 flash slot bounds')
    identity = copy.deepcopy(manifest)
    identity['packId'] = ''
    encoded = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    digest = hashlib.sha256(b'pet-manager-p4-pack-v1\0')
    digest.update(struct.pack('<Q', len(encoded)))
    digest.update(encoded)
    for logical, path in sorted(files.items()):
        key = logical.encode(); data = path.read_bytes()
        digest.update(struct.pack('<Q', len(key))); digest.update(key)
        digest.update(struct.pack('<Q', len(data))); digest.update(data)
    if manifest.get('packId') != digest.hexdigest():
        raise ValueError('fixture packId SHA-256 mismatch')
    return {'target':'esp32s3', 'packId':digest.hexdigest(), 'streams':streams}


def load_preparer():
    spec = importlib.util.spec_from_file_location('preview_preparer', Path(__file__).with_name('prepare-preview-resources.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_lgpl(runtime, target, installed=False):
    prepare = load_preparer()
    names = ['ffmpeg.exe' if target == 'windows' else 'ffmpeg',
             'ffmpeg.README', 'ffmpeg.LICENSE', 'ffmpeg.SOURCE.txt']
    if target == 'windows':
        names.append('zlib.LICENSE')
    files = {name:runtime / name for name in names}
    files[prepare.SOURCE_NAME] = runtime / ('source' if installed else '') / prepare.SOURCE_NAME
    prepare.validate_staged(files, target)
    validate_executable(files[names[0]], target)
    return files


def validate_helper_metadata(tools):
    sources = {
        'ffmpeg-8.1.2.tar.xz':'464beb5e7bf0c311e68b45ae2f04e9cc2af88851abb4082231742a74d97b524c',
        'x264-baee400fa9ced6f5481a728138fed6e867b0ff7f.tar.gz':'436a2be54d8bc0cb05dd33ecbbcb7df9c3b57362714fcdaa3a5991189a33319b',
    }
    for name, expected in sources.items():
        path = tools / 'source' / name
        if not path.is_file():
            raise ValueError(f'S3 helper corresponding source archive missing: {name}')
        if sha256(path) != expected:
            raise ValueError(f'S3 helper source SHA-256 mismatch: {name}')
    for name in ('source/build-s3-ffmpeg.sh', 'source/x264-AUTHORS.txt',
                 'LICENSE-FFmpeg-GPLv2.txt', 'LICENSE-FFmpeg-notices.md',
                 'LICENSE-x264-GPLv2.txt', 'BUILD-README.txt', 'BUILD-SOURCES.txt',
                 'BUILD-COMMANDS.txt', 'BUILD-ENV.txt', 'BUILD-ENCODER.txt',
                 'BUILD-SHA256SUMS.txt'):
        path = tools / name
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f'S3 helper license/build resource missing: {name}')
    for name in ('LICENSE-FFmpeg-GPLv2.txt', 'LICENSE-x264-GPLv2.txt'):
        if 'GNU GENERAL PUBLIC LICENSE' not in (tools / name).read_text(encoding='utf-8'):
            raise ValueError(f'S3 helper GPL license text missing: {name}')
    covered = set()
    for line in (tools / 'BUILD-SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
        if not match:
            raise ValueError('S3 helper build checksum manifest malformed')
        expected, logical = match.groups()
        path = safe_pack_file(tools, logical)
        if logical in covered or sha256(path) != expected:
            raise ValueError(f'S3 helper build checksum mismatch: {logical}')
        covered.add(logical)
    for name in sources:
        if 'source/' + name not in covered:
            raise ValueError(f'S3 helper build manifest omitted source: {name}')
    binary = 's3-ffmpeg.exe' if (tools / 's3-ffmpeg.exe').exists() else 's3-ffmpeg'
    if binary not in covered:
        raise ValueError('S3 helper binary absent from build checksum manifest')


def validate_converter_licenses(tools):
    licenses = tools / 'licenses'
    record = licenses / 'converter-runtime-licenses.json'
    if not record.is_file():
        raise ValueError('converter runtime license metadata missing')
    metadata = json.loads(record.read_text(encoding='utf-8'))
    notices = (
        ('python', 'CPython-LICENSE.txt', 'CPython', (
            'A. HISTORY OF THE SOFTWARE', 'PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2',
            'BEOPEN.COM LICENSE AGREEMENT', 'CNRI LICENSE AGREEMENT', 'CWI LICENSE AGREEMENT',
            'ZERO-CLAUSE BSD LICENSE', 'PERFORMANCE OF THIS SOFTWARE.',
        )),
        ('pyinstaller', 'PyInstaller-COPYING.txt', 'PyInstaller', (
            'The PyInstaller licensing terms', 'Bootloader Exception', 'Bootloader and Related Files',
            'GNU GENERAL PUBLIC LICENSE', 'Version 2, June 1991', 'Apache License', 'MIT License',
            'END OF TERMS AND CONDITIONS', 'SOFTWARE.',
        )),
    )
    for key, filename, name, markers in notices:
        entry = metadata.get(key, {})
        version = entry.get('version', '')
        if not isinstance(version, str) or not re.fullmatch(r'\d+\.\d+\.\d+', version) or entry.get('file') != filename:
            raise ValueError(f'{name} converter license identity mismatch')
        source = entry.get('source')
        expected_sources = ('installed CPython runtime', f'https://raw.githubusercontent.com/python/cpython/v{version}/LICENSE') if key == 'python' else ('installed PyInstaller distribution',)
        if source not in expected_sources:
            raise ValueError(f'{name} converter license source/version mismatch')
        path = licenses / filename
        if not path.is_file() or path.is_symlink():
            raise ValueError(f'converter runtime license missing: {filename}')
        if sha256(path) != entry.get('sha256'):
            raise ValueError(f'{name} converter license SHA-256 mismatch')
        data = path.read_bytes()
        try:
            text = data.decode('utf-8')
        except UnicodeError as error:
            raise ValueError(f'{name} converter license incomplete or not UTF-8') from error
        if len(data) < 4096 or any(marker not in text for marker in markers):
            raise ValueError(f'{name} converter license incomplete')
    return metadata


def validate_node_notice(node, notice):
    if not notice.is_file() or notice.is_symlink():
        raise ValueError('Node full runtime license is missing')
    prepare = load_preparer()
    prepare.validate_node_license(notice.read_bytes())
    version = run([node, '-p', 'process.versions.node']).stdout.strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Node runtime version is not an exact stable version')
    return {'version':version, 'source':f'https://raw.githubusercontent.com/nodejs/node/v{version}/LICENSE',
            'licenseSha256':sha256(notice)}


def verify(target, tools, runtime, firmware, fixture, resource_root=None):
    suffix = '.exe' if target == 'windows' else ''
    converter = tools / ('prepare-s3-assets' + suffix)
    helper = tools / ('s3-ffmpeg' + suffix)
    firmware_info = validate_firmware(firmware)
    validate_lgpl(runtime, target, installed=resource_root is not None)
    node = (resource_root / 'bridge/runtime' if resource_root else runtime) / ('node' + suffix)
    for binary in (converter, helper, node):
        validate_executable(binary, target)
    validate_helper_metadata(tools)
    converter_licenses = validate_converter_licenses(tools)
    node_notice = resource_root / 'licenses/Node-LICENSE.txt' if resource_root else runtime / 'node.LICENSE'
    node_metadata = validate_node_notice(node, node_notice)
    help_text = run([converter, '--help']).stdout
    if '--source' not in help_text or '--ffmpeg' not in help_text:
        raise ValueError('standalone converter --help contract mismatch')
    version = run([helper, '-hide_banner', '-version']).stdout
    encoders = run([helper, '-hide_banner', '-encoders']).stdout
    if '--enable-gpl' not in version or 'libx264' not in encoders:
        raise ValueError('separate S3 FFmpeg helper lacks GPL/libx264 encoder')
    if not fixture.is_file() or fixture.read_bytes()[:100].startswith(b'version https://git-lfs.github.com/spec/v1'):
        raise ValueError(f'real smoke input video missing: {fixture}')
    with tempfile.TemporaryDirectory(prefix='hachimo-s3-native-smoke-') as temporary:
        temp = Path(temporary)
        source = temp / 'input'; source.mkdir()
        # Use the real committed welcome video, bounded to one second. No lavfi
        # input/device support or network is needed in the standalone helper.
        run([helper, '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
             '-i', fixture, '-t', '1', '-an', '-c:v', 'libx264',
             '-pix_fmt', 'yuv420p', source / 'fixture.mp4'])
        output = temp / 'output'
        run([converter, '--source', source, '--output', output, '--ffmpeg', helper])
        manifest = json.loads((output / 'p4/manifest.json').read_text(encoding='utf-8'))
        smoke = validate_pack(manifest, output)
        for stream in smoke['streams']:
            decoded = temp / 'decoded.yuv'
            run([helper, '-hide_banner', '-loglevel', 'error', '-xerror',
                 '-nostdin', '-y', '-i', output / stream['path'], '-an',
                 '-pix_fmt', 'yuv420p', '-f', 'rawvideo', decoded])
            if decoded.stat().st_size != stream['frames'] * 240 * 180 * 3 // 2:
                raise ValueError('SPS-rewritten fixture decoded frame size/count mismatch')
            stream['decodedFrames'] = stream['frames']
    files = {}
    for base, prefix in ((tools, 'tools/s3-runtime'), (runtime, 'tools')):
        for path in sorted(base.rglob('*')):
            if path.is_symlink():
                raise ValueError(f'resource symlink is not portable: {path.name}')
            if path.is_file() and path.name not in ('preview-resource-manifest.json', 'preview-resource-SHA256SUMS'):
                # The staged tools tree is nested beneath runtime; enumerate it
                # once under its actual installed tools/ destination.
                if base == runtime and tools != runtime and path.is_relative_to(tools):
                    continue
                relative = path.relative_to(base).as_posix()
                if resource_root is None and base == runtime and relative == 'node.LICENSE':
                    # This notice is shipped outside tools/, beside the app's
                    # other independent runtime licenses.
                    continue
                if resource_root is None and base == runtime and relative == 'ffmpeg-8.1.2.tar.xz':
                    relative = 'source/' + relative
                logical = ('bridge/runtime/' if resource_root is None and base == runtime and relative in ('node', 'node.exe') else prefix + '/') + relative
                info = {'sha256':sha256(path), 'bytes':path.stat().st_size}
                if logical in files and files[logical] != info:
                    raise ValueError(f'resource destination collision: {logical}')
                files[logical] = info
    files['bridge/runtime/' + node.name] = {'sha256':sha256(node), 'bytes':node.stat().st_size}
    files['licenses/Node-LICENSE.txt'] = {'sha256':sha256(node_notice), 'bytes':node_notice.stat().st_size}
    files['firmware/esp32-s3/firmware.bin'] = {'sha256':firmware_info['sha256'], 'bytes':firmware_info['bytes']}
    return {'schemaVersion':1, 'target':target + ('-x64' if target == 'windows' else '-arm64'),
            'upstreamRuntimeVersion':'0.1.167', 'firmware':firmware_info,
            'nodeRuntime':node_metadata, 'converterRuntimeLicenses':converter_licenses,
            'converterSmoke':smoke, 'files':dict(sorted(files.items()))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True, choices=('windows', 'macos'))
    parser.add_argument('--tools-dir', type=Path)
    parser.add_argument('--runtime-dir', type=Path, default=ROOT / 'pc/src-tauri/generated-runtime')
    parser.add_argument('--resource-root', type=Path, help='Extracted installed application resource root')
    parser.add_argument('--fixture', type=Path, default=ROOT / 'pc/public/terrier-clips/welcome.mp4')
    parser.add_argument('--manifest', type=Path, help='Manifest destination (outside installed resource tree)')
    args = parser.parse_args()
    host = {'win32':'windows', 'darwin':'macos'}.get(sys.platform)
    if host != args.target:
        parser.error('executable smoke verification must run on the native target host')
    resource_root = args.resource_root.resolve() if args.resource_root else None
    runtime = resource_root / 'tools' if resource_root else args.runtime_dir.resolve()
    tools = resource_root / 'tools/s3-runtime' if resource_root else (args.tools_dir or runtime / 's3').resolve()
    firmware = (resource_root if resource_root else ROOT / 'pc/src-tauri') / 'firmware/esp32-s3/firmware.bin'
    result = verify(args.target, tools, runtime, firmware, args.fixture.resolve(), resource_root)
    destination = args.manifest or ROOT / 'pc/src-tauri/preview-resource-manifest.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    destination.with_name(destination.stem + '-SHA256SUMS').write_text(
        ''.join(value['sha256'] + '  ' + name + '\n' for name, value in result['files'].items()), encoding='utf-8')
    print(json.dumps({'manifest':str(destination), 'files':len(result['files']),
                      'target':result['target'], 'converterSmoke':result['converterSmoke']}, sort_keys=True))


if __name__ == '__main__':
    main()
