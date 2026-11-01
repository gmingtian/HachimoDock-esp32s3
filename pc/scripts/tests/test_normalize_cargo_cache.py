"""Cargo target reuse must preserve the absolute workspace used by build scripts."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'normalize-cargo-cache.py'


def load():
    spec = importlib.util.spec_from_file_location('normalize_cargo_cache', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CargoCacheTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.tauri = self.root / 'pc/src-tauri'
        self.tauri.mkdir(parents=True)
        (self.tauri / 'Cargo.toml').write_text('[package]\nname = "test"\n')
        self.target = self.tauri / 'target'
        self.registry = self.root / '.cargo/registry'
        self.registry.mkdir(parents=True)
        (self.registry / 'keep').write_text('crate source')

    def populated_target(self):
        artifact = self.target / 'release/build/tauri/out/stale-permissions.toml'
        artifact.parent.mkdir(parents=True)
        artifact.write_text('old absolute workspace')
        return artifact

    def test_missing_marker_discards_populated_target_and_preserves_registry(self):
        artifact = self.populated_target()
        result = load().normalize_cache(self.root)
        self.assertTrue(result['cleared'])
        self.assertFalse(artifact.exists())
        expected = self.root.resolve().as_posix()
        if sys.platform == 'win32':
            expected = expected.casefold()
        self.assertEqual((self.target / '.desktop-workspace-root').read_text().strip(), expected)
        self.assertEqual((self.registry / 'keep').read_text(), 'crate source')

    def test_different_workspace_discards_cached_target(self):
        artifact = self.populated_target()
        (self.target / '.desktop-workspace-root').write_text('/old/repository-name\n')
        self.assertTrue(load().normalize_cache(self.root)['cleared'])
        self.assertFalse(artifact.exists())

    def test_same_workspace_keeps_existing_artifacts(self):
        artifact = self.populated_target()
        (self.target / '.desktop-workspace-root').write_text(self.root.resolve().as_posix() + '\n')
        self.assertFalse(load().normalize_cache(self.root)['cleared'])
        self.assertEqual(artifact.read_text(), 'old absolute workspace')

    def test_new_and_empty_target_record_current_workspace(self):
        module = load()
        self.assertFalse(module.normalize_cache(self.root)['cleared'])
        marker = self.target / '.desktop-workspace-root'
        self.assertTrue(marker.is_file())
        marker.unlink()
        self.assertFalse(module.normalize_cache(self.root)['cleared'])
        self.assertTrue(marker.is_file())

    def test_windows_workspace_comparison_ignores_case(self):
        artifact = self.populated_target()
        (self.target / '.desktop-workspace-root').write_text(self.root.resolve().as_posix().upper() + '\n')
        self.assertFalse(load().normalize_cache(self.root, windows=True)['cleared'])
        self.assertTrue(artifact.exists())

    def test_unrecognized_repository_is_rejected_before_deleting(self):
        artifact = self.populated_target()
        (self.tauri / 'Cargo.toml').unlink()
        with self.assertRaisesRegex(ValueError, 'Cargo.toml'):
            load().normalize_cache(self.root)
        self.assertTrue(artifact.exists())


if __name__ == '__main__':
    unittest.main()
