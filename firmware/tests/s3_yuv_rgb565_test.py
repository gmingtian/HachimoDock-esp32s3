"""Exhaustive BT.709 equivalence and bounded 2x2 chroma reuse."""
from pathlib import Path
import subprocess
from s3_native_video_row_test import function
ROOT=Path(__file__).resolve().parents[1]

def run_c(tmp_path,code):
    source=tmp_path/'yuv.c';source.write_text(code,encoding='utf-8');binary=tmp_path/'yuv'
    subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
                    '-I',str(ROOT/'s3'),str(source),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)

def test_exact_bt709_all_yuv_values_and_chroma_reuse_per_2x2_cell(tmp_path):
    header=ROOT/'s3/pet_s3_yuv_rgb565.h'
    assert header.exists(),'Missing production 2x2 YUV converter'
    row=function(header.read_text(encoding='utf-8'),'static inline void pet_s3_yuv_pair_rows(')
    row=row.replace('pet_s3_yuv_pair_rows(', 'tested_pair_rows(',1)
    code=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "pet_s3_yuv_rgb565.h"
static unsigned chroma_calls;
static pet_s3_yuv_chroma_t counted_chroma(uint8_t u,uint8_t v){chroma_calls++;return pet_s3_yuv_chroma(u,v);}
#define pet_s3_yuv_chroma counted_chroma
'''+row+r'''
#undef pet_s3_yuv_chroma
static int clamp(int v){return v<0?0:v>255?255:v;}
static uint16_t reference(unsigned y,unsigned u,unsigned v){
  int luma=(int)y-16,cb=(int)u-128,cr=(int)v-128;if(luma<0)luma=0;
  int r=clamp((298*luma+459*cr+128)>>8),g=clamp((298*luma-55*cb-136*cr+128)>>8),b=clamp((298*luma+541*cb+128)>>8);
  return (uint16_t)(((r>>3)<<11)|((g>>2)<<5)|(b>>3));
}
static uint32_t seed=123;
static uint8_t rnd(void){seed=seed*1664525U+1013904223U;return (uint8_t)(seed>>24);}
static void check_rows(int width,int second){
  uint8_t y0[322],y1[322],u[162],v[162];uint16_t out0[322],out1[322];
  for(unsigned i=0;i<322;i++){y0[i]=rnd();y1[i]=rnd();out0[i]=out1[i]=0xa5a5;}
  for(unsigned i=0;i<162;i++){u[i]=rnd();v[i]=rnd();}
  chroma_calls=0;
  tested_pair_rows(out0+1,second==1?out1+1:NULL,y0+1,second?y1+1:NULL,u+1,v+1,width);
  assert(chroma_calls==(unsigned)((width+1)/2));
  for(int x=0;x<width;x++){
    assert(out0[x+1]==reference(y0[x+1],u[x/2+1],v[x/2+1]));
    if(second==1)assert(out1[x+1]==reference(y1[x+1],u[x/2+1],v[x/2+1]));
    else assert(out1[x+1]==0xa5a5);
  }
  assert(out0[0]==0xa5a5&&out1[0]==0xa5a5);
  for(int x=width+1;x<322;x++)assert(out0[x]==0xa5a5&&out1[x]==0xa5a5);
}
int main(void){
  for(unsigned u=0;u<256;u++)for(unsigned v=0;v<256;v++){
    pet_s3_yuv_chroma_t c=pet_s3_yuv_chroma((uint8_t)u,(uint8_t)v);
    for(unsigned y=0;y<256;y++)assert(pet_s3_yuv_rgb565((uint8_t)y,c)==reference(y,u,v));
  }
  for(int width=1;width<=320;width++)for(int second=0;second<3;second++)check_rows(width,second);
  uint8_t input[320]={0};uint16_t output[320];memset(output,0xa5,sizeof(output));
  tested_pair_rows(output,NULL,input,NULL,input,input,0);
  tested_pair_rows(output,NULL,input,NULL,input,input,-1);
  tested_pair_rows(output,NULL,input,NULL,input,input,321);
  tested_pair_rows(NULL,NULL,input,NULL,input,input,320);
  for(unsigned i=0;i<320;i++)assert(output[i]==0xa5a5);
  puts("PASS all 16777216 YUV triples, widths1..320, odd/one/two rows, guards and one chroma calculation per 2x2 cell");
}
'''
    run_c(tmp_path,code)
