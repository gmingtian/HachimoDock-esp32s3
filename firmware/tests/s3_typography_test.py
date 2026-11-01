"""Run production text measuring, clipping and raster paths for both profiles."""
from pathlib import Path
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]

PREFIX = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
#define PET_P4_UI_HEIGHT 480
#define LV_FONT_GLYPH_FORMAT_A8 8
#define LV_FONT_GLYPH_FORMAT_A4 4
#define LV_FONT_GLYPH_FORMAT_A2 2
#define LV_FONT_GLYPH_FORMAT_A1 1
typedef struct font font;
typedef struct {int adv_w,box_w,box_h,ofs_x,ofs_y,req_raw_bitmap,format,stride; const font *resolved_font;} lv_font_glyph_dsc_t;
struct font {int line_height,base_line; const uint8_t *(*get_glyph_bitmap)(lv_font_glyph_dsc_t*,void*);};
static int stroke_x=-1,stroke_y=-1;
static const uint8_t *bitmap(lv_font_glyph_dsc_t*g,void*b){(void)g;(void)b;static uint8_t p[256];
 for(int y=0;y<16;y++){for(int x=0;x<16;x++){p[y*16+x]=(stroke_x<0||x==stroke_x)&&(stroke_y<0||y==stroke_y)?255:0;}}
 return p;}
static const font pet_p4_font_cn_16={16,0,bitmap};
static bool lv_font_get_glyph_dsc(const font*f,lv_font_glyph_dsc_t*g,uint32_t cp,uint32_t next){(void)cp;(void)next;*g=(lv_font_glyph_dsc_t){.adv_w=16,.box_w=16,.box_h=16,.format=8,.resolved_font=f};return true;}
static void lv_font_glyph_release_draw_data(lv_font_glyph_dsc_t*g){(void)g;}
static int pixels,min_x,min_y,max_x,max_y;
static unsigned char frame[480][640];
static void reset(void){memset(frame,0,sizeof(frame));pixels=0;min_x=min_y=9999;max_x=max_y=-9999;}
static void blend_px(int x,int y,int r,int g,int b,int a){(void)r;(void)g;(void)b;assert(a>0);if(x>=0&&x<640&&y>=0&&y<480)frame[y][x]=(unsigned char)a;pixels++;if(x<min_x)min_x=x;if(x>max_x)max_x=x;if(y<min_y)min_y=y;if(y>max_y)max_y=y;}
static void fill_ellipse(int x,int y,int rx,int ry,uint16_t c){(void)x;(void)y;(void)rx;(void)ry;(void)c;assert(0);}
static void draw_line(int x,int y,int xx,int yy,uint16_t c){(void)x;(void)y;(void)xx;(void)yy;(void)c;assert(0);}
static void draw_glyph5x7(int x,int y,char ch,uint16_t c,int s){(void)x;(void)y;(void)ch;(void)c;(void)s;assert(0);}
'''

@pytest.mark.parametrize("landscape", [0, 1])
def test_common_font_metrics_match_raster_and_utf8_clipping(tmp_path, landscape):
    source=(ROOT/'main/pet_p4_renderer.c').read_text()
    text=source[source.index('static uint32_t utf8_next('):source.index('static int append_display_char(')]
    text+=source[source.index('static const char *draw_text_line('):source.index('static int text_y_in_box(')]
    main=r'''
