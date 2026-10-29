/* Native-size navigation: 16 px text remains legible on the 240 px panel.
 * Components themselves retain their existing 640x480 semantic canvas. */
static void s3_native_rect(int x, int y, int width, int height, uint16_t color) {
  for (int py=y; py<y+height && py<PET_S3_PANEL_HEIGHT; ++py) {
    if (py<0) continue;
    for (int px=x; px<x+width && px<PET_S3_PANEL_WIDTH; ++px) {
      if (px>=0) g_native_framebuffer[py*PET_S3_PANEL_WIDTH+px]=color;
    }
  }
}
static const char *s3_native_text_line(const char *text, int x, int y, int max_width, uint16_t color, bool draw) {
  if (!text) return "";
  const char *start=text;
  const int right=x+max_width;
  while (*text) {
    const char *before=text;
    uint32_t cp=utf8_next(&text);
    if(cp=='\n')return text;
    if(cp=='\r')continue;
    lv_font_glyph_dsc_t glyph={0};
    if (!lv_font_get_glyph_dsc(&pet_p4_font_cn_16,&glyph,cp,utf8_peek(text))) {
      if(x+8>right)return before==start?text:before;
      x+=8;continue;
    }
    int advance=glyph_width(cp,utf8_peek(text))+1;
    if (x+advance>right)return before==start?text:before;
    if(!draw){x+=advance;continue;}
    glyph.req_raw_bitmap=1;
    const uint8_t *bitmap=(const uint8_t *)glyph.resolved_font->get_glyph_bitmap(&glyph,NULL);
    const int top=y+pet_p4_font_cn_16.line_height-pet_p4_font_cn_16.base_line-glyph.box_h-glyph.ofs_y;
    if (bitmap) for (int gy=0; gy<glyph.box_h; ++gy) {
      for (int gx=0; gx<glyph.box_w; ++gx) {
        int px=x+glyph.ofs_x+gx,py=top+gy;
        if (px<0||px>=240||py<0||py>=240)continue;
        uint8_t alpha=glyph_alpha_at(bitmap,&glyph,gx,gy);
        if (alpha) {
          uint16_t *pixel=g_native_framebuffer+py*240+px;
          *pixel=blend_rgb565(*pixel,((color>>11)&31)*255/31,((color>>5)&63)*255/63,(color&31)*255/31,alpha);
        }
      }
    }
    lv_font_glyph_release_draw_data(&glyph);
    x+=advance;
  }
  return text;
}
static void s3_native_text(const char *text, int x, int y, int max_width, uint16_t color) {
  (void)s3_native_text_line(text,x,y,max_width,color,true);
}

