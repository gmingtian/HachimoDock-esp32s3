# S3 integration review — 2026-10-29

Reviewed the current uncommitted integration against `0773644d9b8e` and the S3/Linux design and implementation plan. Scope: target CMake/manifest/defaults, partitions, target identity, hello/audio capability metadata, OTA/image compatibility, PSA SHA-256 adapter, and factory assembly. No implementation files changed and no broad tests or hardware operations performed.

## Findings after final reinspection

No unresolved Critical or Important findings remain in this review's integration scope.

1. **Corrected — Consistent conservative audio capability metadata.** Reinspection of `pet_p4_audio.c` confirms that status AEC/full-duplex and preparation flags use `PET_TARGET_CALIBRATED_AEC`; S3 reports `uncalibrated_hardware` and playback codec `MAX98357A`. `pet_p4_main.c:775` also skips frontend initialization on the uncalibrated S3 target, so readiness-derived VAD remains false in the supported runtime path. Conversation mode still forces half-duplex. The integrating agent reports that the production-function/cJSON serialization fixture in `firmware/tests/s3_audio_status_test.py` passed for both S3 and P4; its coverage was inspected, without rerunning the suite here.

2. **Corrected — PROJECT_VER override consistency.** Reinspection confirms that the redundant S3 `PROJECT_VER` reset was removed. The selected default and optional override now feed both the build ID and application description without a later reassignment.

## Checked integration properties

- Target macros identify S3 as `esp-s3`, use `s3-` device IDs, and advertise `pet_manager_s3_runtime`. P4 identity remains in the alternate branch.
- S3 hello reports physical 240×240 display, 16 MiB flash, 8 MiB PSRAM, GPIO 39/38/0 for the three buttons, no joystick, and no touch gestures when the touch backend is unavailable.
- The native vendor-bulk backend is disabled for S3, leaving the shared USB Serial/JTAG driver and UART0 JSONL paths. `nativeUsb`/`bulk` are false. The retained native-protocol string is inert capability metadata when the booleans are respected.
- S3 partitions fit exactly within 16 MiB: two 3 MiB OTA slots, 0x3e0000-byte SPIFFS, and two 3 MiB raw appearance slots. Raw appearance capacity reporting uses the actual partition-backed implementation. The factory packer uses the S3 partition table for both SPIFFS and raw appearance output and checks segment overlap/flash boundaries.
- `factory-config.json` contains 29 component IDs; `build_s3_factory.py` calls the full shared component-tree builder without replacing that list.
- The OTA first-chunk guard checks image magic and chip ID 9 for S3, and commit separately checks the application project name. P4 checks retain chip ID 18 and its revision-family rule.
- The SHA adapter preserves streaming and one-shot SHA-256 semantics in the PSA branch, initializes PSA before setup/compute, and checks digest length. No concrete adapter defect was found by inspection; this is not a runtime known-answer test.
- Final outputs were read directly: `/tmp/hachimo-s3-build/bootloader/bootloader.bin` is 21,232 bytes, image magic 0xe9, chip ID 9, revision range 0–99. `/tmp/hachimo-s3-build/pet_manager_s3_runtime.bin` is 1,920,688 bytes, chip ID 9, version `0.7.103-s3-r1`, project `pet_manager_s3_runtime`. This application fits the 3 MiB OTA slot. The current build log ends in successful project completion. Application SHA-256: `6080feb8bc2bbfc090d197ca1b7abf552d76c6b074180223cad94136c81802e4`.
- Final factory artifact `artifacts/s3/hachimodock-s3-factory.bin` is exactly 16,777,216 bytes, and its computed SHA-256 matches its sidecar metadata (`4db4aa873522f216b19c27ee2d13e7078a050b9ce7e39eda6cbef226bad6b56d`). The application bytes at offset 0x10000 match the final build, as do `artifacts/s3/hachimodock-s3-app.bin` and `pc/src-tauri/firmware/esp32-s3/firmware.bin`. Factory metadata records all 29 components (2,257,211 payload bytes) and the reduced appearance (1,005,200 payload bytes).
- Desktop firmware inspection, transaction validation, and device-specific update entry points allow 3 MiB for S3 (`firmware_transaction.rs:259`, `firmware_chip.rs:111`, `usb_serial.rs:2236`); the remaining 0x280000 constant applies to P4.
- Reinspection of `assemble_image()` found no concrete defect for its supported input: the completed IDF S3 build and its generated flasher arguments. It checks both boot/app chip IDs, required offsets, overlap, and the 16 MiB boundary. Its caller selects the S3 partitions for generated data. IDF's application-size check and firmware OTA checks enforce the 3 MiB application slot; the low-level assembly helper itself is not a generic partition-table validator for arbitrary hand-edited inputs.