int main(void){
 const int advance=PET_S3_LANDSCAPE_LEFT?25:17;
 assert(utf8_text_width("中文",-1,1)==advance*2);
 assert(utf8_text_width("中文",3,1)==advance);
 assert(utf8_text_width("中文",-1,2)==68);
 int top=0,bottom=0;text_visual_bounds("中",1,&top,&bottom);
 assert(top==0 && bottom==(PET_S3_LANDSCAPE_LEFT?23:15));
 glyph_visual_bounds(0x4e2d,0,1,&top,&bottom);assert(top==0&&bottom==15);
 /* Raw source-font bounds must stay independent of presentation policy. */
 reset();const char *s="中文";const char *rest=draw_text_line(s,8,20,advance,0xffff,1,false);
 assert(rest==s+3);assert(pixels>0);assert(min_x==8&&min_y==20);
 assert(max_x-min_x+1==(PET_S3_LANDSCAPE_LEFT?24:16));
 assert(max_y-min_y+1==(PET_S3_LANDSCAPE_LEFT?24:16));
 reset();draw_text_line("中",8,470,200,0xffff,1,false);
 if(PET_S3_LANDSCAPE_LEFT)assert(max_y<480);
 reset();draw_text_line("中",8,20,200,0xffff,2,false);assert(max_x-min_x+1==32);
 if(PET_S3_LANDSCAPE_LEFT)for(int axis=0;axis<2;axis++)for(int stem=0;stem<16;stem++) {
   stroke_x=axis==0?stem:-1;stroke_y=axis==1?stem:-1;
   reset();draw_text_line("中",8,20,200,0xffff,1,false);
   int shown=0;for(int y=0;y<480;y+=2)for(int x=0;x<640;x+=2)shown+=frame[y][x]>0;
   assert(shown>0); /* Thin strokes must survive the actual half-scale sampling. */
 }
 return 0;
}
'''
    code=tmp_path/'text.c';code.write_text(PREFIX+text+main)
    exe=tmp_path/'text'
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-function','-fsanitize=undefined',
        '-DCONFIG_IDF_TARGET_ESP32S3=1',f'-DPET_S3_LANDSCAPE_LEFT={landscape}',str(code),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

@pytest.mark.parametrize("landscape", [0, 1])
def test_graphics_labels_keep_clips_icons_and_fit_promoted_text(tmp_path, landscape):
    source=(ROOT/'main/pet_p4_renderer.c').read_text()
    body=source[source.index('static void draw_app_label('):source.index('/* Bounded game viewport:',source.index('static void draw_app_label('))]
    prefix=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include "pet_p4_surface.h"
static int glyphs,last_px,icons;
static uint32_t utf8_next(const char **s){return (unsigned char)*(*s)++;}
static uint32_t utf8_peek(const char*s){return (unsigned char)*s;}
static int app_glyph_width(uint32_t cp,uint32_t next){(void)cp;(void)next;return 32;}
static int app_text_width(const char*s,int px){return (int)strlen(s)*px;}
static void app_text_bounds(const char*s,int*t,int*b){(void)s;*t=0;*b=32;}
static void draw_app_icon(int i,int x,int y,int z,uint16_t c){(void)c;assert(i==1&&x==14&&y==44&&z==16);icons++;}
static void draw_app_glyph(uint32_t cp,uint32_t next,float x,float y,int px,uint16_t c,const pet_surface_node_t*n){
 (void)cp;(void)next;(void)c;assert(x>=n->x && x+px<=n->x+n->w);assert(y>=n->y && y+px<=n->y+n->h);glyphs++;last_px=px;
}
'''
    main=r'''
int main(void){
 pet_surface_node_t n={.x=10,.y=20,.w=120,.h=48,.font_size=16,.line_height=20,.icon=-1};
 draw_app_label(&n,"abcd",0xffff);assert(glyphs==4&&last_px==(PET_S3_LANDSCAPE_LEFT?24:16));
 assert(n.font_size==16&&n.line_height==20); /* Never mutate cached package geometry. */
 n.h=20;glyphs=0;draw_app_label(&n,"abcd",0xffff);assert(glyphs>0&&last_px==(PET_S3_LANDSCAPE_LEFT?20:16));
 n.h=64;n.type=8;n.icon=1;n.icon_size=16;n.gap=4;n.padding=4;n.valign=1;icons=0;
 draw_app_label(&n,"abc",0xffff);assert(icons==1);
 return 0;
}
'''
    code=tmp_path/'label.c';code.write_text(prefix+body+main);exe=tmp_path/'label'
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=undefined',
        '-DCONFIG_IDF_TARGET_ESP32S3=1',f'-DPET_S3_LANDSCAPE_LEFT={landscape}',
        '-I',str(ROOT/'main'),'-I',str(ROOT/'tests/vendor/cjson'),str(code),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)


def test_package_font_thin_strokes_survive_final_half_scale(tmp_path):
    source=(ROOT/'main/pet_p4_renderer.c').read_text()
    glyph=source[source.index('static float app_glyph_sample('):source.index('static void draw_app_label(')]
    prefix=PREFIX+r'''
#include "pet_p4_surface.h"
static bool custom_font=true;
static pet_surface_font_t custom={.cell_w=32,.cell_h=32};
static const pet_surface_font_t *app_font_glyph(uint32_t cp,int *index){(void)cp;*index=0;return custom_font?&custom:NULL;}
static float app_font_sample(const pet_surface_font_t*f,int i,int x,int y){(void)f;(void)i;if(x<0||x>=32||y<0||y>=32)return 0;return (stroke_x<0||stroke_x==x)&&(stroke_y<0||stroke_y==y)?255:0;}
static int pet_app_symbol_advance(uint32_t cp){(void)cp;return 0;}
static float pet_app_symbol_coverage(uint32_t cp,float x,float y,float s){(void)cp;(void)x;(void)y;(void)s;return 0;}
'''
    main=r'''
int main(void){
 pet_surface_node_t clip={.x=1,.y=1,.w=80,.h=80};
 for(int mode=0;mode<2;mode++){
  custom_font=mode==0;int dimension=custom_font?32:16;
  for(int phase=0;phase<2;phase++)for(int axis=0;axis<2;axis++)for(int stem=0;stem<dimension;stem++){
   stroke_x=axis==0?stem:-1;stroke_y=axis==1?stem:-1;reset();
   draw_app_glyph(0x4e2d,0,8+phase,20+phase,24,0xffff,&clip);
   int shown=0;for(int y=0;y<480;y+=2)for(int x=0;x<640;x+=2)shown+=frame[y][x]>0;
   assert(shown>0);
   assert(min_x>=clip.x&&max_x<clip.x+clip.w&&min_y>=clip.y&&max_y<clip.y+clip.h);
  }
 }
 return 0;
}
'''
    alpha=source[source.index('static uint8_t glyph_alpha_at('):source.index('/* Landscape output halves')]
    code=tmp_path/'package.c';code.write_text(prefix+alpha+glyph+main);exe=tmp_path/'package'
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-function','-fsanitize=undefined',
        '-DCONFIG_IDF_TARGET_ESP32S3=1','-DPET_S3_LANDSCAPE_LEFT=1',
        '-I',str(ROOT/'main'),'-I',str(ROOT/'tests/vendor/cjson'),str(code),'-lm','-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
