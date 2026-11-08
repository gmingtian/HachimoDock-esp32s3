"""Exercise the production page-entry block and native layer lifetime."""
from pathlib import Path
import subprocess
from s3_native_video_row_test import function
ROOT=Path(__file__).resolve().parents[1]

def run_c(tmp_path,code):
    src=tmp_path/'home_layer.c';src.write_text(code,encoding='utf-8')
    exe=tmp_path/'home_layer'
    subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
                    '-I',str(ROOT/'s3'),str(src),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

def test_native_home_reentry_keeps_clean_frame_and_invalidates_stale_identity(tmp_path):
    source=(ROOT/'main/pet_p4_renderer.c').read_text(encoding='utf-8')
    start=source.index('#if PET_S3_NATIVE_COMPOSITION\n  g_s3_native_composing=',source.index('esp_err_t pet_p4_renderer_render('))
    end=source.index('#endif',start)+len('#endif')
    entry=source[start:end]
    rewind_start=source.find('#if PET_S3_NATIVE_COMPOSITION\n  if(g_s3_native_hold_previous)')
    rewind=source[rewind_start:source.index('#endif',rewind_start)+len('#endif')] if rewind_start>=0 else ''
    reset=function(source,'void pet_p4_renderer_reset_playback(')
    transfer_start=source.index('#if PET_S3_NATIVE_COMPOSITION',source.index('esp_err_t pet_p4_renderer_render_transfer_status('))
    transfer=source[transfer_start:source.index('#endif',transfer_start)+len('#endif')]
    output_start=source.find('pet_s3_home_output_t native_output=pet_s3_home_layer_output(')
    output_call=source[output_start:source.index(';',output_start)+1] if output_start>=0 else ''
    header='#include "pet_s3_home_layer.h"\n' if (ROOT/'s3/pet_s3_home_layer.h').exists() else '''
typedef struct {bool valid;unsigned revision;int slot;uint64_t epoch,pending_since_ms;} pet_s3_home_layer_t;
'''
    code=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#define PET_S3_NATIVE_COMPOSITION 1
