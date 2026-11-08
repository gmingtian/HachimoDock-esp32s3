"""2D border-connected matte must pass around multiple floating foregrounds."""
from collections import deque
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
def run_c(tmp_path,code):
    src=tmp_path/'matte_frame.c';src.write_text(code,encoding='utf-8');exe=tmp_path/'matte_frame'
    subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
                    '-I',str(ROOT/'s3'),str(src),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
def test_frame_matte_matches_independent_bfs_with_floating_props_and_enclosed_detail(tmp_path):
    assert (ROOT/'s3/pet_s3_black_matte.h').exists(),'Missing border-connected frame matte'
    run_c(tmp_path,r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "pet_s3_black_matte.h"
static struct {uint32_t pre;pet_s3_black_matte_t work;uint32_t post;} guarded;
static uint16_t pixels[320*240+2],expected[320*240],original[320*240];
static unsigned queue[320*240];static uint8_t seen[320*240];
static uint32_t seed=123;
static uint32_t rnd(void){seed=seed*1664525U+1013904223U;return seed;}
static void oracle(void){
  memset(seen,0,sizeof(seen));unsigned first=0,last=0;
  for(unsigned i=0;i<320*240;i++)if((i<320||i>=320*239||i%320==0||i%320==319)&&pet_s3_video_peak(original[i])<40){seen[i]=1;queue[last++]=i;}
  while(first<last){
    unsigned p=queue[first++],near[4]={p>=320?p-320:p,p<320*239?p+320:p,p%320?p-1:p,p%320<319?p+1:p};
    for(int n=0;n<4;n++){unsigned q=near[n];if(!seen[q]&&pet_s3_video_peak(original[q])<40){seen[q]=1;queue[last++]=q;}}
  }
  for(unsigned i=0;i<320*240;i++)expected[i]=seen[i]?0:original[i];
}
static void check(void){
  memcpy(original,pixels+1,sizeof(original));oracle();
  guarded.pre=0x12345678;guarded.post=0x87654321;
  pet_s3_black_matte_begin(&guarded.work);
  for(int y=0;y<240;y++)pet_s3_black_matte_row(&guarded.work,y,0,pixels+1+y*320,320);
  pet_s3_black_matte_finish(pixels+1,&guarded.work);
  assert(!memcmp(expected,pixels+1,sizeof(expected)));
  assert(pixels[0]==0xa5a5&&pixels[320*240+1]==0xa5a5);
  assert(guarded.pre==0x12345678&&guarded.post==0x87654321);
}
int main(int argc,char **argv){
  if(argc==3){
    FILE *in=fopen(argv[1],"rb");assert(in);assert(fread(pixels+1,2,320*240,in)==320*240);assert(fclose(in)==0);
    pixels[0]=pixels[320*240+1]=0xa5a5;check();
    FILE *out=fopen(argv[2],"wb");assert(out);assert(fwrite(pixels+1,2,320*240,out)==320*240);assert(fclose(out)==0);return 0;
  }
  for(int kind=0;kind<12;kind++){
    pixels[0]=pixels[320*240+1]=0xa5a5;
    for(int y=0;y<240;y++)for(int x=0;x<320;x++){
      uint16_t c=0x00c0;
      if(kind==0)c=0;
      else if(kind==1)c=0xffff;
      else if(kind==2)c=(x==70||x==150||y==40||y==160)?0xffff:0x1082;
      else if(kind==3)c=(x%2&&y%2)?0x2104:0xffff;
      else if(kind==4)c=(y%4==1&&x<(y%8==1?319:318)&&x>(y%8==1?1:0))?0xffff:0x00c0;
      else if(kind>=5)c=(rnd()%100<45)?0xffff:(uint16_t)(rnd()&0x1fff);
      pixels[1+y*320+x]=c;
    }
    check();
  }
  /* Separate butterfly/bone shapes fence each row but must not fence 2D background. */
  for(int y=0;y<240;y++)for(int x=0;x<320;x++)pixels[1+y*320+x]=0x00c0;
  for(int y=50;y<100;y++)for(int x=40;x<80;x++)pixels[1+y*320+x]=0xffff;
  for(int y=80;y<130;y++)for(int x=150;x<200;x++)pixels[1+y*320+x]=0xffff;
  pixels[1+75*320+60]=0x1082; /* enclosed eye/paw-print */
  check();assert(pixels[1+75*320+60]==0x1082&&pixels[1+90*320+120]==0);
  puts("PASS frame matte equals independent BFS for masks, mazes, floating props, enclosed dark details and guarded buffers");
}
''')
