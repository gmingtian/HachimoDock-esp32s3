/* Fixed ESP32-S3 N16R8 wiring. No inferred touch, joystick, I2C or storage pins. */
#pragma once
#define PET_S3_LCD_CLK 21
#define PET_S3_LCD_MOSI 47
#define PET_S3_LCD_RST 45
#define PET_S3_LCD_DC 40
#define PET_S3_LCD_CS 41
#define PET_S3_LCD_BL 42
#define PET_S3_LCD_WIDTH 240
#define PET_S3_LCD_HEIGHT 240
#define PET_S3_MIC_WS 4
#define PET_S3_MIC_BCLK 5
#define PET_S3_MIC_DIN 6
#define PET_S3_SPEAKER_DOUT 7
#define PET_S3_SPEAKER_BCLK 15
#define PET_S3_SPEAKER_WS 16
#define PET_S3_PREVIOUS_GPIO 39
#define PET_S3_NEXT_GPIO 38
#define PET_S3_CONFIRM_GPIO 0
