/* Known built-ins requiring controls beyond the S3 three physical keys.
 * Keep in sync with component-policy.json; host tests verify the canonical list.
 * This projection preserves installed packages and saves for other targets. */
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
static inline bool pet_s3_component_allowed(const char *id) {
#if defined(CONFIG_IDF_TARGET_ESP32S3) && CONFIG_IDF_TARGET_ESP32S3
  static const char *const unsupported[] = {
    "block-combo", "fresh-fruit-slice", "cloud-hop", "bloomfrog_companion"
  };
  if (id) for (size_t i = 0; i < sizeof(unsupported)/sizeof(unsupported[0]); ++i)
    if (strcmp(id, unsupported[i]) == 0) return false;
#else
  (void)id;
#endif
  return true;
}
