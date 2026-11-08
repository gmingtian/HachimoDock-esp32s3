"""Compare actual native S3 scheduling with unchanged portable 8ms reference."""
from pathlib import Path
import os
import subprocess

ROOT=Path(__file__).resolve().parents[1]

def build_run(tmp, s3):
    exe=tmp/('s3.exe' if s3 else 'reference.exe')
    sources=[ROOT/'main/pet_p4_game.c',ROOT/'main/pet_p4_xiangqi.c',ROOT/'tests/p4_xiangqi_cadence_test.c']
    # Mirror IDF: ESP_PLATFORM is a compiler define; target CONFIG comes from
    # sdkconfig.h, not an injected command-line CONFIG define.
    if s3:(tmp/'sdkconfig.h').write_text('#define CONFIG_IDF_TARGET_ESP32S3 1\n',encoding='utf-8')
    if os.name=='nt':
        vcvars=Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat')
        # Existing non-Xiangqi engine branches narrow integer grid fields.
        # Keep all other warnings fatal; independent core test has no waivers.
        args=['cl','/nologo','/std:c11','/utf-8','/W4','/WX','/wd4244','/wd4018','/Zi','/MD','/fsanitize=address',f'/I{ROOT/"main"}']
        if s3:args+=['/DESP_PLATFORM=1',f'/I{tmp}']
        args+=list(map(str,sources))+[f'/Fe:{exe}']
        script=tmp/('s3.cmd' if s3 else 'reference.cmd')
        script.write_text(f'@call "{vcvars}" >nul\n@'+subprocess.list2cmdline(args)+'\n',encoding='utf-8')
        built=subprocess.run(['cmd','/d','/c',str(script)],cwd=tmp,capture_output=True,text=True,encoding='utf-8',errors='replace')
        assert built.returncode==0,built.stdout+'\n'+built.stderr
    else:
        args=['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-error=misleading-indentation','-fsanitize=address,undefined','-I',str(ROOT/'main')]
        if s3:args+=['-DESP_PLATFORM=1','-I',str(tmp)]
        subprocess.run(args+list(map(str,sources))+['-o',str(exe)],cwd=tmp,check=True,capture_output=True)
    # ASAN runtime DLL lives in the MSVC compiler path configured by vcvars.
    if os.name=='nt':
        run=tmp/('run-s3.cmd' if s3 else 'run-reference.cmd')
        run.write_text(f'@call "{vcvars}" >nul\n@"{exe}" {2 if s3 else 8}\n',encoding='utf-8')
        result=subprocess.run(['cmd','/d','/c',str(run)],cwd=tmp,capture_output=True,text=True,encoding='utf-8',errors='replace')
    else:
        result=subprocess.run([str(exe),str(2 if s3 else 8)],cwd=tmp,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+'\n'+result.stderr
    return result.stdout.splitlines()

def test_s3_two_ms_preserves_every_search_result_and_budget(tmp_path):
    reference=build_run(tmp_path,False)
    candidate=build_run(tmp_path,True)
    expected=[line for line in reference if line.startswith('P ')]
    actual=[line for line in candidate if line.startswith('P ')]
    assert len(expected)>=12 and actual==expected,'board/depth/work/node/result differs'
    old=list(map(int,next(v for v in reference if v.startswith('T ')).split()[1:]))
    new=list(map(int,next(v for v in candidate if v.startswith('T ')).split()[1:]))
    assert old[0]==new[0]==len(actual)
    assert new[1]*4==old[1],(old,new)
    print(f'{len(actual)} changing positions: exact board/depth/work/node/result parity; scheduler logical ms {old[1]} -> {new[1]} (not device wall time)')
