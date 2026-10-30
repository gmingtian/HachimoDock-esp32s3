#!/usr/bin/env python3
"""Run the real S3 converter with a built helper; no third-party Python packages."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import wave


def check(helper, converter):
    def run(*args):
        return subprocess.run([str(helper), '-hide_banner', '-loglevel', 'error',
                               '-nostdin', '-y', *map(str, args)],
                              check=True, capture_output=True, text=True).stdout

    spec = importlib.util.spec_from_file_location('s3_converter', converter)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    protocols = run('-protocols').split()
    assert protocols == ['Supported', 'file', 'protocols:', 'Input:', 'file', 'pipe',
                         'Output:', 'file', 'pipe'], protocols
    with tempfile.TemporaryDirectory(prefix='S3 helper smoke ') as tmp:
        root = Path(tmp)
        raw = root / 'input.rgb'
        # Moving RGB gradient, twelve frames at twelve fps: one second.
        raw.write_bytes(bytes(value for frame in range(12)
                              for y in range(48) for x in range(64)
                              for value in ((x * 4 + frame * 5) % 256,
                                            y * 5, (frame * 20 + y) % 256)))
        video = root / 'fixture.mp4'
        run('-f', 'rawvideo', '-pixel_format', 'rgb24', '-video_size', '64x48',
            '-framerate', '12', '-i', raw, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', video)
        # Match prepare-p4-ready-assets.mjs's duration probe used by build.rs.
        progress = run('-i', video, '-map', '0:v:0', '-c', 'copy',
                       '-f', 'null', '-', '-progress', 'pipe:1', '-nostats')
        assert 'progress=end' in progress
        timestamps = re.findall(r'^out_time_us=(\d+)$', progress, re.MULTILINE)
        assert timestamps and max(map(int, timestamps)) > 0, progress
        audio = root / 'fixture.wav'
        with wave.open(str(audio), 'wb') as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(22050)
            wav.writeframes(b''.join(struct.pack('<hh', (i % 200) * 64 - 6400,
                                                (i % 200) * 32 - 3200)
                                     for i in range(22050)))
        (root / 'manifest.json').write_text(json.dumps({
            'families': [{'family': 'idle', 'sourceFile': video.name,
                          'audioPath': audio.name}],
        }))
        manifest = module.prepare(root, root / 'converted', str(helper))
        assert manifest['target'] == 'esp32s3'
        assert (manifest['width'], manifest['height'], manifest['fps']) == (240, 180, 15)
        family, = manifest['families']
        stream_path = root / 'converted' / family['path']
        stream = stream_path.read_bytes()
        assert family['frames'] == module.frame_count(stream) == 15
        assert family['streamBytes'] == len(stream) <= 384 * 1024
        nal_units = [nal for nal in re.split(b'\x00\x00\x00?\x01', stream) if nal]
        sps_units = [nal for nal in nal_units if nal[0] & 31 == 7]
        assert sps_units and all(nal == module.minimal_sps() for nal in sps_units)
        # Decode the actual SPS-rewritten stream: header equality alone does not
        # establish that the x264 payload matches the software decoder contract.
        decoded = root / 'decoded.yuv'
        run('-xerror', '-i', stream_path, '-pix_fmt', 'yuv420p', '-f', 'rawvideo', decoded)
        assert decoded.stat().st_size == 15 * 240 * 180 * 3 // 2
        audio_path = root / 'converted' / family['audioPath']
        with wave.open(str(audio_path), 'rb') as wav:
            assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (1, 2, 16000)
            assert wav.getnframes() == 16000
            assert any(wav.readframes(16000)), 'PCM conversion unexpectedly produced silence'
        module.validate_bounds(manifest, len(stream) + audio_path.stat().st_size + 6)
        print(json.dumps({'helper': str(helper), 'frames': family['frames'],
                          'streamBytes': len(stream), 'pcmFrames': 16000,
                          'canonicalSps': True, 'decodedFrames': 15,
                          'buildDurationProbe': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('helper', type=Path)
    parser.add_argument('--converter', type=Path,
                        default=Path(__file__).resolve().parents[2] /
                        'firmware/tools/prepare_s3_assets.py')
    args = parser.parse_args()
    check(args.helper.resolve(), args.converter.resolve())
