#!/usr/bin/env python3
"""Verify the fixed A4 hardware manifest and create a portable ZIP.

Usage: python tools/package_a4_hardware.py --output artifacts/A4-hardware.zip
No CAD tools, downloads, local Fusion state or unlisted source files are used.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'hardware/release-manifest.json'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verified_inputs(root=ROOT, manifest_path=MANIFEST):
    root = Path(root).resolve()
    manifest_path = Path(manifest_path)
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    entries = {}
    for entry in manifest['files']:
        logical = entry.get('path')
        if not isinstance(logical, str) or not logical:
            raise ValueError('Manifest path must be a nonempty relative POSIX path')
        name = PurePosixPath(logical)
        if (name.is_absolute() or '..' in name.parts or '\\' in logical or ':' in logical
                or name.as_posix() != logical or logical in entries):
            raise ValueError(f'Unsafe or duplicate manifest path: {logical}')
        path = root.joinpath(*name.parts)
        if not path.resolve().is_relative_to(root) or path == manifest_path:
            raise ValueError(f'Manifest path escapes the source root or lists itself: {logical}')
        if any(parent.is_symlink() for parent in [path, *path.parents] if parent != root):
            raise ValueError(f'Manifest path contains a symlink: {logical}')
        if not path.is_file():
            raise ValueError(f'Manifest input is missing: {logical}')
        if not isinstance(entry.get('bytes'), int) or not 0 <= entry['bytes'] < 90 * 1024 * 1024:
            raise ValueError(f'Unexpected manifest size: {logical}')
        expected = entry.get('sha256', '')
        if not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
            raise ValueError(f'Invalid SHA-256: {logical}')
        data = path.read_bytes()
        if len(data) != entry['bytes'] or digest(data) != expected:
            raise ValueError(f'Manifest input changed: {logical}')
        entries[logical] = (path, entry)
    if manifest.get('fileCount') != len(entries) or manifest.get('totalBytes') != sum(e['bytes'] for _, e in entries.values()):
        raise ValueError('Manifest aggregate file count or size does not match its inventory')
    return manifest, manifest_bytes, entries


def package(output):
    manifest, manifest_bytes, entries = verified_inputs()
    output = Path(output).resolve()
    if output == MANIFEST.resolve() or output in {p.resolve() for p, _ in entries.values()}:
        raise ValueError('Output must not overwrite a listed source or its manifest')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix=output.name + '.', suffix='.tmp', dir=output.parent, delete=False) as stream:
            temporary = Path(stream.name)
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for logical in sorted(entries):
                path, entry = entries[logical]
                data = path.read_bytes()
                if len(data) != entry['bytes'] or digest(data) != entry['sha256']:
                    raise ValueError(f'Input changed during packaging: {logical}')
                info = zipfile.ZipInfo(logical, date_time=(2026, 11, 8, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data)
            info = zipfile.ZipInfo('hardware/release-manifest.json', date_time=(2026, 11, 8, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, manifest_bytes)
        with zipfile.ZipFile(temporary) as archive:
            expected_names = set(entries) | {'hardware/release-manifest.json'}
            if len(archive.namelist()) != len(expected_names) or set(archive.namelist()) != expected_names or archive.testzip() is not None:
                raise ValueError('Packaged ZIP inventory or CRC check failed')
            for logical, (_, entry) in entries.items():
                data = archive.read(logical)
                if len(data) != entry['bytes'] or digest(data) != entry['sha256']:
                    raise ValueError(f'Packaged content mismatch: {logical}')
            if archive.read('hardware/release-manifest.json') != manifest_bytes:
                raise ValueError('Packaged manifest differs from verified input')
        os.replace(temporary, output)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {'release': manifest['release'], 'archive': str(output), 'archiveBytes': output.stat().st_size,
            'sha256': digest(output.read_bytes()), 'manifestFiles': len(entries), 'zipEntries': len(entries) + 1,
            'uncompressedManifestBytes': manifest['totalBytes'], 'verified': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(package(args.output), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
