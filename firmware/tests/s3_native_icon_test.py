"""Original vector icons retain geometry, with native pixel coverage at half size."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_every_vector_icon_keeps_thin_strokes_at_native_pixel_size(tmp_path):
    source = (ROOT/'main/pet_p4_renderer.c').read_text()
    icon = source[source.index('static void draw_app_icon('):source.index('static const pet_surface_t *g_app_text_surface;')]
    test = tmp_path/'icons.c'
    test.write_text(r'''
#include <assert.h>
#include <stdlib.h>
#include <math.h>
#include <stdint.h>
#include <string.h>
#include "pet_p4_app_icons.h"
static uint8_t alpha[96][96];
static void blend_px(int x,int y,int r,int g,int b,int a){
  (void)r;(void)g;(void)b;assert(x>=0&&x<96&&y>=0&&y<96);alpha[y][x]=a;
}
''' + icon + r'''
/* Independent high-resolution reference integrated over one screen pixel. */
static float reference(int icon,int size,float x,float y){
  float best=1e6f,scale=size/48.0f;
  for(int i=0;i<pet_app_icons[icon].count;i++){
    const uint8_t *s=pet_app_icon_segments[pet_app_icons[icon].start+i];
    float ax=s[0]*scale,ay=s[1]*scale,dx=(s[2]-s[0])*scale,dy=(s[3]-s[1])*scale;
    float length=dx*dx+dy*dy,t=length?((x-ax)*dx+(y-ay)*dy)/length:0;
    t=fmaxf(0,fminf(1,t));float ex=x-ax-t*dx,ey=y-ay-t*dy;
    best=fminf(best,ex*ex+ey*ey);
  }
  return fmaxf(0,fminf(1,size*.9f/24+.5f-sqrtf(best)));
}
int main(void){
  for(int icon=0;icon<PET_APP_ICON_COUNT;icon++)for(int size=16;size<=48;size+=16){
    memset(alpha,0,sizeof(alpha));draw_app_icon(icon,8,8,size,0xffff);
    unsigned visible=0;
    for(int y=0;y<size;y+=2)for(int x=0;x<size;x+=2){
      float sum=reference(icon,size,x+.5f,y+.5f)+reference(icon,size,x+1.5f,y+.5f)
               +reference(icon,size,x+.5f,y+1.5f)+reference(icon,size,x+1.5f,y+1.5f);
      int expected=(int)(sum*255/4);
      assert(abs((int)alpha[8+y][8+x]-expected)<=1);
      visible+=alpha[8+y][8+x]!=0;
    }
    assert(visible>0);
    for(int y=0;y<96;y++)for(int x=0;x<96;x++)
      if(x<8||x>=8+size||y<8||y>=8+size)assert(alpha[y][x]==0);
  }
  return 0;
}
''')
    exe = tmp_path/'icons'
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
                    '-DCONFIG_IDF_TARGET_ESP32S3=1','-DPET_S3_LANDSCAPE_LEFT=1',
                    '-I',str(ROOT/'main'),str(test),'-lm','-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
