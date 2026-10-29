"""Execute the same bounded scaler used by the S3 renderer with literal pixels."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_aspect_fit_rgb565_and_resource_bounds(tmp_path):
    harness = tmp_path / 'scale.c'
    harness.write_text(r'''
#include <assert.h>
#include <stdint.h>
#include "pet_s3_render.h"
int main(void) {
  const uint16_t pixels[] = {1,2,3,4,5,6,7,8};
  uint16_t out[16];
  pet_s3_rect_t rect;
  assert(pet_s3_fit_rect(4,2,4,4,&rect));
  assert(rect.x==0 && rect.y==1 && rect.width==4 && rect.height==2);
  assert(pet_s3_scale_rgb565(pixels,4,2,4,out,4,4));
  const uint16_t expected[] = {0,0,0,0,1,2,3,4,5,6,7,8,0,0,0,0};
  for(unsigned i=0;i<16;i++) assert(out[i]==expected[i]);
  const uint16_t portrait[] = {11,12,21,22,31,32,41,42};
  assert(pet_s3_scale_rgb565(portrait,2,4,2,out,4,4));
  const uint16_t expected_p[] = {0,11,12,0,0,21,22,0,0,31,32,0,0,41,42,0};
  for(unsigned i=0;i<16;i++) assert(out[i]==expected_p[i]);
  uint16_t down[4];
  assert(pet_s3_scale_rgb565(pixels,4,2,4,down,2,2));
  assert(down[0]==1 && down[1]==3 && down[2]==0 && down[3]==0);
  assert(pet_s3_fit_rect(640,480,240,240,&rect));
  assert(rect.x==0 && rect.y==30 && rect.width==240 && rect.height==180);
  assert(!pet_s3_fit_rect(0,480,240,240,&rect));
  assert(!pet_s3_scale_rgb565(pixels,4,2,3,out,4,4));
  assert(pet_s3_asset_bounds(240,180,10,384*1024));
  assert(!pet_s3_asset_bounds(640,480,10,100));
  assert(!pet_s3_asset_bounds(240,180,11,100));
  assert(!pet_s3_asset_bounds(240,180,10,384*1024+1));
  assert(!pet_s3_asset_bounds(240,180,10,0));
  return 0;
}
''')
    exe = tmp_path / 'scale'
    subprocess.run(['cc', '-std=c11', '-Wall', '-Werror', '-fsanitize=undefined', '-I', str(ROOT/'s3'), str(harness), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)


def test_s3_catalog_rejects_p4_resolution_fps_and_oversize(tmp_path):
    (tmp_path/'esp_heap_caps.h').write_text('''#include <stdlib.h>
#define MALLOC_CAP_SPIRAM 0
#define MALLOC_CAP_8BIT 0
#define heap_caps_calloc(n,s,c) calloc(n,s)
#define heap_caps_free free
''')
    harness=tmp_path/'assets.c'
    harness.write_text(r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include "pet_p4_assets.h"
int main(void) {
  pet_p4_asset_catalog_t *c=calloc(1,sizeof(*c));
  const char *format="{\"format\":\"p4-h264-v1\",\"width\":%d,\"height\":%d,\"fps\":%d,\"families\":[{\"family\":\"idle\",\"path\":\"p4/families/a.h264\",\"frames\":1,\"streamBytes\":%d}]}";
  char s[512];
  snprintf(s,sizeof(s),format,240,180,10,393216);assert(pet_p4_asset_catalog_parse(c,s));
  snprintf(s,sizeof(s),format,640,480,10,100);assert(!pet_p4_asset_catalog_parse(c,s));
  snprintf(s,sizeof(s),format,240,180,15,100);assert(!pet_p4_asset_catalog_parse(c,s));
  snprintf(s,sizeof(s),format,240,180,10,393217);assert(!pet_p4_asset_catalog_parse(c,s));
  snprintf(s,sizeof(s),format,240,180,0,100);assert(!pet_p4_asset_catalog_parse(c,s));
  const char *hidden_rate="{\"format\":\"p4-h264-v1\",\"width\":240,\"height\":180,\"fps\":10,\"families\":[{\"family\":\"idle\",\"path\":\"p4/families/a.h264\",\"frames\":10,\"frameDurationMs\":1,\"streamBytes\":100}]}";
  assert(!pet_p4_asset_catalog_parse(c,hidden_rate));
  free(c);return 0;
}
''')
    exe=tmp_path/'assets'
    subprocess.run(['cc','-std=c11','-fsanitize=undefined','-DCONFIG_IDF_TARGET_ESP32S3=1','-I',str(tmp_path),'-I',str(ROOT/'main'),str(harness),str(ROOT/'main/pet_p4_assets.c'),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)


def test_converter_bounds_and_h264_slice_count(tmp_path):
    import importlib.util
    spec=importlib.util.spec_from_file_location('prepare_s3_assets',ROOT/'tools/prepare_s3_assets.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    # Literal Annex B: SPS, PPS, IDR and P frame, exactly one slice per frame.
    stream=b'\x00\x00\x00\x01\x67\x42\x00\x00\x01\x68\x80\x00\x00\x01\x65\x80\x00\x00\x01\x41\x80'
    assert mod.frame_count(stream)==2
    try:mod.frame_count(b'\x00\x00\x01\x65\x40')
    except ValueError:pass
    else:raise AssertionError('must reject a slice with first_mb_in_slice != 0')
    manifest={'width':240,'height':180,'fps':10,'families':[{'frames':1,'fps':10,'streamBytes':393216}]}
    mod.validate_bounds(manifest,393216,3*1024*1024)
    manifest['families'][0]['streamBytes']=393217
    try:mod.validate_bounds(manifest,393217,3*1024*1024)
    except ValueError:pass
    else:raise AssertionError('must reject stream above decoder cache bound')
    manifest['families'][0]['streamBytes']=393216
    try:mod.validate_bounds(manifest,4*1024*1024,3*1024*1024)
    except ValueError:pass
    else:raise AssertionError('must reject package larger than flash slot')
    manifest['width']=640
    try:mod.validate_bounds(manifest,100,3*1024*1024)
    except ValueError:pass
    else:raise AssertionError('must reject P4 resolution')


def test_h264_sps_is_bounded_before_decoder_allocation(tmp_path):
    harness=tmp_path/'sps.c'
    harness.write_text(r'''
#include <assert.h>
#include "pet_s3_render.h"
int main(void) {
  const uint8_t sps[]={0x67,0x42,0xc0,0x1e,0xda,0x0f,0x19,0x79,0xd0};
  const uint8_t p4[]={0x67,0x42,0xc0,0x1e,0xda,0x02,0x80,0xf6,0x40};
  assert(pet_s3_h264_sps_matches(sps,sizeof(sps),240,180));
  assert(!pet_s3_h264_sps_matches(p4,sizeof(p4),240,180));
  assert(!pet_s3_h264_sps_matches(sps,sizeof(sps),640,480));
  assert(!pet_s3_h264_sps_matches(sps,4,240,180));
  assert(!pet_s3_h264_sps_matches(sps,sizeof(sps),239,180));
  return 0;
}
''')
    exe=tmp_path/'sps'
    subprocess.run(['cc','-std=c11','-Wall','-Werror','-I',str(ROOT/'s3'),str(harness),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)


def test_converter_real_ffmpeg_preserves_annex_b_timing_and_pack_identity(tmp_path):
    import importlib.util
    import json
    import os
    import shutil
    import pytest
    ffmpeg=os.environ.get('S3_TEST_FFMPEG') or shutil.which('ffmpeg')
    if not ffmpeg:pytest.skip('set S3_TEST_FFMPEG to exercise real video conversion')
    spec=importlib.util.spec_from_file_location('prepare_s3_assets',ROOT/'tools/prepare_s3_assets.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    source=tmp_path/'source';source.mkdir()
    # Exactly one second of raw H264 has no container timestamp. The source
    # catalog supplies 15 fps; assuming FFmpeg's default 25 fps would lose frames.
    subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=red:s=16x16:r=15',
                    '-frames:v','15','-c:v','libx264','-profile:v','baseline','-f','h264',str(source/'red.h264')],check=True)
    (source/'manifest.json').write_text(json.dumps({'fps':15,'families':[{'family':'idle','path':'red.h264','fps':15}]}))
    output=tmp_path/'output';manifest=mod.prepare(source,output,ffmpeg)
    entry=manifest['families'][0]
    assert entry['frames']==10
    assert entry['durationMs']==1000
    data=(output/entry['path']).read_bytes()
    assert mod.frame_count(data)==10
    assert mod.minimal_sps() in data
    identity=dict(manifest);identity['packId']=''
    assert manifest['packId']==mod.pack_id(identity,{entry['path']:output/entry['path']})
    # Decoder acceptance as well as byte/SPS checks: output is a real stream.
    subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-i',str(output/entry['path']),'-f','null','-'],check=True)


def test_converter_rejects_overlong_video_and_unplayable_audio(tmp_path):
    import importlib.util
    import json
    import os
    import shutil
    import wave
    import pytest
    ffmpeg=os.environ.get('S3_TEST_FFMPEG') or shutil.which('ffmpeg')
    if not ffmpeg:pytest.skip('set S3_TEST_FFMPEG to exercise real video conversion')
    spec=importlib.util.spec_from_file_location('prepare_s3_assets',ROOT/'tools/prepare_s3_assets.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    source=tmp_path/'source';source.mkdir()
    subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=black:s=16x16:r=1',
                    '-t','31','-c:v','libx264','-pix_fmt','yuv420p',str(source/'long.mp4')],check=True)
    with pytest.raises(ValueError,match='30 seconds'):
        mod.prepare(source,tmp_path/'long-output',ffmpeg)
    assert not (tmp_path/'long-output/p4/manifest.json').exists()
    (source/'long.mp4').unlink()
    subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=black:s=16x16:r=1',
                    '-t','1','-c:v','libx264','-pix_fmt','yuv420p',str(source/'short.mp4')],check=True)
    with wave.open(str(source/'long.wav'),'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000);wav.writeframes(b'\0'*(1048576+2))
    (source/'manifest.json').write_text(json.dumps({'families':[{'family':'idle','sourceFile':'short.mp4','audioPath':'long.wav'}]}))
    with pytest.raises(ValueError,match='1 MiB'):
        mod.prepare(source,tmp_path/'audio-output',ffmpeg)
    assert not (tmp_path/'audio-output/p4/manifest.json').exists()


def test_converter_accepts_partial_desktop_manifest_and_preserves_custom_audio(tmp_path):
    import importlib.util
    import json
    import os
    import shutil
    import wave
    import pytest
    ffmpeg=os.environ.get('S3_TEST_FFMPEG') or shutil.which('ffmpeg')
    if not ffmpeg:pytest.skip('set S3_TEST_FFMPEG to exercise desktop-source conversion')
    spec=importlib.util.spec_from_file_location('prepare_s3_assets',ROOT/'tools/prepare_s3_assets.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    data=tmp_path/'app-data';source=data/'custom-appearances/pet';source.mkdir(parents=True)
    subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=red:s=16x16:r=10',
                    '-t','1','-c:v','libx264','-pix_fmt','yuv420p',str(source/'one.mp4')],check=True)
    with wave.open(str(source/'cue.wav'),'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000);wav.writeframes(b'\0'*3200)
    manifest={'families':[{'family':'done','ok':True,'videoPath':'custom-appearances/pet/one.mp4',
                          'audioPath':'custom-appearances/pet/cue.wav','audioSource':'custom'},
                         {'family':'error','ok':False,'error':'not uploaded'}]}
    (source/'manifest.json').write_text(json.dumps(manifest))
    result=mod.prepare(source,tmp_path/'output',ffmpeg,app_data_dir=data)
    assert len(result['families'])==1
    assert result['families'][0]['family']=='done'
    assert result['families'][0]['audioSource']=='custom'
