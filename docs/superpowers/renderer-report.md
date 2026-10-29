# S3 renderer and appearance implementation

Implemented in the shared renderer; P4 accelerator code and P4 landscape-to-panel rotation remain conditional on P4/SOC capabilities. S3 uses LVGL TJPGD for JPEG and Espressif esp_h264's software I420 decoder with CPU color conversion. It never requests a JPEG engine or PPA handle. S3 renderer output is native, unrotated RGB565 240×240; the LCD backend owns SPI wire byte order.

All existing component/game/media/instrument renderer entry points remain. Their 640×480 logical canvas fits inside a centered 240×180 rectangle (30-pixel black bars), without cropping. Component center and the three-key action menu render native 16 px text as seven-row lists. The virtual pointer maps logical coordinates to the same aspect-fit rectangle. Other component text is scaled with its canvas and may remain small; hardware readability remains to be assessed.

## Bounds and memory

S3 appearance manifests reject dimensions above 240×180, rates above 10 fps, JPEG frames above 128 KiB and individual video streams above 384 KiB. Duration metadata cannot disguise a higher frame rate. The supported software H264 profile uses canonical constrained-baseline SPS, one reference and one slice per access unit. Every SPS is checked against the catalog's bounded dimensions **before** a decoder opens; a dishonest small manifest cannot request a P4-sized decoder picture pool. Decoder-mutated input has a separate bounded copy, retaining the existing P4 replay protection.

The renderer's major peak retained allocations are:

| Allocation | S3 bytes |
| --- | ---: |
| Shared logical RGB565 canvas | 614,400 |
| Two native 240×240 output buffers | 230,400 |
| JPEG compressed input | 131,072 |
| JPEG RGB565 output (preserves full-size component backgrounds) | 614,400 |
| Immutable stream cache (one slot) | ≤393,216 |
| Private software decoder stream copy | ≤393,216 |
| Optional session overlay cache | 614,400 |
| Existing static component background cache | 614,400 |
| JPEG work buffer (internal RAM) | 4,096 |

This is about 3.60 MB excluding renderer sprite snapshots, runtime state, decoder picture/reference storage, task stacks, LVGL, audio and allocator overhead. It is an allocation budget, **not measured free heap**. The S3 component menu skips the P4 background/thumbnail caches. PPA YUV packing worker and its additional buffer are not started/allocated on S3. Remaining shared subsystem allocations must be considered against the complete 8 MB PSRAM budget during on-device validation. No allocation-failure path claims success.

Software decode and SPI presentation timing have not been physically measured; 10 fps is the accepted asset ceiling, not a claimed achieved frame rate. One video picture is decoded per renderer pass, preserving scheduler fairness.

## Default appearance and conversion

Generated `firmware/assets/s3-default/p4/manifest.json` retains all 16 upstream appearance families. Target: `esp32s3`; visible size 240×180; sampling rate 10 fps; total files 1,005,133 bytes; largest video 80,641 bytes. Pack ID:

`b384649824c5fe9e739763cfba20b81edc465f007206098aa91e63f5b2a1feed`

The `p4/` logical namespace and `p4-h264-v1` identify the existing shared wire/container format; they do not advertise an ESP32-P4 device. Genuine target identity is carried by the target protocol/build configuration.

Reproduction (FFmpeg with libx264 required):

```sh
python3 firmware/tools/prepare_s3_assets.py \
  --source pc/public/terrier-clips/p4-ready/v9-640x480-15fps-225f-h264-crf27 \
  --output firmware/assets/s3-default \
  --ffmpeg /path/to/ffmpeg
```

Input may instead be a directory containing raw `.mp4` files, a source manifest JSON, or a directory containing `manifest.json`. A family can use `sourceFile`, `videoPath`, `video`, `source`, or prepared `path`; `--app-data-dir` resolves custom desktop paths. Optional audioPath/audioFile is normalized to mono 16 kHz PCM16. Conversion preserves prepared Annex-B input timing explicitly, rejects source video longer than 30 seconds (rather than silently truncating), accepts at most 300 output frames at 10 fps, rejects normalized audio above the runtime 1 MiB PCM ceiling, and rejects oversized streams/packages rather than silently lowering quality or dropping families. Default package slot check is 3 MiB including 4 KiB header. Source files must be inside their declared input root. FFmpeg is executed directly without a shell. Host pack identity matches the existing SHA256 protocol.

## Verification

Test-first literal fixtures failed before the new scaler/SPS/converter existed and before S3 catalog restrictions were added. The passing host command was:

```sh
ASAN_OPTIONS=detect_leaks=0 \
  S3_TEST_FFMPEG=/tmp/hachimo-python-tools/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2 \
  PYTHONPATH=/tmp/hachimo-python-tools \
  /home/gaomt/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  -m pytest -q firmware/tests/s3_renderer_test.py \
  firmware/tests/p4_h264_replay_test.py firmware/tests/p4_media_renderer_test.py \
  firmware/tests/p4_todo_renderer_test.py firmware/tests/p4_alpha_panel_test.py \
  firmware/tests/instrument_assets_test.py
```

Result: **14 passed**. Address/undefined sanitizers remain active in existing harnesses; only LeakSanitizer is disabled because this execution environment uses ptrace, which LeakSanitizer explicitly refuses. S3 fixtures execute production C integer aspect fit/scaling, landscape/portrait/downsampling pixels, resource policy and actual catalog parser, plus canonical SPS bounds before decode. Converter tests exercise actual single-slice counting/package bounds and real FFmpeg transcode/decode, Annex-B timing preservation, hash identity, overlong video rejection, runtime audio limits and real desktop partial-upload manifests with custom cue preservation. All 16 generated streams separately passed upstream `build_factory_image.parse_p4_h264_stream` (canonical SPS, AUD/single-slice count and frame-index equality).

The actual ESP-IDF 6.1 S3 compiler commands from `/tmp/hachimo-s3-build/compile_commands.json` successfully compiled `pet_p4_renderer.c` and `pet_p4_assets.c` to isolated `/tmp` objects. Build integration exposed existing misleading-indentation diagnostics in compact renderer/image-header statements; these were formatted without behavior changes. Root integration owns the final complete firmware link, factory SPIFFS/raw-partition packaging and firmware memory/linker verification. No display, decode throughput, buttons or audio have been physically tested here. No device was flashed.
