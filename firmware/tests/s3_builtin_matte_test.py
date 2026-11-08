"""Factory black artwork needs colored near-black floor removal, not segmentation."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
def run_c(tmp_path,code):
    src=tmp_path/'matte.c';src.write_text(code,encoding='utf-8');exe=tmp_path/'matte'
    subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
                    '-I',str(ROOT/'s3'),str(src),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
def test_builtin_floor_clears_without_changing_visible_or_enclosed_foreground(tmp_path):
    header=(ROOT/'s3/pet_s3_video_background.h').read_text(encoding='utf-8')
    assert 'pet_s3_clean_builtin_black_matte(' in header,'Missing factory-only black matte cleanup'
    run_c(tmp_path,r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "pet_s3_video_background.h"
int main(int argc,char **argv){
  if(argc==3){
    static uint16_t pixels[320*240];FILE *in=fopen(argv[1],"rb");assert(in);
    assert(fread(pixels,sizeof(*pixels),320*240,in)==320*240);assert(fclose(in)==0);
    for(int y=0;y<240;y++)pet_s3_clean_builtin_black_matte(pixels+y*320,320);
    FILE *out=fopen(argv[2],"wb");assert(out);assert(fwrite(pixels,sizeof(*pixels),320*240,out)==320*240);assert(fclose(out)==0);return 0;
  }
  uint16_t floor[]={0,0x00c0,0x2104,0xffff,0x1082,0xffff,0x2104,0x00c0,0};
  const uint16_t wanted[]={0,0,0,0xffff,0x1082,0xffff,0,0,0};
  pet_s3_clean_builtin_black_matte(floor,9);assert(!memcmp(floor,wanted,sizeof(floor)));
  uint16_t custom[]={0,0x00c0,0x2104,0xffff,0};uint16_t original[5];memcpy(original,custom,sizeof(custom));
  pet_s3_clean_video_background(custom,5);assert(!memcmp(custom,original,sizeof(custom)));
  for(unsigned color=0;color<65536;color++){
    if(pet_s3_video_peak((uint16_t)color)<40)continue;
    uint16_t row[]={0,(uint16_t)color,0x00c0,0xffff,0};
    pet_s3_clean_builtin_black_matte(row,5);
    assert(row[1]==color&&row[2]==0x00c0&&row[3]==0xffff);
  }
  uint16_t fine[]={0,0x2945,0x1082,0xffff,0};
  pet_s3_clean_builtin_black_matte(fine,5);assert(fine[1]==0x2945&&fine[2]==0x1082);
  uint16_t scene[]={0x8410,0x2104,0xffff,0x8410},copy[4];memcpy(copy,scene,sizeof(scene));
  pet_s3_clean_builtin_black_matte(scene,4);assert(!memcmp(scene,copy,sizeof(scene)));
  uint16_t guard[]={0xdead,0x00c0,0xbeef};pet_s3_clean_builtin_black_matte(guard+1,1);
  assert(guard[0]==0xdead&&guard[1]==0&&guard[2]==0xbeef);
  pet_s3_clean_builtin_black_matte(NULL,320);pet_s3_clean_builtin_black_matte(guard,0);
  puts("PASS factory colored floor cleanup, all visible RGB565 foreground blockers, enclosed dark detail, custom profile and guards");
}
''')
