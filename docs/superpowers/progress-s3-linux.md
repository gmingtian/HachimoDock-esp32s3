# S3/Linux progress — docs/superpowers/plans/2026-10-29-s3-linux.md

2026-10-29: User approved three-key adaptation; then requested full migration.
Independent fresh checkout at HachimoDock, branch codex/esp32-s3-linux. Original
XiaoZhi checkout and binaries remain intact. Upstream source inspected before
implementation; P4-only BSP, JPEG/PPA, input ADC and desktop runtime checks found.

Preflight: tasks 1/2 share renderer-to-LCD API, existing signature preserved.
Tasks 2/3 share appearance format: retain protocol format names while resize
limits come from genuine target capabilities. Task 4 owns build definitions,
shared hello/OTA and integration; no parallel commits/staging.

Ruling: user approval authorizes implementing the complete adaptation in this
session; do not add a second approval checkpoint for routine reversible changes.

2026-10-29 implementation and verification:
- Task 1: complete in source; fixed SPI/I2S/three keys, software action/cursor menu.
- Task 2: complete in source; software decoder/scaler, bounded lowres assets, full shared component renderer retained.
- Task 3: source/check/web build complete; final native Linux debug executable rebuilt, staged and startup-checked for15s without temporary library paths, then stopped.
- Task 4: S3 IDF6.1 build/package complete, actual image chip9/project verified.
- Firmware final test suite: 240 passed,1 skipped,11 subtests passed; the optional exported production palette assets test is skipped.
- Firmware: 1,924,656 bytes, version0.7.103-s3-r2; 16MiB factory; 29 components 2,257,211 bytes; appearance1,005,200 bytes including marker/storage metadata.
- Flash is the confirmed N16R8 16MiB part; 8MiB PSRAM is separate runtime memory. The factory image is padded to the flash size, not 16MiB of live content. Updated the Chinese guide and verified the refreshed ZIP, every SHA256SUMS entry, chip9, application embedding and desktop S3 firmware equality.
- Memory: static external1,703,372bytes; DIRAM static145,083 of341,760, leaving196,677 before runtime allocations.
- Review findings fixed: hidden animation rate bypass, overlong video/audio, partial uploads/customcues, desktop virtualpointer gates, S3 audio/status contradiction, version override consistency.
- Original Linux environment had no npm/Rust/native headers. Acquired task-local tools/sysroot only; no system installations or persistent services.
- Original full upstream suite in corrected host env had221passes/1failure(node missing); final port suite above includes new tests and resolves environment-dependent sanitizer skips.
- Linux native unit suite: 653 passed,0 failed,73 ignored in37.44s. Initial sandbox localhost-bind failures were rerun in an allowed environment; a stale PID bounds regression was corrected. Secure storage and ASR fixtures use temporary data, and an independent production non-test Linux encrypted roundtrip passed. Final native build and cargo check passed; the final credential/PID changes are included in the staged executable.
- Desktop JS: 855 passed,1 skipped across128files including staging; npm test passed all127source test files. Final native executable107,124,616bytes, SHA2562f91760bf78fcfd1df33e62e7315d48721689335fb7beead83f3a909f7e40353. Root independently checked executable hash, bundled S3 firmware equality, converter equality, absence of broken symlinks and host-library resolution without LD_LIBRARY_PATH.
- Deliverables: artifacts/HachimoDock_ESP32-S3_三键_试刷包.zip, pc/dist-linux/launch.sh and artifacts/实机验收步骤.md. Linux is a debug build with production frontend, not a self-contained AppImage; S3 asset conversion requires Python3 and a separately configured FFmpeg with libx264. Linux external-app composer automation is unsupported; S3 audio remains half-duplex pending hardware calibration.
- Integration and credential review: no unresolved Critical/Important findings in the recorded scopes. Firmware/renderer/desktop reports describe the bounded checks, not physical-board verification.
- No physical board or acoustic tests performed, no flashing. Live internal/DMAheap, display timing, all component usability and sustainedfps remain physical acceptance.

2026-10-29 Chinese UI follow-up:
- User supplied the actual 1.54-inch 240x240 enclosure with three vertical side keys; existing GPIO assignments remain unchanged. No physical key order is inferred from photographs.
- Native home/session cards now use 16px Chinese text; 1-3 visible cards follow the live queue, the selected card shows two body lines with2.8s UTF-8-safe paging, and additional sessions remain reachable by the original previous/next bindings. Realtime captions/history and recording feedback are separate modes.
- System menus/help translated; component actions use package labels plus Chinese built-in fallbacks while action IDs remain unchanged.
- A review exposed realtime/PTT capture ownership and stale takeover feedback issues. Production C red/green regressions cover both; the final narrow review has no unresolved Critical/Important findings. Prompt says recording completion rather than automatic send.
- Host previews execute production native UI functions with real bitmap font data and fixture sessions. They do not establish physical panel colors or runtime playback speed. See ui-zh-report.md and ui-zh-review.md.
