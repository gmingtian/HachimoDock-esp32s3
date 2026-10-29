/* S3-only STA, per-board TLS identity and bounded single-owner network I/O. */
#include "pet_s3_wifi.h"
#include "pet_s3_transport.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <errno.h>
#include <fcntl.h>
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "esp_tls.h"
#include "esp_heap_caps.h"
#include "nvs.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "lwip/sockets.h"
#include "mbedtls/pk.h"
#include "mbedtls/x509_crt.h"
#include "mbedtls/oid.h"
#include "psa/crypto.h"
#define TX_BUDGET (128*1024)
#define TX_ITEMS 64
static char board_id[64],hostname[72],ssid[33],password[65],credential[65];
static char certificate[2048],private_key[512];
static bool enabled,configured,connected,identity_ready,initialized,scan_done;
static char ip[16];static int wifi_reason;
static unsigned address_epoch;
static uint64_t reconnect_at;static unsigned reconnect_delay=1000;
static uintptr_t next_generation=1,session,authenticated,close_session;
static SemaphoreHandle_t mutex;static QueueHandle_t tx_queue;static size_t tx_bytes;
static pet_s3_wifi_rx_fn receive_bytes;
typedef struct {uintptr_t token;size_t length;char *data;uint64_t deadline;} tx_item_t;
static uint64_t now_ms(void){return esp_timer_get_time()/1000;}
uintptr_t pet_s3_connection_token(unsigned route){uintptr_t gen=__atomic_fetch_add(&next_generation,1,__ATOMIC_RELAXED);return (gen<<2)|(route&3);}
static const char *jstr(const cJSON *o,const char *key){const cJSON *v=cJSON_GetObjectItemCaseSensitive(o,key);return cJSON_IsString(v)?v->valuestring:"";}
static bool persist(void) {
  nvs_handle_t h;if(nvs_open("pet_wifi",NVS_READWRITE,&h)!=ESP_OK)return false;
  esp_err_t e=nvs_set_str(h,"ssid",ssid);
  if(e==ESP_OK)e=nvs_set_str(h,"password",password);
  if(e==ESP_OK)e=nvs_set_u8(h,"enabled",enabled);
  if(e==ESP_OK)e=nvs_set_str(h,"token",credential);
  if(e==ESP_OK)e=nvs_set_str(h,"cert",certificate);
  if(e==ESP_OK)e=nvs_set_str(h,"key",private_key);
  if(e==ESP_OK)e=nvs_commit(h);nvs_close(h);return e==ESP_OK;
}
static bool make_identity(void) {
  if(identity_ready)return true;
  mbedtls_pk_context key;mbedtls_pk_init(&key);
  mbedtls_x509write_cert cert;mbedtls_x509write_crt_init(&cert);
  psa_key_attributes_t attrs=PSA_KEY_ATTRIBUTES_INIT;mbedtls_svc_key_id_t id=0;
  psa_set_key_type(&attrs,PSA_KEY_TYPE_ECC_KEY_PAIR(PSA_ECC_FAMILY_SECP_R1));
  psa_set_key_bits(&attrs,256);psa_set_key_usage_flags(&attrs,PSA_KEY_USAGE_EXPORT|PSA_KEY_USAGE_SIGN_HASH);
  psa_set_key_algorithm(&attrs,PSA_ALG_ECDSA(PSA_ALG_SHA_256));
  int err=psa_crypto_init();if(!err)err=psa_generate_key(&attrs,&id);
  if(!err)err=mbedtls_pk_copy_from_psa(id,&key);
  if(!err)err=mbedtls_pk_write_key_pem(&key,(unsigned char*)private_key,sizeof(private_key));
  unsigned char serial[16];esp_fill_random(serial,sizeof(serial));serial[0]&=0x7f;serial[0]|=1;
  char subject[100];snprintf(subject,sizeof(subject),"CN=%s",hostname);
  mbedtls_x509write_crt_set_version(&cert,MBEDTLS_X509_CRT_VERSION_3);
  mbedtls_x509write_crt_set_md_alg(&cert,MBEDTLS_MD_SHA256);
  mbedtls_x509write_crt_set_subject_key(&cert,&key);mbedtls_x509write_crt_set_issuer_key(&cert,&key);
  if(!err)err=mbedtls_x509write_crt_set_serial_raw(&cert,serial,sizeof(serial));
  if(!err)err=mbedtls_x509write_crt_set_subject_name(&cert,subject);
  if(!err)err=mbedtls_x509write_crt_set_issuer_name(&cert,subject);
  if(!err)err=mbedtls_x509write_crt_set_validity(&cert,"20200101000000","21000101000000");
  if(!err)err=mbedtls_x509write_crt_set_basic_constraints(&cert,0,-1);
  if(!err)err=mbedtls_x509write_crt_set_key_usage(&cert,MBEDTLS_X509_KU_DIGITAL_SIGNATURE);
  mbedtls_x509_san_list san={.node={.type=MBEDTLS_X509_SAN_DNS_NAME,
    .san.unstructured_name={.p=(unsigned char*)hostname,.len=strlen(hostname)}}};
  if(!err)err=mbedtls_x509write_crt_set_subject_alternative_name(&cert,&san);
  mbedtls_asn1_sequence eku={.buf={.tag=MBEDTLS_ASN1_OID,.len=MBEDTLS_OID_SIZE(MBEDTLS_OID_SERVER_AUTH),.p=(unsigned char*)MBEDTLS_OID_SERVER_AUTH}};
  if(!err)err=mbedtls_x509write_crt_set_ext_key_usage(&cert,&eku);
  if(!err)err=mbedtls_x509write_crt_pem(&cert,(unsigned char*)certificate,sizeof(certificate));
  mbedtls_x509write_crt_free(&cert);mbedtls_pk_free(&key);psa_destroy_key(id);psa_reset_key_attributes(&attrs);
  if(err){memset(private_key,0,sizeof(private_key));memset(certificate,0,sizeof(certificate));return false;}
  uint8_t random[32];esp_fill_random(random,sizeof(random));
  for(unsigned i=0;i<32;i++)snprintf(credential+i*2,3,"%02x",random[i]);memset(random,0,sizeof(random));
  identity_ready=persist();return identity_ready;
}
static void wifi_event(void *arg,esp_event_base_t base,int32_t event,void *data) {
  (void)arg;
  xSemaphoreTake(mutex,portMAX_DELAY);
  if(base==WIFI_EVENT&&event==WIFI_EVENT_SCAN_DONE)scan_done=true;
  if(base==IP_EVENT&&event==IP_EVENT_STA_GOT_IP){ip_event_got_ip_t *e=data;snprintf(ip,sizeof(ip),IPSTR,IP2STR(&e->ip_info.ip));connected=true;address_epoch++;wifi_reason=0;reconnect_delay=1000;}
  if(base==WIFI_EVENT&&event==WIFI_EVENT_STA_DISCONNECTED){connected=false;ip[0]=0;wifi_reason=((wifi_event_sta_disconnected_t*)data)->reason;close_session=session;reconnect_at=now_ms()+reconnect_delay;if(reconnect_delay<30000)reconnect_delay*=2;}
  xSemaphoreGive(mutex);
}
static esp_err_t apply_configuration(void) {
  (void)esp_wifi_disconnect();if(!enabled||!configured)return ESP_OK;
  wifi_config_t config={0};memcpy(config.sta.ssid,ssid,strlen(ssid));memcpy(config.sta.password,password,strlen(password));
  config.sta.pmf_cfg.capable=true;config.sta.threshold.authmode=WIFI_AUTH_OPEN;
  esp_err_t err=esp_wifi_set_config(WIFI_IF_STA,&config);if(err==ESP_OK)err=esp_wifi_connect();return err;
}
static void reply(const char *topic,cJSON *payload,const cJSON *request,void (*send)(const char*,void*),void *ctx) {
  cJSON_AddStringToObject(payload,"requestId",jstr(request,"requestId"));
  cJSON *root=cJSON_CreateObject();cJSON_AddStringToObject(root,"topic",topic);cJSON_AddItemToObject(root,"payload",payload);
  char *s=cJSON_PrintUnformatted(root);if(s){send(s,ctx);free(s);}cJSON_Delete(root);
}
static bool wifi_auth_failed(void) {
  return wifi_reason==WIFI_REASON_AUTH_FAIL||wifi_reason==WIFI_REASON_4WAY_HANDSHAKE_TIMEOUT
    ||wifi_reason==WIFI_REASON_HANDSHAKE_TIMEOUT;
}
static cJSON *status_payload(bool ok,const char *error) {
  xSemaphoreTake(mutex,portMAX_DELAY);
  cJSON *p=cJSON_CreateObject();cJSON_AddBoolToObject(p,"ok",ok);if(error)cJSON_AddStringToObject(p,"error",error);
  cJSON_AddBoolToObject(p,"clientConnected",authenticated!=0);
  cJSON_AddBoolToObject(p,"enabled",enabled);cJSON_AddBoolToObject(p,"configured",configured);cJSON_AddBoolToObject(p,"connected",connected);
  cJSON_AddStringToObject(p,"ssid",ssid);cJSON_AddStringToObject(p,"ip",ip);cJSON_AddStringToObject(p,"boardDeviceId",board_id);
  wifi_ap_record_t ap={0};esp_wifi_sta_get_ap_info(&ap);cJSON_AddNumberToObject(p,"rssi",ap.rssi);cJSON_AddNumberToObject(p,"port",PET_S3_WIFI_PORT);
  cJSON_AddStringToObject(p,"state",!configured?"not_configured":!enabled?"disabled":connected?"connected":wifi_auth_failed()?"wrong_password":"disconnected");xSemaphoreGive(mutex);return p;
}
bool pet_s3_wifi_auth(const cJSON *p) {
  if(!mutex)return false;
  const char *token=jstr(p,"token");bool ok;
  xSemaphoreTake(mutex,portMAX_DELAY);
  ok=identity_ready&&strlen(token)==64&&pet_s3_secret_equal(credential,token,64)&&!strcmp(jstr(p,"expectedBoardDeviceId"),board_id)&&jstr(p,"desktopDeviceId")[0];
  xSemaphoreGive(mutex);return ok;
}
void pet_s3_wifi_authenticated(uintptr_t token){if(!mutex)return;xSemaphoreTake(mutex,portMAX_DELAY);if(session==token)authenticated=token;xSemaphoreGive(mutex);}
void pet_s3_wifi_close(uintptr_t token){if(!mutex)return;xSemaphoreTake(mutex,portMAX_DELAY);if(!token||session==token)close_session=session;xSemaphoreGive(mutex);}
bool pet_s3_wifi_send(uintptr_t token,const char *line) {
  if(!mutex||!tx_queue)return false;
  size_t n=strlen(line);if(n+1>32768){pet_s3_wifi_close(token);return false;}
  tx_item_t item={.token=token,.length=n+1,.deadline=now_ms()+1000};
  xSemaphoreTake(mutex,portMAX_DELAY);
  if(session!=token||close_session==token||tx_bytes+n+1>TX_BUDGET){if(session==token)close_session=token;xSemaphoreGive(mutex);return false;}
  item.data=heap_caps_malloc(n+1,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
  if(!item.data){close_session=token;xSemaphoreGive(mutex);return false;}
  memcpy(item.data,line,n);item.data[n]='\n';
  if(xQueueSend(tx_queue,&item,0)!=pdTRUE){free(item.data);close_session=token;xSemaphoreGive(mutex);return false;}
  tx_bytes+=n+1;xSemaphoreGive(mutex);return true;
}
bool pet_s3_wifi_maintenance(const char *topic,const cJSON *p,bool usb,bool busy,void (*send)(const char*,void*),void *ctx) {
  if(strncmp(topic,"wifi/",5)||!strcmp(topic,"wifi/auth"))return false;
  const char *error=NULL;bool ok=true;const char *response=!strcmp(topic,"wifi/pair")?"wifi/pair":!strcmp(topic,"wifi/scan")?"wifi/scan":"wifi/status";cJSON *result=NULL;
  if(!mutex||!initialized){
    result=cJSON_CreateObject();cJSON_AddBoolToObject(result,"ok",false);cJSON_AddStringToObject(result,"error","wifi_unavailable");reply(response,result,p,send,ctx);return true;
  }
  bool secret=!strcmp(topic,"wifi/configure")||!strcmp(topic,"wifi/pair")||!strcmp(topic,"wifi/clear");
  if(secret&&!usb)error="usb_required";
  else if(strcmp(topic,"wifi/status")&&busy)error="device_busy";
  else if(!strcmp(topic,"wifi/status")){}
  else if(!strcmp(topic,"wifi/pair")){
    response="wifi/pair";xSemaphoreTake(mutex,portMAX_DELAY);ok=make_identity();
    if(ok){result=cJSON_CreateObject();cJSON_AddBoolToObject(result,"ok",true);cJSON_AddStringToObject(result,"boardDeviceId",board_id);cJSON_AddStringToObject(result,"hostname",hostname);cJSON_AddStringToObject(result,"certificatePem",certificate);cJSON_AddStringToObject(result,"token",credential);cJSON_AddStringToObject(result,"ip",ip);cJSON_AddNumberToObject(result,"port",PET_S3_WIFI_PORT);}xSemaphoreGive(mutex);if(!ok)error="identity_failed";
  } else if(!strcmp(topic,"wifi/configure")){
    const char *s=jstr(p,"ssid"),*pass=jstr(p,"password");
    if(!strlen(s)||strlen(s)>32||strlen(pass)>64)error="invalid_configuration";
    else {xSemaphoreTake(mutex,portMAX_DELAY);snprintf(ssid,sizeof(ssid),"%s",s);snprintf(password,sizeof(password),"%s",pass);enabled=true;configured=true;bool saved=persist();xSemaphoreGive(mutex);if(!saved||apply_configuration()!=ESP_OK)error="configuration_failed";}
  } else if(!strcmp(topic,"wifi/set_enabled")){
    const cJSON *v=cJSON_GetObjectItemCaseSensitive(p,"enabled");if(!cJSON_IsBool(v))error="invalid_enabled";
    else {xSemaphoreTake(mutex,portMAX_DELAY);enabled=cJSON_IsTrue(v);if(!enabled)close_session=session;bool saved=persist();xSemaphoreGive(mutex);if(!saved||apply_configuration()!=ESP_OK)error="configuration_failed";}
  } else if(!strcmp(topic,"wifi/clear")){if(!pet_s3_wifi_menu_action(3))error="configuration_failed";}
  else if(!strcmp(topic,"wifi/scan")){
    response="wifi/scan";wifi_scan_config_t scan={.show_hidden=true,.scan_type=WIFI_SCAN_TYPE_ACTIVE,.scan_time.active={.min=30,.max=90},.home_chan_dwell_time=30};
    xSemaphoreTake(mutex,portMAX_DELAY);scan_done=false;xSemaphoreGive(mutex);
    if(esp_wifi_scan_start(&scan,false)!=ESP_OK)error="scan_failed";
    else {
      uint64_t deadline=now_ms()+3500;bool done=false;
      while(now_ms()<deadline){xSemaphoreTake(mutex,portMAX_DELAY);done=scan_done;xSemaphoreGive(mutex);if(done)break;vTaskDelay(pdMS_TO_TICKS(10));}
      if(!done){esp_wifi_scan_stop();esp_wifi_clear_ap_list();error="scan_timeout";}
    }
    if(error){}
    else {wifi_ap_record_t aps[20];uint16_t count=20;esp_wifi_scan_get_ap_records(&count,aps);result=cJSON_CreateObject();cJSON_AddBoolToObject(result,"ok",true);cJSON *a=cJSON_AddArrayToObject(result,"networks");for(unsigned i=0;i<count;i++){cJSON *n=cJSON_CreateObject();char s[33]={0};memcpy(s,aps[i].ssid,32);cJSON_AddStringToObject(n,"ssid",s);cJSON_AddNumberToObject(n,"rssi",aps[i].rssi);cJSON_AddBoolToObject(n,"secure",aps[i].authmode!=WIFI_AUTH_OPEN);cJSON_AddItemToArray(a,n);}}
  } else error="unsupported_wifi_topic";
  if(!result)result=status_payload(!error,error);reply(response,result,p,send,ctx);return true;
}
void pet_s3_wifi_menu_status(char *out,size_t size){if(!mutex||!initialized){snprintf(out,size,"无线初始化失败");return;}xSemaphoreTake(mutex,portMAX_DELAY);snprintf(out,size,"%s %s",!configured?"未配网":!enabled?"已关闭":connected?"已连接":wifi_auth_failed()?"密码验证失败":"路由器离线",connected?ip:ssid);xSemaphoreGive(mutex);}
bool pet_s3_wifi_menu_action(unsigned action) {
  if(!mutex||!initialized)return false;
  xSemaphoreTake(mutex,portMAX_DELAY);close_session=session;
  if(action==1)enabled=!enabled;
  if(action==2||action==3){uint8_t random[32];esp_fill_random(random,sizeof(random));for(unsigned i=0;i<32;i++)snprintf(credential+2*i,3,"%02x",random[i]);memset(random,0,sizeof(random));}
  if(action==3){enabled=false;configured=false;memset(ssid,0,sizeof(ssid));memset(password,0,sizeof(password));}
  bool saved=persist();xSemaphoreGive(mutex);return saved&&apply_configuration()==ESP_OK;
}
/* Small DNS-SD responder: PTR/SRV/TXT/A, no discovery credentials. IPv4 only.
 * Names are uncompressed on output; input compression is bounded to 16 jumps. */
static bool dns_name(const uint8_t *p,size_t n,size_t *off,char *out,size_t cap) {
  size_t at=*off,used=0,resume=0;unsigned jumps=0;
  while(at<n){unsigned len=p[at++];if(!len){*off=resume?resume:at;out[used]=0;return true;}
    if((len&0xc0)==0xc0){if(at>=n||++jumps>16)return false;if(!resume)resume=at+1;at=((len&63)<<8)|p[at];continue;}
    if(len>63||at+len>n||used+len+1>=cap)return false;
    if(used)out[used++]='.';memcpy(out+used,p+at,len);used+=len;at+=len;
  }return false;
}
static void dns_u16(uint8_t *b,size_t *n,unsigned v){b[(*n)++]=v>>8;b[(*n)++]=v;}
static void dns_put_name(uint8_t *b,size_t *n,const char *s){while(*s){const char *dot=strchr(s,'.');size_t len=dot?(size_t)(dot-s):strlen(s);b[(*n)++]=len;memcpy(b+*n,s,len);*n+=len;if(!dot)break;s=dot+1;}b[(*n)++]=0;}
static void dns_record(uint8_t *b,size_t *n,const char *name,unsigned type,bool unique,const uint8_t *data,size_t len){dns_put_name(b,n,name);dns_u16(b,n,type);dns_u16(b,n,unique?0x8001:1);dns_u16(b,n,0);dns_u16(b,n,120);dns_u16(b,n,len);memcpy(b+*n,data,len);*n+=len;}
static void mdns_poll(int fd) {
  uint8_t query[512];struct sockaddr_in from;socklen_t flen=sizeof(from);int len=recvfrom(fd,query,sizeof(query),MSG_DONTWAIT,(struct sockaddr*)&from,&flen);
  if(len<12||(query[2]&0x80))return;unsigned count=(query[4]<<8)|query[5];if(count>20)return;
  bool match=false,unicast=false;size_t off=12;char name[256],instance[120];snprintf(instance,sizeof(instance),"%s._hachimodock._tcp.local",board_id);
  for(unsigned i=0;i<count;i++){if(!dns_name(query,len,&off,name,sizeof(name))||off+4>(size_t)len)return;unicast|=(query[off+2]&0x80)!=0;off+=4;if(!strcasecmp(name,"_hachimodock._tcp.local")||!strcasecmp(name,hostname)||!strcasecmp(name,instance)||!strcasecmp(name,"_services._dns-sd._udp.local"))match=true;}
  if(!match)return;
  xSemaphoreTake(mutex,portMAX_DELAY);bool available=connected&&enabled&&identity_ready;char address[16];memcpy(address,ip,sizeof(address));xSemaphoreGive(mutex);if(!available)return;
  uint8_t out[1024]={0},data[256];size_t n=12,d=0;out[2]=0x84;out[7]=5;
  dns_put_name(data,&d,"_hachimodock._tcp.local");dns_record(out,&n,"_services._dns-sd._udp.local",12,false,data,d);
  d=0;dns_put_name(data,&d,instance);dns_record(out,&n,"_hachimodock._tcp.local",12,false,data,d);
  d=0;dns_u16(data,&d,0);dns_u16(data,&d,0);dns_u16(data,&d,PET_S3_WIFI_PORT);dns_put_name(data,&d,hostname);dns_record(out,&n,instance,33,true,data,d);
  const char *txt="protocol=pet-wifi-tls-v1";d=strlen(txt);data[0]=d;memcpy(data+1,txt,d);dns_record(out,&n,instance,16,true,data,d+1);
  struct in_addr addr;inet_aton(address,&addr);dns_record(out,&n,hostname,1,true,(uint8_t*)&addr.s_addr,4);
  if(!unicast&&ntohs(from.sin_port)==5353){from.sin_addr.s_addr=inet_addr("224.0.0.251");from.sin_port=htons(5353);}else {out[0]=query[0];out[1]=query[1];}
  (void)sendto(fd,out,n,0,(struct sockaddr*)&from,sizeof(from));
}
static void network_task(void *arg) {
  (void)arg;int listener=socket(AF_INET,SOCK_STREAM,IPPROTO_TCP),mdns=socket(AF_INET,SOCK_DGRAM,IPPROTO_UDP);
  if(listener<0||mdns<0){if(listener>=0)close(listener);if(mdns>=0)close(mdns);initialized=false;vTaskDelete(NULL);return;}
  int yes=1;setsockopt(listener,SOL_SOCKET,SO_REUSEADDR,&yes,sizeof(yes));setsockopt(mdns,SOL_SOCKET,SO_REUSEADDR,&yes,sizeof(yes));
  struct sockaddr_in bindaddr={.sin_family=AF_INET,.sin_addr.s_addr=INADDR_ANY,.sin_port=htons(PET_S3_WIFI_PORT)};
  if(bind(listener,(struct sockaddr*)&bindaddr,sizeof(bindaddr))||listen(listener,1)){close(listener);close(mdns);initialized=false;vTaskDelete(NULL);return;}
  fcntl(listener,F_SETFL,O_NONBLOCK);bindaddr.sin_port=htons(5353);bind(mdns,(struct sockaddr*)&bindaddr,sizeof(bindaddr));
  struct ip_mreq membership={.imr_multiaddr.s_addr=inet_addr("224.0.0.251"),.imr_interface.s_addr=INADDR_ANY};unsigned joined_epoch=0;
  uint8_t ttl=255;setsockopt(mdns,IPPROTO_IP,IP_MULTICAST_TTL,&ttl,sizeof(ttl));
  for(;;) {
    mdns_poll(mdns);
    xSemaphoreTake(mutex,portMAX_DELAY);bool ready=enabled&&connected&&identity_ready;bool retry=enabled&&configured&&!connected&&now_ms()>=reconnect_at;if(retry)reconnect_at=now_ms()+30000;xSemaphoreGive(mutex);
    if(retry)(void)esp_wifi_connect();
    xSemaphoreTake(mutex,portMAX_DELAY);unsigned epoch=address_epoch;bool online=connected;struct in_addr current_address={0};if(online)inet_aton(ip,&current_address);xSemaphoreGive(mutex);
    if(online&&epoch!=joined_epoch){
      if(joined_epoch)setsockopt(mdns,IPPROTO_IP,IP_DROP_MEMBERSHIP,&membership,sizeof(membership));
      membership.imr_interface=current_address;
      if(setsockopt(mdns,IPPROTO_IP,IP_ADD_MEMBERSHIP,&membership,sizeof(membership))==0)joined_epoch=epoch;
    }
    int fd=accept(listener,NULL,NULL);if(fd<0){vTaskDelay(pdMS_TO_TICKS(20));continue;}if(!ready){close(fd);continue;}
    fcntl(fd,F_SETFL,O_NONBLOCK);
    esp_tls_t *tls=esp_tls_init();if(!tls){close(fd);continue;}
    esp_tls_cfg_server_t cfg={.servercert_buf=(unsigned char*)certificate,.servercert_bytes=strlen(certificate)+1,.serverkey_buf=(unsigned char*)private_key,.serverkey_bytes=strlen(private_key)+1,.tls_handshake_timeout_ms=5000};
    bool success=esp_tls_server_session_init(&cfg,fd,tls)==ESP_OK;uint64_t until=now_ms()+5000;
    while(success){int r=esp_tls_server_session_continue_async(tls);int progress=pet_s3_handshake_result(r,r==ESP_TLS_ERR_SSL_WANT_READ||r==ESP_TLS_ERR_SSL_WANT_WRITE,now_ms(),until);if(progress==1)break;if(progress<0){success=false;break;}vTaskDelay(pdMS_TO_TICKS(5));}
    uintptr_t token=pet_s3_connection_token(3);
    xSemaphoreTake(mutex,portMAX_DELAY);session=token;authenticated=0;close_session=0;xSemaphoreGive(mutex);
    until=now_ms()+5000;
    while(success) {
      xSemaphoreTake(mutex,portMAX_DELAY);bool stop=close_session==token||!connected||!enabled;bool authed=authenticated==token;xSemaphoreGive(mutex);
      if(!authed&&now_ms()>=until)break;
      tx_item_t item;
      while(xQueueReceive(tx_queue,&item,0)==pdTRUE){
        if(item.token==token){size_t offset=0;while(offset<item.length){if(now_ms()>=item.deadline){success=false;break;}int n=esp_tls_conn_write(tls,item.data+offset,item.length-offset);if(n>0){offset+=n;continue;}if((n!=ESP_TLS_ERR_SSL_WANT_READ&&n!=ESP_TLS_ERR_SSL_WANT_WRITE)||now_ms()>=item.deadline){success=false;break;}vTaskDelay(pdMS_TO_TICKS(2));}}
        free(item.data);xSemaphoreTake(mutex,portMAX_DELAY);tx_bytes-=item.length;xSemaphoreGive(mutex);if(!success)break;
      }
      if(!success||stop)break;
      uint8_t buffer[2048];int n=esp_tls_conn_read(tls,buffer,sizeof(buffer));
      if(n>0){if(!receive_bytes(token,buffer,n))break;}
      else if(n!=ESP_TLS_ERR_SSL_WANT_READ&&n!=ESP_TLS_ERR_SSL_WANT_WRITE)break;
      mdns_poll(mdns);vTaskDelay(pdMS_TO_TICKS(2));
    }
    xSemaphoreTake(mutex,portMAX_DELAY);session=0;authenticated=0;close_session=0;tx_item_t item;while(xQueueReceive(tx_queue,&item,0)==pdTRUE){free(item.data);}tx_bytes=0;xSemaphoreGive(mutex);
    /* Retry the close marker until serialized cleanup is guaranteed. */
    while(!receive_bytes(token,NULL,0))vTaskDelay(pdMS_TO_TICKS(10));
    esp_tls_conn_destroy(tls);
  }
}
esp_err_t pet_s3_wifi_init(const char *id,pet_s3_wifi_rx_fn rx) {
  snprintf(board_id,sizeof(board_id),"%s",id);snprintf(hostname,sizeof(hostname),"%s.local",id);receive_bytes=rx;
  mutex=xSemaphoreCreateMutex();tx_queue=xQueueCreate(TX_ITEMS,sizeof(tx_item_t));if(!mutex||!tx_queue)return ESP_ERR_NO_MEM;
  nvs_handle_t h;if(nvs_open("pet_wifi",NVS_READONLY,&h)==ESP_OK){size_t n=sizeof(ssid);nvs_get_str(h,"ssid",ssid,&n);n=sizeof(password);nvs_get_str(h,"password",password,&n);n=sizeof(credential);nvs_get_str(h,"token",credential,&n);n=sizeof(certificate);nvs_get_str(h,"cert",certificate,&n);n=sizeof(private_key);nvs_get_str(h,"key",private_key,&n);uint8_t on=0;nvs_get_u8(h,"enabled",&on);enabled=on;nvs_close(h);}
  configured=ssid[0];identity_ready=strlen(credential)==64&&certificate[0]&&private_key[0];
  esp_err_t e=esp_netif_init();if(e!=ESP_OK)return e;e=esp_event_loop_create_default();if(e!=ESP_OK&&e!=ESP_ERR_INVALID_STATE)return e;
  esp_netif_t *netif=esp_netif_create_default_wifi_sta();if(!netif)return ESP_ERR_NO_MEM;esp_netif_set_hostname(netif,board_id);
  wifi_init_config_t init=WIFI_INIT_CONFIG_DEFAULT();if((e=esp_wifi_init(&init))!=ESP_OK)return e;
  esp_wifi_set_storage(WIFI_STORAGE_RAM);esp_event_handler_register(WIFI_EVENT,ESP_EVENT_ANY_ID,wifi_event,NULL);esp_event_handler_register(IP_EVENT,IP_EVENT_STA_GOT_IP,wifi_event,NULL);
  esp_wifi_set_mode(WIFI_MODE_STA);if((e=esp_wifi_start())!=ESP_OK)return e;esp_wifi_set_ps(WIFI_PS_NONE);apply_configuration();
  initialized=true;
  if(xTaskCreate(network_task,"pet_wifi",12288,NULL,5,NULL)!=pdPASS){initialized=false;return ESP_ERR_NO_MEM;}
  return ESP_OK;
}
