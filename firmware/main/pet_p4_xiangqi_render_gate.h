/* A scheduling gate, never a pixel cache. Only a successful frame authorizes
 * skipping unchanged, static Xiangqi UI work for less than one second. */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

typedef struct {
  uint64_t context,state_update;
  uint32_t view_revision;
  char widget_id[48];
} pet_xq_render_key_t;
typedef struct {
  pet_xq_render_key_t key;
  uint64_t rendered_ms;
  bool valid;
} pet_xq_render_gate_t;

static inline void pet_xq_render_invalidate(pet_xq_render_gate_t *gate){
  if(gate)gate->valid=false;
}
static inline bool pet_xq_render_key_valid(const pet_xq_render_key_t *key){
  return key&&key->widget_id[0]&&key->widget_id[sizeof(key->widget_id)-1]=='\0';
}
static inline bool pet_xq_render_needed(pet_xq_render_gate_t *gate,
    const pet_xq_render_key_t *key,bool eligible,bool dynamic,uint64_t now_ms){
  if(!gate||!eligible||dynamic||!pet_xq_render_key_valid(key)){
    pet_xq_render_invalidate(gate);return true;
  }
  return !gate->valid||now_ms<gate->rendered_ms||now_ms-gate->rendered_ms>=1000U
    ||key->context!=gate->key.context||key->state_update!=gate->key.state_update
    ||key->view_revision!=gate->key.view_revision||strcmp(key->widget_id,gate->key.widget_id)!=0;
}
static inline void pet_xq_render_complete(pet_xq_render_gate_t *gate,
    const pet_xq_render_key_t *key,bool success,uint64_t now_ms){
  if(!gate)return;
  if(!success||!pet_xq_render_key_valid(key)){pet_xq_render_invalidate(gate);return;}
  gate->key=*key;gate->rendered_ms=now_ms;gate->valid=true;
}
