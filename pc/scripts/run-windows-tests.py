#!/usr/bin/env python3
"""Give Cargo's unit-test EXE the Common Controls manifest Tauri adds to its app.

embed-resource's default compile() links the Tauri resource to binary targets,
not the library test harness. TaskDialogIndirect requires Common Controls v6.
Only the native test executable is updated; distribution EXEs keep Tauri's manifest.
"""
import os
from pathlib import Path
import subprocess
import sys


def main():
    if sys.platform != 'win32' or len(sys.argv) < 2:
        raise SystemExit('Usage on Windows: run-windows-tests.py TEST_EXE [TEST_ARGS...]')
    exe = Path(sys.argv[1]).resolve()
    target = Path(__file__).resolve().parents[1] / 'src-tauri/target/x86_64-pc-windows-msvc/release/deps'
    if exe.parent != target or not exe.name.startswith('pet_manager_tauri_lib-') or exe.suffix != '.exe':
        raise SystemExit('Refusing to update a non-test executable')
    kit = Path(os.environ['ProgramFiles(x86)']) / 'Windows Kits/10/bin'
    tools = sorted(kit.glob('*/x64/mt.exe'), reverse=True)
    if not tools:
        raise SystemExit('Windows SDK manifest tool is missing')
    manifest = Path(__file__).with_name('windows-test.manifest').resolve()
    subprocess.run([str(tools[0]), '-nologo', '-manifest', str(manifest),
                    '-outputresource:' + str(exe) + ';#1'], check=True)
    print('Native unit-test manifest: Common Controls v6, asInvoker', flush=True)
    raise SystemExit(subprocess.run([str(exe), *sys.argv[2:]]).returncode)


if __name__ == '__main__':
    main()
