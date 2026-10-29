"""Exercise the real miniapp action enumeration against state-transition fixtures."""
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]

def test_menu_enumerates_unique_actions_including_unbound_pointer_actions(tmp_path):
    source=(ROOT/'main/pet_p4_miniapp.c').read_text()
    start=source.index('static size_t miniapp_action_index(')
    end=source.index('\nbool pet_p4_miniapp_has_input(',start)
    harness=r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#define PET_P4_MINIAPP_ACTION_MAX 48
#define portENTER_CRITICAL(x) ((void)(x))
#define portEXIT_CRITICAL(x) ((void)(x))
static int g_runtime_lock;
static struct {bool active;unsigned transition_count;struct {char action[48];} transitions[8];unsigned button_count;struct {char action[48],label[64];} buttons[8];} g_runtime;
static void copy_utf8(char *out,size_t n,const char *text){snprintf(out,n,"%s",text);}
'''+source[start:end]+r'''
int main(void) {
 char out[48]="stale";
 assert(pet_p4_miniapp_action_count()==0);
 assert(!pet_p4_miniapp_action_get(0,out,sizeof(out)) && !out[0]);
 g_runtime.active=true;g_runtime.transition_count=5;
 strcpy(g_runtime.transitions[0].action,"start");
 strcpy(g_runtime.transitions[1].action,"left");
 strcpy(g_runtime.transitions[2].action,"start");
 strcpy(g_runtime.transitions[3].action,"pointer.only");
 assert(pet_p4_miniapp_action_count()==3);
 assert(pet_p4_miniapp_action_get(0,out,sizeof(out)) && !strcmp(out,"start"));
 assert(pet_p4_miniapp_action_get(1,out,sizeof(out)) && !strcmp(out,"left"));
 assert(pet_p4_miniapp_action_get(2,out,sizeof(out)) && !strcmp(out,"pointer.only"));
 g_runtime.button_count=1;
 strcpy(g_runtime.buttons[0].action,"start");strcpy(g_runtime.buttons[0].label,"开始游戏");
 assert(pet_p4_miniapp_action_label(0,out,sizeof(out)) && !strcmp(out,"开始游戏"));
 assert(!pet_p4_miniapp_action_label(2,out,sizeof(out)) && !out[0]);
 assert(pet_p4_miniapp_action_get(0,out,sizeof(out)) && !strcmp(out,"start"));
 assert(!pet_p4_miniapp_action_get(3,out,sizeof(out)) && !out[0]);
 assert(!pet_p4_miniapp_action_get(0,NULL,0));
 g_runtime.active=false;
 assert(!pet_p4_miniapp_action_label(0,out,sizeof(out)) && !out[0]);
}
'''
    f=tmp_path/'actions.c';f.write_text(harness)
    binary=tmp_path/'actions'
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',str(f),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
