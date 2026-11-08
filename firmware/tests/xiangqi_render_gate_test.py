"""The XQ scheduling gate may skip work only after a matching successful frame."""
from pathlib import Path
import os
import subprocess
from s3_native_video_row_test import function

ROOT = Path(__file__).resolve().parents[1]


def run_host(tmp_path, source):
    path = tmp_path/'xiangqi_gate.c'
    path.write_text(source, encoding='utf-8')
    binary = tmp_path/'xiangqi_gate.exe'
    if os.name == 'nt':
        vcvars = Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat')
        script = tmp_path/'xiangqi_gate.cmd'
        script.write_text(f'@call "{vcvars}" >nul\n@cl /nologo /std:c11 /utf-8 /W4 /WX /Zi /MD /fsanitize=address /I"{ROOT / "main"}" "{path}" /Fo"{tmp_path / "xiangqi_gate.obj"}" /Fd"{tmp_path / "xiangqi_gate.pdb"}" /Fe"{binary}" /link /INCREMENTAL:NO\n@if errorlevel 1 exit /b 1\n@"{binary}"\n', encoding='utf-8')
        subprocess.run(['cmd', '/c', str(script)], check=True)
    else:
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined', '-I', str(ROOT/'main'), str(path), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


def test_xiangqi_render_schedule_invalidations(tmp_path):
    header = ROOT/'main/pet_p4_xiangqi_render_gate.h'
    assert header.exists(), 'Xiangqi needs a bounded static-frame scheduling gate'
    source = r'''
#include <assert.h>
#include "pet_p4_xiangqi_render_gate.h"
int main(void){
  pet_xq_render_gate_t gate={0};
  pet_xq_render_key_t key={.context=UINT64_C(0x100010001),.state_update=10,.view_revision=2,.widget_id="xiangqi-a4"};
  assert(pet_xq_render_needed(&gate,&key,true,false,100));
  /* Requesting a render does not publish a reference before LCD success. */
  assert(pet_xq_render_needed(&gate,&key,true,false,101));
  pet_xq_render_complete(&gate,&key,true,100);
  for(unsigned now=101;now<1100;now++)assert(!pet_xq_render_needed(&gate,&key,true,false,now));
  assert(pet_xq_render_needed(&gate,&key,true,false,1100));
  pet_xq_render_complete(&gate,&key,true,1100);
  assert(!pet_xq_render_needed(&gate,&key,true,false,1101));
  key.view_revision++;assert(pet_xq_render_needed(&gate,&key,true,false,1102));
  pet_xq_render_complete(&gate,&key,true,1102);
  key.state_update++;assert(pet_xq_render_needed(&gate,&key,true,false,1103));
  pet_xq_render_complete(&gate,&key,true,1103);
  /* Same widget and same view revision after reactivation has a new instance epoch. */
  key.context+=UINT64_C(1)<<24;assert(pet_xq_render_needed(&gate,&key,true,false,1104));
  pet_xq_render_complete(&gate,&key,true,1104);
  key.context++;assert(pet_xq_render_needed(&gate,&key,true,false,1105));
  pet_xq_render_complete(&gate,&key,true,1105);
  key.widget_id[0]='X';assert(pet_xq_render_needed(&gate,&key,true,false,1106));
  pet_xq_render_complete(&gate,&key,true,1106);
  /* Page exit/transfer/unsupported/animated surfaces cannot keep a prior reference. */
  assert(pet_xq_render_needed(&gate,&key,false,false,1107));assert(!gate.valid);
  assert(pet_xq_render_needed(&gate,&key,true,false,1108));
  pet_xq_render_complete(&gate,&key,true,1108);
  /* Active touch/approval/confirmation/conversation forces the old cadence;
   * disappearing overlays must also force a clean replacement frame. */
  assert(pet_xq_render_needed(&gate,&key,true,true,1109));assert(!gate.valid);
  assert(pet_xq_render_needed(&gate,&key,true,false,1110));
  pet_xq_render_complete(&gate,&key,true,1110);
  pet_xq_render_complete(&gate,&key,false,1111);assert(!gate.valid);
  assert(pet_xq_render_needed(&gate,&key,true,false,1112));
  pet_xq_render_complete(&gate,&key,true,1112);
  assert(pet_xq_render_needed(&gate,&key,true,false,100));
  pet_xq_render_complete(&gate,&key,true,100);
  pet_xq_render_invalidate(&gate);assert(!gate.valid);
  assert(pet_xq_render_needed(&gate,&key,true,false,101));
  pet_xq_render_complete(&gate,&key,true,101);
  assert(pet_xq_render_needed(&gate,0,true,false,102));assert(!gate.valid);
  /* A normal 1Hz stats push costs one render per second, not a second
   * independent stream of heartbeat renders between those updates. */
  unsigned frames=0;pet_xq_render_invalidate(&gate);
  for(unsigned now=0;now<=5000;now+=50){
    if(now%1000==0)key.state_update++;
    if(pet_xq_render_needed(&gate,&key,true,false,now)){
      frames++;pet_xq_render_complete(&gate,&key,true,now);
    }
  }
  assert(frames==6);
  return 0;
}
'''
    run_host(tmp_path, source)


