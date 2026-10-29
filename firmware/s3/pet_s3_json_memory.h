/* Task-owned JSON lives in PSRAM, leaving internal RAM for RTOS/DMA/libc. */
#pragma once
#include "cJSON.h"
#include "esp_heap_caps.h"

static inline void *pet_s3_json_malloc(size_t size) {
  /* Do not fall back to internal memory when PSRAM is exhausted. A failed
   * JSON parse is recoverable; starving the libc/RTOS mutex allocator is not. */
  return heap_caps_malloc(size, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
}

static inline void pet_s3_json_memory_init(void) {
  cJSON_Hooks hooks = {
    .malloc_fn = pet_s3_json_malloc,
    .free_fn = heap_caps_free,
  };
  /* Set exactly once, before any JSON tree or worker task can exist. */
  cJSON_InitHooks(&hooks);
}
