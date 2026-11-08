"""Test the downloadable Linux archive, including unsafe/tampered artifacts."""
import importlib.util
import io
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest

SCRIPTS=Path(__file__).resolve().parents[1]

def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),SCRIPTS/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

class LinuxPackageTests(unittest.TestCase):
    def make_archive(self,root,*,mutation=None):
        stage=root/'stage'
        files={'launch.sh':b'#!/bin/sh\n','usr/bin/pet-manager-tauri':b'ELF example','usr/lib/HachimiDock/tools/prepare_s3_assets.py':b'converter'}
        artifact=root/'client.tar.gz'
        with tarfile.open(artifact,'w:gz') as archive:
            for name,data in files.items():
                path=stage/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
                info=tarfile.TarInfo('HachimoDock-Linux-x64/'+name);info.size=len(data);info.mode=0o755
                if mutation:info,data=mutation(info,data)
                archive.addfile(info,io.BytesIO(data) if info.isfile() else None)
        return artifact,stage

    def test_compressed_archive_preserves_complete_installed_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact,stage=self.make_archive(Path(tmp))
            load('package-desktop-client').verify_linux_archive(artifact,stage)

    def test_tampered_download_is_rejected(self):
        def mutate(info,data):
            data=b'x'*len(data)
            return info,data
        with tempfile.TemporaryDirectory() as tmp:
            artifact,stage=self.make_archive(Path(tmp),mutation=mutate)
            with self.assertRaisesRegex(ValueError,'content mismatch'):
                load('package-desktop-client').verify_linux_archive(artifact,stage)

    def test_unsafe_archive_paths_and_links_are_rejected(self):
        for name in ('../../outside','/absolute','HachimoDock-Linux-x64/../outside','HachimoDock-Linux-x64/\\outside'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp:
                def mutate(info,data):info.name=name;return info,data
                artifact,stage=self.make_archive(Path(tmp),mutation=mutate)
                with self.assertRaisesRegex(ValueError,'unsafe'):
                    load('package-desktop-client').verify_linux_archive(artifact,stage)
        def link(info,data):info.type=tarfile.SYMTYPE;info.linkname='/outside';return info,data
        with tempfile.TemporaryDirectory() as tmp:
            artifact,stage=self.make_archive(Path(tmp),mutation=link)
            with self.assertRaisesRegex(ValueError,'unsafe'):
                load('package-desktop-client').verify_linux_archive(artifact,stage)

    def test_lost_executable_permissions_are_rejected(self):
        def mutate(info,data):info.mode=0o644;return info,data
        with tempfile.TemporaryDirectory() as tmp:
            artifact,stage=self.make_archive(Path(tmp),mutation=mutate)
            with self.assertRaisesRegex(ValueError,'executable mode'):
                load('package-desktop-client').verify_linux_archive(artifact,stage)

    def test_linux_binary_validation_checks_elf_class_endian_and_machine(self):
        verify=load('verify-preview-resources')
        with tempfile.TemporaryDirectory() as tmp:
            binary=Path(tmp)/'node'
            for arch in (62,183):
                header=bytearray(64);header[:6]=b'\x7fELF\x02\x01';struct.pack_into('<H',header,18,arch);binary.write_bytes(header)
                if arch==62:verify.validate_executable(binary,'linux')
                else:
                    with self.assertRaisesRegex(ValueError,'Linux x86_64'):verify.validate_executable(binary,'linux')
            binary.write_bytes(b'\x7fELF\x01\x01'+b'\0'*58)
            with self.assertRaisesRegex(ValueError,'Linux x86_64'):verify.validate_executable(binary,'linux')

if __name__=='__main__':unittest.main()
