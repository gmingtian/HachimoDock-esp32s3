"""Compile the independent Xiangqi core, then exercise real rules/UI/search."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
VCVARS = Path(r"C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat")


def run_native(group=None):
    with tempfile.TemporaryDirectory(prefix="xiangqi-core-") as tmp:
        exe = Path(tmp) / ("xiangqi.exe" if os.name == "nt" else "xiangqi")
        sources = [ROOT / "main/pet_p4_xiangqi.c", ROOT / "tests/xiangqi_core_test.c"]
        if os.name == "nt" and VCVARS.exists():
            args = ["cl", "/nologo", "/std:c11", "/W4", "/WX", "/Od", "/Zi", "/fsanitize=address", *map(str,sources), f"/Fe:{exe}"]
            script = Path(tmp) / "build.cmd"
            script.write_text(f'@call "{VCVARS}" >nul\n@' + subprocess.list2cmdline(args) + '\n@if errorlevel 1 exit /b %errorlevel%\n@' + subprocess.list2cmdline([str(exe), *([group] if group else [])]) + '\n', encoding="utf-8")
            subprocess.run(["cmd", "/d", "/c", str(script)], cwd=tmp, check=True)
        else:
            cc = shutil.which("clang") or shutil.which("cc")
            if not cc:
                raise RuntimeError("A native C11 compiler is required")
            subprocess.run([cc,"-std=c11","-Wall","-Wextra","-Werror","-O1","-fsanitize=address,undefined",*map(str,sources),"-o",str(exe)],cwd=tmp,check=True)
            subprocess.run([str(exe), *([group] if group else [])],cwd=tmp,check=True)


def test_xiangqi_rules_ui_and_incremental_ai():
    run_native()


if __name__ == "__main__":
    import sys
    run_native(sys.argv[1] if len(sys.argv)>1 else None)
