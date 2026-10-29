# Linux desktop / ESP32-S3 report — 2026-10-29

## Delivered

The full upstream native Tauri application is adapted, built and staged at:

- `pc/dist-linux/launch.sh`
- Native ELF: `pc/dist-linux/usr/bin/pet-manager-tauri`
- Runtime resources: `pc/dist-linux/usr/lib/pet-manager-tauri/`
- Build/run documentation: `pc/docs/linux-native.md`

This artifact is a native x86_64 **debug** build with the production frontend/custom protocol, compiled by Rust 1.95.0 and Tauri CLI 2.11.1. It is not an optimized release or self-contained AppImage. It uses the host GTK3/WebKitGTK4.1, ALSA, udev and OpenSSL libraries. The final executable ran for 15 seconds on this computer's actual desktop without `LD_LIBRARY_PATH`, then the smoke-test process was stopped. GTK/WebKit startup produced no error. This is process-startup evidence, not a visual/interactive or physical-device acceptance test.

The current machine's FFmpeg is task-local rather than in PATH. A ready-to-run command from `pc/` is:

```sh
PET_MANAGER_BUNDLED_FFMPEG=/tmp/hachimo-python-tools/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2 ./dist-linux/launch.sh
```

Python3 is also required for S3 asset preparation. The temporary FFmpeg path is not a portable dependency; install a system FFmpeg with libx264 or select another executable after temporary tools are removed. No task-local library path is required by the staged GUI on this machine. Node is included in resources.

## Behavior

- Genuine `esp-s3` discovery, including S3 aliases/model metadata, takes priority over shared `p4-*` asset format names. Shared session, component, media, voice and input commands retain their complete runtime routes.
- The S3 editor exposes exactly three wired keys / six gestures. GPIO39 previous/back, GPIO38 next/component menu, GPIO0 confirm/hold voice. PTT uses hold/release events, separate from the short press.
- Capability checks accept a declared virtual pointer for compatible pointer scenes and menu-driven screen actions while physical touch remains unavailable.
- S3 appearance sync prepares original custom sources into a separate `s3-ready` pack through the shared Python converter. The desktop validates target, dimensions, fps, H.264 framing, PCM cues, pack identity, 384 KiB stream limit and 3 MiB slot including metadata before sending. S3 skips the P4-specific native USB bulk attempt.
- Firmware preflight rejects P4 image headers on S3 before any abort/erase/upload. It requires chip ID 9, the S3 project name and a maximum 3 MiB app image. Automatic S3 selection resolves only `firmware/esp32-s3/firmware.bin`; no P4 fallback exists.
- Linux now persists ASR, voice/model and generation-provider credentials through the existing authenticated private-file storage. Application/private directories are owner-only; the key is owner-only, no-follow, checked for ownership/link count, atomically published and directory-synced. Missing/corrupt keys do not replace unreadable configuration. ASR uses the same directory validation before chmod. macOS/Windows implementations remain available.
- A baseline Unix PID bug exposed by the native suite was fixed: zero/out-of-range values cannot identify or terminate process groups through managed-runtime PID files.
- Linux foreground input-box discovery, draft insertion and automatic sending to another desktop application remain unsupported. The dashboard says so; backend operations return explicit failures, including draft preservation. Standalone device audio/ASR and the real-time conversation services are separate paths.

## Validation

| Check | Result |
| --- | --- |
| `npm test` with locked dependencies | Passed, all 127 source test files |
| Individually isolated JS cases plus staging test | 855 passed, 1 skipped, 0 failed across 128 files |
| Native Rust full unit suite, temporary/local fixtures | 653 passed, 73 ignored, 0 failed; 37.44 s |
| Production Linux credential harness, compiled without `cfg(test)` | Passed encrypted write/read; previously reproduced unsupported-platform failure |
| Independently reviewed secure configuration fixtures | 11 passed, 1 intentional child-entry ignore |
| Native Tauri build, final sources | Passed, unoptimized/debug build |
| Public credential-input and release CSP preflight | Passed through Tauri before-build hook |
| Staged resource layout test / actual Tauri resolver review | Passed |
| Final native startup smoke, no temporary library path | Process remained running 15 s; stopped after check |
| Git whitespace check | Passed |

The first native suite run in the filesystem/network sandbox could not bind localhost fixtures. Those tests were rerun with local socket access, using mock HTTP/WebSocket/UDP servers and fixture credentials. No live model calls or hardware tests were enabled. The stale PID baseline failure was corrected before the final passing suite. Ignored tests include physical hardware/live-service and explicit large acceptance runs; they are not claimed as verified.

A native credential change was found after the first successful GUI smoke, so the final executable was rebuilt, staged and smoke-tested again. The final staged firmware is the root integration's latest S3 application.

## Artifact identities

- Native executable: 107124616 bytes; SHA-256 `2f91760bf78fcfd1df33e62e7315d48721689335fb7beead83f3a909f7e40353`.
- Bundled S3 application refreshed by root for the Chinese UI follow-up: 1924656 bytes; SHA-256 `b15792a1c098674d81621b164ea8eb429c5baea31f5e2c82d6808656c12431da`. The native ELF is unchanged; this is an external firmware resource. See `ui-zh-report.md` for its verification.

## Reproducible build context

Normal supported-machine commands are `npm ci`, `npm run dev:linux`, and `npm run build:linux`. The last command stages its resulting release binary with all configured resources. For this task the system was left unchanged: native development packages were extracted under `/tmp/hachimo-sysroot`, Rust 1.95 under `/tmp/hachimo-rust195/toolchain`, npm dependencies under `/tmp/hachimo-js`, bridge dependencies under `/tmp/hachimo-bridge`, and Cargo caches/build output under `/tmp/hachimo-cargo` and `/tmp/hachimo-desktop-target`. Registry mirror URLs were used only in temporary lock copies; the repository dependency lockfiles were not rewritten.

The final native command was the equivalent of:

```sh
/tmp/hachimo-native-env.sh node node_modules/@tauri-apps/cli/tauri.js build \
  --debug --no-bundle --config src-tauri/tauri.linux.conf.json --ci
PET_MANAGER_LINUX_BINARY=/tmp/hachimo-desktop-target/debug/pet-manager-tauri \
  node scripts/stage-linux-native.mjs
```

The task-local environment wrapper supplies only the temporary compiler/pkg-config sysroot and caches. Incremental compilation was disabled after its disposable cache reached the temporary build quota; the final rebuild succeeded. Existing native compile warnings remain (platform-specific/dead-code warnings); they are not suppressed or described as a warning-free build.

Logs retained in `/tmp`: `hachimo-desktop-native-build-final.log`, `hachimo-desktop-native-tests-final.log`, `hachimo-desktop-native-smoke-final.log`, `hachimo-desktop-js-final.log`, `hachimo-desktop-tests-isolated.log`, `hachimo-linux-storage.log`, and `hachimo-linux-storage-tests.log`.

No firmware was flashed and no persistent service was installed. Display/audio wiring, physical USB reconnect, button timing and sustained software video playback still require acceptance on the connected board.
