#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Build the independent GPL S3 converter helper, never the app's LGPL runtime.
set -euo pipefail
umask 022

FFMPEG_VERSION=8.1.2
FFMPEG_SHA256=464beb5e7bf0c311e68b45ae2f04e9cc2af88851abb4082231742a74d97b524c
X264_COMMIT=baee400fa9ced6f5481a728138fed6e867b0ff7f
X264_SHA256=436a2be54d8bc0cb05dd33ecbbcb7df9c3b57362714fcdaa3a5991189a33319b

if [[ $# != 1 || "$1" == --help ]]; then
    echo 'Usage: bash build-s3-ffmpeg.sh OUTPUT_DIRECTORY'
    echo 'Optional: S3_FFMPEG_SOURCE_DIR, S3_FFMPEG_OFFLINE=1, S3_FFMPEG_JOBS=N'
    echo 'Linux validation only: S3_FFMPEG_DISABLE_ASM=1'
    [[ $# == 1 && "$1" == --help ]] && exit 0 || exit 2
fi
script_path=$(cd "$(dirname "$0")" && pwd)/$(basename "$0")
mkdir -p "$1"
output=$(cd "$1" && pwd)
mkdir -p "$output/source"
cache=${S3_FFMPEG_SOURCE_DIR:-$output/source}

sha256() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    else
        shasum -a 256 "$1" | awk '{print $1}'
    fi
}
fetch_source() {
    local name=$1 expected=$2 url=$3 archive
    archive="$cache/$name"
    if [[ ! -f "$archive" ]]; then
        if [[ ${S3_FFMPEG_OFFLINE:-0} == 1 ]]; then
            echo "Offline source archive missing: $archive" >&2
            exit 1
        fi
        archive="$output/source/$name"
        curl --fail --location --retry 3 --connect-timeout 30 --max-time 600 \
            --proto '=https' --proto-redir '=https' --output "$archive.part" "$url"
        mv "$archive.part" "$archive"
    fi
    if [[ $(sha256 "$archive") != "$expected" ]]; then
        echo "Source checksum mismatch: $archive (expected $expected)" >&2
        exit 1
    fi
    if [[ $(cd "$(dirname "$archive")" && pwd)/$(basename "$archive") != "$output/source/$name" ]]; then
        cp "$archive" "$output/source/$name"
    fi
}

ffmpeg_archive=ffmpeg-$FFMPEG_VERSION.tar.xz
x264_archive=x264-$X264_COMMIT.tar.gz
fetch_source "$ffmpeg_archive" "$FFMPEG_SHA256" "https://ffmpeg.org/releases/$ffmpeg_archive"
fetch_source "$x264_archive" "$X264_SHA256" "https://codeload.github.com/mirror/x264/tar.gz/$X264_COMMIT"

platform=$(uname -s)
arch=$(uname -m)
suffix=''
ff_platform=()
x264_platform=()
# Bash 3.2 treats an empty array as unset under nounset: expand optional arrays
# with ${array[@]+"${array[@]}"} below, preserving zero arguments and word boundaries.
link_flags=''
case "$platform" in
    MINGW64_NT-*|MINGW64*)
        [[ "$arch" == x86_64 && ${MSYSTEM:-} == MINGW64 ]] || {
            echo 'Use the MSYS2 MINGW64 x64 shell.' >&2; exit 1;
        }
        suffix=.exe
        export CC=gcc
        ff_platform=(--target-os=mingw32 --arch=x86_64 --disable-pthreads --enable-w32threads)
        x264_platform=(--host=x86_64-w64-mingw32)
        link_flags='-static -static-libgcc'
        ;;
    Darwin)
        [[ "$arch" == arm64 ]] || { echo 'macOS release builds require native Apple silicon.' >&2; exit 1; }
        export CC=clang
        export MACOSX_DEPLOYMENT_TARGET=${MACOSX_DEPLOYMENT_TARGET:-11.0}
        ff_platform=(--target-os=darwin --arch=aarch64)
        x264_platform=(--host=aarch64-apple-darwin)
        ;;
    Linux) export CC=${CC:-gcc} ;;
    *) echo "Unsupported build host: $platform/$arch" >&2; exit 1 ;;
esac
for tool in "$CC" make pkg-config tar curl; do
    command -v "$tool" >/dev/null || { echo "Missing build tool: $tool" >&2; exit 1; }
done
jobs=${S3_FFMPEG_JOBS:-4}
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] || { echo 'S3_FFMPEG_JOBS must be positive.' >&2; exit 1; }
ff_asm=()
x264_asm=()
if [[ ${S3_FFMPEG_DISABLE_ASM:-0} == 1 ]]; then
    [[ "$platform" == Linux ]] || { echo 'Assembly may only be disabled for Linux validation.' >&2; exit 1; }
    ff_asm=(--disable-asm)
    x264_asm=(--disable-asm)
