/* Compile-time ST7789 profiles. Facing the panel, FPC is on the left in landscape. */
#pragma once
#ifndef PET_S3_LANDSCAPE_LEFT
#define PET_S3_LANDSCAPE_LEFT 0
#endif
#if PET_S3_LANDSCAPE_LEFT
#define PET_S3_LCD_WIDTH 320
#define PET_S3_LCD_HEIGHT 240
#define PET_S3_LCD_SWAP_XY 1
#define PET_S3_LCD_MIRROR_X 0
#define PET_S3_LCD_MIRROR_Y 1
#define PET_S3_NATIVE_HOME 0
#else
#define PET_S3_LCD_WIDTH 240
#define PET_S3_LCD_HEIGHT 240
#define PET_S3_LCD_SWAP_XY 0
#define PET_S3_LCD_MIRROR_X 0
#define PET_S3_LCD_MIRROR_Y 0
#define PET_S3_NATIVE_HOME 1
#endif
