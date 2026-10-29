#!/usr/bin/env python3
"""Exercise source validation and transport fallback before source code executes."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BUILD = Path(__file__).with_name('build-s3-ffmpeg.sh')
MIRROR = 'https://github.com/YizhengWw/HachimoDock/releases/download/v0.1.167/FFmpeg-8.1.2-source.tar.xz'
AUTHORITATIVE = 'https://ffmpeg.org/releases/ffmpeg-8.1.2.tar.xz'


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


class SourceDownloadTests(unittest.TestCase):
    def invoke(self, root, mode):
        """Replace only the external HTTP transport; keep all validation real."""
        transport = root / 'curl'
        transport.write_text('''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys
calls = Path(os.environ['S3_TEST_CURL_CALLS'])
previous = calls.read_text().splitlines() if calls.exists() else []
with calls.open('a') as log:
    log.write(json.dumps(sys.argv[1:]) + '\\n')
Path(sys.argv[sys.argv.index('--output') + 1]).write_bytes(b'untrusted response')
mode = os.environ['S3_TEST_CURL_MODE']
if mode == 'local-fail':
    sys.exit(23)
sys.exit(28 if mode == 'all-fail' or (mode == 'first-fail' and not previous) else 0)
''')
        transport.chmod(0o755)
        calls = root / 'requests.jsonl'
        result = subprocess.run(
            ['bash', str(BUILD), str(root / 'output directory')],
            capture_output=True, text=True,
            env={**os.environ, 'PATH': str(root) + os.pathsep + os.environ['PATH'],
                 'S3_FFMPEG_SOURCE_DIR': str(root / 'cache'), 'S3_FFMPEG_OFFLINE': '0',
                 'S3_TEST_CURL_CALLS': str(calls), 'S3_TEST_CURL_MODE': mode},
        )
        requests = [json.loads(line) for line in calls.read_text().splitlines()]
        return result, requests

    def test_successful_mirror_response_with_wrong_hash_never_falls_back(self):
        with tempfile.TemporaryDirectory(prefix='s3 download ') as tmp:
            result, requests = self.invoke(Path(tmp), 'success')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Source checksum mismatch:', result.stderr)
            self.assertEqual([request[-1] for request in requests], [MIRROR])

    def test_transport_failure_falls_back_but_still_rejects_wrong_hash(self):
        with tempfile.TemporaryDirectory(prefix='s3 download ') as tmp:
            result, requests = self.invoke(Path(tmp), 'first-fail')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Source checksum mismatch:', result.stderr)
            self.assertEqual([request[-1] for request in requests], [MIRROR, AUTHORITATIVE])

    def test_failed_downloads_remove_partial_archive(self):
        with tempfile.TemporaryDirectory(prefix='s3 download ') as tmp:
            root = Path(tmp)
            result, requests = self.invoke(root, 'all-fail')
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual([request[-1] for request in requests], [MIRROR, AUTHORITATIVE])
            self.assertFalse(list((root / 'output directory' / 'source').glob('*.part')))

    def test_local_write_failure_never_requests_another_url(self):
        with tempfile.TemporaryDirectory(prefix='s3 download ') as tmp:
            root = Path(tmp)
            result, requests = self.invoke(root, 'local-fail')
            self.assertEqual(result.returncode, 23)
            self.assertEqual([request[-1] for request in requests], [MIRROR])
            self.assertFalse(list((root / 'output directory' / 'source').glob('*.part')))


if __name__ == '__main__':
    unittest.main()
