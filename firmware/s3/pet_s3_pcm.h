#pragma once
#include <stddef.h>
#include <stdint.h>
static inline void pet_s3_pcm_capture(int16_t *out,const int32_t *in,size_t count) {
 for (size_t i=0;i<count;i++) out[i]=(int16_t)(in[i] >> 16);
}
static inline void pet_s3_pcm_playback(int16_t *out,const int16_t *in,size_t count,unsigned volume) {
 if(volume>100)volume=100;
 for(size_t i=0;i<count;i++) {
   int16_t value=(int16_t)((int32_t)in[i]*(int32_t)volume/100);
   out[2*i]=value;out[2*i+1]=value;
 }
}
