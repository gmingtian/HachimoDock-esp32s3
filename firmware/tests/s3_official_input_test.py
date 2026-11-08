"""A4 hardware, OTA migration and shared official input behavior."""
import csv
from pathlib import Path
import re
import subprocess
ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent

def function(source, signature):
    start = source.index(signature); end = source.index('{', start) + 1; depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}'); end += 1
    return source[start:end]

def test_pins_match_fabricated_a4_netlist():
    defines=dict(re.findall(r'^#define PET_S3_(\w+) (\d+)$',(ROOT/'s3/pet_s3_board.h').read_text(),re.M))
    with (REPO/'hardware/s3-carrier/output/connections.csv').open(encoding='utf-8') as f:
        pads={(r['reference'],r['pin']):r['net'] for r in csv.DictReader(f)}
    expected={'SW1_GPIO':(39,'SW1','1'),'SW2_GPIO':(38,'SW2','1'),'SW3_GPIO':(0,'SW3','1'),
              'JOYSTICK_X_GPIO':(1,'JS1','B2'),'JOYSTICK_Y_GPIO':(2,'JS1','A2'),'JOYSTICK_PRESS_GPIO':(8,'JS1','B')}
    for name,(gpio,ref,pin) in expected.items():
        assert int(defines[name])==gpio and pads[ref,pin]==f'GPIO{gpio}'
    assert pads['JS1','D']=='GPIO8'
    assert pads['JS1','A1']==pads['JS1','B3']=='+3V3'
    assert pads['JS1','A3']==pads['JS1','B1']=='GND'

def test_official_defaults_execute_identically_on_s3_and_p4(tmp_path):
    source=(ROOT/'main/pet_p4_input.c').read_text(encoding='utf-8')
    code=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define PET_P4_INPUT_CONFIG_VERSION 9
#define PET_P4_INPUT_MAX_BINDINGS 16
typedef struct {char event[40],action[24],value[160];} pet_p4_input_binding_t;
typedef struct {uint32_t version,binding_count;pet_p4_input_binding_t bindings[16];} pet_p4_input_config_t;
static void copy_text(char *d,size_t n,const char *s){snprintf(d,n,"%s",s?s:"");}
''' + function(source,'static void add_default_binding(')+'\n'+function(source,'static void load_default_config(')+r'''
static const char *action(pet_p4_input_config_t *c,const char *event){
 for(unsigned i=0;i<c->binding_count;i++)if(!strcmp(c->bindings[i].event,event))return c->bindings[i].action;
 return "missing";
}
int main(void){pet_p4_input_config_t c;load_default_config(&c);assert(c.version==9&&c.binding_count==16);
 assert(!strcmp(action(&c,"button.sw1.short_press"),"page_enter"));
 assert(!strcmp(action(&c,"button.sw1.hold"),"voice_ptt"));
 assert(!strcmp(action(&c,"button.sw2.short_press"),"component_center"));
 assert(!strcmp(action(&c,"button.sw2.long_press"),"realtime_chat"));
 assert(!strcmp(action(&c,"button.sw3.short_press"),"page_back"));
 assert(!strcmp(action(&c,"button.encoder.short_press"),"page_enter"));
 assert(!strcmp(action(&c,"joystick.up"),"session_previous"));
 assert(!strcmp(action(&c,"joystick.down"),"session_next"));
 assert(!strcmp(action(&c,"knob.rotate_ccw"),"session_previous"));
 assert(!strcmp(action(&c,"knob.rotate_cw"),"session_next"));return 0;}
'''
    path=tmp_path/'defaults.c';path.write_text(code,encoding='utf-8')
    for s3 in (0,1):
        binary=tmp_path/f'defaults-{s3}.exe'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',f'-DCONFIG_IDF_TARGET_ESP32S3={s3}',str(path),'-o',str(binary)],check=True)
        subprocess.run([str(binary)],check=True)

def test_ota_does_not_restore_the_three_key_namespace():
    source=(ROOT/'main/pet_p4_input.c').read_text(encoding='utf-8')
    assert '#define PET_P4_INPUT_NVS_NAMESPACE "pet_input_a4j1"' in source
    assert '#define PET_P4_INPUT_NVS_NAMESPACE "pet_input_s3"' not in source
    assert 'pet_s3_input_task.inc' not in source and 'pet_s3_process_key' not in source
    assert 'ADC1_GPIO1_CHANNEL' in source and 'ADC1_GPIO2_CHANNEL' in source
    assert 'joystick_calibrated ? pet_p4_joystick_decoder_update(' in source
