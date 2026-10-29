/* esp_codec_dev-shaped adapters retain all upstream PCM consumers. The board
 * has no I2C codec: microphone and MAX98357A use separate standard-I2S ports. */
#pragma once
#include <stdlib.h>
#include "driver/i2s_std.h"
#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "pet_s3_board.h"
#include "pet_s3_pcm.h"

typedef struct { int sample_rate,channel,bits_per_sample; } esp_codec_dev_sample_info_t;
typedef struct {
  bool input;
  i2s_chan_handle_t channel;
  SemaphoreHandle_t lock;
  unsigned sample_rate,volume;
} pet_s3_codec_t;
typedef pet_s3_codec_t *esp_codec_dev_handle_t;

static esp_codec_dev_handle_t pet_s3_codec_new(bool input) {
  pet_s3_codec_t *codec=calloc(1,sizeof(*codec));
  if(!codec)return NULL;
  codec->input=input;codec->volume=100;codec->lock=xSemaphoreCreateMutex();
  if(!codec->lock){free(codec);return NULL;}
  return codec;
}
static int esp_codec_dev_close(esp_codec_dev_handle_t codec) {
  if(!codec)return ESP_ERR_INVALID_ARG;
  xSemaphoreTake(codec->lock,portMAX_DELAY);
  esp_err_t err=ESP_OK;
  if(codec->channel) {
    err=i2s_channel_disable(codec->channel);
    esp_err_t del=i2s_del_channel(codec->channel);
    if(err==ESP_OK)err=del;
    if(del==ESP_OK)codec->channel=NULL;
  }
  codec->sample_rate=0;
  xSemaphoreGive(codec->lock);
  return err;
}
static int esp_codec_dev_open(esp_codec_dev_handle_t codec,const esp_codec_dev_sample_info_t *format) {
  if(!codec||!format||format->channel!=1||format->bits_per_sample!=16||format->sample_rate<8000||format->sample_rate>48000)
    return ESP_ERR_INVALID_ARG;
  if(codec->channel&&codec->sample_rate==(unsigned)format->sample_rate)return ESP_OK;
  if(codec->channel) {
    int err=esp_codec_dev_close(codec);
    if(err!=ESP_OK)return err;
  }
  xSemaphoreTake(codec->lock,portMAX_DELAY);
  i2s_chan_config_t cfg=I2S_CHANNEL_DEFAULT_CONFIG(codec->input?I2S_NUM_1:I2S_NUM_0,I2S_ROLE_MASTER);
  cfg.dma_desc_num=6;cfg.dma_frame_num=256;
  cfg.auto_clear=true;
  esp_err_t err=i2s_new_channel(&cfg,codec->input?NULL:&codec->channel,codec->input?&codec->channel:NULL);
  if(err==ESP_OK) {
    i2s_std_config_t standard={
      .clk_cfg=I2S_STD_CLK_DEFAULT_CONFIG(format->sample_rate),
      .slot_cfg=I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(codec->input?I2S_DATA_BIT_WIDTH_32BIT:I2S_DATA_BIT_WIDTH_16BIT,
         codec->input?I2S_SLOT_MODE_MONO:I2S_SLOT_MODE_STEREO),
      .gpio_cfg={.mclk=I2S_GPIO_UNUSED,
        .bclk=codec->input?PET_S3_MIC_BCLK:PET_S3_SPEAKER_BCLK,
        .ws=codec->input?PET_S3_MIC_WS:PET_S3_SPEAKER_WS,
        .dout=codec->input?I2S_GPIO_UNUSED:PET_S3_SPEAKER_DOUT,
        .din=codec->input?PET_S3_MIC_DIN:I2S_GPIO_UNUSED},
    };
    if(codec->input)standard.slot_cfg.slot_mask=I2S_STD_SLOT_LEFT;
    err=i2s_channel_init_std_mode(codec->channel,&standard);
    if(err==ESP_OK)err=i2s_channel_enable(codec->channel);
    if(err!=ESP_OK){i2s_del_channel(codec->channel);codec->channel=NULL;}
    else codec->sample_rate=format->sample_rate;
  }
  xSemaphoreGive(codec->lock);
  return err;
}
static int esp_codec_dev_set_in_gain(esp_codec_dev_handle_t codec,float gain) {
  (void)gain;
  /* Fixed-gain digital microphone: no analogue gain control to advertise. */
  return codec&&codec->input?ESP_ERR_NOT_SUPPORTED:ESP_ERR_INVALID_ARG;
}
static int esp_codec_dev_set_out_vol(esp_codec_dev_handle_t codec,int volume) {
  if(!codec||codec->input||volume<0||volume>100)return ESP_ERR_INVALID_ARG;
  xSemaphoreTake(codec->lock,portMAX_DELAY);codec->volume=volume;xSemaphoreGive(codec->lock);
  return ESP_OK;
}
static int esp_codec_dev_get_out_vol(esp_codec_dev_handle_t codec,int *volume) {
  if(!codec||!volume)return ESP_ERR_INVALID_ARG;
  xSemaphoreTake(codec->lock,portMAX_DELAY);*volume=codec->volume;xSemaphoreGive(codec->lock);
  return ESP_OK;
}
static int esp_codec_dev_read(esp_codec_dev_handle_t codec,void *data,int bytes) {
  if(!codec||!codec->input||!data||bytes<=0||(bytes&1))return ESP_ERR_INVALID_ARG;
  xSemaphoreTake(codec->lock,portMAX_DELAY);
  esp_err_t err=codec->channel?ESP_OK:ESP_ERR_INVALID_STATE;
  int32_t slots[256];
  int16_t *out=data;
  for(int remaining=bytes/2;err==ESP_OK&&remaining>0;) {
    size_t count=remaining>256?256:(size_t)remaining;
    size_t received=0;
    err=i2s_channel_read(codec->channel,slots,count*sizeof(*slots),&received,1000);
    if(err==ESP_OK&&received!=count*sizeof(*slots))err=ESP_ERR_INVALID_SIZE;
    if(err!=ESP_OK)break;
    pet_s3_pcm_capture(out,slots,count);out+=count;remaining-=count;
  }
  xSemaphoreGive(codec->lock);
  return err;
}
static int esp_codec_dev_write(esp_codec_dev_handle_t codec,void *data,int bytes) {
  if(!codec||codec->input||!data||bytes<=0||(bytes&1))return ESP_ERR_INVALID_ARG;
  xSemaphoreTake(codec->lock,portMAX_DELAY);
  esp_err_t err=codec->channel?ESP_OK:ESP_ERR_INVALID_STATE;
  int16_t slots[512];
  const int16_t *in=data;
  for(int remaining=bytes/2;err==ESP_OK&&remaining>0;) {
    size_t count=remaining>256?256:(size_t)remaining;
    pet_s3_pcm_playback(slots,in,count,codec->volume);
    size_t written=0;
    err=i2s_channel_write(codec->channel,slots,count*2*sizeof(*slots),&written,1000);
    if(err==ESP_OK&&written!=count*2*sizeof(*slots))err=ESP_ERR_INVALID_SIZE;
    if(err!=ESP_OK)break;
    in+=count;remaining-=count;
  }
  xSemaphoreGive(codec->lock);
  return err;
}
