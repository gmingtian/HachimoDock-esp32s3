# S3 home clients implementation plan

**Goal:** Deliver downloadable Windows x64 and macOS arm64 preview clients for the existing S3 r2 firmware and three-key hardware, without requiring a compiler or Python installation at home.

**Architecture:** Build native clients on GitHub Windows/macOS runners. Reuse the exact upstream 0.1.167 audited LGPL media runtime, retain the shared S3 protocol, and bundle a standalone S3 converter with a separate source-built x264 FFmpeg helper. The helper runs as a separate program; ship its source, licenses and reproducible build instructions. Preserve all Linux behavior and existing P4 checks.

**Tech stack:** Tauri 2.11, Rust >=1.95, Node 22, Python/PyInstaller for build only, FFmpeg 8.1.2, x264, GitHub Actions.

**Specification:** User approved home testing on Windows and Apple-silicon Mac, retaining the existing S3 hardware/IO. Existing docs/ESP32-S3-Linux.md defines the device contract.

## Constraints

- Do not flash hardware or claim physical, live-service or home-computer acceptance.
- S3 firmware stays chip9 / pet_manager_s3_runtime / r2; no P4 firmware substitution.
- Preview apps remain unsigned/ad-hoc, with honest platform installation instructions.
- Conversion must retain canonical x264/SPS, single-slice and slot limits; no unverified native-encoder substitution.
- Existing first-party and dependency licenses stay present; separate GPL helper is independently licensed.
- Reuse branch codex/esp32-s3-linux; user authorization to publish downloads to personal fork persists.

## Tasks

- [ ] 1. Standalone conversion runtime: tests first for selecting executable vs Python fallback and bundled S3 FFmpeg; use PyInstaller executables named tools/prepare-s3-assets[.exe], helper tools/s3-ffmpeg[.exe]. Update only resource resolution/launch, preserving transactional verification and Linux fallback. Run relevant Rust tests and check actual converter --help/fixture on runners.
- [ ] 2. Reproducible separate FFmpeg helper: pinned FFmpeg8.1.2 source plus pinned x264 source, reproducible Bash build on macOS and Windows MSYS2. Produce s3-ffmpeg[.exe], complete corresponding source/build script/licenses. Verify libx264 and actual canonical converter fixture. Do not relax upstream LGPL runtime checks.
- [ ] 3. Native packages: prepare exact upstream media dependencies using archive digests, include S3 firmware/helper/converter and licenses in platform Tauri resources, and build Windows NSIS/macOS app+DMG through workflow_dispatch. Keep secrets out of artifacts. Test package resource manifest and build/upload identity.
- [ ] 4. Review, push and run: targeted local checks, fresh review of package correctness, then push authorized branch and trigger native jobs. Inspect failures, fix and rerun until both platforms build or a concrete external blocker is established. Download/inspect artifacts, hash and upload to a new prerelease with home验收 guide and direct download links.

## Verification

Local checks cover resource manifests/format, Rust converter launch selection and the existing Linux converter tests. Native CI checks actual executables' architectures, conversion output frame/header/package limits, resource inclusion and installer generation. Release asset API digests must match local files. CI and compilation do not imply USB/audio/UI acceptance on the user's hardware.

Ruling: Windows x64 is the existing supported Windows architecture. macOS arm64 is explicitly selected by the user. Scope is preview distribution, not paid signing/notarization or automatic updates to the installed Linux build.

Progress: converter launch routing and source-built helper pass targeted Rust6/Python19 checks. Fresh reviewer found a missing build-host FFmpeg; workflow now selects the absolute helper and helper smoke covers the exact null-muxer duration probe. Native workflows preserve audited main LGPL runtime checks. Windows/macOS compilation and installed-package verification remain pending.
