#!/usr/bin/env python3
"""Freeze the canonical S3 converter without bundling an FFmpeg media runtime.

Run with the target-native Python and PyInstaller installed at build time.
Only the verified executable and its complete runtime license notices are
published into --output-dir; temporary PyInstaller files and Python's build
environment are never copied as resources.
The separately licensed s3-ffmpeg[.exe] helper must be staged beside it.
"""

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys
import sysconfig
import tempfile
from urllib.request import urlopen


def download_cpython_license(url):
    with urlopen(url, timeout=30) as response:
        data = response.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024:
        raise ValueError("CPython license download exceeds 1 MiB")
    return data


def checked_notice(data, name, markers):
    try:
        text = data.decode("utf-8")
    except UnicodeError as error:
        raise ValueError(f"{name} license notice is incomplete or is not UTF-8") from error
    if len(data) < 4096 or any(marker not in text for marker in markers):
        raise ValueError(f"{name} license notice is incomplete")
    return data


def collect_runtime_licenses(*, python_version, python_candidates,
                             pyinstaller_distribution, download=download_cpython_license):
    """Read only runtime license files, matching the actual build versions.

    A missing CPython install notice falls back to the exact official release
    tag. A malformed local notice or missing PyInstaller distribution notice is
    a build error; neither can silently produce an unlicensed executable.
    """
    pyinstaller_version = pyinstaller_distribution.version
    if not all(re.fullmatch(r"\d+\.\d+\.\d+", version) for version in (python_version, pyinstaller_version)):
        raise ValueError("Converter runtime licenses require exact stable CPython and PyInstaller versions")
    python_source = "installed CPython runtime"
    python_notice = None
    for candidate in python_candidates:
        if candidate.is_file():
            python_notice = candidate.read_bytes()
            break
    if python_notice is None:
        python_source = f"https://raw.githubusercontent.com/python/cpython/v{python_version}/LICENSE"
        try:
            python_notice = download(python_source)
        except (OSError, ValueError) as error:
            raise RuntimeError(f"CPython {python_version} license could not be acquired: {error}") from error
    checked_notice(python_notice, "CPython", (
        "A. HISTORY OF THE SOFTWARE", "PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2",
        "BEOPEN.COM LICENSE AGREEMENT", "CNRI LICENSE AGREEMENT", "CWI LICENSE AGREEMENT",
        "ZERO-CLAUSE BSD LICENSE", "PERFORMANCE OF THIS SOFTWARE.",
    ))

    copying_files = [path for path in pyinstaller_distribution.files or []
                     if Path(str(path)).name.lower() == "copying.txt"]
    if len(copying_files) != 1:
        raise ValueError("PyInstaller full COPYING.txt notice is missing or ambiguous in installed distribution metadata")
    copying_path = pyinstaller_distribution.locate_file(copying_files[0])
    if not copying_path.is_file():
        raise ValueError("PyInstaller full COPYING.txt notice is missing from installed distribution")
    copying = checked_notice(copying_path.read_bytes(), "PyInstaller", (
        "The PyInstaller licensing terms", "Bootloader Exception", "Bootloader and Related Files",
        "GNU GENERAL PUBLIC LICENSE", "Version 2, June 1991", "Apache License", "MIT License",
        "END OF TERMS AND CONDITIONS", "SOFTWARE.",
    ))
    # The complete COPYING file includes the bootloader exception and the
    # GPL, Apache and MIT terms; preserve it byte-for-byte rather than extracting
    # a shorter exception that might omit related runtime license obligations.
    metadata = {
        "python": {"version": python_version, "source": python_source,
                   "file": "CPython-LICENSE.txt", "sha256": hashlib.sha256(python_notice).hexdigest()},
        "pyinstaller": {"version": pyinstaller_version, "source": "installed PyInstaller distribution",
                        "file": "PyInstaller-COPYING.txt", "sha256": hashlib.sha256(copying).hexdigest()},
    }
    return {
        "CPython-LICENSE.txt": python_notice,
        "PyInstaller-COPYING.txt": copying,
        "converter-runtime-licenses.json": (json.dumps(metadata, indent=2) + "\n").encode("utf-8"),
    }


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path,
        default=root / "pc/src-tauri/generated-runtime/s3",
        help="Resource staging directory containing prepare-s3-assets[.exe] and s3-ffmpeg[.exe]",
    )
    args = parser.parse_args()
    if importlib.util.find_spec("PyInstaller") is None:
        parser.error("PyInstaller is required in the build Python environment (python -m pip install pyinstaller)")
    if platform.python_implementation() != "CPython":
        parser.error("The standalone converter requires CPython")
    if sys.platform not in ("win32", "darwin", "linux"):
        parser.error(f"Unsupported native converter platform: {sys.platform}")
    if sys.platform == "win32" and (
        platform.machine().lower() not in ("amd64", "x86_64") or struct.calcsize("P") != 8
    ):
        parser.error("Windows preview converter must be built with native x64 Python")

    source = root / "firmware/tools/prepare_s3_assets.py"
    if not source.is_file():
        parser.error(f"Canonical converter source is missing: {source}")
    stdlib = Path(sysconfig.get_path("stdlib"))
    prefix = Path(sys.base_prefix)
    notices = collect_runtime_licenses(
        python_version=platform.python_version(),
        python_candidates=[stdlib / "LICENSE.txt", stdlib / "LICENSE", prefix / "LICENSE.txt", prefix / "LICENSE"],
        pyinstaller_distribution=importlib.metadata.distribution("PyInstaller"),
    )
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    name = "prepare-s3-assets.exe" if sys.platform == "win32" else "prepare-s3-assets"
    destination = output_dir / name
    with tempfile.TemporaryDirectory(prefix="s3-converter-build-") as temporary:
        stage = Path(temporary)
        command = [
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
            "--onefile", "--console", "--noupx", "--name", "prepare-s3-assets",
            "--distpath", str(stage / "dist"),
            "--workpath", str(stage / "work"),
            "--specpath", str(stage),
        ]
        if sys.platform == "darwin":
            # PyInstaller signs the frozen interpreter and executable ad hoc.
            # Explicit arm64 also rejects incompatible Python/bootloader builds.
            command += ["--target-arch", "arm64", "--codesign-identity", "-"]
        subprocess.run([*command, str(source)], cwd=root, check=True)
        executable = stage / "dist" / name
        result = subprocess.run(
            [str(executable), "--help"], check=True, capture_output=True,
            text=True, timeout=60,
        )
        if not all(option in result.stdout for option in ("--source", "--output", "--ffmpeg")):
            raise RuntimeError("Frozen S3 converter did not expose the canonical conversion interface")
        # Copy beside the destination before replacement, including on Windows
        # where the temporary build directory may use a different filesystem.
        with tempfile.TemporaryDirectory(prefix=".s3-converter-", dir=output_dir) as publish:
            candidate = Path(publish) / name
            shutil.copy2(executable, candidate)
            candidate.chmod(0o755)
            licenses = output_dir / "licenses"
            licenses.mkdir(exist_ok=True)
            for filename, data in notices.items():
                notice = Path(publish) / filename
                notice.write_bytes(data)
                os.replace(notice, licenses / filename)
            # Publish the executable only after all required notices exist.
            os.replace(candidate, destination)
    print(json.dumps({
        "converter": str(destination),
        "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        "platform": sys.platform,
        "architecture": "arm64" if sys.platform == "darwin" else platform.machine(),
        "pyinstaller": importlib.metadata.version("PyInstaller"),
        "licenses": sorted(notices),
    }))


if __name__ == "__main__":
    main()
