"""Compare real incremental center drawing against its full repaint, pixel for pixel."""
from pathlib import Path
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def function(source, signature):
    start = source.index(signature)
    brace = source.index('{', start)
    end, depth = brace + 1, 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def test_real_center_reuses_clean_frames_and_repaints_exact_card_regions(tmp_path):
    source = (ROOT / 'main/pet_p4_renderer.c').read_text()
    primitives = '\n'.join(function(source, name) for name in [
        'static uint16_t rgb565(', 'static bool app_clip_contains(',
        'static void put_px(', 'static void fill_rect(', 'static void fill_ellipse(',
        'static void draw_line(', 'static void fill_round_rect(', 'static void fill_round_rect_outline(',
    ])
    prelude = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CONFIG_IDF_TARGET_ESP32S3 1
#define PET_S3_LANDSCAPE_LEFT 1
#define PET_S3_NATIVE_HOME 0
#define PET_P4_UI_WIDTH 640
#define PET_P4_UI_HEIGHT 480
typedef struct {char widget_id[48],title[64];bool active;uint8_t resource_state,image_count;} pet_p4_miniapp_catalog_entry_t;
#include "pet_s3_center_cache.h"
static uint16_t pixels[640*480],expected[640*480],background_pixels[640*480];
static uint16_t *g_framebuffer=pixels,*center_background;
static struct {bool active;int x,y,right,bottom;} g_app_clip;
static pet_s3_center_snapshot_t g_s3_center_cache;
static bool g_s3_center_may_retain,g_s3_center_unchanged;
static size_t count,selected;
static int missing=-1,text_calls;
static bool thumbnails;
static pet_p4_miniapp_catalog_entry_t catalog[28];
static size_t pet_p4_miniapp_catalog_count(void){return count;}
static size_t pet_p4_miniapp_catalog_selected(void){return selected;}
static bool pet_p4_miniapp_catalog_get(size_t i,pet_p4_miniapp_catalog_entry_t *out){
  memset(out,0,sizeof(*out));if(i>=count||(int)i==missing)return false;*out=catalog[i];return true;
}
static void center_art_prepare(void){}
'''
    text = r'''
/* Raster helpers below are production code. Text/thumbnail sources use bounded
 * deterministic patterns, so transparent glyphs and corner underlays are observable. */
static int text_y_in_box(const char *s,int scale,int y,int h){(void)s;return y+(h-8*scale)/2;}
static void draw_text_line(const char *s,int x,int y,int max,uint16_t color,int scale,bool clip){
  (void)clip;text_calls++;int n=(int)strlen(s)*3*scale;if(n>max)n=max;
  for(int yy=0;yy<8*scale;yy++)for(int xx=0;xx<n;xx++)
    if((xx+yy+(unsigned char)s[0])%3)put_px(x+xx,y+yy,color);
}
static void draw_text_center(const char *s,int x,int y,int max,uint16_t color,int scale){
  int n=(int)strlen(s)*3*scale;if(n>max)n=max;draw_text_line(s,x-n/2,y,max,color,scale,true);
}
static void draw_text_right(const char *s,int x,int y,int max,uint16_t color,int scale){
  int n=(int)strlen(s)*3*scale;if(n>max)n=max;draw_text_line(s,x-n,y,max,color,scale,true);
}
static const char *component_card_caption(const char *id){return id;}
static void draw_component_icon(const char *id,int x,int y,uint16_t ink,uint16_t tile){
  fill_round_rect(x,y,64,48,7,tile);draw_line(x,y,x+25+(int)strlen(id),y+28,ink);
}
static bool center_draw_thumbnail(const char *id,int x,int y){
  if(!thumbnails)return false;draw_component_icon(id,x,y,0x1234,0xabcd);return true;
}
'''
    cases = r'''
