/* Bounded cleanup of near-black video backgrounds, before text/UI composition.
 * This is not segmentation: preserve everything after the first visible or
 * colorful pixel from each side, including equally dark foreground detail. */
#pragma once
#include <stdbool.h>
#include <stdint.h>

static inline unsigned pet_s3_video_peak(uint16_t color) {
  unsigned r = (color >> 8) & 248U;
  unsigned g = (color >> 3) & 252U;
  unsigned b = (color << 3) & 248U;
  unsigned peak = r > g ? r : g;
  return peak > b ? peak : b;
}

static inline bool pet_s3_clean_video_shadow(uint16_t *pixel) {
  const uint16_t color = *pixel;
  unsigned r = (color >> 8) & 248U;
  unsigned g = (color >> 3) & 252U;
  unsigned b = (color << 3) & 248U;
  unsigned peak = r > g ? r : g;
  if (b > peak) peak = b;
  unsigned low = r < g ? r : g;
  if (b < low) low = b;
  /* Do not continue through visible fur or saturated, dark-colored artwork. */
  if (peak >= 40U || peak - low > 16U) return false;
  if (peak <= 20U) {
    *pixel = 0;
  } else {
    /* Continuous knee: grey32 becomes grey19; grey40 is unchanged. No blur. */
    const unsigned gain = peak - 20U;
    r = r * gain / 20U;
    g = g * gain / 20U;
    b = b * gain / 20U;
    *pixel = (uint16_t)(((r & 248U) << 8) | ((g & 252U) << 3) | (b >> 3));
  }
  return true;
}

static inline void pet_s3_clean_video_background(uint16_t *row, int width) {
  if (!row || width <= 0 || pet_s3_video_peak(row[0]) > 12U
      || pet_s3_video_peak(row[width - 1]) > 12U) return;
  int left = 0;
  while (left < width && pet_s3_clean_video_shadow(row + left)) ++left;
  int right = width - 1;
  while (right > left && pet_s3_clean_video_shadow(row + right)) --right;
}
