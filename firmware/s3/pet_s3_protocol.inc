/* Included by the main coordinator: all ingress and lease changes run on the
 * protocol worker under g_state_mutex, including raw asset bytes and cleanup.
 * reply_ctx is an immutable integer generation/route, never a mutable pointer. */
static pet_s3_lease_t g_s3_lease;
static bool g_s3_cleanup_pending;
static pet_s3_framer_t g_s3_frames[4];
static uintptr_t g_s3_frame_tokens[4];
static bool s3_busy(void) {
  return g_state.asset_transfer_active||pet_p4_miniapp_transfer_active()||pet_p4_ota_active()
    ||pet_p4_audio_active()||pet_p4_audio_playback_active()||pet_p4_audio_conversation_active()
    ||pet_p4_audio_music_active();
}
static void s3_cleanup_owner(uintptr_t token) {
  if(g_s3_lease.owner!=token)return;
  g_s3_cleanup_pending=true;
  s3_invalidate_route(token);
  pet_s3_lease_release(&g_s3_lease,token);
  pet_p4_audio_conversation_set(false,true,NULL);pet_p4_audio_capture_stop();
  pet_p4_audio_stream_flush();pet_p4_media_stop_background(transport_send_line,(void*)token);
  pet_p4_protocol_disconnect(&g_state);pet_p4_miniapp_transfer_abort();pet_p4_ota_disconnect();
  pet_p4_audio_set_transport(transport_send_audio_line,(void*)token);
  unsigned route=token&3;g_s3_frames[route].used=0;g_s3_frames[route].failed=false;
  if(route==3)pet_s3_wifi_close(token);

}
static void s3_expire_owner(void) {
  if(g_s3_cleanup_pending&&!pet_p4_audio_active()&&!pet_p4_audio_playback_active())g_s3_cleanup_pending=false;
  if(pet_s3_lease_expired(&g_s3_lease,esp_timer_get_time()/1000))s3_cleanup_owner(g_s3_lease.owner);
}
static void s3_response(uintptr_t token,const char *topic,const cJSON *p,bool ok,const char *error) {
  cJSON *root=cJSON_CreateObject(),*payload=cJSON_CreateObject();cJSON_AddStringToObject(root,"topic",topic);cJSON_AddItemToObject(root,"payload",payload);
  cJSON_AddBoolToObject(payload,"ok",ok);const cJSON *id=cJSON_GetObjectItemCaseSensitive(p,"requestId");
  cJSON_AddStringToObject(payload,"requestId",cJSON_IsString(id)?id->valuestring:"");
  cJSON_AddStringToObject(payload,"boardDeviceId",g_state.board_device_id);if(error)cJSON_AddStringToObject(payload,"error",error);
  char *line=cJSON_PrintUnformatted(root);if(line){transport_send_line(line,(void*)token);free(line);}cJSON_Delete(root);
}
static bool s3_protocol_line(void *ctx,const char *line) {
  uintptr_t token=(uintptr_t)ctx;unsigned route=token&3;
  cJSON *root=cJSON_Parse(line);const cJSON *topic=root?cJSON_GetObjectItemCaseSensitive(root,"topic"):NULL;
  const cJSON *payload=root?cJSON_GetObjectItemCaseSensitive(root,"payload"):NULL;
  if(!cJSON_IsString(topic)||!cJSON_IsObject(payload)){cJSON_Delete(root);return false;}
  const char *name=topic->valuestring;bool authed=g_s3_lease.owner==token;
  if(!strcmp(name,"wifi/auth")){
    bool takeover=cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(payload,"takeover"));
    bool valid=route==3&&pet_s3_wifi_auth(payload);
    bool allowed=valid&&!g_s3_cleanup_pending&&(!g_s3_lease.owner||authed||(takeover&&!s3_busy()));
    if(allowed){if(g_s3_lease.owner&&g_s3_lease.owner!=token){s3_cleanup_owner(g_s3_lease.owner);g_s3_cleanup_pending=false;}
      pet_s3_lease_claim(&g_s3_lease,token,esp_timer_get_time()/1000,true,true,false);
      /* Queue auth before publishing the event destination. */
      s3_response(token,"wifi/auth",payload,true,NULL);pet_s3_wifi_authenticated(token);
      __atomic_store_n(&g_s3_owner,token,__ATOMIC_RELEASE);
      pet_p4_audio_set_transport(transport_send_audio_line,(void*)token);pet_p4_send_hello(&g_state,transport_send_line,(void*)token);
    }else s3_response(token,"wifi/auth",payload,false,!valid?"authentication_failed":(s3_busy()||g_s3_cleanup_pending)?"device_busy":"owner_active");
    cJSON_Delete(root);return allowed;
  }
  if(route==3&&!authed){cJSON_Delete(root);return false;}
  bool maintenance_busy=s3_busy();
  if(route!=3&&!maintenance_busy&&g_s3_lease.owner&&(g_s3_lease.owner&3)==3
      &&(!strcmp(name,"wifi/clear")||!strcmp(name,"wifi/configure"))) {
    s3_cleanup_owner(g_s3_lease.owner);
  }
  if(pet_s3_wifi_maintenance(name,payload,route!=3,maintenance_busy,transport_send_line,ctx)){
    /* Bounded scans may take 3.5 s; authenticated maintenance also renews the
     * host lease so the maintenance operation itself cannot expire its owner. */
    if(authed)pet_s3_lease_accept(&g_s3_lease,token,esp_timer_get_time()/1000);
    if(!maintenance_busy&&!strcmp(name,"wifi/set_enabled")
        &&cJSON_IsFalse(cJSON_GetObjectItemCaseSensitive(payload,"enabled"))
        &&g_s3_lease.owner&&(g_s3_lease.owner&3)==3)s3_cleanup_owner(g_s3_lease.owner);
    /* Disabling/clearing Wi-Fi closes through the same worker's close marker. */
    cJSON_Delete(root);return true;
  }
  if(!strcmp(name,"transport/release")){
    bool ok=authed&&!s3_busy();s3_response(token,"transport/status",payload,ok,!authed?"not_owner":!ok?"device_busy":NULL);
    if(ok)s3_cleanup_owner(token);
    cJSON_Delete(root);return true;
  }
  if(!authed&&route!=3&&!g_s3_lease.owner&&!g_s3_cleanup_pending){
    pet_s3_lease_claim(&g_s3_lease,token,esp_timer_get_time()/1000,true,false,false);
    __atomic_store_n(&g_s3_owner,token,__ATOMIC_RELEASE);pet_p4_audio_set_transport(transport_send_audio_line,ctx);authed=true;
  }
  if(!authed){s3_response(token,"transport/status",payload,false,"owner_active");cJSON_Delete(root);return true;}
  pet_s3_lease_accept(&g_s3_lease,token,esp_timer_get_time()/1000);cJSON_Delete(root);
  if(!maybe_handle_debug_line(line,ctx))pet_p4_handle_line(&g_state,line,transport_send_line,ctx);
  return true;
}
static bool s3_enqueue_bytes(uintptr_t token,const uint8_t *data,size_t len) {
  if(!g_protocol_queue||len>2048)return false;
  char *copy=NULL;if(len){copy=heap_caps_malloc(len,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);if(!copy)return false;memcpy(copy,data,len);}
  pet_p4_protocol_request_t request={.line=copy,.reply_ctx=(void*)token,.bytes=len,.raw_input=true};
  if(xQueueSend(g_protocol_queue,&request,pdMS_TO_TICKS(20))==pdTRUE)return true;
  free(copy);return false;
}
static void s3_process_bytes(const pet_p4_protocol_request_t *request) {
  uintptr_t token=(uintptr_t)request->reply_ctx;unsigned route=token&3;
  /* A late close or fragment must not reset a newer connection's parser. */
  if(route==3&&token<g_s3_frame_tokens[route])return;
  if(!request->bytes){s3_cleanup_owner(token);g_s3_frames[route].used=0;g_s3_frames[route].failed=false;return;}
  if(route!=3&&token!=__atomic_load_n(route==1?&g_s3_uart_token:&g_s3_usb_token,__ATOMIC_ACQUIRE))return;
  pet_s3_framer_t *f=&g_s3_frames[route];
  if(!f->buffer){f->capacity=PET_P4_PROTOCOL_LINE_BUFFER_BYTES;f->buffer=heap_caps_malloc(f->capacity,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);if(!f->buffer){if(route==3)pet_s3_wifi_close(token);return;}}
  if(g_s3_frame_tokens[route]!=token){f->used=0;f->failed=false;g_s3_frame_tokens[route]=token;}
  size_t offset=0;
  while(offset<request->bytes){
    /* Only the exact owner may enter the global raw block parser. */
    if(g_s3_lease.owner==token&&pet_p4_raw_asset_chunk_active()){
      size_t n=pet_p4_consume_raw_asset_bytes((uint8_t*)request->line+offset,request->bytes-offset,transport_send_line,(void*)token);
      if(!n){s3_cleanup_owner(token);return;}offset+=n;pet_s3_lease_accept(&g_s3_lease,token,esp_timer_get_time()/1000);continue;
    }
    if(!pet_s3_frame(f,(uint8_t*)request->line+offset,1,s3_protocol_line,(void*)token)){
      if(route==3)pet_s3_wifi_close(token);
      s3_cleanup_owner(token);return;
    }
    offset++;
  }
}
