"""Exercise the production 240px home UI: session windows, paging and voice."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_native_home_keeps_selected_session_readable_and_within_panel(tmp_path):
    source = (ROOT / 'main/pet_p4_renderer.c').read_text()
    utf8 = source[source.index('static uint32_t utf8_next('):source.index('static uint8_t glyph_alpha_at(')]
    harness = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "pet_p4_view.h"
#include "pet_s3_render.h"
#include "pet_s3_menu.h"
typedef struct font font;
typedef struct { int adv_w,box_w,box_h,ofs_x,ofs_y,req_raw_bitmap; const font *resolved_font; } lv_font_glyph_dsc_t;
struct font {int line_height,base_line; const void *(*get_glyph_bitmap)(lv_font_glyph_dsc_t *,void *);};
static uint32_t rendered[10000],pending;static unsigned used;
static const void *bitmap(lv_font_glyph_dsc_t *g,void *b){(void)g;(void)b;assert(used<10000);rendered[used++]=pending;static uint8_t pixel=255;return &pixel;}
static const font pet_p4_font_cn_16={18,3,bitmap};
static uint16_t guarded[240*240+2],logical[640*480];
static uint16_t *g_native_framebuffer=guarded+1,*g_framebuffer=logical;
static uint16_t rgb565(uint8_t r,uint8_t g,uint8_t b){return ((r>>3)<<11)|((g>>2)<<5)|(b>>3);}
static uint16_t blend_rgb565(uint16_t d,uint8_t r,uint8_t g,uint8_t b,uint8_t a){(void)d;(void)a;return rgb565(r,g,b);}
static int glyph_width(uint32_t cp,uint32_t next){(void)next;return cp<128?8:16;}
static uint8_t glyph_alpha_at(const uint8_t *b,const lv_font_glyph_dsc_t *g,int x,int y){(void)b;(void)g;(void)x;(void)y;return 255;}
static bool lv_font_get_glyph_dsc(const font *f,lv_font_glyph_dsc_t *g,uint32_t cp,uint32_t next){(void)next;pending=cp;*g=(lv_font_glyph_dsc_t){.adv_w=cp<128?8:16,.box_w=1,.box_h=1,.resolved_font=f};return true;}
static void lv_font_glyph_release_draw_data(lv_font_glyph_dsc_t *g){(void)g;}
bool pet_s3_menu_snapshot(pet_s3_menu_view_t *out){memset(out,0,sizeof(*out));return false;}
bool pet_p4_state_host_connected(const pet_p4_runtime_state_t *s,unsigned long long now){(void)s;(void)now;return true;}
typedef struct {char title[64],widget_id[64];} pet_p4_miniapp_catalog_entry_t;
static size_t pet_p4_miniapp_catalog_count(void){return 0;}
static size_t pet_p4_miniapp_catalog_selected(void){return 0;}
static bool pet_p4_miniapp_catalog_get(size_t i,pet_p4_miniapp_catalog_entry_t *out){(void)i;(void)out;return false;}
''' + utf8 + r'''
#include "pet_s3_renderer_ui.inc"
static bool contains_pair(uint32_t a,uint32_t b){for(unsigned i=1;i<used;i++)if(rendered[i-1]==a&&rendered[i]==b)return true;return false;}
int main(void){
  static pet_p4_runtime_state_t state;
  pet_p4_view_model_t view={.page="main",.title="你",.body="你好，这是中文对话。",.show_bubble=true};
  guarded[0]=0x1234;guarded[240*240+1]=0xabcd;
  for(unsigned i=0;i<640*480;i++)logical[i]=0xffff;
  s3_native_navigation("components");s3_native_navigation("main");
  const char *line="中文测试abcdef";
  const char *next=s3_native_text_line(line,0,0,34,0xffff,false);
  assert(next==line+6); /* Two complete Chinese characters, no broken UTF-8. */
  next=s3_native_text_line("一\n二",0,0,220,0xffff,false);
  assert(!strcmp(next,"二"));
  used=0;s3_native_body("abcdefghijkl",0,0,18,2,0xffff,1000);
  assert(used==4 && rendered[0]=='a' && rendered[3]=='d');
  used=0;s3_native_body("abcdefghijkl",0,0,18,2,0xffff,4000);
  assert(used==4 && rendered[0]=='e' && rendered[3]=='h');
  used=0;s3_native_body("abcdefghijkl",0,0,18,2,0xffff,7000);
  assert(used==4 && rendered[0]=='i' && rendered[3]=='l');
  used=0;s3_native_body("ZYXW",0,0,18,2,0xffff,8000);
  assert(used==4 && rendered[0]=='Z');
  for(unsigned count=1;count<=8;count++){
    state.session_queue_count=count;
    for(unsigned i=0;i<count;i++){
      snprintf(state.session_queue[i].id,sizeof(state.session_queue[i].id),"session-%u",i);
      snprintf(state.session_queue[i].title,sizeof(state.session_queue[i].title),"会话%u",i);
      strcpy(state.session_queue[i].content,"状态变化：正在读取项目上下文。随后将检查代码并运行测试。请等待完成。");
      strcpy(state.session_queue[i].state,"working");
    }
    for(unsigned selected=0;selected<count;selected++){
      state.current_session_index=selected+1;
      pet_s3_home_layout_t layout=s3_native_home_layout(count,selected);
      assert(layout.visible==(count<3?count:3));
      assert(layout.first<=selected && selected<layout.first+layout.visible);
      assert(layout.cards_y>=90 && layout.pet_height>=60);
      int y=layout.cards_y;
      for(unsigned row=0;row<layout.visible;row++){
        unsigned index=layout.first+row;
        int h=s3_native_card_height(layout.visible,index==selected);
        assert(h>=(index==selected?68:24));
        y+=h+4;
      }
      assert(y-4==216);
      used=0;
      s3_native_home(&state,&view,1000);
      s3_native_home(&state,&view,4000);
      state.session_voice_active=true;used=0;s3_native_home(&state,&view,4100);state.session_voice_active=false;
      assert(contains_pair(0x5f55,0x97f3)); /* 录音 */
      assert(contains_pair(0x677e,0x5f00)); /* 松开 */
      assert(guarded[0]==0x1234 && guarded[240*240+1]==0xabcd);
    }
  }
  state.current_session_index=999;s3_native_home(&state,&view,5000);
  view.realtime_conversation=true;state.session_voice_active=true;used=0;
  s3_native_home(&state,&view,6000);
  assert(!contains_pair(0x4f1a,0x8bdd)); /* Agent 会话 must not leak into realtime chat. */
  assert(!contains_pair(0x5f55,0x97f3)); /* Stale PTT feedback must not cover captions. */
  state.session_voice_active=false;
  state.session_queue_count=0;
  view.show_bubble=false;view.realtime_conversation=false;
  s3_native_home(&state,&view,7000);
  state.session_voice_active=true;used=0;s3_native_home(&state,&view,8000);
  assert(contains_pair(0x677e,0x5f00));
  assert(guarded[0]==0x1234 && guarded[240*240+1]==0xabcd);
  return 0;
}
'''
    c = tmp_path / 'native.c'
    c.write_text(harness)
    exe = tmp_path / 'native'
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-fsanitize=undefined',
                    '-I', str(ROOT/'main'), '-I', str(ROOT/'s3'), str(c), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)


def test_confirm_hold_cannot_stop_realtime_capture(tmp_path):
    source = (ROOT/'s3/pet_s3_input_menu.inc').read_text()
    start = source.index('static void pet_s3_process_key(')
    end = source.index('  if(action==PET_S3_ACTION_BACK)', start)
    prefix = source[start:end] + '\n(void)app;\n}\n'
    harness = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "pet_p4_protocol.h"
#include "pet_s3_keys.h"
#define ESP_OK 0
typedef int esp_err_t;
typedef struct {unsigned delta;uint64_t ts_ms;} pet_p4_input_event_t;
static bool requested;static unsigned starts,stops,sends;
static bool pet_p4_conversation_active(const pet_p4_runtime_state_t *s){return s->conversation_state[0]!=0;}
static esp_err_t pet_p4_audio_capture_start(bool standalone){(void)standalone;starts++;if(requested)return -1;requested=true;return ESP_OK;}
static esp_err_t pet_p4_audio_capture_stop(void){stops++;requested=false;return ESP_OK;}
static void pet_s3_pointer_cancel(uint64_t now){(void)now;}
static void pet_s3_send_local(pet_p4_runtime_state_t *s,pet_p4_send_line_fn fn,void *ctx,const pet_p4_input_event_t *e,const char *action,const char *value,bool handled){(void)s;(void)fn;(void)ctx;(void)e;(void)value;assert(!strcmp(action,"voice_ptt"));(void)handled;sends++;}
''' + prefix + r'''
int main(void){
 static pet_p4_runtime_state_t state;
 strcpy(state.screen_page,"main");strcpy(state.conversation_state,"listening");requested=true;
 assert(pet_p4_conversation_active(&state));
 pet_p4_input_event_t event={.delta=PET_S3_ACTION_VOICE_START,.ts_ms=1000};
 pet_s3_process_key(&state,NULL,NULL,&event);
 event.delta=PET_S3_ACTION_VOICE_END;pet_s3_process_key(&state,NULL,NULL,&event);
 assert(starts==0&&stops==0&&requested&&sends==0&&!state.session_voice_active);
 state.conversation_state[0]=0;requested=false;
 event.delta=PET_S3_ACTION_VOICE_START;pet_s3_process_key(&state,NULL,NULL,&event);
 assert(starts==1&&requested&&state.session_voice_active&&sends==1);
 event.delta=PET_S3_ACTION_VOICE_END;pet_s3_process_key(&state,NULL,NULL,&event);
 assert(stops==1&&!requested&&!state.session_voice_active&&sends==2);
 event.delta=PET_S3_ACTION_VOICE_START;pet_s3_process_key(&state,NULL,NULL,&event);
 assert(starts==2&&requested&&state.session_voice_active);
 strcpy(state.conversation_state,"listening");
 event.delta=PET_S3_ACTION_VOICE_END;pet_s3_process_key(&state,NULL,NULL,&event);
 assert(stops==1&&requested&&!state.session_voice_active&&sends==3);
 pet_s3_process_key(NULL,NULL,NULL,&event);assert(stops==1);
 return 0;
}
'''
    c = tmp_path/'ptt.c'
    c.write_text(harness)
    exe = tmp_path/'ptt'
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=undefined',
                    '-I',str(ROOT/'main'),'-I',str(ROOT/'s3'),str(c),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
