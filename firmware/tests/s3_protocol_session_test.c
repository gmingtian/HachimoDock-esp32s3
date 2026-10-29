/* Execute the real S3 ingress coordinator and JSON parser, with hardware edges
 * replaced by deterministic sinks. No network/auth/body parser implementation
 * is duplicated here; this exercises ownership and raw-byte side effects. */
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include "cJSON.h"
#include "pet_s3_transport.h"
#define PET_P4_PROTOCOL_LINE_BUFFER_BYTES 32768
#define MALLOC_CAP_SPIRAM 0
#define MALLOC_CAP_8BIT 0
#define pdTRUE 1
#define pdMS_TO_TICKS(n) (n)
typedef struct {char board_device_id[64];bool asset_transfer_active;} pet_p4_runtime_state_t;
typedef struct {char *line;void *reply_ctx;size_t bytes;bool raw_input;} pet_p4_protocol_request_t;
static pet_p4_runtime_state_t g_state={.board_device_id="board-one"};
static uintptr_t g_s3_owner,g_s3_uart_token=5,g_s3_usb_token=10;
static int g_protocol_queue=1;
static uint64_t clock_ms=1;
static bool audio_busy,raw_active,widget_busy,ota_busy,capture_pending,stream_buffering;
static unsigned dispatches,cleanup_count,raw_received,hello_count;
static uintptr_t closed,authed;
static char replies[12][2048];static unsigned reply_count;
static uint64_t esp_timer_get_time(void){return clock_ms*1000;}
static bool pet_p4_miniapp_transfer_active(void){return widget_busy;}
static bool pet_p4_ota_active(void){return ota_busy;}
static bool pet_p4_audio_transport_busy(void){return audio_busy||capture_pending||stream_buffering;}
static void pet_p4_audio_conversation_set(bool a,bool b,void *c){(void)a;(void)b;(void)c;}
static void pet_p4_audio_capture_stop(void){}
static void pet_p4_audio_stream_flush(void){}
static void transport_send_line(const char *line,void *ctx){(void)ctx;assert(reply_count<12);snprintf(replies[reply_count++],2048,"%s",line);}
static void transport_send_audio_line(const char *line,void *ctx){transport_send_line(line,ctx);}
static void pet_p4_media_stop_background(void (*s)(const char*,void*),void *c){(void)s;(void)c;}
static void pet_p4_protocol_disconnect(pet_p4_runtime_state_t *s){s->asset_transfer_active=false;raw_active=false;cleanup_count++;}
static void pet_p4_miniapp_transfer_abort(void){widget_busy=false;}
static void pet_p4_ota_disconnect(void){ota_busy=false;}
static void pet_p4_audio_set_transport(void (*s)(const char*,void*),void *c){(void)s;(void)c;}
static void pet_s3_wifi_close(uintptr_t t){closed=t;}
static uintptr_t pet_s3_connection_token(unsigned route){static uintptr_t gen=20;return (++gen<<2)|route;}
static bool pet_s3_wifi_auth(const cJSON *p){const cJSON *v=cJSON_GetObjectItemCaseSensitive(p,"token");return cJSON_IsString(v)&&!strcmp(v->valuestring,"paired");}
static void pet_s3_wifi_authenticated(uintptr_t t){authed=t;}
static void pet_p4_send_hello(pet_p4_runtime_state_t *s,void (*f)(const char*,void*),void *c){(void)s;hello_count++;f("{\"topic\":\"hello\",\"payload\":{}}",c);}
static bool pet_s3_wifi_maintenance(const char *name,const cJSON *p,bool usb,bool busy,void (*f)(const char*,void*),void *c){(void)p;(void)usb;(void)busy;(void)f;(void)c;return !strcmp(name,"wifi/status");}
static bool maybe_handle_debug_line(const char *s,void *c){(void)s;(void)c;return false;}
static void pet_p4_handle_line(pet_p4_runtime_state_t *s,const char *line,void (*f)(const char*,void*),void *c){
  (void)s;(void)f;(void)c;cJSON *r=cJSON_Parse(line);assert(r);const cJSON *t=cJSON_GetObjectItemCaseSensitive(r,"topic");
  assert(cJSON_IsString(t));dispatches++;if(!strcmp(t->valuestring,"asset/raw")){raw_active=true;s->asset_transfer_active=true;}cJSON_Delete(r);
}
static void *heap_caps_malloc(size_t n,int flags){(void)flags;return malloc(n);}
static int xQueueSend(int q,const void *item,int timeout){(void)q;(void)item;(void)timeout;return 0;}
static bool pet_p4_raw_asset_chunk_active(void){return raw_active;}
static size_t pet_p4_consume_raw_asset_bytes(const uint8_t *b,size_t n,void (*f)(const char*,void*),void *ctx){(void)b;(void)f;(void)ctx;raw_received+=n;return n;}
static void s3_invalidate_route(uintptr_t token){g_s3_owner=0;unsigned route=token&3;if(route!=3)*(route==1?&g_s3_uart_token:&g_s3_usb_token)=pet_s3_connection_token(route);}
#include "../s3/pet_s3_protocol.inc"
static void feed(uintptr_t token,const char *s){s3_expire_owner();pet_p4_protocol_request_t r={.reply_ctx=(void*)token,.line=(char*)s,.bytes=strlen(s),.raw_input=true};s3_process_bytes(&r);}
static bool last_ok(void){cJSON *r=cJSON_Parse(replies[reply_count-1]);assert(r);bool ok=cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(cJSON_GetObjectItemCaseSensitive(r,"payload"),"ok"));cJSON_Delete(r);return ok;}
int main(void){
  feed(7,"{\"topic\":\"state\",\"payload\":{}}\n");assert(dispatches==0&&closed==7&&!g_s3_owner);
  feed(11,"{\"topic\":\"wifi/auth\",\"payload\":{\"token\":\"bad\",\"requestId\":\"a\"}}\n");assert(!last_ok()&&!g_s3_owner&&!hello_count);
  reply_count=0;feed(5,"{\"topic\":\"state\",\"payload\":{}}\n");assert(dispatches==1&&g_s3_owner==5);
  audio_busy=true;feed(15,"{\"topic\":\"wifi/auth\",\"payload\":{\"token\":\"paired\",\"takeover\":true}}\n");assert(!last_ok()&&g_s3_owner==5&&!cleanup_count);
  audio_busy=false;reply_count=0;feed(19,"{\"topic\":\"wifi/auth\",\"payload\":{\"token\":\"paired\",\"takeover\":true}}\n");assert(g_s3_owner==19&&cleanup_count==1&&authed==19&&hello_count==1);
  assert(strstr(replies[0],"wifi/auth")&&strstr(replies[1],"hello"));
  feed(5,"{\"topic\":\"state\",\"payload\":{}}\n");assert(dispatches==1); /* queued old USB */
  feed(19,"{\"topic\":\"asset/raw\",\"payload\":{}}\nBIN");assert(raw_received==3&&dispatches==2);
  feed(10,"not-owner-raw");assert(raw_received==3); /* USB bytes cannot consume Wi-Fi raw body */
  feed(19,"ARY");assert(raw_received==6);
  widget_busy=ota_busy=true;clock_ms=7002;s3_expire_owner();assert(!g_s3_owner&&!raw_active&&!widget_busy&&!ota_busy&&cleanup_count==2);
  feed(23,"{\"topic\":\"wifi/auth\",\"payload\":{\"token\":\"paired\"}}\n");assert(g_s3_owner==23);
  feed(23,"{\"topic\":\"sta");
  feed(19,"old\n");assert(g_s3_owner==23&&dispatches==2);
  feed(23,"te\",\"payload\":{}}\n");assert(g_s3_owner==23&&dispatches==3);
  assert(!s3_enqueue_bytes(23,(const uint8_t*)"x",2049));
  /* A background USB probe/malformed line must not poison future fallback. */
  reply_count=0;unsigned cleaned=cleanup_count;
  feed(10,"\n");assert(!g_s3_frames[2].failed && g_s3_owner==23 && cleanup_count==cleaned);
  feed(10,"{\"v\":1,\"type\":\"hello\",\"namespace\":\"desk\"}\n");
  assert(!g_s3_frames[2].failed && g_s3_owner==23 && hello_count==3);
  capture_pending=true;feed(23,"{\"topic\":\"transport/release\",\"payload\":{}}\n");assert(!last_ok() && g_s3_owner==23);
  reply_count=0;s3_protocol_line((void*)27,"{\"topic\":\"wifi/auth\",\"payload\":{\"token\":\"paired\",\"takeover\":true}}\n");assert(!last_ok() && g_s3_owner==23);
  capture_pending=false;stream_buffering=true;
  feed(23,"{\"topic\":\"transport/release\",\"payload\":{}}\n");assert(!last_ok() && g_s3_owner==23);
  s3_protocol_line((void*)31,"{\"topic\":\"wifi/auth\",\"payload\":{\"token\":\"paired\",\"takeover\":true}}\n");assert(!last_ok() && g_s3_owner==23);
  stream_buffering=false;feed(23,"{\"topic\":\"transport/release\",\"payload\":{}}\n");assert(last_ok() && !g_s3_owner);
  feed(10,"{\"topic\":\"state\",\"payload\":{}}\n");assert(g_s3_owner==10 && dispatches==4);
  puts("S3 real protocol ingress/session tests passed");
}
