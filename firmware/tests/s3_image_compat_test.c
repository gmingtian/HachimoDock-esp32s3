#include <assert.h>
#include <string.h>
#include "pet_p4_image_compat.h"

int main(void) {
  uint8_t image[24] = {0xe9};
  image[12] = 9; /* ESP32-S3, independently specified by esptool image format. */
  image[17] = 99;
  assert(pet_p4_image_header_matches(image, sizeof image, 0));
  assert(pet_p4_image_header_matches(image, sizeof image, 3));
  assert(!pet_p4_image_header_matches(image, 23, 0));
  assert(!pet_p4_image_header_matches(image, sizeof image, 100));
  image[12] = 18; /* A P4 image must never be accepted on S3. */
  assert(!pet_p4_image_header_matches(image, sizeof image, 0));
  image[12] = 9;
  image[0] = 0;
  assert(!pet_p4_image_header_matches(image, sizeof image, 0));
  assert(pet_p4_revision_range_valid(0, 99));
  assert(!pet_p4_revision_range_valid(99, 0));
  return 0;
}
