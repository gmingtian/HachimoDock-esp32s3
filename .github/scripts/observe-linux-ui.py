"""Observe an existing, SHA-pinned native client; never rebuild or weaken its sandbox."""
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tarfile
import time

SOURCE = 'e408705099aae853181195dd214d3549e65bd59c'
ARCHIVE_SHA = '5ce59a84f81bdc65b5814bed9c0f89e786fd7345d6ec3bc98a9df6098d9c7fcf'

archive, output = map(Path, sys.argv[1:])
assert hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest() == ARCHIVE_SHA
output.mkdir(parents=True, exist_ok=False)
with tarfile.open(archive, 'r:gz') as contents:
    contents.extractall(output / 'package', filter='data')
package = output / 'package/HachimoDock-Linux-x64'
binary = package / 'usr/bin/pet-manager-tauri'
raw = binary.read_bytes()
identity = b'0.1.202+e408705099aa'
assert identity in raw and identity + b'-dirty' not in raw, 'Unexpected native build identity'
environment = os.environ.copy()
for key, name in [('XDG_CONFIG_HOME','config'),('XDG_DATA_HOME','data'),('XDG_CACHE_HOME','cache'),('XDG_RUNTIME_DIR','runtime')]:
    directory = output / name
    directory.mkdir(mode=0o700)
    environment[key] = str(directory)
log = output / 'linux-ui-startup.log'
receipt = {'applicationSourceCommit':SOURCE, 'appBuildId':identity.decode(),
           'artifact':archive.name, 'artifactSha256':ARCHIVE_SHA,
           'binarySha256':hashlib.sha256(raw).hexdigest(),
           'diagnosticSourceCommit':os.environ['GITHUB_SHA'],
           'diagnosticRunId':int(os.environ['GITHUB_RUN_ID']),
           'context':'Ubuntu 24.04 native runner; Xvfb and fresh D-Bus session; default WebKit sandbox policy',
           'webViewFinished':False, 'frontendReady':False, 'accepted':False}
started = time.monotonic()
process = None
try:
    with log.open('wb') as stream:
        process = subprocess.Popen([str(package / 'launch.sh')], cwd=package,
                                   env=environment, stdout=stream, stderr=stream, start_new_session=True)
        while time.monotonic() - started < 90:
            text = log.read_text(errors='replace')
            receipt['webViewFinished'] = '[webview-load] window=main phase=Finished ' in text
            receipt['frontendReady'] = re.search(r'\[startup-native\] category=ready(?:\r?\n|$)', text) is not None
            if process.poll() is not None:
                raise RuntimeError(f'Native client exited: {process.returncode}')
            if receipt['webViewFinished'] and receipt['frontendReady'] and time.monotonic() - started >= 10:
                receipt['accepted'] = True
                break
            time.sleep(1)
        if not receipt['accepted']:
            raise RuntimeError('Native WebView/frontend readiness not observed within 90 seconds')
finally:
    receipt['observedSeconds'] = round(time.monotonic() - started, 2)
    if process is not None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=10)
        except ProcessLookupError:
            pass
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)
    (output / 'linux-ui-acceptance.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(log.read_text(errors='replace'))
    print(json.dumps(receipt, indent=2))
