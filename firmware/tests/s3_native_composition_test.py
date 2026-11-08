"""Production native-home primitives/conversion equal the old final sample."""
from pathlib import Path
import subprocess
from s3_native_video_row_test import function
ROOT=Path(__file__).resolve().parents[1]

def run_c(tmp_path,code):
    src=tmp_path/'native_composition.c';src.write_text(code,encoding='utf-8');exe=tmp_path/'native_composition'
    subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
                    '-I',str(ROOT/'s3'),str(src),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

def test_native_home_matches_sampled_logical_without_touching_logical_asset_canvas(tmp_path):
    source=(ROOT/'main/pet_p4_renderer.c').read_text(encoding='utf-8')
    helpers='\n'.join(function(source[source.rindex(s):],s) for s in ['static uint16_t blend_rgb565(',
      'static void put_px(', 'static void fill_rect(', 'static void blend_px(', 'static void blend_rect(',
      'static bool asset_fit_layout(', 'static uint8_t clamp_u8(',
      'static void clear_framebuffer_outside_rect(', 'static void scale_h264_frame_cpu('])
    header='#include "pet_s3_compositor.h"\n#include "pet_s3_yuv_rgb565.h"\n#include "pet_s3_black_matte.h"\nstatic pet_s3_black_matte_t *g_s3_native_matte_work;\n' if (ROOT/'s3/pet_s3_compositor.h').exists() else ''
    code=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "pet_s3_video_background.h"
