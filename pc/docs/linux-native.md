# Native Linux desktop and wired ESP32-S3

This is the existing Tauri desktop application, with the session monitor, component center, games, media, voice services and serial transport retained. The web preview alone cannot operate the USB board.

## Build and run

Use Node.js 22+ with npm, Rust **1.95 or newer** (the locked sysinfo 0.39.6 requires it), a C compiler, pkg-config and Python 3.10+. On Ubuntu/Debian the native development libraries are:

```sh
sudo apt install build-essential pkg-config libgtk-3-dev libwebkit2gtk-4.1-dev \
  libayatana-appindicator3-dev libasound2-dev libudev-dev libssl-dev libbz2-dev ffmpeg python3
```

The Linux app uses a separately installed FFmpeg with the `libx264` encoder. It does not copy that FFmpeg into the application. Check it with `ffmpeg -hide_banner -encoders`; `libx264` must appear. `PET_MANAGER_BUNDLED_FFMPEG` can explicitly select a local FFmpeg executable for development.

From `pc/`:

```sh
npm ci
npm run dev:linux
```

For an optimized native application and its resources:

```sh
npm run build:linux
./dist-linux/launch.sh
```

`build:linux` uses Tauri, then stages the ELF under `dist-linux/usr/bin/pet-manager-tauri` and its complete configured resources under `dist-linux/usr/lib/HachimiDock`. The resource directory follows Tauri's configured `productName`, which overrides the Cargo package name. The directory can be moved as a unit. It requires the host GTK/WebKitGTK, ALSA, udev and OpenSSL runtime libraries, plus FFmpeg and Python3; this is not a self-contained AppImage. No persistent service or device flashing is installed by these commands. `CARGO_TARGET_DIR` and `PET_MANAGER_LINUX_BINARY` are supported by `npm run stage:linux` for an existing native build.

The preparation step copies a native Node executable into application resources and installs the bridge's locked production dependencies. `PET_MANAGER_NODE_BIN` can override the Node executable. Serial access needs the normal permissions on `/dev/ttyACM*` or `/dev/ttyUSB*`; use your distribution's serial-device group if access is denied. No automatic system group/udev changes are made.

## ESP32-S3 contract

The verified hello must report `runtime: "esp-s3"` (S3 aliases and explicit S3 model metadata also normalize to this identity). Shared `p4-*` asset format names describe the file format and do not override S3 identity. Component, session and voice commands use the shared full runtime protocol. S3 uses serial/JTAG or the USB-UART connection, rather than the P4-specific native bulk path.

| Physical key | Short press | Long/hold |
| --- | --- | --- |
| Previous, GPIO39 | Previous item | Back / home |
| Next, GPIO38 | Next item | Component menu |
| Confirm, GPIO0 | Confirm | Hold to capture voice; release to stop |

There is no touch panel or joystick. The button editor exposes only these six gestures. Firmware-declared virtual-pointer capability permits compatible pointer scenes without claiming touch hardware.

Custom appearance synchronization converts the original local family sources into a separate `s3-ready/p4/` package, validates the generated manifest, SHA-256 pack identity, H.264 streams and PCM audio, and only then starts the transactional USB transfer. The limits are 240×180 video, at most 15 fps, 384 KiB and 320 frames per video, and 3 MiB per slot including storage metadata. At 15 fps, 320 frames allow about 21.3 seconds per video. An oversized package fails with a useful error rather than being silently sent as a P4 package. The physical panel is 240×240; firmware aspect-fits the shared logical canvas.

The standalone conversion command is:

```sh
npm run prepare:s3-assets -- --source /path/to/appearance \
  --app-data-dir /path/to/app-data --output /path/to/s3-ready \
  --ffmpeg /path/to/ffmpeg
```

For an existing prepared P4 pack or a directory of MP4 files, omit `--app-data-dir`. The converter retains audio cues and rejects unsupported/oversized media explicitly.

Firmware OTA checks the application header's ESP chip ID before any erase/upload and requires the matching project name. S3 accepts chip ID 9 and `pet_manager_s3_runtime`, within its 3 MiB OTA partition. P4 images are rejected on S3. The S3 bundled update path is exclusively `firmware/esp32-s3/firmware.bin`; if that genuine image is not packaged, automatic update is unavailable and never falls back to a P4 image. The actual firmware artifact must be produced by the S3 firmware build.

## Platform limits

Linux foreground input-box discovery, draft insertion and automatic sending into other desktop applications are unsupported. The dashboard displays this limit and the backend returns an error, including draft-preservation requests. USB capture/playback, ASR and the standalone real-time voice loop are separate functions and still depend on the configured services and physical audio tests. Session monitoring remains available. ASR, voice/model and generation-provider credentials use encrypted files in the current user’s private application directory on Linux; private directories are owner-only, and existing unreadable configurations are preserved. Existing macOS and Windows composer implementations and release-specific encoders are retained.

Compilation and host tests do not verify a physical board, audio quality, display timing, USB reconnect behavior or sustained software H.264 playback speed. See the task's desktop report for exact checks completed on this computer.
