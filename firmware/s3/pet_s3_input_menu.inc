#include "pet_s3_menu.h"
#include "pet_s3_wifi.h"
#include "pet_p4_ota.h"
static bool g_s3_network_menu;
static unsigned g_s3_network_confirm;
static char g_s3_network_notice[64];
#include "pet_p4_touch_core.h"

static bool g_s3_menu_visible, g_s3_pointer_visible, g_s3_pointer_down;
static bool g_s3_pointer_vertical;
static unsigned g_s3_menu_selected;
static int g_s3_pointer_x=320,g_s3_pointer_y=240;
static uint64_t g_s3_menu_context,g_s3_pointer_last_ms;
static unsigned g_s3_pointer_step=16;
static const char *const g_s3_menu_commands[]={
  "关闭菜单","组件中心","返回桌宠","语音聊天","释放蓄力",
  "开关光标","切换横纵方向","光标按下或松开","光标点击",
  "切换步长4/16","向左划动","向右划动","向上划动","向下划动",
  "确认操作","取消操作","Wi-Fi 设置"
};
#define PET_S3_MENU_COMMANDS (sizeof(g_s3_menu_commands)/sizeof(g_s3_menu_commands[0]))
static void pet_s3_pointer_emit(pet_p4_pointer_kind_t kind,uint64_t now_ms) {
  pet_p4_pointer_event_t pointer={.kind=kind,.x=g_s3_pointer_x,.y=g_s3_pointer_y,.ts_ms=now_ms};
  pet_p4_miniapp_pointer(&pointer);
  g_s3_pointer_last_ms=now_ms;
}
static void pet_s3_pointer_cancel(uint64_t now_ms) {
  if(g_s3_pointer_down)pet_s3_pointer_emit(PET_P4_POINTER_CANCEL,now_ms);
  g_s3_pointer_down=false;
  pet_p4_miniapp_hold_event(NULL,2,1,now_ms);
}
static void pet_s3_pointer_move(int dx,int dy,uint64_t now_ms) {
  g_s3_pointer_x+=dx;g_s3_pointer_y+=dy;
  if(g_s3_pointer_x<0)g_s3_pointer_x=0;
  if(g_s3_pointer_x>639)g_s3_pointer_x=639;
  if(g_s3_pointer_y<0)g_s3_pointer_y=0;
  if(g_s3_pointer_y>479)g_s3_pointer_y=479;
  if(g_s3_pointer_down)pet_s3_pointer_emit(PET_P4_POINTER_MOVE,now_ms);
}
static void pet_s3_pointer_tap(uint64_t now_ms) {
  if(!g_s3_pointer_down)pet_s3_pointer_emit(PET_P4_POINTER_DOWN,now_ms);
  pet_s3_pointer_emit(PET_P4_POINTER_UP,now_ms);
  g_s3_pointer_down=false;
}
static unsigned pet_s3_menu_count(void) {
  if(g_s3_network_menu)return g_s3_network_confirm?2:5;
  return (unsigned)PET_S3_MENU_COMMANDS+(unsigned)pet_p4_miniapp_action_count();
}
/* Labels are presentation text; execution still uses the original action ID.
 * Pointer-only built-ins have no buttons.json label, so name those explicitly. */
