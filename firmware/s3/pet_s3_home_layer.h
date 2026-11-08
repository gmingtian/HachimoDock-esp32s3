/* Render-owner metadata for an independent clean native appearance layer. */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#define PET_S3_HOME_LAYER_DEFINED 1
typedef struct {
  bool valid;
  unsigned revision;
  int slot;
  uint64_t epoch,pending_since_ms;
} pet_s3_home_layer_t;
typedef enum {PET_S3_HOME_CLEAN,PET_S3_HOME_PREVIOUS,PET_S3_HOME_PLACEHOLDER} pet_s3_home_output_t;
static inline void pet_s3_home_layer_invalidate(pet_s3_home_layer_t *layer){
  layer->valid=false;layer->pending_since_ms=0;
}
static inline void pet_s3_home_layer_sync(pet_s3_home_layer_t *layer,unsigned revision,
    int slot,uint64_t epoch,bool entering,uint64_t now_ms){
  bool changed=layer->revision!=revision||layer->slot!=slot||layer->epoch!=epoch;
  if(changed)layer->valid=false;
  layer->revision=revision;layer->slot=slot;layer->epoch=epoch;
  if(changed||entering)layer->pending_since_ms=now_ms;
}
static inline void pet_s3_home_layer_publish(pet_s3_home_layer_t *layer,bool converted){
  if(converted)layer->valid=true;
}
static inline pet_s3_home_output_t pet_s3_home_layer_output(const pet_s3_home_layer_t *layer,
    bool pending,bool previous_valid,bool modal,uint64_t now_ms){
  if(layer->valid)return PET_S3_HOME_CLEAN;
  if(pending&&previous_valid&&!modal&&now_ms>=layer->pending_since_ms
      &&now_ms-layer->pending_since_ms<2000)return PET_S3_HOME_PREVIOUS;
  return PET_S3_HOME_PLACEHOLDER;
}
