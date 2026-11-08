"""Native-size artwork must preserve original layout and pass real runtime guards."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import zlib

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
TOOL = ROOT/'tools/prepare_s3_ui_assets.py'


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    out = tmp_path_factory.mktemp('native-ui')/'assets'
    result = subprocess.run([sys.executable,str(TOOL),'--output',str(out)],capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
    return out


def test_every_component_image_is_adapted_without_changing_controls(native):
    from PIL import Image
    inventory = json.loads((native/'inventory.json').read_text())
    ids = json.loads((ROOT/'factory-config.json').read_text())['components']['ids']
    excluded = json.loads((ROOT/'s3/component-policy.json').read_text())['unsupportedBuiltins']
    assert inventory['components'] == [i for i in ids if i not in excluded]
    count = 0
    for identifier in inventory['components']:
        original = REPO/'pc/builtin-clawpkgs'/identifier
        package = native/'packages'/identifier
        before = json.loads((original/'runtime/widget.json').read_text())
        after = json.loads((package/'runtime/widget.json').read_text())
        assert before.get('surface',{}).get('elements') == after.get('surface',{}).get('elements')
        assert before.get('surface',{}).get('fonts') == after.get('surface',{}).get('fonts')
        assert (original/'buttons.json').read_bytes() == (package/'buttons.json').read_bytes()
        a,b = dict(before),dict(after)
        if 'surface' in a:
            a['surface'] = dict(a['surface']);b['surface'] = dict(b['surface'])
            a['surface'].pop('images',None);b['surface'].pop('images',None)
        assert a == b
        for image in after.get('surface',{}).get('images',[]):
            adapted = Image.open(package/image['asset'])
            assert adapted.size == (image['frame_width'],image['frame_height'])
            if image.get('encoding') == 'jpeg':
                assert adapted.size == (320,240)
            count += 1
    assert count == len([i for i in inventory['images'] if i['role']=='component'])
    assert Image.open(native/'launcher/center_background.jpg').size == (320,240)
    thumbs = zlib.decompress((native/'launcher/center_thumbs.deflate').read_bytes())
    assert len(thumbs) == len(ids)*32*24*2
    for name,size in [('body',(160,122)),('mallet',(80,82))]:
        raw = zlib.decompress((native/f'instruments/wooden_fish_{name}.deflate').read_bytes())
        assert struct.unpack('<HH',raw[:4]) == size
        assert len(raw) == 4+size[0]*size[1]*3
        assert min(raw[6::3]) == 0
    for path,digest in inventory['sources'].items():
        assert hashlib.sha256((REPO/path).read_bytes()).hexdigest() == digest
    subprocess.run([sys.executable,str(TOOL),'--output',str(native),'--check'],check=True)


def test_native_images_and_layouts_pass_production_decoder(native,tmp_path):
    main = tmp_path/'native.c'
    main.write_text(r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "pet_p4_surface.h"
#include "pet_p4_image.h"
int main(int argc,char **argv){
  for(int i=1;i<argc;i++){
    FILE*f=fopen(argv[i],"rb");assert(f);fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);
    unsigned char *data=calloc(1,n+1);assert(data);assert(fread(data,1,n,f)==(size_t)n);fclose(f);
    if(n>4&&data[0]=='P'){
      assert(pet_image_decode(data,n,NULL,0));
      if(data[2]!='J'){
        unsigned char *indices=malloc(98305);indices[98304]=42;
        assert(pet_image_decode(data,n,indices,98304));assert(indices[98304]==42);free(indices);
      }
    }else{
      cJSON*j=cJSON_Parse((char*)data);assert(j);cJSON*s=cJSON_GetObjectItemCaseSensitive(j,"surface");
      if(s){pet_surface_t out;if(!pet_surface_parse(s,&out)){fprintf(stderr,"invalid native surface: %s\n",argv[i]);return 1;}}
      cJSON_Delete(j);
    }
    free(data);
  }return 0;
}
''')
    exe = tmp_path/'native'
    vendor = ROOT/'tests/vendor/cjson'
    subprocess.run(['cc','-std=c11','-fsanitize=address,undefined',
                    '-DCONFIG_IDF_TARGET_ESP32S3=1','-DPET_S3_LANDSCAPE_LEFT=1',
                    '-I',str(ROOT/'main'),'-I',str(vendor),str(main),
                    str(ROOT/'main/pet_p4_surface.c'),str(vendor/'cJSON.c'),'-lm','-o',str(exe)],check=True)
    paths = list((native/'packages').glob('*/runtime/widget.json'))+list((native/'surfaces').glob('*/*.p4i'))
    subprocess.run([str(exe),*map(str,paths)],check=True)


def test_native_jpeg_renderer_restores_exact_native_pixels(tmp_path):
    source = (ROOT/'main/pet_p4_renderer.c').read_text()
    from s3_official_input_test import function
    clip=function(source,'static bool app_clip_contains(')
    draw = clip+source[source.index('static void draw_surface_image('):source.index('static void load_surface_images(')]
    harness = tmp_path/'draw.c'
    harness.write_text(r'''
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "pet_p4_surface.h"
#include "pet_p4_miniapp.h"
#include "pet_p4_image.h"
#include "pet_s3_render.h"
static uint16_t fb[640*480],g_jpeg_output[640*480],native[320*240];
static uint16_t *g_framebuffer=fb;
static uint8_t input[100000];static uint8_t *g_jpeg_input=input;
static size_t g_jpeg_input_capacity=sizeof(input);
typedef int esp_err_t;
typedef int JRESULT;
static struct {bool active;int x,y,right,bottom;} g_app_clip;
static pet_p4_miniapp_sprite_pack_t g_surface_images;
static uint8_t g_surface_indices[PET_IMAGE_INDEX_CAPACITY],g_surface_alpha[4][256];
static uint16_t g_surface_colors[4][256];
static uint32_t g_surface_offsets[4];static uint64_t g_surface_play_ms;
static int jpeg_w=320,jpeg_h=240;
static bool decode_jpeg_frame_hardware(const uint8_t*p,size_t n,int*w,int*h,int*s,esp_err_t*err){
 (void)p;(void)n;(void)err;*w=jpeg_w;*h=jpeg_h;*s=jpeg_w;
 for(int i=0;i<jpeg_w*jpeg_h;i++)g_jpeg_output[i]=(uint16_t)(7+i*31);
 return true;
}
static bool decode_jpeg_frame_tjpgd(const uint8_t*p,size_t n,int*w,int*h,JRESULT*err){
 (void)p;(void)n;(void)w;(void)h;(void)err;assert(0);return false;
}
static uint16_t rgb565(unsigned r,unsigned g,unsigned b){return (r>>3)<<11|(g>>2)<<5|(b>>3);}
''' + draw + r'''
int main(void){
  g_surface_images.count=1;pet_p4_miniapp_sprite_t *im=&g_surface_images.items[0];
  im->frame_width=320;im->frame_height=240;im->data_length=41;
  uint8_t *p=g_surface_images.pixels;
  const uint8_t jpeg[]={255,216,255,192,0,17,8,0,240,1,64,3,1,17,0,2,17,1,3,17,1,255,218,0,2,255,217};
  im->data_length=12+sizeof(jpeg);memcpy(p,"P4J1",4);p[4]=64;p[5]=1;p[6]=240;
  p[8]=im->data_length;memcpy(p+12,jpeg,sizeof(jpeg));
  pet_surface_node_t n={.image=0,.w=640,.h=480};
  memset(fb,0xa5,sizeof(fb));draw_surface_image(&n);
  assert(pet_s3_scale_rgb565(fb,640,480,640,native,320,240));
  for(int i=0;i<320*240;i++)assert(native[i]==(uint16_t)(7+i*31));
  /* Legacy full-size resources still render without repacking. */
  jpeg_w=640;jpeg_h=480;im->frame_width=640;im->frame_height=480;
  p[4]=128;p[5]=2;p[6]=224;p[7]=1;p[19]=1;p[20]=224;p[21]=2;p[22]=128;
  draw_surface_image(&n);
  for(int i=0;i<640*480;i++)assert(fb[i]==(uint16_t)(7+i*31));
  return 0;
}
''')
    exe = tmp_path/'draw'
    (tmp_path/'esp_err.h').write_text('typedef int esp_err_t;\n')
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
                    '-DCONFIG_IDF_TARGET_ESP32S3=1','-DPET_S3_LANDSCAPE_LEFT=1',
                    '-I',str(tmp_path),'-I',str(ROOT/'main'),'-I',str(ROOT/'s3'),
                    '-I',str(ROOT/'tests/vendor/cjson'),str(harness),'-lm','-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
