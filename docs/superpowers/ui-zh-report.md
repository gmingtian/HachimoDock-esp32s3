# S3 Chinese UI and native session cards — 2026-10-29

The user requested Chinese menus, original multi-session bubbles, and compatibility
with the photographed 1.54-inch 240x240 device with three vertical side keys. All
existing display/audio/button IO is retained; the photographs do not establish the
physical top/middle/bottom GPIO order.

The S3 main page now renders a native 240x240 home UI rather than shrinking the P4
caption cards. One to three cards follow the active queue automatically. The selected
68px card has a 16px title and two 19px-spaced body lines; other cards retain a summary
or title according to available space. All eight runtime session slots remain
accessible through the existing selection controls. Long selected text advances by
complete UTF-8 codepoints and cycles through two-line pages every2.8seconds. Pet art
is aspect-fitted into the remaining upper area. Shared component/game scenes retain
their existing logical canvas; P4 retains its previous renderer branches.

Fixed menus/help and home status/recording/history labels are Chinese. Component
actions use bounded package button labels; built-in unbound actions have Chinese
fallbacks. An unnamed custom action gets an indexed Chinese fallback. Presentation
labels never replace the original execution IDs.

Realtime conversation owns capture and captions. Confirm hold/release during that
mode clears only stale PTT feedback and never starts/stops its audio capture.
Normal PTT remains functional. Realtime history says 对话回看. 松开完成录音 describes
recording completion; this does not promise automatic submission. Linux external-app
draft insertion/sending remains unsupported as documented previously.

Validation:

- Full firmware suite:240passed,1skipped,11subtests passed in20.76seconds. The skipped
  exported production palette asset test remains optional.
- New production C drawing/input fixtures cover1-8session windows, invalid selection,
  framebuffer canaries, UTF-8/newline wrapping, page cycling/content reset, recording
  with/without sessions, realtime caption isolation, active realtime PTT suppression,
  and normal PTT-to-conversation takeover. Regression failures were reproduced before
  the fixes. UBSan remains enabled.
- Three older literal source assertions were adjusted for the explicit native_home
  guard; it is constant false on P4, preserving its prior semantics.
- Independent narrow review: no unresolved Critical/Important findings after fixes;
  see ui-zh-review.md. No source was edited by that reviewer.
- ESP-IDF6.1 S3 build and factory packaging passed. Application:1,924,656bytes,
  chip9, project pet_manager_s3_runtime, version0.7.103-s3-r2. SHA-256:
  b15792a1c098674d81621b164ea8eb429c5baea31f5e2c82d6808656c12431da.
- Static external BSS1,703,372bytes; DIRAM145,083/341,760bytes, leaving196,677
  before runtime allocations. No additional framebuffer or decoder pool was added.

Previews in artifacts/screen-preview execute the production S3 drawing functions
against a host framebuffer, with the actual bitmap font and fixture session data.
Pet frames are host-decoded from the bounded S3 appearance pack using the production
YUV-to-RGB565 conversion coefficients. These images/GIFs are simulations: no physical
display, touch, microphone, speaker, actual Agent session delivery, live memory peak,
or sustained decoding performance has been verified on this board. No device was flashed.
