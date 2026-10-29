#!/usr/bin/env python3
"""Report unresolved native imports without running application entry points."""
import ctypes
from ctypes import wintypes
from pathlib import Path
import sys


def main():
    if sys.platform != 'win32':
        raise SystemExit('Windows loader diagnostics require Windows')
    import pefile  # Installed by the Windows PyInstaller build dependency.
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetModuleFileNameW.argtypes = [wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
    kernel.GetModuleFileNameW.restype = wintypes.DWORD
    kernel.GetProcAddress.argtypes = [wintypes.HMODULE, ctypes.c_void_p]
    kernel.GetProcAddress.restype = ctypes.c_void_p
    root = Path(__file__).resolve().parents[1] / 'src-tauri/target/x86_64-pc-windows-msvc/release/deps'
    candidates = sorted(root.glob('pet_manager_tauri_lib-*.exe'), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        print('No cached native test executable is available for loader diagnostics')
        return
    path = candidates[0]
    print('Native loader diagnostics:', path, flush=True)
    image = pefile.PE(str(path))
    for descriptor in getattr(image, 'DIRECTORY_ENTRY_IMPORT', []):
        name = descriptor.dll.decode('ascii')
        try:
            module = ctypes.WinDLL(name, use_last_error=True)
        except OSError as error:
            print('LOAD FAILED:', name, str(error), flush=True)
            print('Required imports:', ', '.join(imp.name.decode('ascii') if imp.name else '#' + str(imp.ordinal) for imp in descriptor.imports), flush=True)
            continue
        buffer = ctypes.create_unicode_buffer(32768)
        kernel.GetModuleFileNameW(module._handle, buffer, len(buffer))
        print('DLL:', name, '=>', buffer.value, flush=True)
        for imp in descriptor.imports:
            argument = ctypes.cast(ctypes.c_char_p(imp.name), ctypes.c_void_p) if imp.name else ctypes.c_void_p(imp.ordinal)
            if not kernel.GetProcAddress(module._handle, argument):
                print('MISSING ENTRY:', name, imp.name.decode('ascii') if imp.name else '#' + str(imp.ordinal), flush=True)
    image.close()


if __name__ == '__main__':
    main()
