#pragma once
#include "pet_p4_input_core.h"
enum { PET_S3_PREVIOUS, PET_S3_NEXT, PET_S3_CONFIRM, PET_S3_KEY_COUNT };
enum {
 PET_S3_ACTION_PREVIOUS=1, PET_S3_ACTION_NEXT=2, PET_S3_ACTION_CONFIRM=4,
 PET_S3_ACTION_BACK=8, PET_S3_ACTION_MENU=16,
 PET_S3_ACTION_VOICE_START=32, PET_S3_ACTION_VOICE_END=64
};
typedef struct { pet_p4_button_decoder_t buttons[PET_S3_KEY_COUNT]; } pet_s3_keys_t;
static inline void pet_s3_keys_init(pet_s3_keys_t *keys) {
 for (unsigned i=0;i<PET_S3_KEY_COUNT;i++) pet_p4_button_decoder_init(&keys->buttons[i],false,25,700);
}
static inline unsigned pet_s3_keys_update(pet_s3_keys_t *keys,unsigned key,bool pressed,uint32_t elapsed) {
 if (!keys || key >= PET_S3_KEY_COUNT) return 0;
 unsigned flags=pet_p4_button_decoder_update(&keys->buttons[key],pressed,elapsed);
 if (flags&PET_P4_BUTTON_EVENT_SHORT_PRESS) return 1u<<key;
 if (flags&PET_P4_BUTTON_EVENT_LONG_PRESS) {
   return key==PET_S3_PREVIOUS?PET_S3_ACTION_BACK:key==PET_S3_NEXT?PET_S3_ACTION_MENU:PET_S3_ACTION_VOICE_START;
 }
 if (key==PET_S3_CONFIRM && (flags&PET_P4_BUTTON_EVENT_LONG_RELEASE)) return PET_S3_ACTION_VOICE_END;
 return 0;
}
