"""Reproduce S3 boot JSON memory pressure and synchronous SPIFFS lookup bursts."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_builtin_json_uses_psram_and_fails_without_consuming_internal_ram(tmp_path):
    sys.path.insert(0, str(ROOT / 'tools'))
    from build_builtin_bundle import render_bundle
    bundle = tmp_path / 'bundle.json'
    bundle.write_text(render_bundle())
    (tmp_path / 'esp_heap_caps.h').write_text('''#pragma once
#include <stddef.h>
#define MALLOC_CAP_SPIRAM 1
#define MALLOC_CAP_8BIT 2
void *heap_caps_malloc(size_t, unsigned);
void heap_caps_free(void *);
''')
    harness = tmp_path / 'json_memory.c'
    harness.write_text(r'''
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include "pet_s3_json_memory.h"
static size_t used,peak,calls,limit=4*1024*1024;
typedef union {max_align_t align;size_t size;} allocation;
void *heap_caps_malloc(size_t size,unsigned caps){
  assert(caps==(MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
  ++calls;if(size>limit-used)return NULL;
  allocation *p=malloc(sizeof(*p)+size);assert(p);p->size=size;
  used+=size;if(used>peak)peak=used;return p+1;
}
void heap_caps_free(void *ptr){if(ptr){allocation*p=(allocation*)ptr-1;used-=p->size;free(p);}}
int main(int argc,char **argv){
  assert(argc==2);FILE*f=fopen(argv[1],"rb");assert(f);
  char*bytes=calloc(1,170000);assert(bytes);assert(fread(bytes,1,169999,f)>0);fclose(f);
  pet_s3_json_memory_init();
  for(int i=0;i<3;i++){
    cJSON*tree=cJSON_Parse(bytes);assert(tree);
    assert(cJSON_GetArraySize(cJSON_GetObjectItemCaseSensitive(tree,"components"))>=25);
    char*wire=cJSON_PrintUnformatted(tree);assert(wire);cJSON_free(wire);
    cJSON_Delete(tree);assert(used==0);
  }
  assert(peak>150000&&calls>1000);
  limit=128;cJSON*failed=cJSON_Parse(bytes);assert(!failed&&used==0);
  free(bytes);return 0;
}
''')
    vendor = ROOT / 'tests/vendor/cjson'
    exe = tmp_path / 'json_memory'
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-I', str(tmp_path),
                    '-I', str(vendor), '-I', str(ROOT / 's3'),
                    str(harness), str(vendor / 'cJSON.c'), '-o', str(exe)], check=True)
    subprocess.run([str(exe), str(bundle)], check=True)
    main = (ROOT / 'main/pet_p4_main.c').read_text().split('void app_main(void)', 1)[1]
    assert main.index('pet_s3_json_memory_init();') < main.index('nvs_flash_init()')
    assert main.index('pet_s3_json_memory_init();') < main.index('xTaskCreate(')


def test_catalog_text_binary_and_missing_file_reads_release_cpu_for_idle(tmp_path):
    code = (ROOT / 'main/pet_p4_miniapp.c').read_text()
    start = code.index('static bool read_file(')
    end = code.index('bool pet_p4_miniapp_installed_id(', start)
    harness = tmp_path / 'catalog_reads.c'
    harness.write_text(r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static unsigned lookups,delays;
static void vTaskDelay(unsigned ticks){assert(ticks>0);++delays;}
static FILE *scan_open(const char*path,const char*mode){
  ++lookups;assert(delays>=lookups);return fopen(path,mode);
}
#define fopen scan_open
''' + code[start:end] + r'''
#undef fopen
int main(int argc,char**argv){
  assert(argc==2);char path[512];snprintf(path,sizeof(path),"%s/data",argv[1]);
  FILE*f=fopen(path,"wb");assert(f);assert(fwrite("hello",1,5,f)==5);fclose(f);
  for(int i=0;i<25;i++){
    char text[16];size_t n=0;uint8_t bytes[16];
    assert(read_file(path,text,sizeof(text))&&!strcmp(text,"hello"));
    assert(read_binary_file(path,bytes,sizeof(bytes),&n)&&n==5);
    assert(!read_binary_file(path,bytes,3,&n));
    assert(!read_file("/missing-s3-catalog-file",text,sizeof(text)));
    assert(!read_binary_file("/missing-s3-sprite-file",bytes,sizeof(bytes),&n));
  }
  assert(lookups==125&&delays==lookups);return 0;
}
''')
    exe = tmp_path / 'catalog_reads'
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', str(harness), '-o', str(exe)], check=True)
    subprocess.run([str(exe), str(tmp_path)], check=True)


def test_usb_hello_larger_than_driver_ring_is_transmitted_without_truncation(tmp_path):
    code = (ROOT / 'main/pet_p4_main.c').read_text()
    start = code.index('static void usb_queue_all(')
    end = code.index('static void usb_write_all(', start)
    harness = tmp_path / 'usb_queue.c'
    harness.write_text(r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#define pdMS_TO_TICKS(x) (x)
static unsigned char output[20000];
static size_t used,calls,fail_at;
static int usb_serial_jtag_write_bytes(const void*src,size_t size,unsigned timeout){
  assert(timeout>0);++calls;
  if(size>256||(fail_at&&calls>=fail_at))return 0;
  /* Also exercise a driver returning fewer bytes than requested. */
  size_t n=size>97?97:size;memcpy(output+used,src,n);used+=n;return (int)n;
}
''' + code[start:end] + r'''
int main(void){
  char input[12000];for(size_t i=0;i<sizeof(input);i++)input[i]=(char)(i%251);
  usb_queue_all(input,sizeof(input));
  assert(used==sizeof(input)&&!memcmp(input,output,used));
  used=0;calls=0;fail_at=2;usb_queue_all(input,sizeof(input));
  assert(calls==2&&used==97&&!memcmp(input,output,used));
  used=0;calls=0;usb_queue_all(input,0);assert(!calls&&!used);return 0;
}
''')
    exe = tmp_path / 'usb_queue'
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', str(harness), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
