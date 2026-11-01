"""Pixel-equivalence and work bounds for the real software H264 presentation path."""
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def implementation(source, signature):
    start = source.index(signature)
    brace = source.index('{', start)
    end, depth = brace + 1, 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


@pytest.mark.parametrize('s3', [0, 1])
def test_h264_scaling_preserves_pixels_without_reconverting_enlarged_pixels(tmp_path, s3):
    source = (ROOT / 'main/pet_p4_renderer.c').read_text()
    functions = '\n'.join(implementation(source, signature) for signature in [
        'static bool asset_fit_layout(', 'static uint8_t clamp_u8(',
        'static void clear_framebuffer_outside_rect(',
        'static void scale_h264_frame_cpu(',
    ])
    harness = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define PET_P4_UI_WIDTH 640
#define PET_P4_UI_HEIGHT 480
static uint16_t frame[640*480], expected[640*480];
static uint16_t *g_framebuffer=frame;
static uint8_t input[336*240*3/2];
static unsigned conversions;
static uint16_t rgb565(uint8_t r,uint8_t g,uint8_t b) {
  conversions++; return ((r>>3)<<11)|((g>>2)<<5)|(b>>3);
}
/* IMPLEMENTATION */
static uint32_t random_state=12345;
static uint8_t random_byte(void) {
  random_state=random_state*1664525U+1013904223U;return random_state>>24;
}
static void check(int w,int h,int stride,int storage_h,bool clean) {
  for(unsigned i=0;i<sizeof(input);i++)input[i]=random_byte();
  int x0,y0,dw,dh;
  assert(asset_fit_layout(w,h,&x0,&y0,&dw,&dh,NULL));
  const uint8_t *u=input+stride*storage_h,*v=u+stride*storage_h/4;
  memset(expected,0,sizeof(expected));
  for(int y=0;y<dh;y++)for(int x=0;x<dw;x++) {
    int sx=x*w/dw,sy=y*h/dh;
    int luma=input[sy*stride+sx]-16;
    if(luma<0)luma=0;
    int cb=u[sy/2*(stride/2)+sx/2]-128,cr=v[sy/2*(stride/2)+sx/2]-128;
    uint8_t r=clamp_u8((298*luma+459*cr+128)>>8);
    uint8_t g=clamp_u8((298*luma-55*cb-136*cr+128)>>8);
    uint8_t b=clamp_u8((298*luma+541*cb+128)>>8);
    uint16_t color=rgb565(r,g,b);
#if CONFIG_IDF_TARGET_ESP32S3
    if(clean&&r<=12&&g<=12&&b<=12)color=0;
#endif
    expected[(y0+y)*640+x0+x]=color;
  }
  memset(frame,0xa5,sizeof(frame));conversions=0;
  scale_h264_frame_cpu(input,w,h,stride,storage_h,clean);
  assert(!memcmp(frame,expected,sizeof(frame)));
#if CONFIG_IDF_TARGET_ESP32S3
  /* Work is bounded by sampled source pixels, not enlarged logical pixels. */
  assert(conversions<=(unsigned)(w*h));
#endif
  printf("source=%dx%d stride=%d storage=%d conversions=%u logical=%d\n",
         w,h,stride,storage_h,conversions,dw*dh);
}
static void check_idle_black(void) {
  memset(input,20,16*16);
  memset(input+16*16,126,16*16/4);
  memset(input+16*16*5/4,128,16*16/4);
  scale_h264_frame_cpu(input,16,16,16,16,false);
  assert(frame[240*640+320]!=0);
  scale_h264_frame_cpu(input,16,16,16,16,true);
#if CONFIG_IDF_TARGET_ESP32S3
  /* Literal decoded background from the bundled idle assets, formerly 0x20. */
  assert(frame[240*640+320]==0);
#else
  assert(frame[240*640+320]!=0);
#endif
}
int main(void) {
  check(320,240,320,240,false);
  check(320,240,336,240,false);
  check(320,240,320,240,true);
  check(240,180,240,192,false);
  check(240,180,256,192,false);
  check(160,120,160,128,false);
  check(32,64,48,64,false);
  check(17,19,32,32,false);
  check(2,2,16,16,false);
  memset(frame,0xa5,sizeof(frame));
  scale_h264_frame_cpu(NULL,240,180,240,192,false);
  assert(frame[0]==0xa5a5);
  scale_h264_frame_cpu(input,240,180,16,192,false);
  assert(frame[0]==0xa5a5);
  clear_framebuffer_outside_rect(-1,0,10,10);
  for(unsigned i=0;i<640*480;i++)assert(frame[i]==0);
  check_idle_black();
  return 0;
}
'''
    test = tmp_path / 'video.c'
    test.write_text(harness.replace('/* IMPLEMENTATION */', functions))
    binary = tmp_path / 'video'
    subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', f'-DCONFIG_IDF_TARGET_ESP32S3={s3}',
                    str(test), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
