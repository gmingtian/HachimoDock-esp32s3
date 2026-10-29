#include <assert.h>
#include <stdint.h>
#include "pet_s3_pcm.h"
int main(void) {
  // I2S microphones return signed 24-bit samples left aligned in 32-bit slots.
  int32_t mic[] = {0x12340000, (int32_t)0xFEDC0000u, INT32_MAX, INT32_MIN};
  int16_t mono[4] = {0};
  pet_s3_pcm_capture(mono,mic,4);
  assert(mono[0] == 4660 && mono[1] == -292 && mono[2] == 32767 && mono[3] == -32768);
  int16_t stereo[8] = {0};
  pet_s3_pcm_playback(stereo,mono,4,100);
  assert(stereo[0]==4660 && stereo[1]==4660 && stereo[6]==-32768 && stereo[7]==-32768);
  pet_s3_pcm_playback(stereo,mono,4,50);
  assert(stereo[0]==2330 && stereo[1]==2330 && stereo[2]==-146 && stereo[6]==-16384);
  pet_s3_pcm_playback(stereo,mono,4,0);
  for (int i=0;i<8;i++) assert(stereo[i]==0);
}
