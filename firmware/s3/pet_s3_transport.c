#include "pet_s3_transport.h"
bool pet_s3_lease_claim(pet_s3_lease_t *l,uintptr_t token,uint64_t now,bool authenticated,bool takeover,bool busy) {
  if(!token||!authenticated)return false;
  if(l->owner&&l->owner!=token&&(!takeover||busy))return false;
  l->owner=token;l->last_seen=now;return true;
}
bool pet_s3_lease_accept(pet_s3_lease_t *l,uintptr_t token,uint64_t now) {
  if(!token||l->owner!=token)return false;
  l->last_seen=now;return true;
}
bool pet_s3_lease_expired(const pet_s3_lease_t *l,uint64_t now) {return l->owner&&now-l->last_seen>6000;}
void pet_s3_lease_release(pet_s3_lease_t *l,uintptr_t token) {if(l->owner==token){l->owner=0;l->last_seen=0;}}
bool pet_s3_frame(pet_s3_framer_t *f,const unsigned char *data,size_t length,bool (*line)(void *,const char *),void *ctx) {
  if(f->failed)return false;
  for(size_t i=0;i<length;i++) {
    if(data[i]=='\r')continue;
    if(data[i]=='\n'){f->buffer[f->used]=0;if(f->used&&!line(ctx,f->buffer)){f->failed=true;return false;}f->used=0;}
    else if(!data[i]||f->used+1>=f->capacity){f->failed=true;return false;}
    else f->buffer[f->used++]=(char)data[i];
  }
  return true;
}
bool pet_s3_secret_equal(const char *a,const char *b,size_t size) {volatile unsigned char diff=0;for(size_t i=0;i<size;i++)diff|=(unsigned char)a[i]^(unsigned char)b[i];return diff==0;}
int pet_s3_handshake_result(int result,bool retryable,uint64_t now,uint64_t deadline) {
  if(now>=deadline)return -1;
  if(result==0)return 1;
  return retryable?0:-1;
}
