/* Exact limited-range BT.709, with one chroma calculation per I420 2x2 cell.
 * No approximation/table allocation: clamp after discarding only RGB565 bits. */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

typedef struct {int32_t red,green,blue;} pet_s3_yuv_chroma_t;
static inline pet_s3_yuv_chroma_t pet_s3_yuv_chroma(uint8_t u,uint8_t v) {
  int cb=(int)u-128,cr=(int)v-128;
  return (pet_s3_yuv_chroma_t){459*cr,-55*cb-136*cr,541*cb};
}
static inline uint16_t pet_s3_yuv_rgb565(uint8_t y,pet_s3_yuv_chroma_t chroma) {
  int luma=(y>16?(int)y-16:0)*298+128;
  int red=(luma+chroma.red)>>11;
  int green=(luma+chroma.green)>>10;
  int blue=(luma+chroma.blue)>>11;
  if(red<0)red=0;else if(red>31)red=31;
  if(green<0)green=0;else if(green>63)green=63;
  if(blue<0)blue=0;else if(blue>31)blue=31;
  return (uint16_t)((red<<11)|(green<<5)|blue);
}
static inline void pet_s3_yuv_pair_rows(uint16_t *out0,uint16_t *out1,
    const uint8_t *y0,const uint8_t *y1,const uint8_t *u,const uint8_t *v,int width) {
  if(!out0||!y0||!u||!v||width<1||width>320)return;
  const bool second=out1&&y1;
  /* Burst external planes into bounded internal scratch before arithmetic;
   * avoid interleaving byte reads between three PSRAM planes for every pixel. */
  uint8_t luma0[320],luma1[320],chroma_u[160],chroma_v[160];
  const size_t chroma_width=((size_t)width+1U)/2U;
  memcpy(luma0,y0,(size_t)width);
  if(second)memcpy(luma1,y1,(size_t)width);
  memcpy(chroma_u,u,chroma_width);memcpy(chroma_v,v,chroma_width);
  for(int x=0;x<width;x+=2){
    pet_s3_yuv_chroma_t c=pet_s3_yuv_chroma(chroma_u[x/2],chroma_v[x/2]);
    out0[x]=pet_s3_yuv_rgb565(luma0[x],c);
    if(x+1<width)out0[x+1]=pet_s3_yuv_rgb565(luma0[x+1],c);
    if(second){
      out1[x]=pet_s3_yuv_rgb565(luma1[x],c);
      if(x+1<width)out1[x+1]=pet_s3_yuv_rgb565(luma1[x+1],c);
    }
  }
}