#define CONFIG_IDF_TARGET_ESP32S3 1
#define PET_S3_NATIVE_COMPOSITION 1
#define PET_P4_UI_WIDTH 640
#define PET_P4_UI_HEIGHT 480
static uint16_t logical[640*480+2],output[320*240+2],asset[320*240+2],expected[320*240];
static uint16_t *g_framebuffer=logical+1,*g_native_framebuffer=output+1,*g_s3_native_asset=asset+1;
static bool g_s3_native_composing,g_s3_native_asset_written;
static bool g_s3_native_builtin_matte,g_s3_native_matte_applied,g_s3_logical_asset_written;
static struct{bool active;int x,y,right,bottom;}g_app_clip;
static bool app_clip_contains(int x,int y){return !g_app_clip.active||(x>=g_app_clip.x&&y>=g_app_clip.y&&x<g_app_clip.right&&y<g_app_clip.bottom);}
static uint16_t rgb565(uint8_t r,uint8_t g,uint8_t b){return ((r>>3)<<11)|((g>>2)<<5)|(b>>3);}
'''+header+helpers+r'''
static uint32_t seed=0x12345678;
static uint32_t rnd(void){seed=seed*1664525U+1013904223U;return seed;}
static void draw_ops(void){
  for(int i=0;i<200;i++){
    int x=(int)(rnd()%720)-40,y=(int)(rnd()%560)-40,w=(int)(rnd()%80),h=(int)(rnd()%70);
    uint8_t r=rnd()>>24,g=rnd()>>24,b=rnd()>>24,a=rnd()>>24;
    put_px(x,y,rgb565(r,g,b));fill_rect(x+1,y-1,w,h,rgb565(b,r,g));
    blend_px(x+2,y+2,r,g,b,a);blend_rect(x-1,y+1,w,h,r,g,b,a);
  }
}
static void primitives(bool clip){
  g_app_clip.active=clip;g_app_clip.x=7;g_app_clip.y=11;g_app_clip.right=631;g_app_clip.bottom=471;
  memset(logical,0xa5,sizeof(logical));memset(output,0xa5,sizeof(output));
  for(int y=0;y<240;y++)for(int x=0;x<320;x++)g_native_framebuffer[y*320+x]=g_framebuffer[(2*y)*640+2*x];
  seed=42;g_s3_native_composing=false;draw_ops();
  for(int y=0;y<240;y++)for(int x=0;x<320;x++)expected[y*320+x]=g_framebuffer[(2*y)*640+2*x];
  memset(logical,0xa5,sizeof(logical));
  seed=42;g_s3_native_composing=true;draw_ops();
  assert(!memcmp(expected,g_native_framebuffer,sizeof(expected)));
  for(unsigned i=0;i<640*480+2;i++)assert(logical[i]==0xa5a5);
  assert(output[0]==0xa5a5&&output[320*240+1]==0xa5a5);
  g_app_clip.active=false;
}
static uint8_t input[336*256*3/2];
static void convert(int w,int h,int stride,int storage_h,bool clean){
  for(unsigned i=0;i<sizeof(input);i++)input[i]=(uint8_t)(rnd()>>24);
  /* Exercise near-black neutral edges with visible foreground. */
  if(clean){
    memset(input+stride*storage_h,128,(size_t)stride*storage_h/2);
    for(int y=0;y<h;y++)for(int x=0;x<w;x++)input[y*stride+x]=(x<w/3||x>=2*w/3)?20:180;
  }
  memset(logical,0xa5,sizeof(logical));g_s3_native_composing=false;
  scale_h264_frame_cpu(input,w,h,stride,storage_h,clean);
  for(int y=0;y<240;y++)for(int x=0;x<320;x++)expected[y*320+x]=g_framebuffer[(2*y)*640+2*x];
  memset(logical,0xa5,sizeof(logical));memset(asset,0xa5,sizeof(asset));
  g_s3_native_composing=true;g_s3_native_asset_written=false;
  scale_h264_frame_cpu(input,w,h,stride,storage_h,clean);
  assert(g_s3_native_asset_written);
  assert(!memcmp(expected,g_s3_native_asset,sizeof(expected)));
  for(unsigned i=0;i<640*480+2;i++)assert(logical[i]==0xa5a5);
  assert(asset[0]==0xa5a5&&asset[320*240+1]==0xa5a5);
}
static void builtin_layer(void){
  static pet_s3_black_matte_t work;g_s3_native_matte_work=&work;
  memset(input,16,320*240);memset(input+320*240,128,320*240/2);
  /* Authored dark floor and prop shadow must keep the pre-trial appearance. */
  for(int y=170;y<210;y++)for(int x=20;x<300;x++)input[y*320+x]=42;
  for(int y=20;y<220;y++)for(int x=110;x<210;x++)input[y*320+x]=180;
  for(int y=80;y<160;y++)input[y*320+160]=28;
  g_s3_native_composing=false;
  scale_h264_frame_cpu(input,320,240,320,240,true);
  for(int y=0;y<240;y++)for(int x=0;x<320;x++)expected[y*320+x]=g_framebuffer[(2*y)*640+2*x];
  assert(expected[190*320+30]!=0);
  memset(logical,0xa5,sizeof(logical));
  g_s3_native_composing=true;
  g_s3_native_builtin_matte=true;g_s3_native_matte_applied=false;
  scale_h264_frame_cpu(input,320,240,320,240,true);
  assert(g_s3_native_matte_applied);
  assert(g_s3_native_asset[190*320+30]==0); /* factory matte requested again */
  for(int y=0;y<240;y++){
    assert(g_s3_native_asset[y*320]==0&&g_s3_native_asset[y*320+319]==0);
    if(y>=20&&y<220)assert(g_s3_native_asset[y*320+120]!=0);
    if(y>=80&&y<160)assert(g_s3_native_asset[y*320+160]!=0);
  }
  for(unsigned i=0;i<640*480+2;i++)assert(logical[i]==0xa5a5);
  g_s3_native_builtin_matte=false;g_s3_native_matte_work=NULL;
}
int main(void){
  primitives(false);primitives(true);
  for(int clean=0;clean<2;clean++){
    convert(320,240,320,240,clean);convert(320,240,336,256,clean);
    convert(320,200,336,208,clean);convert(200,240,208,256,clean);
    convert(319,240,320,256,clean);
    convert(320,239,336,256,clean);
  }
  builtin_layer();
  puts("PASS native composition pixels, clipped primitives, alpha, guarded buffers, native I420 and untouched logical canvas");
}
'''
    run_c(tmp_path,code)
    run_c(tmp_path,'''
#include <stdbool.h>
#define PET_P4_RASTER_EXACT 1
#define PET_P4_ALPHA_FAST 1
#define PET_P4_RENDER_SPAN_FILL 1
#include "../main/pet_p4_rgb565_blend.h"
#include "../main/pet_p4_rgb565_span.h"
static pet_rgb565_blend_t g_blend_lookup;
'''+code)
