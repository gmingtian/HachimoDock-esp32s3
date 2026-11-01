#!/usr/bin/env python3
"""Discard desktop Cargo build output restored from another absolute workspace.

Only pc/src-tauri/target is managed; Cargo registry/git and media helper caches
remain reusable. Importing this module does not inspect or change the cache.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys


def normalize_cache(repo_root, *, windows=None):
    root = Path(repo_root).resolve()
    tauri = root / 'pc/src-tauri'
    if not (tauri / 'Cargo.toml').is_file():
        raise ValueError('Expected desktop repository pc/src-tauri/Cargo.toml')
    if not tauri.resolve().is_relative_to(root):
        raise ValueError('Desktop Cargo directory must stay inside the repository')
    target = tauri / 'target'
    if target.is_symlink() or target.resolve() != tauri.resolve() / 'target':
        raise ValueError('Desktop Cargo target must not redirect to another directory')
    if target.exists() and not target.is_dir():
        raise ValueError('Desktop Cargo target must be a directory')
    marker = target / '.desktop-workspace-root'
    if marker.is_symlink():
        raise ValueError('Desktop workspace marker must not be a symlink')
    windows = sys.platform == 'win32' if windows is None else windows
    identity = root.as_posix()
    previous = marker.read_text(encoding='utf-8').strip() if marker.is_file() else None
    if windows:
        identity = identity.casefold()
        previous = previous.casefold() if previous is not None else None
    populated = target.is_dir() and any(target.iterdir())
    cleared = bool(populated and previous != identity)
    if cleared:
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    marker.write_text(identity + '\n', encoding='utf-8')
    return {'workspaceRoot':identity, 'cleared':cleared, 'target':str(target)}


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    # The CLI deliberately has no configurable deletion path.
    print(json.dumps(normalize_cache(Path(__file__).resolve().parents[2])))


if __name__ == '__main__':
    main()
