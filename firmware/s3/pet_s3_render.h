#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define PET_S3_PANEL_WIDTH 240
#define PET_S3_PANEL_HEIGHT 240
#define PET_S3_ASSET_MAX_WIDTH 240
#define PET_S3_ASSET_MAX_HEIGHT 180
#define PET_S3_ASSET_MAX_FPS 15
#define PET_S3_ASSET_MAX_STREAM_BYTES (384U * 1024U)

typedef struct { int x, y, width, height; } pet_s3_rect_t;

/* Integer aspect fit: every source edge is visible; never crop or rotate. */
static inline bool pet_s3_fit_rect(int sw, int sh, int dw, int dh, pet_s3_rect_t *r) {
  if (!r || sw <= 0 || sh <= 0 || dw <= 0 || dh <= 0) return false;
  if ((int64_t) dw * sh <= (int64_t) dh * sw) {
    r->width = dw;
    r->height = (int) ((int64_t) sh * dw / sw);
  } else {
    r->height = dh;
    r->width = (int) ((int64_t) sw * dh / sh);
  }
  if (r->width < 1) r->width = 1;
  if (r->height < 1) r->height = 1;
  r->x = (dw - r->width) / 2;
  r->y = (dh - r->height) / 2;
  return true;
}

static inline bool pet_s3_scale_rgb565(const uint16_t *src, int sw, int sh, int stride,
                                     uint16_t *dst, int dw, int dh) {
  pet_s3_rect_t r;
  if (!src || !dst || stride < sw || !pet_s3_fit_rect(sw,sh,dw,dh,&r)) return false;
  memset(dst, 0, (size_t) dw * dh * sizeof(*dst));
  for (int y = 0; y < r.height; ++y) {
    const uint16_t *row = src + (size_t) ((int64_t) y * sh / r.height) * stride;
    uint16_t *out = dst + (size_t) (r.y + y) * dw + r.x;
    for (int x = 0; x < r.width; ++x) out[x] = row[(int64_t) x * sw / r.width];
  }
  return true;
}

static inline bool pet_s3_asset_bounds(unsigned width, unsigned height, unsigned fps, size_t bytes) {
  return width > 0 && width <= PET_S3_ASSET_MAX_WIDTH
    && height > 0 && height <= PET_S3_ASSET_MAX_HEIGHT
    && fps > 0 && fps <= PET_S3_ASSET_MAX_FPS
    && bytes > 0 && bytes <= PET_S3_ASSET_MAX_STREAM_BYTES;
}

/* The supported tinyh264 SPS has one reference, POC type 2 and bounded visible
 * dimensions. Compare before decoding: a dishonest catalog cannot allocate a
 * larger decoder picture pool. Host conversion emits this same canonical SPS. */
typedef struct { uint8_t data[32]; unsigned bits; } pet_s3_bit_writer_t;
static inline void pet_s3_write_bit(pet_s3_bit_writer_t *w, unsigned b) {
  w->data[w->bits / 8] |= (b & 1U) << (7U - w->bits % 8U); w->bits++;
}
static inline void pet_s3_write_ue(pet_s3_bit_writer_t *w, unsigned v) {
  unsigned value = v + 1, n = 0;
  for (unsigned t = value; t > 1; t >>= 1) n++;
  for (unsigned i = 0; i < n; i++) pet_s3_write_bit(w,0);
  for (unsigned i = n + 1; i > 0; i--) pet_s3_write_bit(w,value >> (i - 1));
}
static inline bool pet_s3_h264_sps_matches(const uint8_t *sps, size_t n, unsigned width, unsigned height) {
  if (!sps || !pet_s3_asset_bounds(width,height,1,1) || (width & 1) || (height & 1)) return false;
  unsigned mw = (width + 15) / 16, mh = (height + 15) / 16;
  unsigned right = (mw * 16 - width) / 2, bottom = (mh * 16 - height) / 2;
  bool crop = right || bottom;
  pet_s3_bit_writer_t w = {0};
  pet_s3_write_ue(&w,0); pet_s3_write_ue(&w,0); pet_s3_write_ue(&w,2); pet_s3_write_ue(&w,1);
  pet_s3_write_bit(&w,0); pet_s3_write_ue(&w,mw-1); pet_s3_write_ue(&w,mh-1);
  pet_s3_write_bit(&w,1); pet_s3_write_bit(&w,0); pet_s3_write_bit(&w,crop);
  if (crop) {
    pet_s3_write_ue(&w,0); pet_s3_write_ue(&w,right); pet_s3_write_ue(&w,0); pet_s3_write_ue(&w,bottom);
  }
  pet_s3_write_bit(&w,0); pet_s3_write_bit(&w,1);
  uint8_t expected[40] = {0x67,66,0xc0,30};
  size_t used=4; unsigned zeros=0;
  for (unsigned i=0; i<(w.bits+7)/8; ++i) {
    uint8_t value=w.data[i];
    if (zeros>=2 && value<=3) { expected[used++]=3; zeros=0; }
    expected[used++]=value; zeros=value==0 ? zeros+1 : 0;
  }
  return used==n && memcmp(sps,expected,n)==0;
}
