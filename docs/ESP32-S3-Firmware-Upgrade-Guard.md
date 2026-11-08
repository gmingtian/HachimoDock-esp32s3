# S3 local firmware upgrade protection — 2026-11-07

The sidebar update incorrectly offered the bundled r10 image to a device running
`0.7.103-s3-r14c-80m-l320`. Both old version parsers recognized only a numeric
`rNNN` segment: `r14c` became revision zero, which compared below r10. The desktop
completed this unintended downgrade to r10, so the guard was not effective for
the local lettered builds.

The device was restored by reading the complete 2583744-byte image from OTA_1,
checking SHA256
`0db5dca8b77ab6acc9b4259201efa5b01c86a7d4bbb78c9b34a6e1c64a704221`, and selecting
that existing r14c slot. No media or user-data partition was erased or rewritten.
Runtime readiness, boot selection, native composition, A4/16 bindings and the
unchanged historical fault count of one were verified after reboot. OTA_0 now
contains the desktop-installed r10; the older r13n is recoverable from the saved
full pre-r14 backup, not from OTA_0.

The local desktop repair:

- Compares the numeric revision and optional single letter, including r13n,
  r14b and r14c. Unknown, empty or duplicate `r` segments reject automatic update
  decisions instead of becoming revision zero.
- Requires a newer version for a bundled update, with matching rules in the UI
  and Rust backend. S3 `80m` and `l320` markers already present on the device must
  also be present on a newer bundled target.
- Rechecks that same bundled policy after acquiring the transfer lock, using
  the new connected-device snapshot and actual image descriptor. A request
  queued behind another firmware update cannot rely on its old preflight.
- Keeps manual file-selected recovery separate. Manual images still undergo
  chip/project/size/integrity/boot validation; this path does not promise an
  automatic downgrade prohibition.

Version markers are naming conventions, not cryptographic hardware-profile
attestation. These checks protect the known bundled-update workflow and do not
prove arbitrary manually selected firmware matches every PCB IO or screen.
Existing chip/project identity, OTA capacity, SHA256, ACK and post-reboot
validation logic remains in place. Firmware runtime rollback handles unhealthy
boots; it does not reject an older image that boots successfully.

The repaired desktop keeps version 0.1.201 with a distinct local installer and
executable hash. The bundled stable S3 firmware remains r10/40MHz. Build/test,
device restore and installation receipts are under
`artifacts/firmware-upgrade-guard/`; temporary logs and pre-repair executable are
under `.build-tools/firmware-guard/`. No firmware pixel/shadow behavior changed
in this repair, and the remaining shadow issue is not marked resolved.
