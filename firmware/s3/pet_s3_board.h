/* ESP32-S3 N16R8 A4 carrier wiring, verified against connections.csv. */
#pragma once
#define PET_S3_LCD_CLK 21
#define PET_S3_LCD_MOSI 47
#define PET_S3_LCD_RST 45
#define PET_S3_LCD_DC 40
#define PET_S3_LCD_CS 41
#define PET_S3_LCD_BL 42
#include "pet_s3_display.h"
#define PET_S3_MIC_WS 4
#define PET_S3_MIC_BCLK 5
#define PET_S3_MIC_DIN 6
#define PET_S3_SPEAKER_DOUT 7
#define PET_S3_SPEAKER_BCLK 15
#define PET_S3_SPEAKER_WS 16
#define PET_S3_SW1_GPIO 39
#define PET_S3_SW2_GPIO 38
#define PET_S3_SW3_GPIO 0
#define PET_S3_JOYSTICK_X_GPIO 1
#define PET_S3_JOYSTICK_Y_GPIO 2
#define PET_S3_JOYSTICK_PRESS_GPIO 8

/* Wire/storage identity for the fabricated A4 official control layout. */
#define PET_S3_INPUT_MODEL "s3-a4-buttons-joystick-v1"
