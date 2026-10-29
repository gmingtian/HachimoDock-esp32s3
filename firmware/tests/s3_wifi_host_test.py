"""Run portable and real ingress coordinator tests without an ESP board."""
import pathlib
import subprocess
ROOT = pathlib.Path(__file__).resolve().parents[1]
def test_transport_ownership_and_framing(tmp_path):
    binary = tmp_path / 'transport'
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-I'+str(ROOT/'s3'), str(ROOT/'tests/s3_transport_test.c'), str(ROOT/'s3/pet_s3_transport.c'), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
def test_actual_protocol_session_and_raw_isolation(tmp_path):
    binary = tmp_path / 'session'
    cjson = ROOT / 'tests/vendor/cjson'
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-I'+str(ROOT/'s3'), '-I'+str(cjson), str(ROOT/'tests/s3_protocol_session_test.c'), str(ROOT/'s3/pet_s3_transport.c'), str(cjson/'cJSON.c'), '-lm', '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)

def test_capture_replies_keep_the_session_generation(tmp_path):
    source = (ROOT/'main/pet_p4_audio.c').read_text()
    function = source[source.index('static void send_topic('):source.index('\nvoid pet_p4_audio_diagnostic(')]
    code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include "cJSON.h"
#define CONFIG_IDF_TARGET_ESP32S3 1
#define portENTER_CRITICAL(p) ((void)(p))
#define portEXIT_CRITICAL(p) ((void)(p))
typedef void (*pet_p4_send_line_fn)(const char*,void*);
static int g_send_lock;
static void *g_audio_task=(void*)2,*task=(void*)2,*observed;
static void *xTaskGetCurrentTaskHandle(void){return task;}
static char g_board_device_id[]="test-board";
static void sink(const char *s,void *ctx){cJSON *p=cJSON_Parse(s);assert(p);cJSON_Delete(p);observed=ctx;}
static pet_p4_send_line_fn g_send_line=sink,g_capture_session_send=sink;
static void *g_send_ctx=(void*)23,*g_capture_session_ctx=(void*)19;
''' + function + r'''
int main(void){
 send_topic("audio/chunk",cJSON_CreateObject());assert(observed==(void*)19);
 g_send_ctx=(void*)27;send_topic("audio/end",cJSON_CreateObject());assert(observed==(void*)19);
 task=(void*)3;send_topic("audio/status",cJSON_CreateObject());assert(observed==(void*)27);
}
'''
    file = tmp_path/'capture.c';file.write_text(code)
    cjson=ROOT/'tests/vendor/cjson';binary=tmp_path/'capture'
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I'+str(cjson),str(file),str(cjson/'cJSON.c'),'-lm','-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)

def test_network_menu_requires_confirmation_and_refuses_busy_clear(tmp_path):
    source=(ROOT/'s3/pet_s3_input_menu.inc').read_text()
    function=source[source.index('static void pet_s3_menu_execute('):source.index('  g_s3_menu_visible=false;\n  if(selected>=PET_S3_MENU_COMMANDS)')]
    function += '\n(void)now_ms;(void)send_line;(void)ctx;\n}\n'
    code=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stddef.h>
typedef struct {bool asset_transfer_active;} pet_p4_runtime_state_t;
typedef void (*pet_p4_send_line_fn)(const char*,void*);
typedef struct {uint64_t ts_ms;} pet_p4_input_event_t;
static unsigned g_s3_menu_selected,g_s3_network_confirm,called,last_action;
static bool g_s3_network_menu=true,busy;
static char g_s3_network_notice[64];
static bool pet_p4_ota_active(void){return busy;}
static bool pet_p4_miniapp_transfer_active(void){return false;}
static bool pet_p4_audio_active(void){return false;}
static bool pet_p4_audio_playback_active(void){return false;}
static bool pet_p4_audio_conversation_active(void){return false;}
static bool pet_p4_audio_music_active(void){return false;}
static bool pet_s3_wifi_menu_action(unsigned action){called++;last_action=action;return true;}
''' + function + r'''
int main(void){pet_p4_runtime_state_t state={0};pet_p4_input_event_t event={.ts_ms=1};
 g_s3_menu_selected=3;pet_s3_menu_execute(&state,NULL,NULL,&event);assert(!called&&g_s3_network_confirm==3&&g_s3_menu_selected==0);
 pet_s3_menu_execute(&state,NULL,NULL,&event);assert(!called&&!g_s3_network_confirm);
 g_s3_menu_selected=2;pet_s3_menu_execute(&state,NULL,NULL,&event);assert(!called&&g_s3_network_confirm==2);
 g_s3_menu_selected=1;pet_s3_menu_execute(&state,NULL,NULL,&event);assert(called==1&&last_action==2);
 g_s3_menu_selected=3;pet_s3_menu_execute(&state,NULL,NULL,&event);busy=true;
 g_s3_menu_selected=1;pet_s3_menu_execute(&state,NULL,NULL,&event);assert(called==1&&g_s3_network_notice[0]);
}
'''
    file=tmp_path/'menu.c';file.write_text(code);binary=tmp_path/'menu'
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',str(file),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