elif [[ "$arch" == x86_64 ]]; then
    command -v nasm >/dev/null || { echo 'Missing build tool: nasm' >&2; exit 1; }
fi

# FFmpeg and x264 makefiles do not support spaces in their build/install paths.
# Keep only their temporary working tree in /tmp; source/output paths may contain spaces.
work=$(mktemp -d /tmp/s3-ffmpeg.XXXXXX)
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/ffmpeg" "$work/x264" "$work/prefix"
tar -xf "$output/source/$ffmpeg_archive" -C "$work/ffmpeg" --strip-components=1
tar -xf "$output/source/$x264_archive" -C "$work/x264" --strip-components=1
export PKG_CONFIG_PATH=''
export PKG_CONFIG_LIBDIR="$work/prefix/lib/pkgconfig"
# Ignore ambient flags; emit every intentional configure argument below.
unset CFLAGS CPPFLAGS CXXFLAGS LDFLAGS
export LC_ALL=C
export SOURCE_DATE_EPOCH=1661000000
commands="$output/BUILD-COMMANDS.txt"
: > "$commands"
run() {
    printf 'cd %q && ' "$PWD" >> "$commands"
    printf '%q ' "$@" >> "$commands"
    printf '\n' >> "$commands"
    "$@"
}
(
    cd "$work/x264"
    run ./configure --prefix="$work/prefix" --enable-static --disable-cli \
        --disable-opencl --disable-lavf --disable-swscale --disable-ffms \
        --bit-depth=8 --chroma-format=420 --enable-pic \
        ${x264_platform[@]+"${x264_platform[@]}"} ${x264_asm[@]+"${x264_asm[@]}"}
    run make -j"$jobs"
    run make install-lib-static
)
(
    cd "$work/ffmpeg"
    run ./configure --prefix="$work/prefix" --cc="$CC" \
        --disable-autodetect --disable-shared --enable-static --enable-gpl --enable-libx264 \
        --disable-programs --enable-ffmpeg --disable-doc --disable-debug --disable-avdevice \
        --disable-network --disable-protocols --enable-protocol=file,pipe \
        --disable-hwaccels --disable-encoders --enable-encoder=libx264,pcm_s16le,rawvideo \
        --disable-muxers --enable-muxer=h264,wav,mp4,rawvideo,null \
        --pkg-config-flags=--static --extra-ldflags="$link_flags" \
        ${ff_platform[@]+"${ff_platform[@]}"} ${ff_asm[@]+"${ff_asm[@]}"}
    run make -j"$jobs" ffmpeg
)
cp "$work/ffmpeg/ffmpeg$suffix" "$output/s3-ffmpeg$suffix"
chmod +x "$output/s3-ffmpeg$suffix"
if [[ "$platform" == Darwin ]]; then
    # arm64 macOS requires a valid signature even for unsigned preview apps.
    codesign --force --sign - --timestamp=none "$output/s3-ffmpeg"
    codesign --verify --strict "$output/s3-ffmpeg"
fi
cp "$script_path" "$output/source/build-s3-ffmpeg.sh"
cp "$work/ffmpeg/COPYING.GPLv2" "$output/LICENSE-FFmpeg-GPLv2.txt"
cp "$work/ffmpeg/LICENSE.md" "$output/LICENSE-FFmpeg-notices.md"
cp "$work/x264/COPYING" "$output/LICENSE-x264-GPLv2.txt"
cp "$work/x264/AUTHORS" "$output/source/x264-AUTHORS.txt"

