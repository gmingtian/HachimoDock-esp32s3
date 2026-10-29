#include "pet_s3_board.h"
#include "pet_s3_keys.h"
static void input_task(void *arg) {
  (void)arg;
  pet_s3_keys_t keys;
  pet_s3_keys_init(&keys);
  const int pins[]={PET_S3_PREVIOUS_GPIO,PET_S3_NEXT_GPIO,PET_S3_CONFIRM_GPIO};
  const pet_p4_input_control_t controls[]={PET_P4_INPUT_CONTROL_SW1,PET_P4_INPUT_CONTROL_SW2,PET_P4_INPUT_CONTROL_SW3};
  TickType_t wake=xTaskGetTickCount();
  while(true) {
    for(unsigned key=0;key<PET_S3_KEY_COUNT;key++) {
      unsigned action=pet_s3_keys_update(&keys,key,gpio_get_level(pins[key])==0,PET_P4_INPUT_SAMPLE_MS);
      if(action)queue_event(controls[key],PET_S3_INPUT_GESTURE_ACTION,(int)action);
    }
    vTaskDelayUntil(&wake,pdMS_TO_TICKS(PET_P4_INPUT_SAMPLE_MS));
  }
}
esp_err_t pet_p4_input_init(void) {
  if(g_event_queue)return ESP_OK;
  gpio_config_t config={.pin_bit_mask=(1ULL<<PET_S3_PREVIOUS_GPIO)|(1ULL<<PET_S3_NEXT_GPIO)|(1ULL<<PET_S3_CONFIRM_GPIO),
    .mode=GPIO_MODE_INPUT,.pull_up_en=GPIO_PULLUP_ENABLE,.intr_type=GPIO_INTR_DISABLE};
  esp_err_t err=gpio_config(&config);
  if(err!=ESP_OK)return err;
  load_persisted_config();
  g_event_queue=xQueueCreate(PET_P4_INPUT_QUEUE_LENGTH,sizeof(pet_p4_input_event_t));
  if(!g_event_queue)return ESP_ERR_NO_MEM;
  if(xTaskCreate(input_task,"pet_s3_keys",4096,NULL,9,NULL)!=pdPASS) {
    vQueueDelete(g_event_queue);g_event_queue=NULL;return ESP_ERR_NO_MEM;
  }
  ESP_LOGI(TAG,"three keys ready previous=%d next=%d confirm=%d; no ADC/encoder",
    PET_S3_PREVIOUS_GPIO,PET_S3_NEXT_GPIO,PET_S3_CONFIRM_GPIO);
  return ESP_OK;
}
