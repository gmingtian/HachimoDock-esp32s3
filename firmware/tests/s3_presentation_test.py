"""Exercise production presentation code: exact pixels, partial rows and DMA ownership."""
from pathlib import Path
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]


def run_c(tmp_path, name, source):
    path = tmp_path / f'{name}.c'
    path.write_text(source)
    binary = tmp_path / name
    subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-I', str(ROOT/'s3'),
                    str(path), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)


def function(source, signature):
    start = source.index(signature)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def test_full_frame_scaling_preserves_pixels_without_redundant_clear(tmp_path):
    # Regression: clearing a fully overwritten output adds one framebuffer write.
    run_c(tmp_path, 'scale', r'''
#include <assert.h>
#include <string.h>
#include <stdint.h>
static size_t cleared;
static void *counted_clear(void *p,int c,size_t n) {
  cleared+=n;return memset(p,c,n);
}
#define memset counted_clear
#include "pet_s3_render.h"
#undef memset
int main(void) {
  const uint16_t padded[]={1,2,3,4,99,5,6,7,8,99,9,10,11,12,99,13,14,15,16,99};
  uint16_t out[8];
  assert(pet_s3_scale_rgb565(padded,4,4,5,out,2,2));
  const uint16_t half[]={1,3,9,11};
  assert(!memcmp(out,half,sizeof(half)));
  assert(cleared==0);
  assert(pet_s3_scale_rgb565(padded,4,4,5,out,2,4));
  const uint16_t bars[]={0,0,1,3,9,11,0,0};
  assert(!memcmp(out,bars,sizeof(bars)));
  static uint16_t large[648*480],small[320*240];
  for(unsigned i=0;i<648*480;i++)large[i]=(uint16_t)(i*31+7);
  cleared=0;
  assert(pet_s3_scale_rgb565(large,640,480,648,small,320,240));
  assert(cleared==0);
  for(int y=0;y<240;y++)for(int x=0;x<320;x++)
    assert(small[y*320+x]==large[y*2*648+x*2]);
  assert(!pet_s3_scale_rgb565(padded,4,4,3,out,2,2));
  assert(!pet_s3_scale_rgb565(padded,4,4,5,out,0,2));
  return 0;
}
''')