static void pet_s3_action_label(unsigned index,char *out,size_t size) {
  if(pet_p4_miniapp_action_label(index,out,size))return;
  char action[PET_P4_MINIAPP_ACTION_MAX]={0};
  static const char *const labels[][2]={
    {"tomato.reset_phase","重置本轮"},{"host.fire","篝火声"},
    {"host.insects","虫鸣声"},{"host.rain","雨声"},{"host.sea","海浪声"},
    {"select.object","选择物品"},{"select.plant","选择植物"},
    {"host.row_a","选择第1项"},{"host.row_b","选择第2项"},
    {"host.row_c","选择第3项"},{"host.row_d","选择第4项"},{"host.row_e","选择第5项"},
    {"host.delete","删除笔记"},{"host.todo","转为待办"},{"stats.show_output","输出用量"}
  };
  if(pet_p4_miniapp_action_get(index,action,sizeof(action)))
    for(unsigned i=0;i<sizeof(labels)/sizeof(*labels);i++)if(!strcmp(action,labels[i][0])) {
      snprintf(out,size,"%s",labels[i][1]);return;
    }
  snprintf(out,size,"组件操作%u",index+1);
}
bool pet_s3_menu_snapshot(pet_s3_menu_view_t *out) {
  if(!out)return false;
  *out=(pet_s3_menu_view_t){.visible=g_s3_menu_visible,.selected=g_s3_menu_selected,
    .count=pet_s3_menu_count(),.pointer_visible=g_s3_pointer_visible,
    .pointer_down=g_s3_pointer_down,.pointer_x=g_s3_pointer_x,.pointer_y=g_s3_pointer_y};
  if(g_s3_network_menu){
    snprintf(out->title,sizeof(out->title),"%s",g_s3_network_confirm==3?"确认清除配网？":g_s3_network_confirm==2?"确认撤销所有绑定？":"Wi-Fi 设置");
    if(g_s3_network_confirm){snprintf(out->rows[0],64,"取消");snprintf(out->rows[1],64,"确认");}
    else {pet_s3_wifi_menu_status(out->rows[0],64);snprintf(out->rows[1],64,"开关 Wi-Fi");snprintf(out->rows[2],64,"撤销所有无线绑定");snprintf(out->rows[3],64,"清除配网和绑定");snprintf(out->rows[4],64,"%s",g_s3_network_notice[0]?g_s3_network_notice:"返回");}
    return out->visible;
  }
  snprintf(out->title,sizeof(out->title),"操作菜单：%s光标",g_s3_pointer_vertical?"纵向":"横向");
  out->first=g_s3_menu_selected/PET_S3_MENU_VISIBLE_ROWS*PET_S3_MENU_VISIBLE_ROWS;
  for(unsigned row=0;row<PET_S3_MENU_VISIBLE_ROWS;row++) {
    unsigned index=out->first+row;
    if(index>=out->count)break;
    if(index<PET_S3_MENU_COMMANDS)snprintf(out->rows[row],sizeof(out->rows[row]),"%s",g_s3_menu_commands[index]);
    else pet_s3_action_label(index-PET_S3_MENU_COMMANDS,out->rows[row],sizeof(out->rows[row]));
  }
  return out->visible||out->pointer_visible;
}
static void pet_s3_send_local(pet_p4_runtime_state_t *state,pet_p4_send_line_fn send_line,void *ctx,
    const pet_p4_input_event_t *event,const char *action,const char *value,bool handled) {
  pet_p4_input_binding_t binding={0};
  copy_text(binding.action,sizeof(binding.action),action);
  copy_text(binding.value,sizeof(binding.value),value);
  const char *prefix=button_event_prefix(event->control);
  char name[PET_P4_INPUT_EVENT_MAX];
  const char *gesture=event->delta==PET_S3_ACTION_VOICE_START?"hold_start":
    event->delta==PET_S3_ACTION_VOICE_END?"hold_end":
    (event->delta==PET_S3_ACTION_MENU||event->delta==PET_S3_ACTION_BACK)?"long_press":"short_press";
  snprintf(name,sizeof(name),"%s.%s",prefix,
    (event->delta==PET_S3_ACTION_VOICE_START||event->delta==PET_S3_ACTION_VOICE_END)?"hold":gesture);
  if(state)state->last_update_ms=event->ts_ms;
  send_input_event(state,send_line,ctx,event,name,gesture,&binding,value,handled);
}
static void pet_s3_menu_execute(pet_p4_runtime_state_t *state,pet_p4_send_line_fn send_line,void *ctx,
    const pet_p4_input_event_t *event) {
  unsigned selected=g_s3_menu_selected;
  uint64_t now_ms=event->ts_ms;
  if(g_s3_network_menu){
    if(g_s3_network_confirm){
      if(selected==1){
        bool busy=state->asset_transfer_active||pet_p4_ota_active()||pet_p4_miniapp_transfer_active()||pet_p4_audio_active()||pet_p4_audio_playback_active()||pet_p4_audio_conversation_active()||pet_p4_audio_music_active();
        if(busy)snprintf(g_s3_network_notice,sizeof(g_s3_network_notice),"请先停止录音或传输");
        else {bool ok=pet_s3_wifi_menu_action(g_s3_network_confirm);snprintf(g_s3_network_notice,sizeof(g_s3_network_notice),"%s",ok?"":"保存失败，请重试");}
      }
      g_s3_network_confirm=0;g_s3_menu_selected=0;
    }else if(selected==1){
      bool busy=state->asset_transfer_active||pet_p4_ota_active()||pet_p4_miniapp_transfer_active()||pet_p4_audio_active()||pet_p4_audio_playback_active()||pet_p4_audio_conversation_active()||pet_p4_audio_music_active();
      if(!busy){bool ok=pet_s3_wifi_menu_action(1);snprintf(g_s3_network_notice,sizeof(g_s3_network_notice),"%s",ok?"":"保存失败，请重试");}else snprintf(g_s3_network_notice,sizeof(g_s3_network_notice),"请先停止录音或传输");
    }else if(selected==2||selected==3){g_s3_network_confirm=selected;g_s3_menu_selected=0;}
    else if(selected==4){g_s3_network_menu=false;g_s3_menu_selected=0;}
    return;
  }
  g_s3_menu_visible=false;
  if(selected>=PET_S3_MENU_COMMANDS) {
    char action[PET_P4_MINIAPP_ACTION_MAX]={0};
    bool handled=pet_p4_miniapp_action_get(selected-PET_S3_MENU_COMMANDS,action,sizeof(action));
    if(handled) {
      // A software hold preserves charge/release games even though the physical
      // confirm hold is reserved for voice. The menu offers explicit release.
      handled=pet_p4_miniapp_hold_event(action,0,1,now_ms)
        ||pet_p4_miniapp_dispatch_action(action,now_ms);
    }
    pet_s3_send_local(state,send_line,ctx,event,"miniapp_action",action,handled);
    return;
  }
  bool handled=true;
  const char *action="s3_menu";
  switch(selected) {
    case 0:break;
    case 1:
      pet_s3_pointer_cancel(now_ms);g_s3_pointer_visible=false;
      pet_p4_miniapp_catalog_focus_active();
      copy_text(state->screen_page,sizeof(state->screen_page),"components");
      action="component_center";break;
    case 2:
      pet_s3_pointer_cancel(now_ms);g_s3_pointer_visible=false;
      copy_text(state->screen_page,sizeof(state->screen_page),"main");action="page_main";break;
    case 3:action="realtime_chat";handled=false;break;
    case 4:handled=pet_p4_miniapp_hold_event(NULL,1,1,now_ms);break;
    case 5:
      pet_s3_pointer_cancel(now_ms);g_s3_pointer_visible=!g_s3_pointer_visible;break;
    case 6:g_s3_pointer_vertical=!g_s3_pointer_vertical;g_s3_pointer_visible=true;break;
    case 7:
      g_s3_pointer_visible=true;
      g_s3_pointer_down=!g_s3_pointer_down;
      pet_s3_pointer_emit(g_s3_pointer_down?PET_P4_POINTER_DOWN:PET_P4_POINTER_UP,now_ms);break;
    case 8:g_s3_pointer_visible=true;pet_s3_pointer_tap(now_ms);break;
    case 9:g_s3_pointer_step=g_s3_pointer_step==16?4:16;g_s3_pointer_visible=true;break;
    case 10:case 11:case 12:case 13:
      g_s3_pointer_visible=true;
      pet_s3_pointer_cancel(now_ms);
      pet_s3_pointer_emit(PET_P4_POINTER_DOWN,now_ms);
      g_s3_pointer_down=true;
      pet_s3_pointer_move(selected==10?-160:selected==11?160:0,
        selected==12?-160:selected==13?160:0,now_ms);
      pet_s3_pointer_emit(PET_P4_POINTER_UP,now_ms);g_s3_pointer_down=false;break;
    case 14:handled=pet_p4_miniapp_dispatch_action("input.confirm",now_ms);break;
    case 15:handled=pet_p4_miniapp_dispatch_action("input.cancel",now_ms);break;
    case 16:g_s3_network_menu=true;g_s3_network_confirm=0;g_s3_menu_selected=0;g_s3_menu_visible=true;break;
    default:handled=false;break;
  }
  pet_s3_send_local(state,send_line,ctx,event,action,"",handled);
}
static void pet_s3_process_key(pet_p4_runtime_state_t *state,pet_p4_send_line_fn send_line,void *ctx,
    const pet_p4_input_event_t *event) {
  if(!state)return;
  unsigned action=event->delta;
  bool app=!strcmp(state->screen_page,"app");
  if(action==PET_S3_ACTION_VOICE_START||action==PET_S3_ACTION_VOICE_END) {
    /* Realtime conversation owns capture; PTT must not start or stop its mic. */
    if(pet_p4_conversation_active(state)){state->session_voice_active=false;return;}
    bool start=action==PET_S3_ACTION_VOICE_START;
    if(start)pet_s3_pointer_cancel(event->ts_ms);
    state->session_voice_active=start;
    esp_err_t err=start?pet_p4_audio_capture_start(state->session_queue_count==0):pet_p4_audio_capture_stop();
    if(start&&err!=ESP_OK)state->session_voice_active=false;
    pet_s3_send_local(state,send_line,ctx,event,"voice_ptt","",err==ESP_OK);
    return;
  }
  if(action==PET_S3_ACTION_BACK) {
    if(g_s3_menu_visible){g_s3_menu_visible=false;g_s3_network_menu=false;g_s3_network_confirm=0;return;}
    pet_s3_pointer_cancel(event->ts_ms);g_s3_pointer_visible=false;
    if(pet_p4_conversation_active(state)) {
      pet_s3_send_local(state,send_line,ctx,event,"realtime_chat","",false);return;
    }
    pet_p4_input_binding_t back={.action="page_back"};
    char value[PET_P4_MINIAPP_ACTION_MAX]={0};
    if(!strcmp(state->screen_page,"main"))pet_p4_media_stop_background(send_line,ctx);
    bool handled=apply_local_action(state,&back,event->ts_ms,value,sizeof(value));
    pet_s3_send_local(state,send_line,ctx,event,"page_back","",handled);return;
  }
  if(action==PET_S3_ACTION_MENU) {
    if(app) {
      g_s3_menu_visible=!g_s3_menu_visible;g_s3_menu_selected=0;g_s3_network_menu=false;g_s3_network_confirm=0;
      g_s3_menu_context=pet_p4_miniapp_input_context();
    } else {
      pet_p4_miniapp_catalog_focus_active();
      copy_text(state->screen_page,sizeof(state->screen_page),"components");
      pet_s3_send_local(state,send_line,ctx,event,"component_center","",true);
    }
    return;
  }
  if(g_s3_menu_visible) {
    unsigned count=pet_s3_menu_count();
    if(action==PET_S3_ACTION_PREVIOUS)g_s3_menu_selected=(g_s3_menu_selected+count-1)%count;
    else if(action==PET_S3_ACTION_NEXT)g_s3_menu_selected=(g_s3_menu_selected+1)%count;
    else if(action==PET_S3_ACTION_CONFIRM)pet_s3_menu_execute(state,send_line,ctx,event);
    state->last_update_ms=event->ts_ms;return;
  }
  if(app&&g_s3_pointer_visible) {
    int delta=action==PET_S3_ACTION_PREVIOUS?-(int)g_s3_pointer_step:(int)g_s3_pointer_step;
    if(action==PET_S3_ACTION_CONFIRM)pet_s3_pointer_tap(event->ts_ms);
    else pet_s3_pointer_move(g_s3_pointer_vertical?0:delta,g_s3_pointer_vertical?delta:0,event->ts_ms);
    state->last_update_ms=event->ts_ms;return;
  }
  if(app&&pet_p4_miniapp_confirmation(NULL,event->ts_ms)) {
    const char *confirm=action==PET_S3_ACTION_CONFIRM?"input.confirm":"input.cancel";
    bool handled=pet_p4_miniapp_dispatch_action(confirm,event->ts_ms);
    pet_s3_send_local(state,send_line,ctx,event,"miniapp_action",confirm,handled);return;
  }
  if(pet_p4_conversation_active(state)) {
    if(action==PET_S3_ACTION_PREVIOUS||action==PET_S3_ACTION_NEXT)
      pet_p4_conversation_move(state,action==PET_S3_ACTION_PREVIOUS?-1:1,event->ts_ms);
    return;
  }
  const char *physical=action==PET_S3_ACTION_PREVIOUS?"button.sw1.short_press":
    action==PET_S3_ACTION_NEXT?"button.sw2.short_press":"button.sw3.short_press";
  const pet_p4_input_binding_t *binding=active_binding(physical);
  bool factory=binding&&(!strcmp(binding->action,"session_previous")||!strcmp(binding->action,"session_next")||!strcmp(binding->action,"page_enter"));
  if(app&&factory) {
    // Keep package bindings intact; translate the three navigation concepts to
    // their upstream event vocabulary and expose every other action in the menu.
    const char *previous[]={"knob.rotate_ccw","joystick.up","button.sw3.short_press"};
    const char *next[]={"knob.rotate_cw","joystick.down","button.sw2.short_press"};
    const char *confirm[]={"button.sw1.short_press","button.encoder.short_press","screen.region.tap"};
    const char **events=action==PET_S3_ACTION_PREVIOUS?previous:action==PET_S3_ACTION_NEXT?next:confirm;
    for(unsigned i=0;i<3;i++)if(pet_p4_miniapp_has_input(events[i])) {
      char resolved[48]={0};
      bool handled=pet_p4_miniapp_dispatch_input(events[i],event->ts_ms,resolved,sizeof(resolved));
      pet_s3_send_local(state,send_line,ctx,event,"miniapp_action",resolved,handled);return;
    }
    // A component with pointer-only controls is still operable without a PC.
    g_s3_menu_visible=true;g_s3_menu_selected=PET_S3_MENU_COMMANDS;
    if(!pet_p4_miniapp_action_count())g_s3_menu_selected=0;
    g_s3_menu_context=pet_p4_miniapp_input_context();return;
  }
  dispatch_binding_event(state,send_line,ctx,event,physical,"short_press");
}
static void pet_s3_input_tick(pet_p4_runtime_state_t *state) {
  uint64_t now_ms=esp_timer_get_time()/1000ULL;
  if(!state||strcmp(state->screen_page,"app")) {
    g_s3_menu_visible=false;g_s3_pointer_visible=false;pet_s3_pointer_cancel(now_ms);return;
  }
  if(g_s3_menu_visible&&g_s3_menu_context!=pet_p4_miniapp_input_context()) {
    g_s3_menu_visible=false;pet_s3_pointer_cancel(now_ms);
  }
  if(g_s3_pointer_down&&now_ms-g_s3_pointer_last_ms>=50)
    pet_s3_pointer_emit(PET_P4_POINTER_MOVE,now_ms);
}
