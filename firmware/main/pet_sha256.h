#pragma once

/* ESP-IDF 5 uses the legacy Mbed TLS digest API; IDF 6.1 uses PSA Crypto. */
#if __has_include("mbedtls/sha256.h")
#include "mbedtls/sha256.h"
typedef mbedtls_sha256_context pet_sha256_context;
#define pet_sha256_init mbedtls_sha256_init
#define pet_sha256_free mbedtls_sha256_free
#define pet_sha256_starts mbedtls_sha256_starts
#define pet_sha256_update mbedtls_sha256_update
#define pet_sha256_finish mbedtls_sha256_finish
#define pet_sha256 mbedtls_sha256
#else
#include <stdbool.h>
#include <stddef.h>
#include "psa/crypto.h"

typedef psa_hash_operation_t pet_sha256_context;
static inline void pet_sha256_init(pet_sha256_context *context) {
  *context = (psa_hash_operation_t) PSA_HASH_OPERATION_INIT;
}
static inline void pet_sha256_free(pet_sha256_context *context) {
  (void) psa_hash_abort(context);
}
static inline int pet_sha256_starts(pet_sha256_context *context, int is224) {
  if (is224 || psa_crypto_init() != PSA_SUCCESS) return -1;
  return psa_hash_setup(context, PSA_ALG_SHA_256) == PSA_SUCCESS ? 0 : -1;
}
static inline int pet_sha256_update(pet_sha256_context *context,
                                      const unsigned char *data, size_t size) {
  return psa_hash_update(context, data, size) == PSA_SUCCESS ? 0 : -1;
}
static inline int pet_sha256_finish(pet_sha256_context *context,
                                      unsigned char output[32]) {
  size_t written = 0;
  return psa_hash_finish(context, output, 32, &written) == PSA_SUCCESS && written == 32 ? 0 : -1;
}
static inline int pet_sha256(const unsigned char *data, size_t size,
                               unsigned char output[32], int is224) {
  size_t written = 0;
  if (is224 || psa_crypto_init() != PSA_SUCCESS) return -1;
  return psa_hash_compute(PSA_ALG_SHA_256, data, size, output, 32, &written) == PSA_SUCCESS
      && written == 32 ? 0 : -1;
}
#endif
