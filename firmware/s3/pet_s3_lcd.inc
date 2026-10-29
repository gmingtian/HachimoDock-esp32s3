/* Native 240x240 ST7789 backend; callers retain ownership after a synchronous draw. */
#include "pet_p4_lcd.h"
#include "pet_s3_board.h"
#include <stdio.h>
#include <stdlib.h>
#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "esp_check.h"
#include "esp_heap_caps.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_panel_vendor.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"

static const char *TAG="pet-s3-lcd";
static esp_lcd_panel_handle_t g_panel;
static esp_lcd_panel_io_handle_t g_io;
static SemaphoreHandle_t g_transfer_done, g_draw_lock;
static uint16_t *g_stripe;
static esp_err_t g_backlight_status=ESP_ERR_INVALID_STATE;
static bool g_revealed;
#define PET_S3_LCD_STRIPE_ROWS 16

static bool IRAM_ATTR pet_s3_lcd_done(esp_lcd_panel_io_handle_t io,
    esp_lcd_panel_io_event_data_t *event,void *ctx) {
  (void)io;(void)event;
  BaseType_t wake=pdFALSE;
  xSemaphoreGiveFromISR((SemaphoreHandle_t)ctx,&wake);
  return wake==pdTRUE;
}
esp_err_t pet_p4_lcd_prepare_boot(void) {
  gpio_config_t config={.pin_bit_mask=1ULL<<PET_S3_LCD_BL,.mode=GPIO_MODE_OUTPUT};
  esp_err_t err=gpio_config(&config);
  if(err==ESP_OK)err=gpio_set_level(PET_S3_LCD_BL,0);
  g_revealed=false;
  return g_backlight_status=err;
}
esp_err_t pet_p4_lcd_init(void) {
  if(g_panel)return ESP_OK;
  ESP_RETURN_ON_ERROR(pet_p4_lcd_prepare_boot(),TAG,"backlight off");
  g_transfer_done=xSemaphoreCreateBinary();
  g_draw_lock=xSemaphoreCreateMutex();
  g_stripe=heap_caps_malloc(PET_S3_LCD_WIDTH*PET_S3_LCD_STRIPE_ROWS*2,MALLOC_CAP_DMA|MALLOC_CAP_INTERNAL);
  if(!g_transfer_done||!g_draw_lock||!g_stripe)return ESP_ERR_NO_MEM;
  spi_bus_config_t bus={.sclk_io_num=PET_S3_LCD_CLK,.mosi_io_num=PET_S3_LCD_MOSI,
    .miso_io_num=-1,.quadwp_io_num=-1,.quadhd_io_num=-1,
    .max_transfer_sz=PET_S3_LCD_WIDTH*PET_S3_LCD_STRIPE_ROWS*2};
  ESP_RETURN_ON_ERROR(spi_bus_initialize(SPI2_HOST,&bus,SPI_DMA_CH_AUTO),TAG,"SPI bus");
  esp_lcd_panel_io_spi_config_t io={.dc_gpio_num=PET_S3_LCD_DC,.cs_gpio_num=PET_S3_LCD_CS,
    .pclk_hz=40000000,.spi_mode=0,.trans_queue_depth=1,.lcd_cmd_bits=8,.lcd_param_bits=8,
    .on_color_trans_done=pet_s3_lcd_done,.user_ctx=g_transfer_done};
  ESP_RETURN_ON_ERROR(esp_lcd_new_panel_io_spi(SPI2_HOST,&io,&g_io),TAG,"panel SPI IO");
  esp_lcd_panel_dev_config_t panel={.reset_gpio_num=PET_S3_LCD_RST,
    .rgb_ele_order=LCD_RGB_ELEMENT_ORDER_RGB,.bits_per_pixel=16};
  ESP_RETURN_ON_ERROR(esp_lcd_new_panel_st7789(g_io,&panel,&g_panel),TAG,"ST7789");
  ESP_RETURN_ON_ERROR(esp_lcd_panel_reset(g_panel),TAG,"reset");
  ESP_RETURN_ON_ERROR(esp_lcd_panel_init(g_panel),TAG,"init");
  ESP_RETURN_ON_ERROR(esp_lcd_panel_invert_color(g_panel,true),TAG,"inversion");
  ESP_RETURN_ON_ERROR(esp_lcd_panel_swap_xy(g_panel,false),TAG,"orientation");
  ESP_RETURN_ON_ERROR(esp_lcd_panel_mirror(g_panel,false,false),TAG,"mirror");
  return esp_lcd_panel_disp_on_off(g_panel,true);
}
esp_err_t pet_p4_lcd_reveal(void) {
  if(!g_panel)return ESP_ERR_INVALID_STATE;
  g_backlight_status=gpio_set_level(PET_S3_LCD_BL,1);
  if(g_backlight_status==ESP_OK)g_revealed=true;
  return g_backlight_status;
}
esp_err_t pet_p4_lcd_backlight_status(void){return g_backlight_status;}
esp_err_t pet_p4_lcd_keep_awake(void){return g_revealed?g_backlight_status:ESP_ERR_INVALID_STATE;}
esp_err_t pet_p4_lcd_draw_rgb565(int x,int y,int width,int height,const uint16_t *pixels) {
  if(!g_panel)return ESP_ERR_INVALID_STATE;
  if(!pixels||x<0||y<0||width<=0||height<=0||width>PET_S3_LCD_WIDTH-x||height>PET_S3_LCD_HEIGHT-y)
    return ESP_ERR_INVALID_ARG;
  xSemaphoreTake(g_draw_lock,portMAX_DELAY);
  esp_err_t err=ESP_OK;
  for(int row=0;row<height;row+=PET_S3_LCD_STRIPE_ROWS) {
    int rows=height-row;
    if(rows>PET_S3_LCD_STRIPE_ROWS)rows=PET_S3_LCD_STRIPE_ROWS;
    for(int i=0;i<width*rows;i++) {
      uint16_t pixel=pixels[row*width+i];
      g_stripe[i]=(uint16_t)((pixel>>8)|(pixel<<8));
    }
    while(xSemaphoreTake(g_transfer_done,0)==pdTRUE){}
    err=esp_lcd_panel_draw_bitmap(g_panel,x,y+row,x+width,y+row+rows,g_stripe);
    if(err!=ESP_OK)break;
    /* Never reuse a DMA stripe while its transaction is still queued. */
    xSemaphoreTake(g_transfer_done,portMAX_DELAY);
  }
  xSemaphoreGive(g_draw_lock);
  return err;
}
esp_err_t pet_p4_lcd_show_software_test_pattern(uint32_t phase) {
  uint16_t row[PET_S3_LCD_WIDTH];
  const uint16_t colors[]={0xf800,0x07e0,0x001f,0xffff,0x0000,0xffe0,0x07ff,0xf81f};
  for(int x=0;x<PET_S3_LCD_WIDTH;x++)row[x]=colors[(x*8/PET_S3_LCD_WIDTH+phase)%8];
  for(int y=0;y<PET_S3_LCD_HEIGHT;y++) {
    esp_err_t err=pet_p4_lcd_draw_rgb565(0,y,PET_S3_LCD_WIDTH,1,row);
    if(err!=ESP_OK)return err;
  }
  return ESP_OK;
}
esp_err_t pet_p4_lcd_show_color_bar(void){return pet_p4_lcd_show_software_test_pattern(0);}
int pet_p4_lcd_scan_i2c(char *buffer,size_t size) {
  if(buffer&&size)snprintf(buffer,size,"not_configured");
  return 0;
}
