"""Native I420 presentation must preserve pixels without scanning enlarged copies."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def function(source, signature):
    start = source.index(signature)
    end, depth = source.index('{', start) + 1, 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def run_c(tmp_path, source):
    path = tmp_path/'native_video.c'
    path.write_text(source,encoding='utf-8')
    binary = tmp_path/'native_video'
    subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
                    '-I',str(ROOT/'s3'),str(path),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)


def test_native_rows_keep_exact_bt709_background_and_letterboxes_with_bounded_work(tmp_path):
    source=(ROOT/'main/pet_p4_renderer.c').read_text(encoding='utf-8')
    helpers='\n'.join(function(source,s) for s in [
        'static bool asset_fit_layout(', 'static uint8_t clamp_u8(',
        'static void clear_framebuffer_outside_rect(', 'static void scale_h264_frame_cpu(',
    ])
    prelude=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "pet_s3_video_background.h"
#define CONFIG_IDF_TARGET_ESP32S3 1
#define PET_P4_UI_WIDTH 640
#define PET_P4_UI_HEIGHT 480
static uint16_t frame[640*480],expected[640*480];
static uint16_t *g_framebuffer=frame;
static uint8_t input[336*256*3/2];
static unsigned conversions,clean_pixels;
static size_t framebuffer_read_bytes;
static void *counted_memcpy(void *dst,const void *src,size_t bytes){
  uintptr_t address=(uintptr_t)src,begin=(uintptr_t)frame;
  if(address>=begin && address<begin+sizeof(frame))framebuffer_read_bytes+=bytes;
  return memcpy(dst,src,bytes);
}
#define memcpy counted_memcpy
static uint16_t rgb565(uint8_t r,uint8_t g,uint8_t b){conversions++;return ((r>>3)<<11)|((g>>2)<<5)|(b>>3);}
static void counted_clean(uint16_t *row,int width){clean_pixels+=(unsigned)width;pet_s3_clean_video_background(row,width);}
#define pet_s3_clean_video_background counted_clean
'''
    cases=r'''
#undef pet_s3_clean_video_background
#undef memcpy
static uint32_t seed=0x12345678;
static uint8_t random_byte(void){seed=seed*1664525U+1013904223U;return (uint8_t)(seed>>24);}
static void check(int w,int h,int stride,int storage_h,bool clean,bool dark){
  for(unsigned i=0;i<sizeof(input);i++)input[i]=random_byte();
  uint8_t *u=input+stride*storage_h,*v=u+stride*storage_h/4;
  if(dark){
    memset(u,128,(size_t)stride*storage_h/4);memset(v,128,(size_t)stride*storage_h/4);
    for(int y=0;y<h;y++)for(int x=0;x<w;x++)
      input[y*stride+x]=(uint8_t)((x<w/3||x>=2*w/3)?16+(x+y)%23:180);
    /* Dark foreground inside bright fur must survive edge-only cleaning. */
    for(int y=0;y<h;y++)input[y*stride+w/2]=28;
  }
  int x0,y0,dw,dh;assert(asset_fit_layout(w,h,&x0,&y0,&dw,&dh,NULL));
  memset(expected,0,sizeof(expected));
  for(int y=0;y<dh;y++){
    int sy=y*h/dh;
    for(int x=0;x<dw;x++){
      int sx=x*w/dw,luma=(int)input[sy*stride+sx]-16;
      int cb=(int)u[(sy/2)*(stride/2)+sx/2]-128,cr=(int)v[(sy/2)*(stride/2)+sx/2]-128;
      if(luma<0)luma=0;
      uint8_t r=clamp_u8((298*luma+459*cr+128)>>8);
      uint8_t g=clamp_u8((298*luma-55*cb-136*cr+128)>>8);
      uint8_t b=clamp_u8((298*luma+541*cb+128)>>8);
      expected[(y0+y)*640+x0+x]=(uint16_t)(((r>>3)<<11)|((g>>2)<<5)|(b>>3));
    }
    if(clean)pet_s3_clean_video_background(expected+(y0+y)*640+x0,dw);
  }
  memset(frame,0xa5,sizeof(frame));conversions=clean_pixels=0;framebuffer_read_bytes=0;
  scale_h264_frame_cpu(input,w,h,stride,storage_h,clean);
  assert(!memcmp(frame,expected,sizeof(frame)));
  assert(conversions<=(unsigned)(w*h));
  /* Native 2x copies contain no extra information: background work must stay
   * bounded by source pixels, rather than rescan their enlarged duplicates. */
  if(dw==2*w && dh==2*h){
    assert(clean_pixels<=(unsigned)(w*h));
    /* Duplicated logical rows must not round-trip through external memory. */
    assert(framebuffer_read_bytes==0);
  }
}
int main(void){
  for(int clean=0;clean<2;clean++)for(int dark=0;dark<2;dark++)for(int i=0;i<3;i++){
    check(320,240,320,240,clean,dark);check(320,240,336,256,clean,dark);
    check(320,200,336,208,clean,dark);check(200,240,208,256,clean,dark);
    check(319,240,320,256,clean,dark); /* unaligned letterbox destination */
    check(240,180,256,192,clean,dark);check(160,120,160,128,clean,dark);
  }
  puts("PASS exact native I420 pixels, padded storage, unaligned letterboxes, legacy sizes, dark edges, native cleanup bound and no framebuffer memcpy reads");
  return 0;
}
'''
    run_c(tmp_path,prelude+helpers+cases)
