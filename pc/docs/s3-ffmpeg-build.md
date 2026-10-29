# Independent S3 FFmpeg helper

Build this GPL helper separately from the desktop app's audited LGPL media runtime.
Do not substitute it for the upstream runtime or change that runtime's audit checks.

On **Windows x64**, run in MSYS2's **MINGW64** Bash with these packages:

```text
mingw-w64-x86_64-gcc mingw-w64-x86_64-pkgconf mingw-w64-x86_64-nasm
make diffutils curl tar xz coreutils bash
```

On **native macOS Apple silicon**, install Xcode command line tools and
`pkg-config` (GNU make and nasm may also be installed by CI; arm64 assembly uses
clang). The release recipe refuses Intel/Rosetta macOS and non-MINGW64 Windows.

From the repository root:

```bash
bash pc/scripts/build-s3-ffmpeg.sh generated-runtime/s3
python3 pc/scripts/smoke-s3-ffmpeg.py generated-runtime/s3/s3-ffmpeg
# Windows: use generated-runtime/s3/s3-ffmpeg.exe instead.
python3 pc/scripts/test-s3-ffmpeg-build.py
```

Python is a build verification dependency, not a dependency of the shipped
FFmpeg executable. The source-integrity tests exercise missing and corrupted
offline caches. The smoke check creates local MP4/stereo WAV fixtures, invokes
the actual S3 converter, verifies canonical SPS, frame and slot bounds, decodes
the converted stream, and checks mono 16 kHz PCM output.
It also runs the desktop build preflight's copy-to-null duration probe and
requires a successful final progress report with a positive output timestamp.

The build pins FFmpeg **8.1.2** to SHA256
`464beb5e7bf0c311e68b45ae2f04e9cc2af88851abb4082231742a74d97b524c` and
x264 commit **baee400fa9ced6f5481a728138fed6e867b0ff7f** to archive SHA256
`436a2be54d8bc0cb05dd33ecbbcb7df9c3b57362714fcdaa3a5991189a33319b`.
Every downloaded or cached archive is verified before extraction or configure.

The output directory contains `s3-ffmpeg[.exe]`, complete unmodified corresponding
source archives and the build script in `source/`, upstream `LICENSE*` files,
exact commands in `BUILD-COMMANDS.txt`, compiler/configuration/system dependencies
in `BUILD-ENV.txt`, instructions/notices in `BUILD-README.txt`, and hashes in
`BUILD-SHA256SUMS.txt`. Distribute the whole directory together. The Windows
binary rejects unexpected non-system DLL dependencies; macOS rejects non-system
dylibs. x264 is statically linked. No network protocols or device inputs are
enabled, and optional installed libraries are not autodetected.

Output paths and source-cache paths may contain spaces. The upstream makefiles
build in a fresh path under `/tmp` because their own build paths cannot contain
spaces. The build removes this temporary directory on exit.

For an offline rebuild, use the already distributed source archives:

```bash
S3_FFMPEG_SOURCE_DIR="$PWD/generated-runtime/s3/source" \
S3_FFMPEG_OFFLINE=1 S3_FFMPEG_JOBS=4 \
bash pc/scripts/build-s3-ffmpeg.sh 'rebuilt S3 runtime'
```

The recipe reproduces source versions and configuration. Matching output bytes
also requires matching the recorded OS, compiler, SDK and tool versions.
`S3_FFMPEG_DISABLE_ASM=1` is accepted only on Linux for local validation without
nasm; release Windows/macOS builds always retain assembly.
