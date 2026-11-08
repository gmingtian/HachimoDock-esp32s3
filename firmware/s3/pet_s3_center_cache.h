/* Exact, renderer-owned component-center metadata. No retained catalog pointers
 * or extra pixel buffers; a failed/overlaid/foreign frame cannot be reused. */
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include "pet_p4_center_layout.h"

typedef struct {
  bool valid, loading;
  size_t count, selected, start;
  pet_p4_miniapp_catalog_entry_t items[PET_CENTER_PAGE_SIZE];
} pet_s3_center_snapshot_t;

typedef enum { PET_S3_CENTER_FULL, PET_S3_CENTER_CARDS, PET_S3_CENTER_RETAIN } pet_s3_center_mode_t;
typedef struct { pet_s3_center_mode_t mode; uint8_t cards; } pet_s3_center_plan_t;

static inline bool pet_s3_center_item_equal(const pet_p4_miniapp_catalog_entry_t *a,
    const pet_p4_miniapp_catalog_entry_t *b) {
  return !strcmp(a->widget_id,b->widget_id) && !strcmp(a->title,b->title)
    && a->active==b->active && a->resource_state==b->resource_state && a->image_count==b->image_count;
}

static inline pet_s3_center_plan_t pet_s3_center_plan(const pet_s3_center_snapshot_t *old,
    const pet_s3_center_snapshot_t *next,bool may_retain) {
  pet_s3_center_plan_t plan={PET_S3_CENTER_FULL,0};
  if(!may_retain || !old->valid || !next->valid || old->count!=next->count
      || old->start!=next->start || old->loading!=next->loading) return plan;
  for(size_t slot=0;slot<PET_CENTER_PAGE_SIZE && next->start+slot<next->count;slot++) {
    size_t index=next->start+slot;
    if(!pet_s3_center_item_equal(&old->items[slot],&next->items[slot])
        || (old->selected==index)!=(next->selected==index)) plan.cards|=(uint8_t)(1U<<slot);
  }
  plan.mode=plan.cards?PET_S3_CENTER_CARDS:PET_S3_CENTER_RETAIN;
  return plan;
}
