"""Exercise image assembly before any board is connected or written."""
import importlib.util
from pathlib import Path
import pytest
import subprocess

TOOLS = Path(__file__).resolve().parents[1] / "tools"

def module():
    spec = importlib.util.spec_from_file_location("s3_factory", TOOLS / "build_s3_factory.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

def image(path, chip=9):
    data = bytearray(24)
    data[0] = 0xe9
    data[12] = chip
    path.write_bytes(data)
    return path

def test_factory_keeps_boot_app_and_data_at_exact_offsets(tmp_path):
    boot = image(tmp_path / "boot.bin")
    app = image(tmp_path / "app.bin")
    data = tmp_path / "data.bin"
    data.write_bytes(b"pet")
    out = tmp_path / "factory.bin"
    module().assemble_image([(0, boot), (0x10000, app), (0x620000, data)], out)
    result = out.read_bytes()
    assert len(result) == 16 * 1024 * 1024
    assert result[:24] == boot.read_bytes()
    assert result[0x10000:0x10018] == app.read_bytes()
    assert result[0x620000:0x620003] == b"pet"
    assert result[-1] == 255

def test_factory_rejects_p4_image_without_creating_output(tmp_path):
    out = tmp_path / "factory.bin"
    with pytest.raises(ValueError, match="ESP32-S3"):
        module().assemble_image([(0, image(tmp_path / "boot.bin")),
                                 (0x10000, image(tmp_path / "p4.bin", 18))], out)
    assert not out.exists()

def test_factory_rejects_overlapping_segments_without_output(tmp_path):
    boot = image(tmp_path / "boot.bin")
    app = image(tmp_path / "app.bin")
    with pytest.raises(ValueError, match="overlap"):
        module().assemble_image([(0, boot), (0x10000, app), (0x10001, app)], tmp_path / "out")

def test_device_rejects_cross_chip_ota_images(tmp_path):
    firmware = TOOLS.parent
    for source, flags in [("s3_image_compat_test.c", ["-DCONFIG_IDF_TARGET_ESP32S3=1"]),
                          ("p4_image_compat_test.c", [])]:
        output = tmp_path / source.removesuffix(".c")
        subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", *flags,
            "-I", str(firmware / "main"), str(firmware / "tests" / source),
            "-o", str(output)], check=True)
        subprocess.run([str(output)], check=True)
