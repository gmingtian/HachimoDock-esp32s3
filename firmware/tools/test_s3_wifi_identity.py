#!/usr/bin/env python3
"""Execute the production S3 PSA certificate writer on the host.

An isolated SDK library build uses software crypto. The two compatibility
headers only satisfy ESP-IDF's extra includes, pointing at upstream private
headers; SDK source and configuration are never edited. Output is a disposable
TEST identity, never copied to firmware or a release artifact.
"""
import argparse
import os
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--idf-path', type=Path, default=os.environ.get('IDF_PATH'))
parser.add_argument('--work-dir', type=Path, required=True)
args = parser.parse_args()
if not args.idf_path:
    parser.error('--idf-path or IDF_PATH is required')
root = Path(__file__).resolve().parents[1]
work = args.work_dir.resolve()
work.mkdir(parents=True, exist_ok=True)
sdk = args.idf_path.resolve()/'components/mbedtls/mbedtls'
crypto = sdk/'tf-psa-crypto'
shim = work/'shim/mbedtls'
shim.mkdir(parents=True, exist_ok=True)
for name in ('bignum', 'ecp'):
    (shim/f'{name}.h').write_text(f'#include "mbedtls/private/{name}.h"\n')
build = work/'mbedtls'
subprocess.run(['cmake','-S',str(sdk),'-B',str(build),'-DENABLE_TESTING=OFF','-DENABLE_PROGRAMS=OFF','-DGEN_FILES=OFF',f'-DCMAKE_C_FLAGS=-I{shim.parent}'],check=True)
subprocess.run(['cmake','--build',str(build),'-j4'],check=True)
source = (root/'s3/pet_s3_wifi.c').read_text()
writer = source[source.index('static bool make_identity(void)'):source.index('static void wifi_event(')]
harness = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include <sys/random.h>
#include "mbedtls/pk.h"
#include "mbedtls/x509_crt.h"
#include "mbedtls/oid.h"
#include "psa/crypto.h"
static bool identity_ready;
static char certificate[2048],private_key[512],credential[65];
static char hostname[]="esp32-s3-fixture.local";
static bool persist(void){return true;}
static void esp_fill_random(void *p,size_t n){assert(getrandom(p,n,0)==(long)n);}
''' + writer + r'''
int main(void){
 assert(make_identity());assert(strlen(credential)==64);
 FILE *f=fopen("certificate.pem","w");assert(f);fputs(certificate,f);fclose(f);
 f=fopen("private-key.pem","w");assert(f);fputs(private_key,f);fclose(f);
 puts("Production PSA identity generation passed; disposable test identity only");
}
'''
file = work/'identity.c'
file.write_text(harness)
exe = work/'identity'
subprocess.run(['cc','-std=c11','-I'+str(sdk/'include'),'-I'+str(crypto/'include'),'-I'+str(crypto/'drivers/builtin/include'),str(file),str(build/'library/libmbedx509.a'),str(build/'tf-psa-crypto/core/libtfpsacrypto.a'),'-o',str(exe)],check=True)
old_mask=os.umask(0o077)
try:
    subprocess.run([str(exe)],cwd=work,check=True)
finally:
    os.umask(old_mask)
subprocess.run(['openssl','verify','-CAfile',str(work/'certificate.pem'),'-purpose','sslserver','-verify_hostname','esp32-s3-fixture.local',str(work/'certificate.pem')],check=True)
