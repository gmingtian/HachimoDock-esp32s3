"""Extract the production pinned RLE blitter; compare native output to old pixels.

The mutex double checks lock ordering and permits a deterministic release/retire
between pin and draw. This is not a pthread concurrency stress test.
Run directly to emit the host C harness, or use pytest with CC=cc/clang/gcc.
"""
import argparse
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def function(source, signature):
    assert signature in source, f"missing production API/helper: {signature}"
    start = source.index(signature)
    end, depth = source.index('{', start) + 1, 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def host_source():
    source = (ROOT/'main/pet_p4_bubble_pixels.c').read_text(encoding='utf-8')
    image_type = source[source.index('typedef struct {'):source.index('} text_image_t;') + len('} text_image_t;')]
    helpers = '\n'.join(function(source, s) for s in [
        'static unsigned\nwidth_for(', 'static uint16_t blend(',
        'static void     discard(', 'static void     bump(',
        'static void     evict(', 'static void     unpin(',
        'void            pet_bubble_pixels_release(',
        'bool\npet_bubble_pixels_draw_pinned_scaled(',
        'bool\npet_bubble_pixels_draw_pinned(',
    ])
    prelude = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "pet_p4_bubble_pixels.h"
#define CACHE_SLOTS 8
#define portMAX_DELAY 0
static int mutex = 1, lock_depth;
static unsigned takes, gives;
static void (*unlock_hook)(void);
static void xSemaphoreTake(int m, int wait){(void)wait;assert(m && !lock_depth);lock_depth=1;takes++;}
static void xSemaphoreGive(int m){assert(m && lock_depth==1);lock_depth=0;gives++;if(unlock_hook){void(*hook)(void)=unlock_hook;unlock_hook=NULL;hook();}}
'''
    globals_ = r'''
static text_image_t cache[CACHE_SLOTS];
static size_t cache_bytes;
static unsigned clock_age;
static atomic_uint revision;
'''
    cases = r'''
