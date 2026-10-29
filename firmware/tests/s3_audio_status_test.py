"""Serialize the production status/metadata with real cJSON and hardware fixtures."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]

def test_audio_status_agrees_with_target_and_actual_dsp(tmp_path):
    source=(ROOT/'main/pet_p4_audio.c').read_text()
    metadata=source[source.index('static void add_conversation_metadata('):source.index('static atomic_bool g_stream_active;')]
    status=source[source.index('void pet_p4_audio_send_status('):source.index('static void send_audio_error(')]
    harness=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "cJSON.h"
#include "pet_target.h"
#include "pet_p4_audio_frontend.h"
#define PET_P4_AUDIO_SAMPLE_RATE 16000
#define PET_P4_AUDIO_CHANNELS 1
#define PET_P4_AUDIO_BITS_PER_SAMPLE 16
#define PET_P4_AUDIO_FRAME_MS 20
#define MALLOC_CAP_INTERNAL 1
#define MALLOC_CAP_8BIT 2
static atomic_bool g_conversation_starting,g_conversation_half_duplex,g_stream_active;
static atomic_uint g_capture_tx_last_us,g_capture_tx_max_us,g_stream_underruns,g_stream_received_bytes;
static void *g_audio_task,*g_speaker;
static bool dsp_ready,preparing,playback_ready;
static cJSON *serialized;
static bool pet_p4_audio_ready(void){return true;}
static bool pet_p4_audio_enabled(void){return true;}
static bool pet_p4_audio_active(void){return false;}
static bool pet_p4_audio_playback_ready(void){return playback_ready;}
static bool pet_p4_audio_playback_active(void){return false;}
static const char *pet_p4_audio_codec_name(void){return "fixture-microphone";}
static bool pet_p4_audio_conversation_active(void){return true;}
bool pet_p4_afe_ready(void){return dsp_ready;}
bool pet_p4_afe_preparing(void){return preparing;}
const char *pet_p4_afe_failure(void){return "fixture_failure";}
pet_p4_afe_metrics_t pet_p4_afe_metrics(void){return (pet_p4_afe_metrics_t){.frames=3};}
static void conversation_session_copy(char session[64]){strcpy(session,"fixture-session");}
static unsigned heap_caps_get_free_size(int caps){(void)caps;return 1024;}
static unsigned heap_caps_get_largest_free_block(int caps){(void)caps;return 512;}
static unsigned uxTaskGetStackHighWaterMark(void *task){(void)task;return 2048;}
static int esp_codec_dev_get_out_vol(void *speaker,int *out){(void)speaker;*out=75;return 0;}
static unsigned stream_buffered(void){return 0;}
static void send_topic(const char *topic,cJSON *payload){
 assert(!strcmp(topic,"audio/status"));char *wire=cJSON_PrintUnformatted(payload);
 serialized=cJSON_Parse(wire);assert(serialized);free(wire);cJSON_Delete(payload);
}
'''+metadata+status+r'''
static bool field(const char *key){return cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(serialized,key));}
int main(void){
 for(unsigned ready=0;ready<2;ready++){
  dsp_ready=ready;preparing=true;playback_ready=true;
  atomic_store(&g_conversation_starting,true);
  pet_p4_audio_send_status();
  assert(field("audioVad")==ready);
  assert(field("audioAec")==((bool)PET_TARGET_CALIBRATED_AEC&&ready));
  assert(field("audioFullDuplex")==((bool)PET_TARGET_CALIBRATED_AEC&&ready));
  assert(field("audioAecPreparing")==((bool)PET_TARGET_CALIBRATED_AEC));
  const char *codec=cJSON_GetObjectItemCaseSensitive(serialized,"playbackCodec")->valuestring;
#if CONFIG_IDF_TARGET_ESP32S3
  assert(!strcmp(codec,"MAX98357A"));
  assert(!strcmp(cJSON_GetObjectItemCaseSensitive(serialized,"aecReason")->valuestring,"uncalibrated_hardware"));
#else
  assert(!strcmp(codec,"ES8311"));
  assert(!strcmp(cJSON_GetObjectItemCaseSensitive(serialized,"aecReason")->valuestring,"fixture_failure"));
#endif
  cJSON_Delete(serialized);
 }
 playback_ready=false;pet_p4_audio_send_status();
 assert(!strcmp(cJSON_GetObjectItemCaseSensitive(serialized,"playbackCodec")->valuestring,"unavailable"));
 cJSON_Delete(serialized);
}
'''
    file=tmp_path/'status.c';file.write_text(harness)
    for target in [0,1]:
        binary=tmp_path/f'status-{target}'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',f'-DCONFIG_IDF_TARGET_ESP32S3={target}','-I',str(ROOT/'main'),'-I',str(ROOT/'tests/vendor/cjson'),str(file),str(ROOT/'tests/vendor/cjson/cJSON.c'),'-lm','-o',str(binary)],check=True)
        subprocess.run([str(binary)],check=True)
