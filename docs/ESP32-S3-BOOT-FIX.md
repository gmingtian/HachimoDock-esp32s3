# ESP32-S3 r4 boot repair

## Evidence

The failing r3 log already reaches `app_main()`, loads the application at
`0x10000`, detects 16 MiB Flash and passes the 8 MiB octal PSRAM memory test.
The original ELF SHA-256 is
`3ed9e1ccfa1c07995600ec6094731a10847e1200f1cd8a314e35ac0a5fab0fb2`.
Decoding this exact ELF identifies two independent startup failures:

- Watchdog traces enter `pet_p4_miniapp_init` -> `validate_catalog_snapshot` ->
  `load_catalog_runtime_item` -> `load_sprite_pack` -> SPIFFS name lookup.
  Consecutive synchronous file reads starve IDLE0 during catalog restoration.
- The later abort enters `pet_p4_miniapp_sync_builtins` -> `write_file_atomic`
  -> SPIFFS mtime -> `time()` -> `lock_init_generic`. The abort is the
  `xQueueCreateMutex` allocation failure in ESP-IDF `esp_libc/src/locks.c`.
  Thousands of small cJSON allocations use scarce internal RAM by default,
  despite megabytes of PSRAM remaining available.

After boot was fixed, USB testing exposed another existing failure: a complete
capabilities hello exceeds the 4096-byte USB TX ring. The driver queues each
write atomically, so the old whole-line write was rejected and only its newline
was sent. Writes are now bounded to 512 bytes, retaining frame serialization.

## Changes

`pet_s3_json_memory_init()` installs PSRAM-only cJSON hooks once, before JSON
parsing or worker creation. No internal fallback is used for JSON OOM. Existing
P4 allocation is unchanged. Component text and binary reads block for one tick
before each filesystem lookup, including missing-file paths. The watchdog
remains enabled. No format/reseed, partition or pin change is needed.

## Recovery

For an existing r3 installation, flash the r4 application at `0x10000` when the
boot log confirms `ota_0` is active. This preserves resources/configuration.
Use the complete 16 MiB factory image at `0x0` for a fresh install; a factory
write replaces the full flash contents. Never write the app-only image at zero.
Flash Download Tool `DoNotChgBin` preserves the image's DIO/80 MHz header;
the selected download baud does not set the runtime logging baud.

## Validation

The three regression harnesses execute the actual JSON hook, file read helpers
and USB queue function under address/undefined-behavior sanitizers. The JSON
test parses the real embedded component bundle, checks PSRAM caps, frees every
allocation and simulates OOM. The file test covers all 25 components plus
missing/oversized files. USB testing covers a 12 KiB frame, partial writes,
transport failure and empty input.

ESP-IDF v6.1 builds using the original Ubuntu environment. On 2026-10-29 the
connected ESP32-S3 revision 0.2 / N16R8 board was updated through COM3. The user
confirmed the display and desktop pet became visible after the startup fix.
Final USB, reboot and test results are recorded with the release artifacts.
This does not claim Wi-Fi, microphone, speaker or gameplay acceptance.
