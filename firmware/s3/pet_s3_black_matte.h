/* Factory black-background matte: 4-connected background can pass around
 * separate flying props. Two bit masks, not a pixel queue or segmentation. */
#pragma once
#include <stdint.h>
#include <string.h>
#include "pet_s3_video_background.h"
typedef struct {
  uint32_t candidate[240][10],connected[240][10];
  uint16_t left[240],right[240];
} pet_s3_black_matte_t;
_Static_assert(sizeof(pet_s3_black_matte_t)==20160,"bounded native matte workspace");
static inline void pet_s3_black_matte_begin(pet_s3_black_matte_t *work) {
  if(!work)return;
  memset(work->candidate,0xff,sizeof(work->candidate));
  memset(work->connected,0,sizeof(work->connected));
  for(int y=0;y<240;y++)work->left[y]=work->right[y]=320;
}
static inline void pet_s3_black_matte_row(pet_s3_black_matte_t *work,int y,int x,
    uint16_t *pixels,int width) {
  if(!work||!pixels||y<0||y>=240||x<0||width<=0||width>320-x)return;
  uint32_t row[10];memcpy(row,work->candidate[y],sizeof(row));int first=width,last=-1;
  for(int col=0;col<width;col++){
    unsigned at=(unsigned)(x+col);uint32_t bit=UINT32_C(1)<<(at&31U);
    if(pet_s3_video_peak(pixels[col])<40U)row[at/32]|=bit;
    else {row[at/32]&=~bit;if(first==width)first=col;last=col;}
  }
  memcpy(work->candidate[y],row,sizeof(row));
  /* Horizontal border runs are a proven subset of the 2D background. Clear
   * them while RGB rows are internal; finish only writes newly reached gaps. */
  if(last<0)memset(pixels,0,(size_t)width*2);
  else{
    if(first)memset(pixels,0,(size_t)first*2);
    if(last+1<width)memset(pixels+last+1,0,(size_t)(width-last-1)*2);
    work->left[y]=(uint16_t)(x+first);work->right[y]=(uint16_t)(x+last+1);
  }
}
static inline uint32_t pet_s3_black_matte_grow(uint32_t mask,uint32_t seeds) {
  uint32_t bits=seeds&mask;
  if(!bits||mask==UINT32_MAX)return bits?mask:0;
  for(;;){uint32_t next=bits|(((bits<<1)|(bits>>1))&mask);if(next==bits)return bits;bits=next;}
}
static inline void pet_s3_black_matte_enqueue(uint8_t *queue,uint8_t *queued,
    unsigned *tail,unsigned *count,int y) {
  if(y<0||y>=240||queued[y]||*count>=240)return;
  queue[*tail]=(uint8_t)y;*tail=(*tail+1)%240;(*count)++;queued[y]=1;
}
static inline void pet_s3_black_matte_finish(uint16_t *pixels,pet_s3_black_matte_t *work) {
  if(!pixels||!work)return;
  uint8_t queue[240],queued[240];unsigned head=0,tail=0,count=240;
  for(int y=0;y<240;y++){
    queue[y]=(uint8_t)y;queued[y]=1;
    if(y==0||y==239)memcpy(work->connected[y],work->candidate[y],40);
    else{
      work->connected[y][0]=work->candidate[y][0]&UINT32_C(1);
      work->connected[y][9]=work->candidate[y][9]&UINT32_C(0x80000000);
    }
  }
  while(count){
    unsigned y=queue[head];head=(head+1)%240;count--;queued[y]=0;
    uint32_t mask[10],row[10];memcpy(mask,work->candidate[y],sizeof(mask));
    for(int word=0;word<10;word++)row[word]=(work->connected[y][word]
      |(y?work->connected[y-1][word]:0)|(y<239?work->connected[y+1][word]:0))&mask[word];
    uint32_t carry=0;
    for(int word=0;word<10;word++){
      row[word]=pet_s3_black_matte_grow(mask[word],row[word]|carry);carry=row[word]>>31;
    }
    carry=0;
    for(int word=9;word>=0;word--){
      row[word]=pet_s3_black_matte_grow(mask[word],row[word]|carry);
      carry=(row[word]&1U)?UINT32_C(0x80000000):0;
    }
    if(memcmp(row,work->connected[y],sizeof(row))){
      memcpy(work->connected[y],row,sizeof(row));
      pet_s3_black_matte_enqueue(queue,queued,&tail,&count,(int)y-1);
      pet_s3_black_matte_enqueue(queue,queued,&tail,&count,(int)y+1);
    }
  }
  /* Zero long connected spans in bursts; no external RGB reads are needed. */
  for(int y=0;y<240;y++){
    uint32_t row[10];memcpy(row,work->connected[y],sizeof(row));int start=-1;
    for(int x=work->left[y];x<work->right[y];x++){
      bool connected=((row[x/32]>>(x&31))&1U)!=0;
      if(connected&&start<0)start=x;
      if(!connected&&start>=0){memset(pixels+y*320+start,0,(size_t)(x-start)*2);start=-1;}
    }
    if(start>=0)memset(pixels+y*320+start,0,(size_t)(work->right[y]-start)*2);
  }
}