## Memory follow-up

The S3-only change moves the 130,856-byte runtime state into `EXT_RAM_BSS_ATTR` and reduces its UART receive buffer to 32 KiB, while P4 keeps its previous layout. Inspection found no ISR or cache-disabled callback holding or accessing this state. The accesses in main are task code, with shared work serialized by `g_state_mutex`; RX-health critical sections use separate internal scalars and locks. The S3 native-USB stub does not retain the passed state pointer. OTA reads the shared state in ordinary task context before invoking IDF flash APIs. No concrete unsafe PSRAM-access defect was found. The configured UART ISR is not IRAM-enabled; its buffer remains driver-managed.

The final linker map places the main state in `.ext_ram.bss` at 0x3c1d0000 with size 0x1ff28 (130,856 bytes). Total static external BSS is 0x19fbcc (1,702,860 bytes). The saved size report (`artifacts/s3/memory-layout.json`) records 196,693 bytes of unallocated DIRAM, up from the integrating agent's earlier 65,829-byte result. These are link-time figures, not measured free heap after task, DMA, decoder, and asset-cache allocations. Peak live/internal/DMA heap still requires a physical-board check.

## Validation boundaries

Physical display orientation/refresh, microphone slot alignment and signal levels, speaker quality, GPIO0 boot-strapping behavior, USB/UART reliability, live OTA/rollback, peak runtime memory, and all component usability remain hardware validation work. Their absence is not itself a demonstrated code defect. Full-duplex/AEC calibration is explicitly pending and must remain unadvertised. The active IDF build log is owned by the integrating agent; transient compile failures observed during review are not treated here as final build results.

## Additional Linux credential-storage review

Reviewed the added Linux production branches in `pc/src-tauri/src/secure_config.rs`, `secure_config_local.rs`, `volcengine_asr.rs`, and the ASR storage setup in `lib.rs`. Linux now selects the existing authenticated AES-256-GCM local-key backend and initializes the ASR application data directory, rather than taking the unsupported-platform path. The ciphertext format and purpose binding are unchanged; Windows keeps its vault backend and macOS keeps the existing local-key backend.

Two review requests were addressed before signoff: the shared root-preparation helper validates directory type, final-component symlink status, and current-user ownership before applying mode 0700; ASR now calls this helper instead of chmoding an unchecked path. Key publication also synchronizes both the private directory and application root before returning a key, including existing-key and concurrent-winner branches. Key reads use `O_NOFOLLOW`, require a current-user-owned regular 32-byte file with one link, and enforce mode 0600. New keys are written to a temporary file, synchronized, and published without clobbering an existing key. Missing-key encrypted configurations remain protected from automatic replacement; legacy plaintext migration and ciphertext purpose authentication remain covered.

Independent verification used only generated fixtures under `/tmp`, with Rust 1.95 and the harness importing the production source files:

- `cargo test --offline --manifest-path /tmp/hachimo-desktop-contract/Cargo.toml --lib secure_config -- --test-threads=1`: 11 passed, 0 failed, 1 intentionally ignored child-process entry point. The cold-start parent test invokes that child separately to verify persisted-key reload.
- `cargo run --offline --manifest-path /tmp/hachimo-desktop-contract/Cargo.toml --quiet`: production, non-`cfg(test)` Linux encrypted write/read passed. This specifically verifies the platform branch that the original test-only fallback could hide.

No actual credentials or existing user configuration were read or modified. No unresolved Important issue was found in this added storage path. The review assumes a trusted current-user application-data location and does not claim protection against another process already running as the same user, hostile replacement of ancestor directories, or a physical power-loss experiment. The desktop worker owns the final native application/ASR test rebuild; results from that rebuild are recorded separately.
