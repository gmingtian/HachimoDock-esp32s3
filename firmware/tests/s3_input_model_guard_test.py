"""Execute the production config handler against real cJSON and a counted NVS stub."""
from pathlib import Path
import subprocess
from s3_official_input_test import function

ROOT=Path(__file__).resolve().parents[1]

def test_old_client_cannot_replace_a4_bindings(tmp_path):
    source=(ROOT/'main/pet_p4_input.c').read_text(encoding='utf-8')
    cjson=ROOT/'managed_components/espressif__cjson/cJSON'
    code=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "cJSON.h"
#define CONFIG_IDF_TARGET_ESP32S3 1
#define PET_S3_INPUT_MODEL "s3-a4-buttons-joystick-v1"
#define PET_P4_INPUT_CONFIG_VERSION 9
#define PET_P4_INPUT_MAX_BINDINGS 16
#define MALLOC_CAP_SPIRAM 1
#define MALLOC_CAP_8BIT 2
#define ESP_OK 0
#define ESP_LOGI(...) ((void)0)
typedef int esp_err_t;
typedef void (*pet_p4_send_line_fn)(const char*,void*);
typedef struct {char event[40],action[24],value[160];} pet_p4_input_binding_t;
typedef struct {uint32_t version,binding_count;pet_p4_input_binding_t bindings[16];} pet_p4_input_config_t;
static pet_p4_input_config_t g_config;
static unsigned allocations,writes;static bool ack;
static void *heap_caps_malloc(size_t n,int flags){(void)flags;allocations++;return malloc(n);}
static void copy_text(char *d,size_t n,const char *s){snprintf(d,n,"%s",s?s:"");}
static const char *json_string(const cJSON *p,const char *key){const cJSON *v=cJSON_GetObjectItemCaseSensitive(p,key);return cJSON_IsString(v)?v->valuestring:"";}
static bool apply_binding_json(pet_p4_input_config_t *c,const cJSON *p,char *e,size_t n){(void)c;(void)p;(void)e;(void)n;return true;}
static esp_err_t persist_config(const pet_p4_input_config_t *c){assert(c->binding_count==16);writes++;return ESP_OK;}
static const char *esp_err_to_name(esp_err_t e){(void)e;return "error";}
static void send_config_ack(pet_p4_send_line_fn s,void *c,bool legacy,const char *id,bool ok,unsigned count,const char *error){
 (void)s;(void)c;(void)legacy;(void)id;(void)count;ack=ok;if(!ok)assert(error&&strstr(error,"input model mismatch"));
}
'''
    for signature in ('static void add_default_binding(', 'static void load_default_config(', 'bool pet_p4_input_handle_config('):
        code+='\n'+function(source,signature)+'\n'
    code+=r'''
int main(void){
 g_config.binding_count=9;strcpy(g_config.bindings[0].action,"old_navigation");
 cJSON *old=cJSON_Parse("{\"requestId\":\"legacy\",\"bindings\":[]}");assert(old);
 assert(!pet_p4_input_handle_config(old,false,NULL,NULL));
 assert(!ack&&writes==0&&allocations==0&&g_config.binding_count==9);
 assert(!strcmp(g_config.bindings[0].action,"old_navigation"));cJSON_Delete(old);
 cJSON *fresh=cJSON_CreateObject();cJSON_AddStringToObject(fresh,"requestId","a4");
 cJSON_AddStringToObject(fresh,"inputModel",PET_S3_INPUT_MODEL);cJSON_AddBoolToObject(fresh,"reset",true);
 assert(pet_p4_input_handle_config(fresh,false,NULL,NULL));
 assert(ack&&writes==1&&allocations==1&&g_config.binding_count==16);
 cJSON_DeleteItemFromObjectCaseSensitive(fresh,"inputModel");
 assert(!pet_p4_input_handle_config(fresh,true,NULL,NULL));
 assert(!ack&&writes==1&&allocations==1&&g_config.binding_count==16);cJSON_Delete(fresh);
 return 0;
}
'''
    src=tmp_path/'guard.c';exe=tmp_path/'guard.exe';src.write_text(code,encoding='utf-8')
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I',str(cjson),str(src),str(cjson/'cJSON.c'),'-lm','-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
