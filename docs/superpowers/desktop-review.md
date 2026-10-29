# Independent desktop review

Reviewed the Task 3 working-tree diff and new PC files against the S3/Linux full-port spec without editing PC files. Validation remains a source/host review; a connected S3 and interactive desktop were not exercised.

Material issues identified and resolved during review:

- Slicing-game OTA required `touchInput.ready == true`, rejecting the declared S3 virtual pointer. Desktop worker changed the backend gate and frontend game capability check to accept real touch **or** explicit virtual-pointer capability, retaining engine/revision/pointer checks.
- A separate frontend binding gate rejected `screen.*` events and removed their options even after the engine gate accepted virtual pointer. Desktop worker added a separate pointer-ready helper and labels virtual screen actions as key-menu actions, preserving honest physical-touch reporting.
- Linux `tauri build --no-bundle` alone did not provide a resource layout. Desktop worker added resource staging with `usr/bin/pet-manager-tauri` and `usr/lib/pet-manager-tauri`; reviewed this against the actual downloaded `tauri-utils 2.9.3` implementation, whose resource lookup checks executable-relative `../lib/<package-name>` before APPDIR/system paths.
- Real desktop partial-upload manifests contain unavailable `ok:false` families. The S3 converter now skips explicitly unavailable families, retains all successful families, and has a real-FFmpeg integration fixture matching app-data-relative video/audio paths. Custom audioSource markers are preserved so firmware does not replace custom cues with system cues.
- S3 bundled firmware selection requires the actual `firmware/esp32-s3/firmware.bin` resource. Root integration was notified to include the successfully built S3 image in release resources; this review did not substitute or fabricate an image.

Confirmed source properties:

- Explicit S3 runtime/model identifiers take priority over shared `p4-*` format names in hello discovery and frontend normalization. Espressif VID 0x303a is accepted by USB serial discovery.
- Serial appearance sync chooses the S3 ready loader for S3 and does not use the P4-only native bulk path. Source/import preparation routes through target-aware conversion; source and Codex import paths remain available on Linux through system FFmpeg/libx264.
- Firmware upload checks application descriptor, chip-family image header and target project before recovery/upload side effects; P4 images are rejected for S3. The desktop selects the S3 bundled resource for an explicitly identified S3 connection.
- S3 button configuration offers the three real keys with fixed pin labels; component screen actions are represented through the declared virtual pointer rather than invented physical touch.
- Linux foreground-draft operations return explicit unsupported errors, and MiMoCode terminal voice limitations are visible in the UI.

Checks run independently:

- Node tests for S3 controls, runtime normalization and agent voice capability reporting: 3 test files passed.
- Focused renderer/converter suite after the desktop-source fixes: 14 passed, including actual FFmpeg transcode/decode, prepared Annex-B timing preservation, partial source manifests, custom cue preservation, stream/package/audio limits and P4 rendering regressions.

Integration limitations to report accurately:

- Linux native release needs host WebKitGTK/GTK3/ALSA/OpenSSL, FFmpeg with libx264 and Python3. The staging script deliberately does not produce a self-contained redistribution bundle.
- Automatic voice-service startup requires `voice-service/src/index.mjs` resources or an externally configured service root; that service is absent from this repository and from the added base/Linux resource maps. Retaining device PCM/audio protocols does not by itself establish an available local speech/model service.
- Full Rust check/link, final resource staging with actual firmware, launch verification and target hardware behavior are owned by root/desktop integration, not inferred from these passing host tests.
