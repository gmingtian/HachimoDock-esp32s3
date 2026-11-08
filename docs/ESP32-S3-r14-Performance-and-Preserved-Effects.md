# ESP32-S3 r14c: faster native composition, preserved animation effects

The r14c candidate keeps the accepted r13n native 320×240 home composition and
80MHz panel clock. It reuses I420 U/V calculations across each 2×2 luma cell,
converts two rows together using bounded internal scratch, and quantizes directly
to RGB565. Its integer result is exactly the previous clamp/quantize result.

This optimization also applies to uploaded H264 animations when they use the
exact-2x native home path, including the usual 320×240 assets. Other sizes, JPEG,
component packages and P4 retain their compatible paths; performance gains are
scene dependent. This change does not increase the source animation frame rate.

## Preserve ground, prop shadows and authored dark details

Source-video inspection found the photographed dark floor already present in
the decoded built-in animation. A generic dark-color threshold cannot determine
whether such pixels are intentional ground, prop shadows or unwanted background.

The r14b border-connected black-matte experiment was withdrawn after the user
specified that authored ground and shadows must remain. r14c removes that
algorithm, its 20160-byte PSRAM workspace, its factory-only fallback and its
`nativeMatte` diagnostic field. Existing conservative edge-only cleanup remains
exactly as before this optimization. No media assets, manifest or appearance slot
contents are rewritten. Some dark areas visible in the source therefore remain
visible by design; this is not a claim that every uploaded animation is segmented
or that all halos are eliminated.

Final user decision: after initially reporting normal effects, the user reported
the gray shadow reappearing, requested rollback, then cancelled it. r14c remains
installed. No rollback was performed and the gray-shadow issue is not marked
resolved. Desktop 0.1.201 was restored on USB COM3 with matching button settings.

## Verification and reproduction

`s3_yuv_rgb565_test.py` exhaustively checks all 16777216 YUV byte combinations,
row widths, odd/two-row cases and guarded buffers. Native composition tests
compare production conversion with the prior sampled logical path, including a
dark floor, enclosed dark facial detail, clipping, alpha, padded stride and odd
height. The floor-preservation test failed against r14b and passes on r14c in
both raster configurations with MSVC AddressSanitizer.

The independent source review found no remaining new matte logic. Final build,
binary SHA256, same-device idle/main measurements and device scenario receipts
are recorded under `artifacts/s3-animation-r14/`. Performance uses actual panel
submissions divided by device uptime, not a software target or source FPS.
Decode/convert times are nested in the asset stage and must not be summed twice.

Rebuild from the workspace root with:

```powershell
.build-tools/s3-r14/build.ps1 -Version '0.7.103-s3-r14c-80m-l320' -OutputName preserve
```

The ordinary `build-local.ps1 -Target S3` keeps the explicit 40MHz default and
uses a version without the 80MHz trial marker. Desktop 0.1.201 remains compatible;
its bundled stable firmware stays r10/40MHz. This firmware needs no desktop
reinstallation and does not modify input, microphone or account configuration.

The full private 16MiB backup before r14 is kept separately under
`artifacts/a4-flash-backup/`; it contains user data and is not a public package.
Only OTA_1 is used for the r14 candidates; the accepted r13n image in OTA_0 is
preserved. Original startup resource-integrity checks remain in place. No claim
of faster startup or long-term 80MHz hardware stability is made.