typedef struct {unsigned first,visible;int cards_y,pet_height;} pet_s3_home_layout_t;
static int s3_native_card_height(unsigned visible,bool selected) {
  return selected?68:visible>=3?24:44;
}
static pet_s3_home_layout_t s3_native_home_layout(unsigned count,unsigned selected) {
  pet_s3_home_layout_t out={.cards_y=216,.pet_height=188};
  if(!count)return out;
  if(selected>=count)selected=0;
  out.visible=count<3?count:3;
  if(count>out.visible) {
    if(selected>=count-1)out.first=count-out.visible;
    else if(selected>0)out.first=selected-1;
  }
  int height=(int)(out.visible-1)*4;
  for(unsigned i=0;i<out.visible;i++)height+=s3_native_card_height(out.visible,out.first+i==selected);
  out.cards_y-=height;
  out.pet_height=out.cards_y-28;
  return out;
}
static const char *s3_native_status_name(const char *status) {
  if(!status)return "休息中";
  if(!strcmp(status,"working")||!strcmp(status,"tool_running"))return "正在执行";
  if(!strcmp(status,"speaking"))return "正在回答";
  if(!strcmp(status,"waiting_user"))return "等待确认";
  if(!strcmp(status,"done"))return "已完成";
  if(!strcmp(status,"error"))return "出现错误";
  return "休息中";
}
static void s3_native_body(const char *body,int x,int y,int width,unsigned lines,
    uint16_t color,uint64_t now_ms) {
  static uint32_t last_key;
  static uint64_t since_ms;
  const char *pages[32];unsigned count=0;
  const char *cursor=body?body:"";
  uint32_t key=2166136261U;
  for(const unsigned char *p=(const unsigned char *)cursor;*p;p++)key=(key^*p)*16777619U;
  if(key!=last_key||now_ms<since_ms){last_key=key;since_ms=now_ms;}
  do {
    pages[count++]=cursor;
    for(unsigned line=0;line<lines&&*cursor;line++)
      cursor=s3_native_text_line(cursor,0,0,width,0,false);
  }while(*cursor&&count<32);
  cursor=pages[(unsigned)((now_ms-since_ms)/2800ULL)%count];
  for(unsigned line=0;line<lines&&*cursor;line++)
    cursor=s3_native_text_line(cursor,x,y+(int)line*19,width,color,true);
}
static void s3_native_home(const pet_p4_runtime_state_t *state,const pet_p4_view_model_t *view,uint64_t now_ms) {
  const bool realtime=view&&view->realtime_conversation;
  unsigned count=!realtime&&state?state->session_queue_count:0;
  if(count>PET_P4_SESSION_QUEUE_MAX)count=PET_P4_SESSION_QUEUE_MAX;
  bool queue=count>0;
  unsigned selected=queue&&state->current_session_index>0?state->current_session_index-1:0;
  if(selected>=count)selected=0;
  bool voice=!realtime&&state&&state->session_voice_active;
  if(!queue&&(voice||(view&&view->show_bubble)))count=1;
  pet_s3_home_layout_t layout=s3_native_home_layout(count,selected);
  const uint16_t ink=rgb565(218,255,252),muted=rgb565(154,205,200);
  const uint16_t accent=rgb565(72,206,194),surface=rgb565(200,242,240);
  const uint16_t card_ink=rgb565(13,49,47),card_muted=rgb565(65,103,99);
  s3_native_rect(0,0,240,240,0);
  pet_s3_rect_t art;
  if(g_framebuffer&&pet_s3_fit_rect(640,480,240,layout.pet_height,&art)) {
    art.y+=22;
    for(int y=0;y<art.height;y++)for(int x=0;x<art.width;x++)
      g_native_framebuffer[(art.y+y)*240+art.x+x]=g_framebuffer[(y*480/art.height)*640+x*640/art.width];
  }
  const char *phase=queue?state->session_queue[selected].state:
    realtime&&state?state->conversation_state:state?state->current_state:"idle";
  const char *heading=voice?"正在录音":realtime?(view->conversation_history?"对话回看":"语音对话"):s3_native_status_name(phase);
  if(!realtime&&!voice&&!pet_p4_state_host_connected(state,now_ms))heading="等待电脑连接";
  s3_native_text(heading,8,1,180,ink);
  if(queue){char counter[24];snprintf(counter,sizeof(counter),"%u/%u",selected+1,count);s3_native_text(counter,195,1,42,muted);}
  int y=layout.cards_y;
  for(unsigned row=0;row<layout.visible;row++) {
    unsigned index=layout.first+row;
    bool active=index==selected;
    int height=s3_native_card_height(layout.visible,active);
    const pet_p4_session_queue_item_t *item=queue?&state->session_queue[index]:NULL;
    const char *title=item?item->title:view&&view->title&&view->title[0]?view->title:"桌宠";
    const char *body=item?(item->content[0]?item->content:s3_native_status_name(item->state)):
      view&&view->body?view->body:"";
    s3_native_rect(8,y,224,height,active?accent:rgb565(38,87,82));
    s3_native_rect(10,y+2,220,height-4,surface);
    s3_native_text(title,15,y+3,202,card_ink);
    if(active) {
      if(voice){title="正在录音";body="松开完成录音";
        s3_native_text(title,15,y+24,208,card_ink);s3_native_text(body,15,y+43,208,card_ink);}
      else s3_native_body(body,15,y+24,208,2,card_ink,now_ms);
    }else if(height>24)s3_native_text(body,15,y+23,208,card_muted);
    y+=height+4;
  }
  s3_native_text(realtime?"切换回看  长按返回退出":queue?"切换会话  按住说话":"长按下一项打开组件",8,220,224,muted);
}
static void s3_native_list_row(unsigned row, const char *text, bool selected) {
  const int y=35+(int)row*25;
  if (selected) s3_native_rect(5,y,230,24,rgb565(115,65,38));
  s3_native_text(text,10,y+2,218,selected?rgb565(255,244,218):rgb565(218,216,204));
}
static void s3_native_navigation(const char *page) {
  pet_s3_menu_view_t menu={0};
  bool has_menu=pet_s3_menu_snapshot(&menu);
  const uint16_t ink=rgb565(255,241,204),muted=rgb565(172,176,164);
  if (has_menu && menu.visible) {
    s3_native_rect(0,0,240,240,rgb565(14,20,17));
    s3_native_text(menu.title[0]?menu.title:"操作菜单",10,8,220,ink);
    unsigned visible=menu.count>menu.first?menu.count-menu.first:0;
    if (visible>PET_S3_MENU_VISIBLE_ROWS)visible=PET_S3_MENU_VISIBLE_ROWS;
    for(unsigned i=0;i<visible;++i)s3_native_list_row(i,menu.rows[i],i+menu.first==menu.selected);
    s3_native_text("上一项 / 下一项 / 确认",10,218,220,muted);
    return;
  }
  if (!strcmp(page,"components")) {
    size_t count=pet_p4_miniapp_catalog_count(),selected=pet_p4_miniapp_catalog_selected();
    if(selected>=count)selected=0;
    size_t first=selected/7*7;
    s3_native_rect(0,0,240,240,rgb565(14,20,17));
    char title[48];snprintf(title,sizeof(title),"组件中心 %u/%u",count?(unsigned)selected+1:0,(unsigned)count);
    s3_native_text(title,10,8,220,ink);
    for(size_t i=0;i<7&&first+i<count;++i) {
      pet_p4_miniapp_catalog_entry_t item={0};
      if(pet_p4_miniapp_catalog_get(first+i,&item))
        s3_native_list_row(i,item.title[0]?item.title:item.widget_id,first+i==selected);
    }
    if(!count)s3_native_text("还没有组件",10,65,220,ink);
    s3_native_text("上一项 / 下一项 / 确认",10,218,220,muted);
  } else if (has_menu && menu.pointer_visible) {
    int x=menu.pointer_x*240/640,y=30+menu.pointer_y*180/480;
    uint16_t color=menu.pointer_down?rgb565(255,110,70):rgb565(255,241,204);
    s3_native_rect(x-5,y,11,1,color);s3_native_rect(x,y-5,1,11,color);
  }
}
