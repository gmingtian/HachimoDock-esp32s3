"""Exercise the real factory ZIP contract and reject incompatible firmware."""
import importlib.util
import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile

SPEC=importlib.util.spec_from_file_location('package_s3_release',Path(__file__).with_name('package_s3_release.py'))
release=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(release)

class S3ReleasePackageTests(unittest.TestCase):
    def images(self,root,version='0.7.103-s3-r16c-80m-l320'):
        app=bytearray(512);app[0]=0xe9;app[12:14]=b'\x09\x00'
        app[48:48+len(version)]=version.encode('ascii')
        project=b'pet_manager_s3_runtime';app[80:80+len(project)]=project
        full=bytearray(b'\xff')*(16*1024*1024);full[0]=0xe9;full[12:14]=b'\x09\x00'
        full[0x10000:0x10000+len(app)]=app
        factory=root/'factory.bin';application=root/'app.bin'
        factory.write_bytes(full);application.write_bytes(app)
        return factory,application

    def test_current_factory_zip_defaults_to_a4_native_landscape_and_separate_ota(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);factory,app=self.images(root)
            output=root/'factory.zip';ota=root/'upgrade.bin'
            release.package(factory,app,output,upgrade_output=ota)
            self.assertEqual(ota.read_bytes(),app.read_bytes())
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(archive.read(release.PREFIX+'hachimodock-s3-factory.bin'),factory.read_bytes())
                text=archive.read(release.PREFIX+'使用说明.txt').decode('utf-8-sig')
                for expected in ('A4','320×240','原生合成','80MHz','GPIO1 / 2','0x10000','0x0'):
                    self.assertIn(expected,text)
                for obsolete in ('三键操作','640×480 UI','25 个','28 个','GPIO39：短按上一项'):
                    self.assertNotIn(obsolete,text)
                sums=archive.read(release.PREFIX+'SHA256SUMS').decode()
                self.assertIn('  使用说明.txt\n',sums)
                for line in sums.splitlines():
                    digest,name=line.split('  ',1)
                    self.assertEqual(hashlib.sha256(archive.read(release.PREFIX+name)).hexdigest(),digest,name)

    def test_square_is_explicit_and_still_requires_matching_application(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);factory,app=self.images(root,'0.7.103-s3-r16c-80m')
            release.package(factory,app,root/'square.zip',display_profile='square')
            with zipfile.ZipFile(root/'square.zip') as archive:
                text=archive.read(release.PREFIX+'使用说明.txt').decode('utf-8-sig')
                self.assertIn('240×240',text);self.assertIn('A4',text)
                self.assertNotIn('三键操作',text)
            with self.assertRaisesRegex(ValueError,'display variant'):
                release.package(factory,app,root/'wrong-default.zip')

    def test_factory_ota_mismatch_never_creates_release(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);factory,app=self.images(root)
            changed=bytearray(app.read_bytes());changed[-1]^=1;app.write_bytes(changed)
            with self.assertRaisesRegex(ValueError,'does not match'):
                release.package(factory,app,root/'invalid.zip')
            self.assertFalse((root/'invalid.zip').exists())

    def test_foreign_chip_and_wrong_profile_are_rejected(self):
        for bad_chip in (False,True):
            with self.subTest(bad_chip=bad_chip),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);factory,app=self.images(root)
                if bad_chip:
                    changed=bytearray(app.read_bytes());changed[12:14]=b'\x10\x00';app.write_bytes(changed)
                with self.assertRaisesRegex(ValueError,'ESP32-S3' if bad_chip else 'display variant'):
                    release.package(factory,app,root/'invalid.zip',display_profile='square')
                self.assertFalse((root/'invalid.zip').exists())

    def test_wrong_project_and_incomplete_factory_are_rejected(self):
        for truncated in (False,True):
            with self.subTest(truncated=truncated),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);factory,app=self.images(root)
                if truncated:factory.write_bytes(factory.read_bytes()[:-1])
                else:
                    data=bytearray(app.read_bytes());data[80:112]=b'wrong_project'.ljust(32,b'\0');app.write_bytes(data)
                    full=bytearray(factory.read_bytes());full[0x10000:0x10000+len(data)]=data;factory.write_bytes(full)
                with self.assertRaisesRegex(ValueError,'16MiB' if truncated else 'Unexpected application project'):
                    release.package(factory,app,root/'invalid.zip')
                self.assertFalse((root/'invalid.zip').exists())

if __name__=='__main__':unittest.main()
