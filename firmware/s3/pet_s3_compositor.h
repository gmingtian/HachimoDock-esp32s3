/* Native storage with logical coordinates: equivalent to the final even sample.
 * Only the landscape home enables this context; package coordinates stay intact. */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

typedef struct {int x0,y0,x1,y1;} pet_s3_native_bounds_t;
static inline bool pet_s3_native_bounds(int x0,int y0,int x1,int y1,
    pet_s3_native_bounds_t *out) {
  if(x0<0)x0=0;
  if(y0<0)y0=0;
  if(x1>640)x1=640;
  if(y1>480)y1=480;
  if(!out||x0>=x1||y0>=y1)return false;
  *out=(pet_s3_native_bounds_t){(x0+1)/2,(y0+1)/2,(x1+1)/2,(y1+1)/2};
  return out->x0<out->x1&&out->y0<out->y1;
}
static inline uint16_t *pet_s3_native_pixel(uint16_t *frame,int x,int y) {
  if(!frame||(unsigned)x>=640U||(unsigned)y>=480U||((x|y)&1))return NULL;
  return frame+(size_t)(y/2)*320+x/2;
}
static inline void pet_s3_native_fill(uint16_t *frame,int x0,int y0,int x1,int y1,uint16_t color) {
  pet_s3_native_bounds_t b;
  if(!frame||!pet_s3_native_bounds(x0,y0,x1,y1,&b))return;
  for(int y=b.y0;y<b.y1;y++)for(int x=b.x0;x<b.x1;x++)frame[y*320+x]=color;
}
static inline void pet_s3_native_clear_outside(uint16_t *frame,int x,int y,int w,int h) {
  pet_s3_native_bounds_t b;
  if(!frame)return;
  if(!pet_s3_native_bounds(x,y,x+w,y+h,&b)){memset(frame,0,320*240*sizeof(*frame));return;}
  if(b.y0)memset(frame,0,(size_t)b.y0*320*sizeof(*frame));
  if(b.y1<240)memset(frame+b.y1*320,0,(size_t)(240-b.y1)*320*sizeof(*frame));
  if(b.x0||b.x1<320)for(int row=b.y0;row<b.y1;row++){
    if(b.x0)memset(frame+row*320,0,(size_t)b.x0*sizeof(*frame));
    if(b.x1<320)memset(frame+row*320+b.x1,0,(size_t)(320-b.x1)*sizeof(*frame));
  }
}
