# HachimoDock S3 / Linux adaptation

User-approved direction: replace XiaoZhi with HachimoDock, retain the assembled
ESP32-S3 N16R8, 240×240 ST7789 display, microphone, MAX98357A speaker and three
buttons, using exactly the existing wiring. Target the current Linux computer.
The requested scope is a full adaptation, not a separate status-only demo.

## Hardware contract

Display SPI: CLK 21, MOSI 47, RST 45, DC 40, CS 41, backlight 42. RGB565,
SPI mode 0, inversion enabled, no mirror or XY swap. Microphone I2S: WS 4,
BCLK 5, DIN 6. Speaker I2S: DOUT 7, BCLK 15, LRCK 16. Buttons active low with
pullups: previous 39, next 38, confirm 0. No joystick, touch panel or external
storage. Native USB uses the board's existing connector; UART0 is a fallback.

Short press: previous / next / confirm. Long previous: home/back. Long next:
component menu. Hold confirm: capture voice until release. Long press must not
also issue a short press. GPIO0 retains its hardware boot-strapping behavior.
Components get equivalent previous/next/confirm and configured game actions;
menus/settings provide additional directional actions without new hardware.

## Implementation boundaries

Keep the upstream protocol, session lifecycle, shape/asset management, bounded
component runtime, games, media, voice and update mechanisms. Add a genuine
S3 target rather than advertising the board as P4. Keep upstream P4 behavior
and its build target intact. Desktop operations must use declared device
capabilities. S3 OTA must reject P4 images. Resource sizes must fit 16 MB flash
and 8 MB PSRAM, with useful failures for oversized user packages.

Replace P4-only BSP/MIPI/PPA/JPEG hardware paths with S3 ST7789 SPI, software
conversion/scaling and independent I2S input/output. Retain the logical
component coordinate space initially and scale to the physical panel without
cropping; add small-screen layouts where readable text/navigation requires it.
Use reduced-resolution appearance packages for S3; do not decode full P4 video
and silently claim equivalent speed. Retain cue/music/voice playback and PCM
capture. Report actual AEC availability; no unsupported full-duplex claim.

Linux must have a runnable native desktop path, device discovery/serial
transport, session monitoring and asset conversion. Platforms that require
OS-specific foreground-input APIs must report capability limits explicitly.
The original three-button wiring and audio/display pin mappings are fixed.

## Verification and delivery

Exercise real input decoding, aspect-fit/scaling, resource bounds, target
identity, capability negotiation and OTA image selection with host tests.
Build the S3 firmware and Linux desktop where dependencies permit; retain exact
commands/logs. Run relevant upstream tests and review the complete diff. Deliver
source, firmware images and Linux launch/build instructions, plus a feature
matrix distinguishing implemented, build-verified, physically verified and
remaining limitations. Compilation is not a physical hardware test. Do not
flash a connected board or install a persistent service automatically.
