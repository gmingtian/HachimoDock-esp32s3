# S3 hardware and three-key adaptation report

Implementation is in the existing hardware boundary translation units, selected
with `CONFIG_IDF_TARGET_ESP32S3`; original P4 implementations remain in the other
branch. No hardware was flashed or physically tested.

## Implemented hardware

- `firmware/s3/pet_s3_board.h` records only the user's fixed wiring.
- LCD: ST7789 SPI2 mode 0, 40 MHz, RGB565, inversion enabled, no mirror/XY swap;
  CLK21/MOSI47/RST45/DC40/CS41/BL42. Renderer passes native 240×240 RGB565 via the
  unchanged `pet_p4_lcd_draw_rgb565(x,y,width,height,pixels)` API. A 7,680-byte
  internal DMA stripe swaps wire byte order and waits for transfer completion
  before reuse. Backlight stays off until the renderer reveals its first frame.
- Audio: independent standard-I2S peripherals, I2S1 RX WS4/BCLK5/DIN6 and I2S0 TX
  DOUT7/BCLK15/WS16. The local codec adapter keeps all original cue, instrument,
  fruit-game, WAV, streaming, music and microphone runtime code. RX converts
  signed left-aligned 32-bit microphone slots to mono signed 16-bit PCM; TX
  duplicates mono into left/right 16-bit slots for MAX98357A and applies volume.
  Original 16 kHz voice / 48 kHz music reconfiguration APIs remain operational.
- Microphone digital input assumes its hardware L/R selector uses the left slot,
  and a standard Philips-I2S 24-bit sample left-aligned in a 32-bit slot. Verify
  this against the assembled microphone. There is no configurable analogue gain.
- Hardware touch reports absent (`ready=false`, controller `none`, init
  `ESP_ERR_NOT_SUPPORTED`); no I2C probing or invented touch GPIOs occur.
- Native vendor USB deliberately reports unsupported and does not acquire the
  shared internal PHY. The root build preserves USB Serial/JTAG JSONL transport.
  P4 vendor descriptors and TinyUSB target configuration remain target guarded.

## Three-key operation

SW1/previous GPIO39, SW2/next GPIO38, SW3/confirm GPIO0 are active-low pullups.
There is no encoder/joystick initialization, ADC sampling, or additional input
GPIO on S3. S3 settings use separate NVS namespace `pet_input_s3`.

Short previous/next move through sessions or the component catalog; confirm opens
the selection. In a running component, equivalent legacy navigation/confirm
bindings are resolved without modifying installed packages. Every declared
transition action is also available by holding Next to open the software menu.
The menu uses Previous/Next/Confirm and includes component catalog, pet home,
realtime chat, explicit charge release, and confirmation/cancellation commands.
Holding Previous closes the menu first or performs global back; holding Confirm
starts microphone capture and its release stops it. A long press never generates
an additional short press.

Pointer-only components can use the software cursor: enable Pointer in the menu,
choose X/Y axis, move with Previous/Next, tap with Confirm, choose a 4/16-pixel
step, toggle down/up for dragging, or choose a 160-pixel directional stroke.
Coordinates cover the existing 640×480 logical component canvas. While contact
is down, stationary pointer samples retain continuous contact; leaving the
component cancels the contact. Hardware touch remains false. The small-screen
renderer consumes `pet_s3_menu_snapshot()` for readable action lists and cursor.
The shared miniapp additions enumerate unique declared transition actions and
permit slicing on S3 through this software pointer instead of physical touch.

This provides access to the original controls; a three-key software cursor is
slower than a continuous physical touch device, especially for time-critical
slicing or drag games. Physical usability/performance is unverified.

## Audio capability limit

S3 conversations force half-duplex until acoustic bench calibration. The
upstream ESP-SR software pipeline remains available in the source, but its P4
reference delay and the independent S3 I2S clocks/DMA have not been calibrated.
Do not advertise verified AEC or full-duplex operation. Capture, playback and
network conversation lifecycle remain implemented.

## Verification evidence

Focused checks (2026-10-29):

```sh
PYTHONPATH=/tmp/hachimo-python-tools \
  python3 \
  -m pytest -q firmware/tests/s3_hardware_test.py \
  firmware/tests/s3_action_list_test.py firmware/tests/s3_virtual_pointer_test.py \
  firmware/tests/p4_input_logic_test.py
```

Result: **7 passed**. Tests execute production decoder/conversion code and
production miniapp enumeration/pointer helpers with bounded host fixtures.
Covered bounce rejection; previous/next/confirm; one-shot long back/menu;
voice start/release with no short-after-long; signed PCM conversion, stereo
replication/volume; unique action enumeration including pointer-only actions;
pointer bounds/tap/stroke/cancel; S3 forced half-duplex and unchanged P4 choice.
The new key/PCM/half-duplex behaviors were observed failing before implementation.
The upstream P4 input decoder executable also passes unchanged.

Using `/tmp/hachimo-s3-build/compile_commands.json`, the real ESP-IDF 6.1
Xtensa-ESP32-S3 GCC 15.2 commands compiled these owned modules to isolated output
objects, with normal project warning/error flags and no suppressed warnings:

- `pet_p4_lcd.c`
- `pet_p4_audio.c`
- `pet_p4_input.c`
- `pet_p4_touch.c`
- `pet_p4_usb_native.c`
- `pet_p4_usb_descriptors.c`
- `pet_p4_miniapp.c` (including the S3 action enumeration)
- `pet_p4_local_tools.c`

Evidence: `/tmp/s3-hardware-pet_p4_*.c.o` and matching `.log` files. Shared
miniapp/local-tools GCC 15 format/indentation diagnostics were repaired without
disabling their warning checks; both modules now compile with the actual S3
commands. Compact UINT64_MAX formatting and all three complete 14-character
statistics fields fit the 64-byte summary (59 visible bytes). Root integration
owns the complete firmware build and link. Module compilation is not evidence
of successful linking, firmware boot, or physical signal correctness.

## Physical checks still required

Verify panel red/green/blue order, panel offsets/orientation, first-frame reveal
and SPI stability; verify all three keys including GPIO0 boot strapping; verify
microphone left-slot alignment and amplitude, MAX98357A output, 16/48 kHz
transitions, playback underruns, voice press/release, software cursor usability,
and acoustic half-duplex timing. No measurements or real-device claims are made.
