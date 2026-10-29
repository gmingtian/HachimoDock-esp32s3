#include <assert.h>
#include "pet_s3_keys.h"

static unsigned sample(pet_s3_keys_t *keys, unsigned key, bool pressed, unsigned ms) {
  unsigned events = 0;
  for (unsigned i = 0; i < ms; i += 5) events |= pet_s3_keys_update(keys, key, pressed, 5);
  return events;
}
int main(void) {
  pet_s3_keys_t keys = {0};
  pet_s3_keys_init(&keys);
  // Bounce must not move the selection; a stable release moves exactly once.
  assert(sample(&keys, PET_S3_PREVIOUS, true, 10) == 0);
  assert(sample(&keys, PET_S3_PREVIOUS, false, 40) == 0);
  assert(sample(&keys, PET_S3_PREVIOUS, true, 100) == 0);
  assert(sample(&keys, PET_S3_PREVIOUS, false, 40) == PET_S3_ACTION_PREVIOUS);
  assert(sample(&keys, PET_S3_NEXT, true, 100) == 0);
  assert(sample(&keys, PET_S3_NEXT, false, 40) == PET_S3_ACTION_NEXT);
  assert(sample(&keys, PET_S3_CONFIRM, true, 100) == 0);
  assert(sample(&keys, PET_S3_CONFIRM, false, 40) == PET_S3_ACTION_CONFIRM);
  // A hold produces its long action exactly once and never a short action.
  assert(sample(&keys, PET_S3_PREVIOUS, true, 800) == PET_S3_ACTION_BACK);
  assert(sample(&keys, PET_S3_PREVIOUS, true, 800) == 0);
  assert(sample(&keys, PET_S3_PREVIOUS, false, 40) == 0);
  assert(sample(&keys, PET_S3_NEXT, true, 800) == PET_S3_ACTION_MENU);
  assert(sample(&keys, PET_S3_NEXT, false, 40) == 0);
  assert(sample(&keys, PET_S3_CONFIRM, true, 800) == PET_S3_ACTION_VOICE_START);
  assert(sample(&keys, PET_S3_CONFIRM, true, 800) == 0);
  assert(sample(&keys, PET_S3_CONFIRM, false, 40) == PET_S3_ACTION_VOICE_END);
  // A fresh confirm after voice release must work, without a stale hold.
  assert(sample(&keys, PET_S3_CONFIRM, true, 100) == 0);
  assert(sample(&keys, PET_S3_CONFIRM, false, 40) == PET_S3_ACTION_CONFIRM);
}
