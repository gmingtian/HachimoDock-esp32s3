"""Validate every shipped native landscape animation against the runtime gate."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_all_native_landscape_families_are_safe_and_fit_flash(tmp_path):
    spec = importlib.util.spec_from_file_location('s3_assets', ROOT/'tools/prepare_s3_assets.py')
    converter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(converter)
    pack = ROOT/'assets/s3-landscape-default'
    manifest = json.loads((pack/'p4/manifest.json').read_text())
    square = json.loads((ROOT/'assets/s3-default/p4/manifest.json').read_text())
    assert (manifest['width'], manifest['height'], manifest['fps']) == (320, 240, 15)
    assert {f['family'] for f in manifest['families']} == {f['family'] for f in square['families']}
    assert len(manifest['families']) == 16
    sources = json.loads((ROOT/'assets/s3-landscape-source.json').read_text())
    source_root = ROOT.parent/sources['sourceRoot']
    assert {f['family'] for f in sources['families']} == {f['family'] for f in manifest['families']}
    for family in sources['families']:
        assert hashlib.sha256((source_root/family['sourceFile']).read_bytes()).hexdigest() == family['sourceSha256']
    files = {}
    for family in manifest['families']:
        path = pack/family['path']
        data = path.read_bytes()
        assert path.stem == 'sha256-' + hashlib.sha256(data).hexdigest()[:24]
        assert converter.frame_count(data) == family['frames']
        assert len(data) == family['streamBytes']
        assert family['fps'] == 15
        assert family['durationMs'] == (family['frames']*1000+14)//15
        assert converter.minimal_sps(320,240) in data
        files[family['path']] = path
        if family.get('audioPath'):
            files[family['audioPath']] = pack/family['audioPath']
    converter.validate_bounds(manifest, sum(p.stat().st_size+3 for p in files.values()))
    identity = dict(manifest, packId='')
    assert manifest['packId'] == converter.pack_id(identity, files)
    source = (ROOT/'main/pet_p4_renderer.c').read_text()
    from s3_official_input_test import function
    start=source.index('static bool h264_stream_has_single_slice_access_units(',source.index('static bool h264_stream_has_single_slice_access_units(')+1)
    gate=function(source[start:],'static bool h264_stream_has_single_slice_access_units(')
    harness = tmp_path/'streams.c'
    harness.write_text(r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include "pet_s3_render.h"
#define PET_P4_ASSET_PREPARE_CHUNK_BYTES 16384U
typedef struct {int unused;} pet_p4_asset_cache_entry_t;
static void vTaskDelay(unsigned n){(void)n;}
static bool asset_prepare_current(const pet_p4_asset_cache_entry_t *job){(void)job;return true;}
''' + gate + r'''
int main(int argc,char **argv){
  for(int i=1;i<argc;i++){
    FILE *f=fopen(argv[i],"rb");assert(f);
    assert(fseek(f,0,SEEK_END)==0);long n=ftell(f);assert(n>0&&n<=384*1024);
    rewind(f);uint8_t *bytes=malloc(n);assert(bytes);
    assert(fread(bytes,1,n,f)==(size_t)n);fclose(f);
    assert(h264_stream_has_single_slice_access_units(bytes,n,320,240,NULL));
    assert(!h264_stream_has_single_slice_access_units(bytes,n,240,180,NULL));
    free(bytes);
  }
  return 0;
}
''')
    exe = tmp_path/'streams'
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',
                    '-fsanitize=address,undefined','-DPET_S3_LANDSCAPE_LEFT=1',
                    '-DCONFIG_IDF_TARGET_ESP32S3=1','-I',str(ROOT/'s3'),
                    str(harness),'-o',str(exe)],check=True)
    subprocess.run([str(exe),*[str(pack/f['path']) for f in manifest['families']]],check=True)
