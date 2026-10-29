"""Run real menu pointer movement: bounds, taps, continuous strokes and cancel."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]

def test_virtual_pointer_preserves_contact_lifecycle(tmp_path):
    source=(ROOT/'s3/pet_s3_input_menu.inc').read_text()
    body=source[source.index('static bool g_s3_menu_visible'):source.index('static unsigned pet_s3_menu_count(')]
    harness=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include "pet_p4_touch_core.h"
static pet_p4_pointer_event_t events[20];
static int count,cancelled;
static void pet_p4_miniapp_pointer(const pet_p4_pointer_event_t *event){assert(count<20);events[count++]=*event;}
static bool pet_p4_miniapp_hold_event(const char *action,int phase,unsigned owner,uint64_t now){(void)action;(void)owner;(void)now;cancelled+=phase==2;return true;}
'''+body+r'''
int main(void) {
  g_s3_menu_visible=g_s3_pointer_visible=g_s3_pointer_vertical=false;
  g_s3_menu_selected=0;g_s3_menu_context=0;
  assert(g_s3_pointer_step==16 && g_s3_menu_commands[0]);
  pet_s3_pointer_tap(100);
  assert(count==2 && events[0].kind==PET_P4_POINTER_DOWN && events[1].kind==PET_P4_POINTER_UP);
  assert(!g_s3_pointer_down && events[0].x==320 && events[0].y==240);
  count=0;g_s3_pointer_down=true;pet_s3_pointer_emit(PET_P4_POINTER_DOWN,200);
  pet_s3_pointer_move(1000,-1000,205);
  assert(events[1].kind==PET_P4_POINTER_MOVE && events[1].x==639 && events[1].y==0);
  assert(g_s3_pointer_last_ms==205);
  pet_s3_pointer_move(-1000,1000,210);
  assert(events[2].kind==PET_P4_POINTER_MOVE && events[2].x==0 && events[2].y==479);
  pet_s3_pointer_cancel(215);
  assert(events[3].kind==PET_P4_POINTER_CANCEL && !g_s3_pointer_down && cancelled==1);
  pet_s3_pointer_move(4,-4,220);
  assert(count==4 && g_s3_pointer_x==4 && g_s3_pointer_y==475);
  g_s3_pointer_down=true;pet_s3_pointer_tap(225);
  assert(count==5 && events[4].kind==PET_P4_POINTER_UP && !g_s3_pointer_down);
}
'''
    f=tmp_path/'pointer.c';f.write_text(harness)
    binary=tmp_path/'pointer'
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I',str(ROOT/'main'),str(f),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
