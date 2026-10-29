#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
typedef struct { uintptr_t owner; uint64_t last_seen; } pet_s3_lease_t;
bool pet_s3_lease_claim(pet_s3_lease_t *,uintptr_t,uint64_t,bool,bool,bool);
bool pet_s3_lease_accept(pet_s3_lease_t *,uintptr_t,uint64_t);
bool pet_s3_lease_expired(const pet_s3_lease_t *,uint64_t);
void pet_s3_lease_release(pet_s3_lease_t *,uintptr_t);
typedef struct {char *buffer;size_t capacity,used;bool failed;} pet_s3_framer_t;
bool pet_s3_frame(pet_s3_framer_t *,const unsigned char *,size_t,bool (*)(void *,const char *),void *);
bool pet_s3_secret_equal(const char *,const char *,size_t);
/* ESP-TLS server async handshake returns zero on completion, negative WANT on
 * retry. Distinguish WANT from errors and enforce the absolute deadline. */
int pet_s3_handshake_result(int,bool,uint64_t,uint64_t);
