"""Fail closed before downloading, extracting, or running preview resources."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]

def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class PreviewPreparationTests(unittest.TestCase):
    def test_rejects_wrong_archive_before_extracting(self):
        prepare = load('prepare-preview-resources')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / 'installer.exe'
            archive.write_bytes(b'untrusted installer')
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                prepare.prepare('windows', root / 'cache', root / 'output', archive)
            self.assertFalse((root / 'output').exists())

    def test_rejects_ambiguous_archive_members(self):
        prepare = load('prepare-preview-resources')
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            prepare.select_members(['tools/ffmpeg.exe', 'other/ffmpeg.exe'], 'windows')

    def test_rejects_ambiguous_source_archives(self):
        prepare = load('prepare-preview-resources')
        names = ['tools/ffmpeg.exe', 'tools/ffmpeg.README', 'tools/ffmpeg.LICENSE',
                 'tools/ffmpeg.SOURCE.txt', 'tools/zlib.LICENSE',
                 'tools/source/ffmpeg-8.1.2.tar.xz', 'other/ffmpeg-8.1.2.tar.xz']
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            prepare.select_members(names, 'windows')

    def test_rejects_archive_path_escape(self):
        prepare = load('prepare-preview-resources')
        with self.assertRaisesRegex(ValueError, 'unsafe'):
            prepare.select_members(['../ffmpeg.exe'], 'windows')

    def test_selects_only_audited_media_files(self):
        prepare = load('prepare-preview-resources')
        names = ['app/tools/' + n for n in ('ffmpeg.exe', 'ffmpeg.README', 'ffmpeg.LICENSE',
                 'ffmpeg.SOURCE.txt', 'zlib.LICENSE', 'source/ffmpeg-8.1.2.tar.xz')]
        selected = prepare.select_members(names + ['app/node.exe', 'app/secret.txt'], 'windows')
        self.assertEqual(len(selected), 6)
        self.assertNotIn('node.exe', selected)
        self.assertEqual(selected['ffmpeg.exe'], 'app/tools/ffmpeg.exe')

class PreviewVerificationTests(unittest.TestCase):
    def test_missing_firmware_is_rejected(self):
        verify = load('verify-preview-resources')
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'firmware.*missing'):
                verify.validate_firmware(Path(tmp) / 'missing.bin')

    def test_p4_image_cannot_pass_s3_firmware_validation(self):
        verify = load('verify-preview-resources')
        firmware = SCRIPTS.parents[1] / 'pc/src-tauri/firmware/esp32-p4/firmware.bin'
        with self.assertRaisesRegex(ValueError, 'S3|chip'):
            verify.validate_firmware(firmware)

    def test_checked_in_firmware_is_real_pinned_s3_r1(self):
        verify = load('verify-preview-resources')
        firmware = SCRIPTS.parents[1] / 'pc/src-tauri/firmware/esp32-s3/firmware.bin'
        result = verify.validate_firmware(firmware)
        self.assertEqual(result['chipId'], 9)
        self.assertEqual(result['projectName'], 'pet_manager_s3_runtime')
        self.assertEqual(result['version'], '0.7.103-s3-r1')
        self.assertEqual(result['sha256'], 'e37a62e63b6a5590d400449c2c4514a83676e91987233e6692bd9dea7aa9a320')

    def test_corrupt_s3_helper_source_is_rejected(self):
        verify = load('verify-preview-resources')
        with tempfile.TemporaryDirectory() as tmp:
            tools = Path(tmp)
            (tools / 'source').mkdir()
            (tools / 'source/ffmpeg-8.1.2.tar.xz').write_bytes(b'unverified source')
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                verify.validate_helper_metadata(tools)

    def test_helper_metadata_rejects_placeholder_source_directories(self):
        verify = load('verify-preview-resources')
        with tempfile.TemporaryDirectory() as tmp:
            tools = Path(tmp)
            (tools / 'source').mkdir()
            (tools / 'source/README').write_text('sources available elsewhere')
            with self.assertRaisesRegex(ValueError, 'source.*missing'):
                verify.validate_helper_metadata(tools)

    def test_rejects_foreign_executable_before_running_it(self):
        verify = load('verify-preview-resources')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'wrong.exe'
            path.write_bytes(b'#!/bin/sh\nexit 0\n')
            with self.assertRaisesRegex(ValueError, 'Windows x64'):
                verify.validate_executable(path, 'windows')

    @unittest.skipUnless(os.environ.get('FFMPEG') or shutil.which('ffmpeg'), 'FFMPEG executable required for real conversion')
    def test_real_conversion_has_canonical_sps_and_detects_manifest_tampering(self):
        verify = load('verify-preview-resources')
        ffmpeg = os.environ.get('FFMPEG') or shutil.which('ffmpeg')
        root = SCRIPTS.parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            source = temp / 'input'; source.mkdir()
            subprocess.run([ffmpeg, '-v', 'error', '-nostdin', '-y', '-i',
                            str(root / 'pc/public/terrier-clips/welcome.mp4'),
                            '-t', '1', '-an', '-c:v', 'libx264',
                            str(source / 'fixture.mp4')], check=True)
            output = temp / 'output'
            subprocess.run([sys.executable, str(root / 'firmware/tools/prepare_s3_assets.py'),
                            '--source', str(source), '--output', str(output),
                            '--ffmpeg', ffmpeg], check=True, capture_output=True)
            manifest = json.loads((output / 'p4/manifest.json').read_text())
            smoke = verify.validate_pack(manifest, output)
            self.assertEqual(smoke['streams'][0]['frames'], 10)
            stream = output / smoke['streams'][0]['path']
            decoded = temp / 'decoded.yuv'
            subprocess.run([ffmpeg, '-v', 'error', '-xerror', '-nostdin', '-y',
                            '-i', str(stream), '-pix_fmt', 'yuv420p',
                            '-f', 'rawvideo', str(decoded)], check=True)
            self.assertEqual(decoded.stat().st_size, 648000)
            manifest['packId'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'packId'):
                verify.validate_pack(manifest, output)
            stream.write_bytes(stream.read_bytes() + b'changed')
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                verify.validate_pack(manifest, output)

    def test_rejects_fixture_manifest_target_substitution(self):
        verify = load('verify-preview-resources')
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'target'):
                verify.validate_pack({'target':'esp32p4'}, Path(tmp))

    def test_rejects_fixture_manifest_path_escape(self):
        verify = load('verify-preview-resources')
        manifest = {'target':'esp32s3', 'format':'p4-h264-v1', 'codec':'h264',
                    'container':'annex-b', 'width':240, 'height':180, 'fps':10,
                    'families':[{'path':'../../outside.h264', 'frames':1, 'streamBytes':10, 'fps':10}]}
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'path'):
                verify.validate_pack(manifest, Path(tmp))

class RuntimeLicenseTests(unittest.TestCase):
    def test_short_node_mit_notice_cannot_replace_full_third_party_licenses(self):
        prepare = load('prepare-preview-resources')
        with self.assertRaisesRegex(ValueError, 'Node.*incomplete'):
            prepare.collect_node_license('22.21.1', fetch=lambda url: b'Copyright Node.js contributors. All rights reserved.')

    def test_node_license_must_match_exact_stable_runtime_version(self):
        prepare = load('prepare-preview-resources')
        with self.assertRaisesRegex(ValueError, 'Node.*version'):
            prepare.collect_node_license('22.0.0-nightly', fetch=lambda url: self.fail('must not fetch'))

    def test_converter_notices_cannot_be_omitted_from_installed_tools(self):
        verify = load('verify-preview-resources')
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'converter.*license.*missing'):
                verify.validate_converter_licenses(Path(tmp))

    def test_converter_license_metadata_cannot_hide_shortened_notices(self):
        verify = load('verify-preview-resources')
        with tempfile.TemporaryDirectory() as tmp:
            tools = Path(tmp)
            licenses = tools / 'licenses'; licenses.mkdir()
            python = b'PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2'
            installer = b'Bootloader Exception'
            (licenses / 'CPython-LICENSE.txt').write_bytes(python)
            (licenses / 'PyInstaller-COPYING.txt').write_bytes(installer)
            metadata = {'python':{'version':'3.12.12', 'file':'CPython-LICENSE.txt',
                                 'source':'installed CPython runtime', 'sha256':hashlib.sha256(python).hexdigest()},
                        'pyinstaller':{'version':'6.16.0', 'file':'PyInstaller-COPYING.txt',
                                       'source':'installed PyInstaller distribution', 'sha256':hashlib.sha256(installer).hexdigest()}}
            (licenses / 'converter-runtime-licenses.json').write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError, 'CPython.*incomplete'):
                verify.validate_converter_licenses(tools)

    def test_converter_metadata_checks_notice_hash_before_accepting_full_text(self):
        verify = load('verify-preview-resources')
        with tempfile.TemporaryDirectory() as tmp:
            tools = Path(tmp)
            licenses = tools / 'licenses'; licenses.mkdir()
            python = b'notice bytes'
            (licenses / 'CPython-LICENSE.txt').write_bytes(python)
            metadata = {'python':{'version':'3.12.12', 'file':'CPython-LICENSE.txt',
                                 'source':'installed CPython runtime', 'sha256':'0' * 64}}
            (licenses / 'converter-runtime-licenses.json').write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                verify.validate_converter_licenses(tools)

if __name__ == '__main__':
    unittest.main()
