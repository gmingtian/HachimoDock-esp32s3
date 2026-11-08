"""Exercise the production Xiangqi cell renderer without a board or display."""
from pathlib import Path
import os
import subprocess
from s3_native_video_row_test import function

ROOT = Path(__file__).resolve().parents[1]


def test_xiangqi_native_piece_labels_and_authoritative_guides(tmp_path):
    renderer = (ROOT/'main/pet_p4_renderer.c').read_text(encoding='utf-8')
    helper = function(renderer, 'static void draw_app_xiangqi_cell(')
    source = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef struct {int x,y,w,h,font_size,line_height,align,valign,icon;} pet_surface_node_t;
static int ellipses,rects,label_count,green,capture,selected,cursor,last;
static char text[16];
static uint16_t rgb565(int r,int g,int b){return (uint16_t)(((r>>3)<<11)|((g>>2)<<5)|(b>>3));}
static void fill_ellipse(int x,int y,int rx,int ry,uint16_t color){
  assert(x-rx>=0&&y-ry>=0&&x+rx<80&&y+ry<80);ellipses++;
  if(color==rgb565(37,135,121))green++;
  if(color==rgb565(223,100,61))capture++;
  if(color==rgb565(195,147,44))last++;
}
static void fill_rect(int x,int y,int w,int h,uint16_t color){
  assert(x>=0&&y>=0&&w>=0&&h>=0&&x+w<=80&&y+h<=80);rects++;
  if(color==rgb565(34,104,175))selected++;
  if(color==rgb565(231,120,40))cursor++;
}
static void draw_app_label(const pet_surface_node_t *n,const char *value,uint16_t color){
  (void)color;assert(n->font_size>0&&n->font_size<=32);label_count++;memcpy(text,value,strlen(value)+1);
}
''' + helper + r'''
int main(void){
  static const char *const want[]={"","帅","仕","相","马","车","炮","兵","将","士","象","马","车","炮","卒"};
  draw_app_xiangqi_cell(0,8,8,44);assert(!ellipses&&!rects&&!label_count);
  for(int p=1;p<=14;p++){draw_app_xiangqi_cell(p,8,8,44);assert(!strcmp(text,want[p]));}
  assert(label_count==14&&!green&&!capture);
  draw_app_xiangqi_cell(0x80,8,8,44);assert(green==1&&!capture&&label_count==14);
  draw_app_xiangqi_cell(0x80|8,8,8,44);assert(capture==1&&label_count==15);
  draw_app_xiangqi_cell(0x70|5,8,8,44);assert(selected==4&&cursor==4&&last==1&&label_count==16);
  draw_app_xiangqi_cell(0x40,8,8,44);assert(last==2&&label_count==16);
  draw_app_xiangqi_cell(1,8,8,8);assert(label_count==17);
  return 0;
}
'''
    path = tmp_path/'xiangqi_ui.c'
    path.write_text(source, encoding='utf-8')
    binary = tmp_path/'xiangqi_ui.exe'
    if os.name == 'nt':
        vcvars = Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat')
        script = tmp_path/'xiangqi_ui.cmd'
        script.write_text(f'@call "{vcvars}" >nul\n@cl /nologo /std:c11 /utf-8 /W4 /WX /Zi /MD /fsanitize=address "{path}" /Fo"{tmp_path / "xiangqi_ui.obj"}" /Fd"{tmp_path / "xiangqi_ui.pdb"}" /Fe"{binary}" /link /INCREMENTAL:NO\n@if errorlevel 1 exit /b 1\n@"{binary}"\n', encoding='utf-8')
        subprocess.run(['cmd', '/c', str(script)], check=True)
    else:
        subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined', str(path), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