def test_changed_rows_reconstruct_exact_screen_and_recover_after_failure(tmp_path):
    # A missed edge row or using an invalid reference would leave stale LCD pixels.
    run_c(tmp_path, 'rows', r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "pet_s3_render.h"
static uint16_t previous[8*6],next[8*6],screen[8*6];
static unsigned random_state=421;
int main(void) {
  pet_s3_rect_t r;
  assert(pet_s3_changed_rows(next,previous,8,6,false,&r));
  assert(r.x==0 && r.y==0 && r.width==8 && r.height==6);
  assert(!pet_s3_changed_rows(next,previous,8,6,true,&r));
  next[2*8+3]=7;next[3*8+6]=9;
  assert(pet_s3_changed_rows(next,previous,8,6,true,&r));
  assert(r.x==0 && r.y==2 && r.width==8 && r.height==2);
  memcpy(screen+r.y*8,next+r.y*8,r.height*8*sizeof(uint16_t));
  assert(!memcmp(screen,next,sizeof(next)));
  /* A failed write invalidates the reference: force a complete recovery. */
  assert(pet_s3_changed_rows(next,previous,8,6,false,&r));
  assert(r.y==0 && r.height==6);
  memcpy(previous,next,sizeof(next));
  next[0]=1;next[47]=2;
  assert(pet_s3_changed_rows(next,previous,8,6,true,&r));
  assert(r.y==0 && r.height==6);
  assert(pet_s3_changed_rows(next,NULL,8,6,true,&r));
  assert(r.height==6);
  assert(pet_s3_changed_rows(next,next,8,6,true,&r));
  assert(r.height==6);
  assert(!pet_s3_changed_rows(NULL,previous,8,6,true,&r));
  assert(!pet_s3_changed_rows(next,previous,0,6,true,&r));
  assert(!pet_s3_changed_rows(next,previous,8,6,true,NULL));
  /* Successive alternating framebuffers, including repeated and single-row changes. */
  memcpy(previous,next,sizeof(next));memcpy(screen,next,sizeof(next));
  for(int iteration=0;iteration<1000;iteration++) {
    memcpy(next,previous,sizeof(next));
    for(int k=0;k<iteration%7;k++) {
      random_state=random_state*1664525U+1013904223U;
      next[(random_state>>8)%48]^=(uint16_t)random_state;
    }
    if(pet_s3_changed_rows(next,previous,8,6,true,&r))
      memcpy(screen+r.y*8,next+r.y*8,r.height*8*sizeof(uint16_t));
    assert(!memcmp(screen,next,sizeof(next)));
    memcpy(previous,next,sizeof(next));
  }
  return 0;
}
''')


@pytest.mark.parametrize('panel_width', [240, 320])
def test_lcd_prepares_next_stripe_during_dma_and_returns_with_no_pending_work(tmp_path, panel_width):
    # Fake only FreeRTOS/SPI hardware; execute the production callback/draw loop.
    # DMA retains the pointer until completion, so overwriting it is detectable.
    lcd = (ROOT/'s3/pet_s3_lcd.inc').read_text()
    globals_ = lcd[lcd.index('static const char *TAG'):lcd.index('static bool IRAM_ATTR')]
    production = globals_ + '\n' + function(lcd, 'static bool IRAM_ATTR pet_s3_lcd_done(')
    production += '\n' + function(lcd, 'esp_err_t pet_p4_lcd_draw_rgb565(')
    run_c(tmp_path, 'dma', r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
typedef int esp_err_t;
typedef int BaseType_t;
typedef void *esp_lcd_panel_handle_t;
typedef void *esp_lcd_panel_io_handle_t;
typedef void *SemaphoreHandle_t;
typedef struct {int unused;} esp_lcd_panel_io_event_data_t;
#define ESP_OK 0
#define ESP_ERR_INVALID_STATE 1
#define ESP_ERR_INVALID_ARG 2
#define IRAM_ATTR
#define pdFALSE 0
#define pdTRUE 1
#define portMAX_DELAY 100
#define PET_S3_LCD_WIDTH 320
#define PET_S3_LCD_HEIGHT 240
static int xSemaphoreTake(SemaphoreHandle_t,int);
static int xSemaphoreGive(SemaphoreHandle_t);
static void xSemaphoreGiveFromISR(SemaphoreHandle_t,BaseType_t*);
static int esp_lcd_panel_draw_bitmap(void*,int,int,int,int,const void*);
/* PRODUCTION */
static uint16_t pixels[320*240],screen[320*240],snapshot[320*16];
static const uint16_t *pending;
static int signal_count,py,px,pw,ph,calls,fail_at,overlaps,prepared_y;
static uint16_t swap(uint16_t v){return (uint16_t)((v>>8)|(v<<8));}
static int xSemaphoreTake(SemaphoreHandle_t sem,int wait) {
  if(sem==g_draw_lock)return pdTRUE;
  if(wait && pending) {
    assert(!memcmp(pending,snapshot,(size_t)pw*ph*2));
    /* Before waiting for a stripe, the other buffer should already hold the next. */
    if(prepared_y>=0 && py+ph<prepared_y) {
      const uint16_t *other=pending==g_stripe?g_stripe+320*16:g_stripe;
      if(other[0]==swap(pixels[(py+ph)*320+px]))overlaps++;
    }
    for(int y=0;y<ph;y++)for(int x=0;x<pw;x++)
      screen[(py+y)*320+px+x]=swap(pending[y*pw+x]);
    pending=NULL;
    pet_s3_lcd_done(g_io,NULL,g_transfer_done);
  }
  if(signal_count){signal_count--;return pdTRUE;}
  assert(!wait);return pdFALSE;
}
static int xSemaphoreGive(SemaphoreHandle_t sem){assert(sem==g_draw_lock);return pdTRUE;}
static void xSemaphoreGiveFromISR(SemaphoreHandle_t sem,BaseType_t *wake){
  assert(sem==g_transfer_done);assert(!signal_count);signal_count++;*wake=pdFALSE;
}
static int esp_lcd_panel_draw_bitmap(void *panel,int x,int y,int x1,int y1,const void *p){
  assert(panel==g_panel && !pending);
  if(++calls==fail_at)return ESP_ERR_INVALID_STATE;
  px=x;py=y;pw=x1-x;ph=y1-y;
  assert(pw>0 && ph>0 && ph<=16);
  pending=p;memcpy(snapshot,p,(size_t)pw*ph*2);return ESP_OK;
}
int main(void) {
  /* Touch other production globals to keep strict host warnings meaningful. */
  (void)TAG;(void)g_backlight_status;(void)g_revealed;
  g_panel=(void*)1;g_io=(void*)2;g_draw_lock=(void*)3;g_transfer_done=(void*)4;
  g_stripe=calloc(320*16*2,sizeof(uint16_t));assert(g_stripe);
  for(int i=0;i<320*240;i++)pixels[i]=(uint16_t)(i*13+1);
  prepared_y=240;
  assert(pet_p4_lcd_draw_rgb565(0,0,320,240,pixels)==ESP_OK);
  assert(!pending && !signal_count);
  assert(!memcmp(screen,pixels,sizeof(screen)));
  assert(overlaps==14);
  /* Non-full-width, odd sizes, offsets and a final partial stripe. */
  memset(screen,0,sizeof(screen));prepared_y=-1;
  assert(pet_p4_lcd_draw_rgb565(5,7,13,35,pixels)==ESP_OK);
  for(int y=0;y<35;y++)for(int x=0;x<13;x++)
    assert(screen[(y+7)*320+x+5]==pixels[y*13+x]);
  /* Boundary sizes: one pixel/row, exactly one stripe, and two full stripes. */
  for(int height=1;height<=32;height++) {
    assert(pet_p4_lcd_draw_rgb565(0,0,1,height,pixels)==ESP_OK);
    assert(!pending && !signal_count);
    for(int y=0;y<height;y++)assert(screen[y*320]==pixels[y]);
  }
  for(int failed=1;failed<=3;failed++) {
    calls=0;fail_at=failed;
    assert(pet_p4_lcd_draw_rgb565(0,0,320,35,pixels)==ESP_ERR_INVALID_STATE);
    assert(!pending && !signal_count);
    fail_at=0;
    assert(pet_p4_lcd_draw_rgb565(0,0,320,35,pixels)==ESP_OK);
    assert(!pending && !signal_count);
  }
  calls=0;
  assert(pet_p4_lcd_draw_rgb565(319,0,2,1,pixels)==ESP_ERR_INVALID_ARG);
  assert(pet_p4_lcd_draw_rgb565(0,0,0,1,pixels)==ESP_ERR_INVALID_ARG);
  assert(pet_p4_lcd_draw_rgb565(0,0,1,1,NULL)==ESP_ERR_INVALID_ARG);
  assert(calls==0);free(g_stripe);return 0;
}
'''.replace('/* PRODUCTION */', production).replace('320', str(panel_width))
     .replace('319,0,2,1', f'{panel_width-1},0,2,1'))
