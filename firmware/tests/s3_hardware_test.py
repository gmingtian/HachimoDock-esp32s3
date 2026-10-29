"""Host checks for real S3 key, PCM and conservative conversation adapters."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]

def test_three_keys_and_pcm_conversion(tmp_path):
    for name in ['keys','pcm']:
        command=['cc','-std=c11','-Wall','-Wextra','-Werror','-I',str(ROOT/'main'),'-I',str(ROOT/'s3'),str(ROOT/f'tests/s3_{name}_test.c')]
        if name=='keys':command.append(str(ROOT/'main/pet_p4_input_core.c'))
        binary=tmp_path/name
        subprocess.run(command+['-o',str(binary)],check=True)
        subprocess.run([str(binary)],check=True)

def test_s3_conversation_forces_half_duplex_until_acoustic_calibration(tmp_path):
    source=(ROOT/'main/pet_p4_audio.c').read_text()
    body=source[source.index('esp_err_t pet_p4_audio_conversation_set('):]
    body=body[:body.index('  if (!enabled) {')]
    harness='''#include <assert.h>\n#include <stdbool.h>\ntypedef int esp_err_t;\n'''+body+'''  (void)enabled;(void)session_id;return half_duplex;\n}\nint main(void) {
#if CONFIG_IDF_TARGET_ESP32S3
 assert(pet_p4_audio_conversation_set(true,false,"test")==1);
#else
 assert(pet_p4_audio_conversation_set(true,false,"test")==0);
#endif
 assert(pet_p4_audio_conversation_set(true,true,"test")==1);
}\n'''
    f=tmp_path/'duplex.c';f.write_text(harness)
    for s3 in [0,1]:
        binary=tmp_path/f'duplex-{s3}'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',f'-DCONFIG_IDF_TARGET_ESP32S3={s3}',str(f),'-o',str(binary)],check=True)
        subprocess.run([str(binary)],check=True)
