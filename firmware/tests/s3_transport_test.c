#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "pet_s3_transport.h"
static char messages[4][64]; static unsigned received;
static bool line(void *ctx,const char *s) {(void)ctx;strcpy(messages[received++],s);return true;}
int main(void) {
  pet_s3_lease_t l={0};
  assert(!pet_s3_lease_claim(&l,7,0,false,false,false)); /* unpaired Wi-Fi */
  assert(pet_s3_lease_claim(&l,5,1,true,false,false));
  assert(!pet_s3_lease_claim(&l,7,2,true,false,false));
  assert(!pet_s3_lease_claim(&l,7,2,true,true,true)); /* busy takeover */
  assert(pet_s3_lease_claim(&l,7,2,true,true,false));
  assert(!pet_s3_lease_accept(&l,5,3)); /* stale source including raw bytes */
  assert(pet_s3_lease_accept(&l,7,3));
  assert(!pet_s3_lease_accept(&l,11,3)); /* same Wi-Fi, new generation */
  assert(pet_s3_lease_expired(&l,6004));
  pet_s3_lease_release(&l,5);assert(l.owner==7);
  pet_s3_lease_release(&l,7);assert(l.owner==0);
  char buf[64];pet_s3_framer_t f={.buffer=buf,.capacity=sizeof(buf)};
  assert(pet_s3_frame(&f,(const unsigned char*)"{\"a\":",5,line,0));assert(!received);
  assert(pet_s3_frame(&f,(const unsigned char*)"1}\n{\"b\":2}\n",11,line,0));
  assert(received==2&&!strcmp(messages[0],"{\"a\":1}")&&!strcmp(messages[1],"{\"b\":2}"));
  unsigned char huge[80];memset(huge,'x',sizeof(huge));assert(!pet_s3_frame(&f,huge,sizeof(huge),line,0));
  assert(!pet_s3_frame(&f,(const unsigned char*)"{}\n",3,line,0)); /* never resync an overflow */
  assert(pet_s3_secret_equal("abc","abc",3));assert(!pet_s3_secret_equal("abc","abd",3));
  assert(pet_s3_handshake_result(0,false,100,5000)==1);
  assert(pet_s3_handshake_result(-0x6900,true,100,5000)==0);
  assert(pet_s3_handshake_result(-0x6880,true,100,5000)==0);
  assert(pet_s3_handshake_result(-123,false,100,5000)==-1);
  assert(pet_s3_handshake_result(-0x6900,true,5000,5000)==-1);
  puts("S3 transport ownership/framing tests passed");
}
