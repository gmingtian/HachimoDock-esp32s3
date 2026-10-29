/* [Input] ESP application header and actual chip revision (major * 100 + minor).
 * [Output] Fail-closed v1/v3 image compatibility checks, shared with host tests.
 * [Pos] Pure OTA guard; no UI or transport behavior. */
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

static inline bool pet_p4_revision_range_valid(uint16_t min, uint16_t max) {
#if defined(CONFIG_IDF_TARGET_ESP32S3) && CONFIG_IDF_TARGET_ESP32S3
  return min <= max;
#else
  return min <= max && ((min < 200 && max < 200) || (min >= 300 && max < 400));
#endif
}

static inline bool pet_p4_image_header_matches(
  const uint8_t *bytes, size_t length, uint16_t revision
) {
#if defined(CONFIG_IDF_TARGET_ESP32S3) && CONFIG_IDF_TARGET_ESP32S3
  const uint8_t chip_id = 9;
#else
  const uint8_t chip_id = 18;
#endif
  if (!bytes || length < 24 || bytes[0] != 0xe9 || bytes[12] != chip_id || bytes[13] != 0) return false;
  uint16_t min = (uint16_t) bytes[15] | ((uint16_t) bytes[16] << 8);
  uint16_t max = (uint16_t) bytes[17] | ((uint16_t) bytes[18] << 8);
  return pet_p4_revision_range_valid(min, max) && revision >= min && revision <= max;
}
