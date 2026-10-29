"""The frozen converter must ship complete notices for its build runtimes."""
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "build-s3-converter.py"
SPEC = importlib.util.spec_from_file_location("build_s3_converter", SCRIPT)
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)

# Complete matching-tag upstream notices are deterministic offline fixtures.
# https://raw.githubusercontent.com/python/cpython/v3.12.12/LICENSE
# https://raw.githubusercontent.com/pyinstaller/pyinstaller/v6.16.0/COPYING.txt
FIXTURES = Path(__file__).resolve().parent / "fixtures"
PYTHON_NOTICE = (FIXTURES / "cpython-3.12.12-LICENSE.txt").read_bytes()
PYINSTALLER_NOTICE = (FIXTURES / "pyinstaller-6.16.0-COPYING.txt").read_bytes()


class ConverterLicenseTests(unittest.TestCase):
    def distribution(self, root, notice=PYINSTALLER_NOTICE):
        info = root / "pyinstaller-6.16.0.dist-info"
        (info / "licenses").mkdir(parents=True)
        (info / "METADATA").write_text("Metadata-Version: 2.4\nName: pyinstaller\nVersion: 6.16.0\n")
        (info / "RECORD").write_text("pyinstaller-6.16.0.dist-info/licenses/COPYING.txt,,\n")
        if notice is not None:
            (info / "licenses/COPYING.txt").write_bytes(notice)
        return importlib.metadata.Distribution.at(info)

    def collect(self, root, candidates, distribution=None, download=None):
        return BUILD.collect_runtime_licenses(
            python_version="3.12.12", python_candidates=candidates,
            pyinstaller_distribution=distribution or self.distribution(root),
            download=download or (lambda url: self.fail(f"Unexpected download: {url}")),
        )

    def test_preserves_installed_notices_and_records_matching_runtime_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local = root / "python/LICENSE.txt"
            local.parent.mkdir()
            local.write_bytes(PYTHON_NOTICE)
            notices = self.collect(root, [local])
            self.assertEqual(notices["CPython-LICENSE.txt"], PYTHON_NOTICE)
            self.assertEqual(notices["PyInstaller-COPYING.txt"], PYINSTALLER_NOTICE)
            metadata = json.loads(notices["converter-runtime-licenses.json"])
            self.assertEqual(metadata["python"]["version"], "3.12.12")
            self.assertEqual(metadata["pyinstaller"]["version"], "6.16.0")
            self.assertIn(b"Bootloader Exception", notices["PyInstaller-COPYING.txt"])
            self.assertNotIn(str(root), notices["converter-runtime-licenses.json"].decode())

    def test_missing_python_license_downloads_only_the_exact_cpython_release_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def official(url):
                self.assertEqual(url, "https://raw.githubusercontent.com/python/cpython/v3.12.12/LICENSE")
                return PYTHON_NOTICE
            notices = self.collect(root, [root / "missing/LICENSE"], download=official)
            self.assertEqual(notices["CPython-LICENSE.txt"], PYTHON_NOTICE)

    def test_incomplete_python_notice_is_rejected_before_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local = root / "LICENSE.txt"
            local.write_bytes(b"Python Software Foundation License Version 2")
            with self.assertRaisesRegex(ValueError, "CPython.*incomplete"):
                self.collect(root, [local])

    def test_missing_or_incomplete_pyinstaller_exception_fails_closed(self):
        for notice in (None, PYINSTALLER_NOTICE.replace(b"Bootloader Exception", b"Removed exception")):
            with self.subTest(notice=notice is None), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                local = root / "LICENSE.txt"
                local.write_bytes(PYTHON_NOTICE)
                distribution = self.distribution(root, notice)
                with self.assertRaisesRegex(ValueError, "PyInstaller.*(missing|incomplete)"):
                    self.collect(root, [local], distribution=distribution)

    def test_network_failure_and_incomplete_response_do_not_omit_python_notice(self):
        for response in (OSError("offline"), b"404: Not Found"):
            with self.subTest(response=response), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                def unavailable(url):
                    if isinstance(response, Exception):
                        raise response
                    return response
                with self.assertRaisesRegex((ValueError, RuntimeError), "CPython"):
                    self.collect(root, [], download=unavailable)


if __name__ == "__main__":
    unittest.main()