#define LOGICAL (640*480)
#define NATIVE (320*240)
#define GUARD 32
static uint16_t full[LOGICAL+2*GUARD], native[NATIVE+2*GUARD], old[LOGICAL];
static unsigned cases_checked;
static uint16_t background(unsigned x,unsigned y){return (uint16_t)((x*117U+y*503U)^(x*y*13U));}
/* Independent frozen pre-native RLE behavior, including original 4bit rounding. */
static void reference(const uint8_t *data,size_t size,unsigned width,int x,int y,int clip,uint16_t color){
 unsigned pixel=0;
 for(size_t i=0;i<size;i++){
  unsigned a=data[i]>>4;
  for(unsigned n=(data[i]&15U)+1U;n;n--,pixel++){
   int col=(int)(pixel%width),dx=x+col,dy=y+(int)(pixel/width);
   if(!a || col>=clip || dx<0 || dx>=640 || dy<0 || dy>=480)continue;
   uint16_t b=old[dy*640+dx];
   unsigned r=(((color>>11)&31)*a+((b>>11)&31)*(15-a)+7)/15;
   unsigned g=(((color>>5)&63)*a+((b>>5)&63)*(15-a)+7)/15;
   unsigned blue=((color&31)*a+(b&31)*(15-a)+7)/15;
   old[dy*640+dx]=(uint16_t)((r<<11)|(g<<5)|blue);
  }
 }
}
static void initialize(void){
 for(unsigned i=0;i<GUARD;i++)full[i]=full[LOGICAL+GUARD+i]=native[i]=native[NATIVE+GUARD+i]=0xA71C;
 for(unsigned y=0;y<480;y++)for(unsigned x=0;x<640;x++)old[y*640+x]=full[GUARD+y*640+x]=background(x,y);
 for(unsigned y=0;y<240;y++)for(unsigned x=0;x<320;x++)native[GUARD+y*320+x]=background(2*x,2*y);
}
static void compare(void){
 assert(!memcmp(full+GUARD,old,sizeof(old)));
 for(unsigned y=0;y<240;y++)for(unsigned x=0;x<320;x++)assert(native[GUARD+y*320+x]==old[2*y*640+2*x]);
 for(unsigned i=0;i<GUARD;i++)assert(full[i]==0xA71C&&full[LOGICAL+GUARD+i]==0xA71C&&native[i]==0xA71C&&native[NATIVE+GUARD+i]==0xA71C);
 assert(!lock_depth&&takes==gives);
 cases_checked++;
}
static unsigned fixture_width(unsigned style){return style==1?474:style==3?348:496;}
static uint8_t *fixture(unsigned style,size_t *size){
 unsigned pixels=fixture_width(style)*(style==2||style==4?54:38),p=0;
 uint8_t *data=malloc(pixels);assert(data);*size=0;
 while(p<pixels){unsigned run=1U+((p*7U+*size*3U)%16U);if(run>pixels-p)run=pixels-p;data[*size]=(uint8_t)(((*size%16U)<<4)|(run-1U));(*size)++;p+=run;}
 return data;
}
static pet_bubble_text_view_t make_view(unsigned style,unsigned page){
 assert(!cache[0].data);size_t size;uint8_t *data=fixture(style,&size);
 cache[0]=(text_image_t){.data=data,.size=size,.style=style,.page=page,.pages=page+1,.readers=1};cache_bytes=size;
 pet_bubble_text_view_t v={.pixels=true,.style=style,.title_pin=-1,.body_pin=-1};
 if(style==1)v.title_pin=0;else v.body_pin=0;return v;
}
static void clear_view(pet_bubble_text_view_t *v){cache[0].retired=true;pet_bubble_pixels_release(v);assert(!cache[0].data&&!cache_bytes);}
static void draw_pair(pet_bubble_text_view_t *v,unsigned style,unsigned page,int x,int y,int clip,uint16_t color){
 unsigned readers=cache[0].readers;
 reference(cache[0].data,cache[0].size,fixture_width(style),x,y,clip,color);
 assert(pet_bubble_pixels_draw_pinned(v,style,page,full+GUARD,x,y,clip,color));
 assert(cache[0].readers==readers);
 assert(pet_bubble_pixels_draw_pinned_scaled(v,style,page,native+GUARD,x,y,clip,color,2));
 assert(cache[0].readers==readers);
 compare();
}
static void all_pixels_and_overlap(void){
 const int positions[][3]={{0,0,640},{1,1,499},{-1,-1,497},{-13,-17,347},{639,479,500},{640,480,499},{-499,13,500},{211,471,31},{0,0,0},{1,0,-1},{-3,1,1},{0,-53,496},{-473,479,474}};
 for(unsigned s=1;s<=4;s++)for(unsigned p=0;p<(s==2?3U:1U);p++){
  pet_bubble_text_view_t v=make_view(s,p);
  for(unsigned i=0;i<sizeof(positions)/sizeof(positions[0]);i++){
   initialize();draw_pair(&v,s,p,positions[i][0],positions[i][1],positions[i][2],0xA51B);
   draw_pair(&v,s,p,positions[i][0]+3,positions[i][1]-1,positions[i][2],0x1E43);
  }
  initialize();reference(cache[0].data,cache[0].size,fixture_width(s),3,5,117,0xFFFF);
  assert(pet_bubble_pixels_draw_pinned_scaled(&v,s,p,full+GUARD,3,5,117,0xFFFF,1));
  assert(!memcmp(full+GUARD,old,sizeof(old)));clear_view(&v);
 }
}
static void rejects_without_side_effects(void){
 pet_bubble_text_view_t v=make_view(4,0);initialize();text_image_t before=cache[0];unsigned age=clock_age,take_count=takes;
 const unsigned invalid[]={0,3,4,UINT32_MAX};
 for(unsigned i=0;i<sizeof(invalid)/sizeof(invalid[0]);i++){
  assert(!pet_bubble_pixels_draw_pinned_scaled(&v,4,0,native+GUARD,0,0,496,0,invalid[i]));
  assert(!memcmp(&before,&cache[0],sizeof(before))&&clock_age==age&&takes==take_count);
 }
 for(unsigned scale=1;scale<=2;scale++){
  uint16_t *fb=scale==1?full+GUARD:native+GUARD;
  assert(!pet_bubble_pixels_draw_pinned_scaled(&v,2,0,fb,0,0,496,0,scale));
  assert(!pet_bubble_pixels_draw_pinned_scaled(&v,4,1,fb,0,0,496,0,scale));
  assert(!pet_bubble_pixels_draw_pinned_scaled(&v,0,0,fb,0,0,496,0,scale));
  assert(!pet_bubble_pixels_draw_pinned_scaled(NULL,4,0,fb,0,0,496,0,scale));
  assert(!pet_bubble_pixels_draw_pinned_scaled(&v,4,0,NULL,0,0,496,0,scale));
  v.pixels=false;assert(!pet_bubble_pixels_draw_pinned_scaled(&v,4,0,fb,0,0,496,0,scale));v.pixels=true;
  mutex=0;assert(!pet_bubble_pixels_draw_pinned_scaled(&v,4,0,fb,0,0,496,0,scale));mutex=1;
  assert(!memcmp(&before,&cache[0],sizeof(before))&&clock_age==age);
 }
 compare();
 /* Nonexistent, out of range and unpinned handles must never read freed data. */
 v.body_pin=-1;assert(!pet_bubble_pixels_draw_pinned_scaled(&v,4,0,native+GUARD,0,0,496,0,2));
 v.body_pin=CACHE_SLOTS;assert(!pet_bubble_pixels_draw_pinned_scaled(&v,4,0,native+GUARD,0,0,496,0,2));
 v.body_pin=0;cache[0].readers=0;assert(!pet_bubble_pixels_draw_pinned_scaled(&v,4,0,native+GUARD,0,0,496,0,2));cache[0].readers=1;
 clear_view(&v);v.pixels=true;v.body_pin=0;
 assert(!pet_bubble_pixels_draw_pinned_scaled(&v,4,0,native+GUARD,0,0,496,0,2));compare();
}
static pet_bubble_text_view_t *release_at_unlock;
static void retire_while_drawing(void){
 assert(cache[0].readers==2);cache[0].retired=true;
 pet_bubble_pixels_release(release_at_unlock);
 assert(cache[0].data&&cache[0].readers==1);
}
static void separate_draw_pin_survives_release(void){
 for(unsigned scale=1;scale<=2;scale++){
  pet_bubble_text_view_t v=make_view(4,0);initialize();
  reference(cache[0].data,cache[0].size,496,-1,1,496,0xF81F);
  release_at_unlock=&v;unlock_hook=retire_while_drawing;
  assert(pet_bubble_pixels_draw_pinned_scaled(&v,4,0,scale==1?full+GUARD:native+GUARD,-1,1,496,0xF81F,scale));
  assert(!v.pixels&&v.body_pin==-1&&!cache[0].data&&!cache_bytes);
  if(scale==1)assert(!memcmp(full+GUARD,old,sizeof(old)));
  else for(unsigned y=0;y<240;y++)for(unsigned x=0;x<320;x++)assert(native[GUARD+y*320+x]==old[2*y*640+2*x]);
  assert(!lock_depth&&takes==gives);
 }
 /* A previously retired but still pinned view intentionally remains drawable. */
 pet_bubble_text_view_t v=make_view(1,0);cache[0].retired=true;initialize();draw_pair(&v,1,0,1,1,474,0xBCDE);clear_view(&v);
}
int main(void){
 all_pixels_and_overlap();rejects_without_side_effects();separate_draw_pin_survives_release();
 printf("PASS %u sampled pixel/guard comparisons, all styles/pages, alpha overlap, scale1 compatibility, invalid inputs, stale pins and deterministic release/retire pin lifetime\n",cases_checked);
 return 0;
}
'''
    return prelude + image_type + globals_ + helpers + cases


def test_native_blit_matches_old_sample_and_preserves_pins(tmp_path):
    path = tmp_path/'bubble-native-host.c'
    path.write_text(host_source(), encoding='utf-8')
    binary = tmp_path/'bubble-native-host'
    subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-O1', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-I', str(ROOT/'main'),
                    '-I', str(ROOT/'tests/vendor/cjson'), str(path), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--emit-c', type=Path, required=True)
    args = parser.parse_args()
    args.emit_c.write_text(host_source(), encoding='utf-8')