cat > "$output/BUILD-SOURCES.txt" <<EOF
FFmpeg $FFMPEG_VERSION, unmodified: https://ffmpeg.org/releases/$ffmpeg_archive
SHA256 $FFMPEG_SHA256  source/$ffmpeg_archive
x264 $X264_COMMIT, unmodified: https://codeload.github.com/mirror/x264/tar.gz/$X264_COMMIT
SHA256 $X264_SHA256  source/$x264_archive
EOF
cat > "$output/BUILD-README.txt" <<'EOF'
This independent s3-ffmpeg executable combines FFmpeg and static x264 under
GNU GPL version 2 or later. Copyright belongs to their respective contributors.
Complete unmodified corresponding sources, including dependency notices, are
provided in source/*.tar.*; the exact build script is source/build-s3-ffmpeg.sh.
No source patches are applied. This helper is a separate process used only for
S3 asset preparation. The app's separate audited LGPL media runtime is unrelated.

Rebuild on native macOS arm64 (Xcode command line tools, make, pkg-config), or
MSYS2 MINGW64 Windows x64 (mingw-w64-x86_64-gcc, mingw-w64-x86_64-pkgconf,
mingw-w64-x86_64-nasm, make, diffutils, curl, tar, xz, coreutils, bash):
  S3_FFMPEG_SOURCE_DIR="$PWD/source" S3_FFMPEG_OFFLINE=1 bash source/build-s3-ffmpeg.sh rebuilt
Run from the directory containing this file. No downloads are needed in offline
mode. BUILD-COMMANDS.txt records all configure/make commands; BUILD-ENV.txt records
the toolchain, system-library dependencies and effective configuration. Temporary
paths in the command transcript are recreated automatically by the build script.
Sources/options are reproducible; byte-identical output requires the recorded
OS/toolchain/SDK. The recipe does not claim cross-toolchain bit reproducibility.

macOS executables receive an ad-hoc signature after linking/stripping and before
the final file hashes are recorded; preserve it when copying into the app.

External codec dependencies: only x264 (statically linked, GPL-2.0-or-later).
All other enabled media code is in the FFmpeg source archive; see its LICENSE.md
and per-file notices. Windows uses OS DLLs and GCC runtime under the GCC Runtime
Library Exception; macOS uses Apple system libraries/SDK. Build tools and system
libraries are not bundled. Network protocols, devices, autodetected third-party
libraries, and hardware codecs are disabled. Local MOV/MP4/MKV/WebM/AVI inputs
use FFmpeg's internal software decoders. Output includes Annex B H.264 and PCM WAV.

Keep this entire directory together when redistributing this helper, including
both full source archives, licenses, notices, build script and command transcript.
EOF
{
    printf 'Host: %s %s\n' "$platform" "$arch"
    printf 'SOURCE_DATE_EPOCH=%s\nMACOSX_DEPLOYMENT_TARGET=%s\nS3_FFMPEG_DISABLE_ASM=%s\n' \
        "$SOURCE_DATE_EPOCH" "${MACOSX_DEPLOYMENT_TARGET:-unset}" "${S3_FFMPEG_DISABLE_ASM:-0}"
    "$CC" --version
    make --version
    pkg-config --version
    if command -v nasm >/dev/null; then nasm -v; fi
    "$output/s3-ffmpeg$suffix" -version
    "$output/s3-ffmpeg$suffix" -buildconf
    case "$platform" in
        MINGW64*) objdump -p "$output/s3-ffmpeg$suffix" | awk '/DLL Name:/{print $0}' ;;
        Darwin) xcrun --show-sdk-version; otool -L "$output/s3-ffmpeg" ;;
        Linux) ldd "$output/s3-ffmpeg" ;;
    esac
} > "$output/BUILD-ENV.txt" 2>&1
# Fail if a package manager runtime leaks into an otherwise standalone build.
case "$platform" in
    MINGW64*)
        if awk '/DLL Name:/ {print tolower($NF)}' "$output/BUILD-ENV.txt" | \
            grep -Ev '^(api-ms-win-.*|ext-ms-win-.*|kernel32|msvcrt|ucrtbase|user32|advapi32|shell32|ole32|oleaut32|ws2_32|bcrypt|crypt32|secur32|ncrypt|shlwapi|gdi32|winmm|psapi)\.dll$' > "$work/extra-dlls"; then
            cat "$work/extra-dlls" >&2
            echo 'Unexpected external DLL dependency in S3 helper.' >&2; exit 1
        fi
        ;;
    Darwin)
        if otool -L "$output/s3-ffmpeg" | tail -n +2 | awk '{print $1}' | \
            grep -Ev '^(/usr/lib/|/System/Library/)' > "$work/extra-dylibs"; then
            cat "$work/extra-dylibs" >&2
            echo 'Unexpected external dylib dependency in S3 helper.' >&2; exit 1
        fi
        ;;
esac
"$output/s3-ffmpeg$suffix" -hide_banner -h encoder=libx264 > "$output/BUILD-ENCODER.txt" 2>&1
grep -q 'libx264' "$output/BUILD-ENCODER.txt"
(
    cd "$output"
    for item in "s3-ffmpeg$suffix" LICENSE* BUILD* source/*; do
        [[ "$item" == BUILD-SHA256SUMS.txt ]] && continue
        printf '%s  %s\n' "$(sha256 "$item")" "$item"
    done
) > "$output/BUILD-SHA256SUMS.txt"
echo "S3 helper and corresponding sources: $output"
