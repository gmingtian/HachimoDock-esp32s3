# S3 LAN transport (0.7.103-s3-r3)

The fixed S3 hardware now supports either USB Serial/JTAG, USB-UART, or one
TLS-authenticated Wi-Fi STA runtime owner. P4 does not link any S3 Wi-Fi sources.
Existing state, key, widget, appearance, audio, screenshot and OTA envelopes use
the same protocol worker and transaction handlers over either transport.

## Pairing and endpoints

Connect USB first. `wifi/configure` accepts `ssid`, `password`, `enabled:true`;
`wifi/pair` returns the device-specific public `certificatePem`, lowercase hex64
`token`, `boardDeviceId`, `hostname`, `ip` and `port`. Both commands, and
`wifi/clear`, are USB maintenance only. Every maintenance envelope carries a
`requestId` that is echoed in its response. Secrets never enter logs or mDNS.
The private key is never exposed by a runtime command.

The certificate is generated with the SDK mbedTLS 4 PSA API on first USB pairing:
ECDSA P-256, self-signed leaf, CA:FALSE, digitalSignature, serverAuth, DNS SAN
`<boardDeviceId>.local`, validity 2020–2100. Store this device-specific certificate
as the only trust anchor for the paired board; validate its signature and SAN.
Initial provisioning generates 32 random token bytes. Additional USB pairing
reuses that token; local revocation rotates it. The key/certificate survive
configuration clearing, preserving the board's cryptographic identity.

`wifi/status` returns enabled/configured/connected, SSID, IP, RSSI, port and board
ID, plus `clientConnected` and a non-secret `state` code. `wifi/scan` returns at
most 20 SSID/RSSI/secure records; its active scan has a 3.5-second absolute bound.
`wifi/set_enabled` toggles the station. Mutation and scan requests fail with
`device_busy` during capture, playback, widget/resource transfer or OTA.

Service: TCP 48973, TLS 1.2 or newer, DNS-SD `_hachimodock._tcp.local`.
The bounded IPv4 mDNS responder publishes PTR, SRV, TXT and A records. A manually
entered IP uses exactly the same certificate identity validation.

The first TLS JSONL request must be `wifi/auth`, with `token`,
`desktopDeviceId`, `expectedBoardDeviceId`, `takeover` and `requestId`. Auth
success is queued before hello or normal events. `takeover:true` is an explicit
idle-only switch from an existing USB owner. `transport/release` releases only
the current idle owner and acknowledges via `transport/status`.

## Isolation and resource limits

All S3 RX chunks, including raw binary resource bytes, enter one bounded worker
queue. Every queued chunk and reply carries an immutable route/generation token.
Only the exact owner may consume a pending raw asset block. Late old fragments
or close markers cannot reset the new stream's framing. The host lease is six
seconds; host messages, raw transfer progress and maintenance renew it.

Disconnect cleanup is serialized with commands: it invalidates event routing,
stops capture/conversation/playback, clears transient conversation state, aborts
uncommitted appearance/widget/OTA data, then admits another owner. Already
committed OTA reboot remains valid. Capture tasks retain their original session
reply context, so late PCM/end events cannot be routed to a replacement client.
No command or failed transfer is replayed.

The network task alone owns TLS/socket I/O. Senders copy complete JSONL frames
into a queue of at most 64 items and 128 KiB, including the in-flight frame.
Each frame has a one-second absolute send deadline. Queue exhaustion, malformed
or oversized input, a half-open peer, or send failure closes that generation.
TLS allocation and Wi-Fi/LwIP copies prefer PSRAM; DMA RX/TX pools are six
frames each and the dynamic RX pool is eight frames. Wi-Fi IRAM optimizations
are disabled to preserve internal task/I2S headroom. The line limit is 32768 bytes; TLS handshake and authentication each have a
five-second deadline. Large framing, ingress and egress buffers use PSRAM.

Three-key component menus contain “Wi-Fi 设置”, showing Chinese status/IP,
enable/disable, revoke all bindings, and clear configuration. Revocation and
clearing require a separate confirmation with cancel selected by default.
Existing three-key short/hold behavior and GPIO wiring remain unchanged.

## Validation

`tests/s3_wifi_host_test.py` compiles the portable ownership/framing helpers and
the real S3 ingress coordinator with deterministic hardware edges. It verifies
unpaired/unauthenticated rejection, busy takeover, auth ordering, raw isolation,
stale-generation fragmentation, lease-expiry cleanup, capture session pinning,
and menu confirmation/busy rules. The full firmware suite also exercises P4
regressions. The real certificate writer was executed against a host build of
the installed mbedTLS4 source; OpenSSL and desktop rustls both accepted its
server purpose, signature and SAN. This is host interoperability, not a radio test.

The ESP-IDF S3 build retains two 3 MiB application slots and unchanged resource
partitions. Use an ASCII-only dedicated build path with the installed GCC15
SDK: its generated picolibc specs mishandle Chinese build-directory names.
`build_s3.sh` also updates the bundled desktop image; use `idf.py` directly for
verification when an existing release must remain untouched. No board was
flashed. RF reliability, real NVS power loss, audio latency/underflow, framebuffer
rate, IP changes and prolonged connection stability require physical testing.

## Three-key built-in component policy

The S3 catalog keeps `snake-turn`, `two-key-pong` and `flappy-bird`, which can be
played directly with the three physical keys. `block-combo`, `fresh-fruit-slice`,
`cloud-hop` and `bloomfrog_companion` are excluded from S3 factory defaults,
embedded bootstrap and new installations. Existing upgraded catalogs hide these
four IDs without deleting packages or saves. P4 defaults and original packages
remain unchanged. The canonical list is `component-policy.json`; this policy
covers reviewed built-ins and does not classify arbitrary custom applications.
