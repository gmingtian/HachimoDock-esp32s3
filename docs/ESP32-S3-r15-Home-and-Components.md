# r15: clean animation background, home transition and component resources

This local firmware is `0.7.103-s3-r15-80m-l320`, retaining CPU240MHz, SPI80MHz,
native 320×240 home composition and the A4 three buttons plus four-way joystick.
It restores the r14b border-connected black-background cleanup for the protected
built-in appearance, as requested. Custom appearances retain the prior cleanup
policy. This intentionally restores that earlier visual effect, including its
removal of connected dark floor pixels. No appearance video files were replaced.

## Home transition

The previous native entry block cleared the independent clean appearance layer
when returning to home. A pending first decode or media retirement could then
copy that zero layer to the output. A deterministic test using the production
entry block reproduced the clearing.

r15 retains a valid clean layer across page changes, keyed by appearance slot,
asset revision and storage epoch. Only a successful native or logical conversion
can publish validity. Playback reset, transfer and identity changes invalidate
it. Without a valid layer, a pending decode can retain the previous successful
LCD buffer for at most two seconds. Both pointer and index remain authoritative;
tentative overlays are discarded rather than repeatedly blended into the old
frame. If no frame becomes available, a loading/unavailable message replaces an
unexplained black screen. Media retirement continues on every frame.

Visible or changed approval state disables old-frame retention, so cancelling
or expiring a modal cannot retain an obsolete approval card. Completed-frame
diagnostics expose `nativeAssetReady` and `nativeHeldPrevious` in addition to the
existing native and matte execution flags.

This fixes the identified transition path. A finite test does not establish that
every possible future black-screen cause has been eliminated. Physical feedback
for this particular build is recorded separately in the delivery receipt.

## The three applications

`cloud-hop` (云端跳一跳), `block-combo` (像素方块) and `bloomfrog_companion`
(蛙蛙养成) were present as `bootstrap/resources-incomplete`, and activation
failed on the real device. Their control definitions already support the A4
buttons and joystick; only the touch-only `fresh-fruit-slice` remains excluded.

The desktop prepared trusted native S3 artwork, then a duplicate generic sprite
preparation shadowed that result. That second call could reject the resized
runtime against original large images before `widget/begin`. Removing it keeps
the verified native sprites; generic/P4/custom fallback still prepares once.
The source-identity, dimension, encoding and resource-budget checks remain.

After a fresh full flash backup, the production `repairResources` transaction
restored the three packages without deleting saves or changing button settings.
All three became `ready/valid`, then real activation returned successful ACKs
and completed application frames. No resource limits were raised. Stale tests
and documentation referring to the old three-key exclusions were corrected.

## Validation and deployment

- Deterministic production-entry, pointer/index, reset/transfer and approval
  RED→GREEN tests, plus native pixels/alpha/guarded buffers in both raster modes.
- Exact YUV comparison over all 16777216 byte triples; frame matte against an
  independent BFS oracle and foreground/custom-profile checks, using MSVC ASAN.
- Production resource-repair HIL for the three packages, followed by 30 actual
  activations and home returns. Every return regained a valid layer; no
  unexplained no-layer/non-held completed-frame samples, reboot or input loss
  were observed.
- Existing page/state/session/conversation/approval scenarios, including modal
  cancellation, and a final device identity/readiness/input check.
- Focused native-artwork/custom-package/policy/version/chip checks, independent
  review, ESP-IDF build and Windows desktop release build. Exact final counts
  and hashes are in `artifacts/s3-animation-r15/verification.json`.

The device uses r15 in OTA_0; r14c remains in OTA_1. The full private backup before
resource repair is `artifacts/a4-flash-backup/before-r15-full.bin`, SHA256
`93e8660743df911d7f6e6fa0627c5af0e71c3589fe97ad3a1645407bd91661fb`.
It contains user data and must not be included in a public package.

The desktop is a local 0.1.201 repair with a distinct executable/installer hash.
Its stable bundled firmware stays r10/40MHz, and the previous one-click
anti-downgrade/profile-marker checks remain. Installed and build executables
differ only by the official three-byte Tauri UNK→NSS bundle marker. No account,
voice API or volume configuration was changed by this repair.

Rebuild with `.build-tools/s3-r15/build.ps1`; the ordinary `build-local.ps1`
uses an r15 label but explicitly retains the normal 40MHz default. No commit,
push or publication was performed.
