"""Production S3 catalog/install policy, preserving upgraded records and P4."""
import importlib.util
import json
from pathlib import Path
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]
BLOCKED = ['block-combo', 'fresh-fruit-slice', 'cloud-hop', 'bloomfrog_companion']
KEPT = ['snake-turn', 'two-key-pong', 'flappy-bird']

def function(source, signature):
    start = source.index(signature)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]

def test_factory_filters_only_s3_without_mutating_shared_config():
    spec = importlib.util.spec_from_file_location('factory_s3', ROOT / 'tools/build_s3_factory.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = json.loads((ROOT / 'factory-config.json').read_text())
    before = json.dumps(config, sort_keys=True)
    assert hasattr(module, 's3_factory_config'), 'target factory policy is missing'
    selected = module.s3_factory_config(config)
    assert len(selected['components']['ids']) == 25
    assert not set(BLOCKED) & set(selected['components']['ids'])
    assert set(KEPT) <= set(selected['components']['ids'])
    assert json.dumps(config, sort_keys=True) == before
    policy = json.loads((ROOT / 's3/component-policy.json').read_text())
    assert policy['unsupportedBuiltins'] == BLOCKED
    assert policy['supportedGames'] == KEPT
    import re
    header = (ROOT / 's3/pet_s3_component_policy.h').read_text()
    assert re.findall(r'"([^"]+)"', header) == policy['unsupportedBuiltins']

@pytest.mark.parametrize('s3', [0, 1])
def test_upgrade_projection_and_install_policy_preserve_records(tmp_path, s3):
    source = (ROOT / 'main/pet_p4_miniapp.c').read_text()
    functions = '\n'.join(function(source, name) for name in [
        'static bool catalog_entry_visible(', 'static int catalog_visible_index(',
        'static int catalog_visible_preferred(', 'bool pet_p4_miniapp_install_begin('])
    header = ROOT / 's3/pet_s3_component_policy.h'
    harness = tmp_path / 'policy.c'
    harness.write_text(r'''
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include "cJSON.h"
''' + (f'#include "{header}"\n' if header.exists() else '') + r'''
static struct { const char *widget_id; int slot, save; } g_catalog[] = {
 {"block-combo",1,61},{"fresh-fruit-slice",2,62},{"cloud-hop",3,63},
 {"bloomfrog_companion",4,64},{"snake-turn",5,65},{"two-key-pong",6,66},
 {"flappy-bird",7,67},{"custom-pointer-tool",8,68}};
static size_t g_catalog_count=8;
static struct { bool active,repair_resources; char transfer_id[64],widget_id[64]; } g_staging;
static int g_image_used,g_image_next; static char g_image_id[64];
static bool g_builtin_sync_in_progress;
static const char *json_string(const cJSON *j,const char *k){const cJSON *v=cJSON_GetObjectItemCaseSensitive(j,k);return cJSON_IsString(v)?v->valuestring:"";}
static void set_error(char *dst,size_t len,const char *text){snprintf(dst,len,"%s",text);}
static bool safe_id(const char *id,size_t n){return id[0] && strlen(id)<n;}
static bool safe_widget_id(const char *id){return safe_id(id,64);}
static void copy_utf8(char *dst,size_t n,const char *src){snprintf(dst,n,"%s",src);}
static bool pet_p4_audio_active(void){return false;}
static bool pet_p4_audio_playback_active(void){return false;}
static bool pet_p4_audio_conversation_active(void){return false;}
static bool pet_p4_audio_music_active(void){return false;}
''' + functions + r'''
int main(void) {
 assert(catalog_visible_preferred(0)==(CONFIG_IDF_TARGET_ESP32S3?4:0));
 for(int i=0;i<8;i++){
   assert(catalog_entry_visible(i)==(!CONFIG_IDF_TARGET_ESP32S3 || i>=4));
   assert(g_catalog[i].slot==i+1 && g_catalog[i].save==61+i);
   cJSON *j=cJSON_CreateObject(); cJSON_AddStringToObject(j,"transferId","new");
   cJSON_AddStringToObject(j,"widgetId",g_catalog[i].widget_id);
   g_staging.active=true; strcpy(g_staging.transfer_id,"preserved");
   char error[128]={0};
   assert(pet_p4_miniapp_install_begin(j,error,sizeof(error))==(!CONFIG_IDF_TARGET_ESP32S3 || i>=4));
   if(CONFIG_IDF_TARGET_ESP32S3 && i<4) assert(g_staging.active && !strcmp(g_staging.transfer_id,"preserved"));
   cJSON_Delete(j);
 }
 assert(g_catalog_count==8);
}
''')
    exe = tmp_path / 'policy'
    vendor = ROOT / 'tests/vendor/cjson'
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',f'-DCONFIG_IDF_TARGET_ESP32S3={s3}',
        '-I',str(vendor),str(harness),str(vendor/'cJSON.c'),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

def test_bootstrap_uses_same_non_destructive_policy():
    source = (ROOT / 'main/pet_p4_miniapp.c').read_text()
    sync = function(source, 'esp_err_t pet_p4_miniapp_sync_builtins(void)')
    assert 'if (!pet_s3_component_allowed(widget_id)) continue;' in sync
    assert sync.index('if (!pet_s3_component_allowed(widget_id)) continue;') < sync.index('char *widget_json')