def test_production_main_adapter_rejects_dynamic_unknown_and_changed_instances(tmp_path):
    main = (ROOT/'main/pet_p4_main.c').read_text(encoding='utf-8')
    helpers = '\n'.join(function(main, name) for name in (
        'static void main_xiangqi_gate_reset(', 'static bool main_xiangqi_surface_static(',
        'static bool main_xiangqi_render_due('))
    source = r'''
#include <assert.h>
#include <stdlib.h>
#include "pet_p4_xiangqi_render_gate.h"
#define PET_P4_KEYFRAME_BG 1
#define PET_P4_PARTICLES 1
#define PET_SERVICE_BRIDGE_ENABLED 1
#define PET_P4_GAME_XIANGQI 6
#define MALLOC_CAP_SPIRAM 1
#define MALLOC_CAP_8BIT 2
typedef struct {bool floating;unsigned rotate_ms;} node;
typedef struct {bool app,game_view,media_touch,service_bridge;unsigned keyframes,particle_count,count;node nodes[2];} pet_surface_t;
typedef struct {bool active,app_surface,app_host,media,instrument,slicing;struct {int kind;} game;char widget_id[48];unsigned revision;} pet_p4_miniapp_view_t;
typedef struct {uint64_t last_update_ms;} pet_p4_runtime_state_t;
static pet_xq_render_gate_t g_xq_render_gate;
static pet_p4_miniapp_view_t g_xq_schedule_view,fixture_view;
static uint64_t g_xq_surface_context,fixture_context=100;
static bool g_xq_surface_known,g_xq_surface_static,view_unknown,surface_unknown,no_memory,race;
static unsigned surface_captures;
static pet_surface_t fixture_surface;
static void *heap_caps_malloc(size_t size,int caps){(void)caps;return no_memory?NULL:malloc(size);}
static void heap_caps_free(void *p){free(p);}
static bool pet_p4_miniapp_app_surface(pet_surface_t *p){surface_captures++;if(surface_unknown)return false;*p=fixture_surface;return true;}
static uint64_t pet_p4_miniapp_input_context(void){return fixture_context;}
static bool pet_p4_miniapp_get_view(pet_p4_miniapp_view_t *out){if(view_unknown)return false;*out=fixture_view;if(race)fixture_context++;return true;}
''' + helpers + r'''
int main(void){
  fixture_view.active=fixture_view.app_surface=true;fixture_view.game.kind=6;fixture_view.revision=1;
  memcpy(fixture_view.widget_id,"xiangqi-a4",11);
  fixture_surface.app=fixture_surface.game_view=true;fixture_surface.count=1;
  pet_p4_runtime_state_t state={.last_update_ms=10};pet_xq_render_key_t key={0};bool eligible;
  assert(main_xiangqi_render_due(&state,100,false,&key,&eligible)&&eligible&&surface_captures==1);
  pet_xq_render_complete(&g_xq_render_gate,&key,true,100);
  for(unsigned i=1;i<=18;i++)assert(!main_xiangqi_render_due(&state,100+i*50,false,&key,&eligible));
  assert(surface_captures==1);assert(main_xiangqi_render_due(&state,1100,false,&key,&eligible));
  pet_xq_render_complete(&g_xq_render_gate,&key,true,1100);
  fixture_view.revision++;assert(main_xiangqi_render_due(&state,1150,false,&key,&eligible));
  assert(surface_captures==1);pet_xq_render_complete(&g_xq_render_gate,&key,true,1150);
  fixture_context+=UINT64_C(1)<<24;assert(main_xiangqi_render_due(&state,1200,false,&key,&eligible));
  assert(surface_captures==2);pet_xq_render_complete(&g_xq_render_gate,&key,true,1200);
  assert(main_xiangqi_render_due(&state,1250,true,&key,&eligible)&&!eligible&&!g_xq_render_gate.valid);
  assert(main_xiangqi_render_due(&state,1300,false,&key,&eligible)&&eligible);
  pet_xq_render_complete(&g_xq_render_gate,&key,true,1300);
  view_unknown=true;assert(main_xiangqi_render_due(&state,1350,false,&key,&eligible)&&!eligible);
  view_unknown=false;assert(main_xiangqi_render_due(&state,1400,false,&key,&eligible)&&eligible);
  pet_xq_render_complete(&g_xq_render_gate,&key,true,1400);
  race=true;assert(main_xiangqi_render_due(&state,1450,false,&key,&eligible)&&!eligible);race=false;
  fixture_view.game.kind=5;assert(main_xiangqi_render_due(&state,1500,false,&key,&eligible)&&!eligible);
  fixture_view.game.kind=6;fixture_view.app_host=true;assert(main_xiangqi_render_due(&state,1550,false,&key,&eligible)&&!eligible);fixture_view.app_host=false;
  for(unsigned mode=0;mode<7;mode++){
    main_xiangqi_gate_reset();fixture_surface.nodes[0].floating=mode==0;fixture_surface.nodes[0].rotate_ms=mode==1;
    fixture_surface.keyframes=mode==2?2:0;fixture_surface.particle_count=mode==3?1:0;
    fixture_surface.service_bridge=mode==4;surface_unknown=mode==5;no_memory=mode==6;
    assert(main_xiangqi_render_due(&state,1600+mode,false,&key,&eligible)&&!eligible&&!g_xq_render_gate.valid);
  }
  return 0;
}
'''
    run_host(tmp_path, source)