'''+header+r'''
static uint16_t clean[320*240+2],snapshot[320*240];
static uint16_t *g_s3_native_asset=clean+1;
static bool g_s3_native_composing,g_s3_native_asset_written,g_s3_native_previous_mode;
static bool g_s3_logical_asset_written,g_s3_native_hold_previous;
static bool g_s3_native_builtin_matte,g_s3_native_matte_applied;
#define PET_P4_BUILTIN_APPEARANCE_SLOT 0
static bool g_main_appearance_ready,g_session_overlay_cache_valid;
static int g_main_compact_underlay,g_asset_prepare_mux,active_slot;
static uint64_t g_asset_prepare_storage_epoch;
static pet_s3_home_layer_t g_s3_home_layer;
static uint16_t frames[2][320*240],*g_native_framebuffers[2]={frames[0],frames[1]},*g_native_framebuffer;
static unsigned g_native_framebuffer_index;
static bool g_last_native_valid;
static int g_behavior;
static char g_decoder_fs_path[80];
static void cancel_pending_asset_prepares(void){}
static void pet_p4_behavior_init(int*p){*p=0;}
static void reset_h264_decoder(void){}
static int pet_p4_asset_active_slot(void){return active_slot;}
#define portENTER_CRITICAL(p) ((void)(p))
#define portEXIT_CRITICAL(p) ((void)(p))
static void pet_compact_underlay_forget(int*p){*p=0;}
static void enter(const char *page,uint64_t now_ms,unsigned revision,int slot,uint64_t epoch){
  struct {unsigned asset_revision;} value={revision};
  const void *unused_state=&value;(void)unused_state;
  const typeof(value) *state=&value;
  active_slot=slot;g_asset_prepare_storage_epoch=epoch;
'''+entry+r'''
}
static void restore_presented(unsigned previous_native_index){
'''+rewind+r'''
}
static void transfer_begin(void){
'''+transfer+r'''
}
static pet_s3_home_output_t selected_output(bool g_asset_cache_pending,bool previous_valid,
    bool approval_visible,bool approval_changed,uint64_t now_ms){
  (void)approval_changed;
'''+output_call+r'''
  return native_output;
}
'''+reset+r'''
int main(void){
  for(unsigned i=0;i<320*240+2;i++)clean[i]=(uint16_t)(i|1);
  memcpy(snapshot,g_s3_native_asset,sizeof(snapshot));
  g_s3_home_layer=(pet_s3_home_layer_t){.valid=true,.revision=7,.slot=0,.epoch=5};
  enter("main",1000,7,0,5);
  assert(!memcmp(snapshot,g_s3_native_asset,sizeof(snapshot)));
  assert(g_main_appearance_ready);
  enter("app",1100,7,0,5);enter("components",1200,7,0,5);enter("main",1300,7,0,5);
  assert(!memcmp(snapshot,g_s3_native_asset,sizeof(snapshot))&&g_main_appearance_ready);
#ifdef PET_S3_HOME_LAYER_DEFINED
  assert(pet_s3_home_layer_output(&g_s3_home_layer,true,true,false,1300)==PET_S3_HOME_CLEAN);
  enter("main",1400,8,0,5);assert(!g_s3_home_layer.valid);
  assert(pet_s3_home_layer_output(&g_s3_home_layer,true,true,false,1400)==PET_S3_HOME_PREVIOUS);
  assert(pet_s3_home_layer_output(&g_s3_home_layer,true,true,false,3500)==PET_S3_HOME_PLACEHOLDER);
  assert(pet_s3_home_layer_output(&g_s3_home_layer,false,true,false,1500)==PET_S3_HOME_PLACEHOLDER);
  assert(pet_s3_home_layer_output(&g_s3_home_layer,true,false,false,1500)==PET_S3_HOME_PLACEHOLDER);
  assert(pet_s3_home_layer_output(&g_s3_home_layer,true,true,true,1500)==PET_S3_HOME_PLACEHOLDER);
  assert(selected_output(true,true,true,false,1500)==PET_S3_HOME_PLACEHOLDER);
  assert(selected_output(true,true,false,true,1500)==PET_S3_HOME_PLACEHOLDER);
  pet_s3_home_layer_publish(&g_s3_home_layer,false);assert(!g_s3_home_layer.valid);
  pet_s3_home_layer_publish(&g_s3_home_layer,true);assert(g_s3_home_layer.valid);
  enter("app",1600,8,0,5);enter("main",1700,8,1,5);assert(!g_s3_home_layer.valid);
  pet_s3_home_layer_publish(&g_s3_home_layer,true);
  enter("main",1800,8,1,6);assert(!g_s3_home_layer.valid);
  pet_s3_home_layer_publish(&g_s3_home_layer,true);
  pet_s3_home_layer_invalidate(&g_s3_home_layer);assert(!g_s3_home_layer.valid);
  frames[0][0]=0x1234;frames[1][0]=0x5678;
  g_s3_native_hold_previous=true;g_native_framebuffer_index=1;g_native_framebuffer=frames[1];
  restore_presented(0);assert(g_native_framebuffer_index==0&&g_native_framebuffer==frames[0]&&frames[0][0]==0x1234);
  g_s3_native_hold_previous=false;g_native_framebuffer_index=1;g_native_framebuffer=frames[1];
  restore_presented(0);assert(g_native_framebuffer_index==1&&g_native_framebuffer==frames[1]);
  pet_s3_home_layer_publish(&g_s3_home_layer,true);pet_p4_renderer_reset_playback();
  assert(!g_s3_home_layer.valid&&!g_last_native_valid);
  pet_s3_home_layer_publish(&g_s3_home_layer,true);transfer_begin();
  assert(!g_s3_home_layer.valid&&!g_s3_native_previous_mode&&!g_s3_native_hold_previous);
#endif
  assert(clean[0]==1&&clean[320*240+1]==(uint16_t)((320*240+1)|1));
  puts("PASS production home entry, retained clean pixels, identity changes, bounded pending and invalidation");
}
'''
    # Avoid compiler-specific anonymous-struct typeof in the host harness.
    code=code.replace('struct {unsigned asset_revision;} value={revision};','struct test_state {unsigned asset_revision;} value={revision};').replace('typeof(value)','struct test_state')
    run_c(tmp_path,code)
