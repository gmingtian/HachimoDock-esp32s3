#!/usr/bin/env python3
"""Build a 16 MiB S3 factory image; this command never opens a serial port."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
import build_factory_image as factory

FLASH_BYTES = 16 * 1024 * 1024

def s3_factory_config(config):
    """Derive target defaults without changing the shared P4 configuration."""
    config = copy.deepcopy(config)
    policy = json.loads((TOOLS.parent / "s3/component-policy.json").read_text())
    excluded = set(policy["unsupportedBuiltins"])
    config["components"]["ids"] = [identifier for identifier in config["components"]["ids"]
                                    if identifier not in excluded]
    return config

def assemble_image(segments, output):
    ordered = sorted(segments, key=lambda entry: entry[0])
    previous_end = 0
    validated = []
    for offset, path in ordered:
        data = Path(path).read_bytes()
        if offset < previous_end:
            raise ValueError("overlapping flash segments")
        if offset < 0 or offset + len(data) > FLASH_BYTES:
            raise ValueError("segment exceeds 16 MiB flash")
        if offset in (0, 0x10000):
            if len(data) < 24 or data[0] != 0xe9 or data[12:14] != b"\x09\x00":
                raise ValueError("bootloader and application must target ESP32-S3")
        validated.append((offset, data))
        previous_end = offset + len(data)
    if not {0, 0x10000}.issubset({offset for offset, _ in validated}):
        raise ValueError("ESP32-S3 bootloader and application are required")
    result = bytearray(b"\xff") * FLASH_BYTES
    for offset, data in validated:
        result[offset:offset + len(data)] = data
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_bytes(result)
    temporary.replace(output)

def build(build_dir, output, spiffsgen):
    project = TOOLS.parent
    build_dir = Path(build_dir).resolve()
    config = s3_factory_config(json.loads((project / "factory-config.json").read_text()))
    manifest = json.loads((project / "assets/s3-default/p4/manifest.json").read_text())
    config["partitionFile"] = "partitions.s3.csv"
    config["appearance"].update(width=240, height=180, fps=10,
        readyRoot="assets/s3-default", readyProfile="s3-240x180-10fps",
        packId=manifest["packId"])
    appearance = factory.build_default_appearance_tree(project, build_dir, config)
    components = factory.build_builtin_component_tree(project, config, appearance["tree"])
    spiffs, offset, _ = factory.build_spiffs_image(project, build_dir, config,
        appearance["tree"], Path(spiffsgen))
    raw, raw_offset, _ = factory.build_raw_appearance_image(project, build_dir,
        appearance, "partitions.s3.csv")
    flasher = json.loads((build_dir / "flasher_args.json").read_text())
    if flasher.get("extra_esptool_args", {}).get("chip") != "esp32s3":
        raise ValueError("build configuration must target ESP32-S3")
    segments = [(int(address, 0), build_dir / path)
                for address, path in flasher["flash_files"].items()]
    segments.extend([(offset, spiffs), (raw_offset, raw)])
    assemble_image(segments, output)
    summary = {"target": "esp32s3", "projectName": "pet_manager_s3_runtime",
        "flashBytes": FLASH_BYTES, "psramBytes": 8 * 1024 * 1024,
        "physicalDisplay": [240, 240], "appearancePackId": manifest["packId"],
        "appearanceBytes": appearance["payloadBytes"],
        "componentCount": components["count"],
        "componentBytes": components["payloadBytes"],
        "sha256": factory.sha256_file(Path(output)),
        "segments": [{"offset": address, "file": str(path.name),
                      "bytes": path.stat().st_size, "sha256": factory.sha256_file(path)}
                     for address, path in sorted(segments)]}
    Path(output).with_suffix(".json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--spiffsgen", required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.build_dir, args.output, args.spiffsgen), indent=2))
