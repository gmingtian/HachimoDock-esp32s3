#!/usr/bin/env python3
"""Exercise offline source validation before the build can execute source code."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BUILD = Path(__file__).with_name('build-s3-ffmpeg.sh')


class SourceIntegrityTests(unittest.TestCase):
    def invoke(self, cache, output):
        return subprocess.run(
            ['bash', str(BUILD), str(output)], capture_output=True, text=True,
            env={**os.environ, 'S3_FFMPEG_SOURCE_DIR': str(cache),
                 'S3_FFMPEG_OFFLINE': '1'},
        )

    def test_missing_offline_source_never_downloads_or_creates_binary(self):
        with tempfile.TemporaryDirectory(prefix='s3 build ') as tmp:
            root = Path(tmp)
            result = self.invoke(root, root / 'output directory')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Offline source archive missing:', result.stderr)
            self.assertFalse((root / 'output directory' / 's3-ffmpeg').exists())

    def test_corrupt_cached_source_is_rejected_before_extracting(self):
        with tempfile.TemporaryDirectory(prefix='s3 build ') as tmp:
            root = Path(tmp)
            (root / 'ffmpeg-8.1.2.tar.xz').write_bytes(b'not approved source')
            result = self.invoke(root, root / 'output directory')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Source checksum mismatch:', result.stderr)
            self.assertFalse((root / 'output directory' / 's3-ffmpeg').exists())


if __name__ == '__main__':
    unittest.main()
