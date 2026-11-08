# S3 Native Home Implementation Plan

> Implement continuously in this session; delegate the independent host-text blit task with isolated context, and request scoped review before flashing. User authorization covers implementation and reversible device testing. No commits or publishing.

**Goal:** Direct 320×240 pet-home animation and overlay composition with no full logical-canvas round trip for current H264 assets.

**Architecture:** A clean native asset layer plus the existing native output pair; project logical UI coordinates into native pixels in raster primitives. Keep logical components and legacy asset fallback.

**Tech stack:** ESP-IDF6.1 C, ESP32-S3, MSVC ASAN host harnesses, Python serial diagnostics.

**Spec:** `docs/superpowers/specs/2026-11-07-s3-native-composition-design.md`.

## Constraints

SPI80MHz, A4 input model/16 bindings, existing 16 animations and quality, 3MiB slots and 384KiB stream cap remain. Preserve original r12 OTA_1, backup all16MiB; candidate OTA_0. No client reinstall or account operations.

## Task 1 — Native primitives and asset layer

- [ ] Add a failing host regression around production `put_px`, `fill_rect`, `blend_px`, `blend_rect`, `scale_h264_frame_cpu`: native output must equal sampled logical output, with unchanged guarded logical storage during direct H264 conversion.
- [ ] Add `firmware/s3/pet_s3_compositor.h` for clipped even-coordinate pixel/rectangle projection; native target is320×240, logical coordinates640×480.
- [ ] Update renderer low-level primitives to use native targets only during main-page native composition. Asset conversion writes the clean layer directly for exact2x fits; other asset profiles remain logical fallbacks.
- [ ] Restore the clean native layer into the output before overlays; disable logical underlay/queue caches for native home; skip final scale for native home, reset context across page changes, reconstruct logical screenshot data on demand.
- [ ] Run pixel/work-bound and existing P4/S3 regression harnesses with MSVC ASAN.

## Task 2 — Host bubble pixels

- [ ] Extend production pinned RLE draw through `pet_bubble_pixels_draw_pinned_scaled(..., unsigned output_scale)` accepting1/2; keep the old public wrapper at scale1.
- [ ] Validate the scaled helper with guarded buffers, odd/negative positions, style/page identity, alpha overlap and pin/unpin behavior. Compare each native output pixel with logical output at `(2*x,2*y)`.
- [ ] Integrate scale2 in the renderer native context; retain old call outside native home. Request read-only task review.

## Task 3 — Build, device, handoff

- [ ] Snapshot coherent completed-frame native flags in metrics; expose them in optional diagnostics.
- [ ] Build a distinct r13n/80MHz candidate, inspect stack usage and source/binary hashes, review the complete native delta.
- [ ] Compare with fresh r12 idle/main baseline; verify original image and full backup, flash onlyOTA_0, boot and validate runtime/input/fault counters/native flags. Roll back on failure.
- [ ] Measure actual submitted FPS under matched conditions, exercise transitions and overlays, obtain physical feedback, restore desktop connection and save receipts/docs/handoff.

## Execution ledger

- Ruling: reuse the current checkout — it contains the user's only active uncommitted hardware/client port; do not create/reset branches or move work.
- r13 row-copy-only candidate built and tested but never flashed; user redirected work to native composition. r12 remains running and fully backed up.
- Fresh full backup SHA256: dfadabc34520e9d3ea6100a86026f0062495c415d760c72130e1d7a9518dcba2.
- Tasks 1 and 2 complete: production native primitives/conversion pass sampled pixel equivalence under both raster configurations, with untouched logical asset storage; 159 host RLE/pin cases pass ASAN. Generic P4/S3 and telemetry regressions pass.
- Task 3 technical implementation/deployment complete: r13n SHA256 96258cf348bc0bffd2ae30158f92f59bb0980dd5874dc420b275cc9094e08d63, OTA_0; r12 remains OTA_1. Read-only review found no important defects. Fresh static stack3072/400/80bytes; main16384.
- Same idle/main FPS6.776→7.712 (+13.81%), frame137.178→117.686ms, scale10.389→0.015ms. Native completion flags verified;15 real device page/state/queue/conversation/approval sequences pass, cleanup verified, faults remain1, dropped input0. Desktop0.1.201 restored COM3 with synchronized controls.
- Ruling: transfer→home context reset is reviewed without initiating a real transfer, because that would overwrite staging user media for a rendering-only check. Physical PTT capture and actual S3 screenshot transfer were not exercised. These limits are explicit in the delivery receipt.
- Ruling: an idle nonselected session is intentionally filtered by official lifecycle rules; corrected the synthetic fixture to two working sessions, then all15 scenarios passed. No production change was needed for that failed fixture.
- Physical display acceptance complete: user confirmed “显示正常，无明显异常”. User data, client bundle, quality parameters and SPI80MHz remain preserved. No commits/push/publication.
