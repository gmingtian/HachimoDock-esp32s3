"""Select the current NSIS installer without publishing stale cached builds."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC=importlib.util.spec_from_file_location('desktop_package',Path(__file__).resolve().parents[1]/'package-desktop-client.py')
package=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(package)

class WindowsInstallerTests(unittest.TestCase):
    def test_current_installer_is_selected_when_old_version_remains(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for version in ('0.1.201','0.1.202'):
                (root/f'HachimiDock_{version}_x64-setup.exe').write_bytes(version.encode())
            current=package.select_windows_installer(root,'0.1.202')
            self.assertEqual(current.read_bytes(),b'0.1.202')

    def test_wrong_version_and_unknown_filename_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'HachimiDock_0.1.201_x64-setup.exe').write_bytes(b'stale')
            (root/'unrecognized_0.1.202.exe').write_bytes(b'unknown')
            with self.assertRaisesRegex(ValueError,'current Windows NSIS'):
                package.select_windows_installer(root,'0.1.202')

if __name__=='__main__':unittest.main()