static void check(bool retain,bool loading,bool expect_clean){
  g_s3_center_may_retain=retain;g_s3_center_unchanged=false;text_calls=0;
  render_component_center_page(loading);int incremental=text_calls;
  if(expect_clean){assert(g_s3_center_unchanged);assert(incremental==0);}
  memcpy(expected,pixels,sizeof(pixels));pet_s3_center_snapshot_t saved=g_s3_center_cache;
  memset(pixels,0xa5,sizeof(pixels));g_s3_center_may_retain=false;g_s3_center_unchanged=false;
  text_calls=0;render_component_center_page(loading);assert(!memcmp(expected,pixels,sizeof(pixels)));
  assert(incremental<=text_calls);g_s3_center_cache=saved;
}
int main(void){
  /* Independent geometric oracle for the production span rasterizer, including
   * degenerate ellipses, framebuffer clipping and active widget clipping. */
  for(int clip=0;clip<2;clip++)for(int rx=0;rx<=24;rx++)for(int ry=0;ry<=24;ry++){
    const int cx=rx%3?20:-3,cy=ry%3?22:-2;
    memset(pixels,0,sizeof(pixels));g_app_clip.active=clip;
    g_app_clip.x=4;g_app_clip.y=5;g_app_clip.right=35;g_app_clip.bottom=36;
    fill_ellipse(cx,cy,rx,ry,0xabcd);
    for(int y=0;y<55;y++)for(int x=0;x<55;x++){
      long long dx=x-cx,dy=y-cy;
      bool member=dx>=-rx&&dx<=rx&&dy>=-ry&&dy<=ry
        &&dx*dx*(long long)ry*ry+dy*dy*(long long)rx*rx<=(long long)rx*rx*ry*ry;
      if(clip)member=member&&x>=4&&x<35&&y>=5&&y<36;
      assert(pixels[y*640+x]==(member?0xabcd:0));
    }
  }
  g_app_clip.active=false;
  for(size_t i=0;i<28;i++){snprintf(catalog[i].widget_id,48,"item-%zu",i);snprintf(catalog[i].title,64,"Title-%zu",i);}
  for(int bg=0;bg<2;bg++)for(int art=0;art<2;art++){
    for(size_t i=0;i<640*480;i++)background_pixels[i]=(uint16_t)(i*17+bg);
    center_background=bg?background_pixels:NULL;thumbnails=art;
    for(size_t n=0;n<=28;n++){
      count=n;selected=0;g_s3_center_cache.valid=false;check(false,false,false);check(true,false,true);
      for(size_t i=0;i<n;i++){
        selected=i;check(true,false,false);check(true,false,true);
        catalog[i].active=!catalog[i].active;check(true,false,false);
        catalog[i].title[0]^=1;check(true,false,false);
        catalog[i].widget_id[0]^=1;check(true,false,false);
        catalog[i].resource_state++;catalog[i].image_count++;check(true,false,false);
      }
      selected=0;check(true,true,false);check(true,true,true);check(true,false,false);
      /* A page change, modal overlay, failed LCD write or invalid previous
       * framebuffer forbids retention, even when the metadata is identical. */
      memset(pixels,0x6b,sizeof(pixels));check(false,false,false);check(true,false,true);
      if(n){missing=0;check(true,false,false);assert(!g_s3_center_cache.valid);missing=-1;check(true,false,false);}
    }
  }
  puts("PASS pixel-exact center retain/card/full repaint; 0..28 items, paging, titles, active state, loading, missing entries and underlay recovery");
  return 0;
}
'''
    harness = tmp_path / 'center.c'
    harness.write_text(prelude + primitives + text + function(source, 'static void render_component_center_page(') + cases, encoding='utf-8')
    compiler = shutil.which('cc') or shutil.which('gcc')
    assert compiler, 'C compiler required'
    exe = tmp_path / ('center.exe' if os.name == 'nt' else 'center')
    flags = [] if os.name == 'nt' else ['-fsanitize=address,undefined']
    subprocess.run([compiler,'-std=c11','-O2','-Wall','-Werror','-Wno-misleading-indentation',*flags,
                    '-I',str(ROOT/'s3'),'-I',str(ROOT/'main'),str(harness),'-o',str(exe)],check=True)
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0')
    subprocess.run([str(exe)],check=True,env=env)


def test_center_retention_is_scoped_to_a_successful_unobscured_previous_page():
    source = (ROOT/'main/pet_p4_renderer.c').read_text()
    frame = function(source,'esp_err_t pet_p4_renderer_render(')
    gate = frame.split('g_s3_center_may_retain=',1)[1].split(';',1)[0]
    for token in ['previous_valid','g_last_render_page','components','!approval_visible','!approval_changed','!realtime_changed']:
        assert token in gate
    assert 'g_s3_center_unchanged=false;' in frame
    assert 'g_native_framebuffer_index=previous_native_index;' in frame
    assert 'g_s3_center_unchanged ||' in frame
    assert 'g_s3_center_cache.valid=false;' in function(source,'static void center_art_release(')
