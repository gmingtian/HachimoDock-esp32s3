"""Near-black cleanup must preserve the foreground, colorful art and nonblack scenes."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_only_edge_connected_neutral_shadows_are_cleaned(tmp_path):
    source = tmp_path/'background.c'
    source.write_text(r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "pet_s3_video_background.h"
int main(void) {
  /* Literal RGB565: black, dark green noise, grey16, grey32, white,
   * an equally dark foreground detail, white, bright fur edge, grey16, black. */
  uint16_t row[]={0,0x0020,0x1082,0x2104,0xffff,0x1082,0xffff,0x2945,0x1082,0};
  const uint16_t expected[]={0,0,0,0x1082,0xffff,0x1082,0xffff,0x2945,0,0};
  pet_s3_clean_video_background(row,10);
  assert(!memcmp(row,expected,sizeof(row)));
  /* Deep blue artwork blocks cleanup rather than being mistaken for black. */
  uint16_t color[]={0,0x001f,0x1082,0xffff,0};
  const uint16_t want_color[]={0,0x001f,0x1082,0xffff,0};
  pet_s3_clean_video_background(color,5);
  assert(!memcmp(color,want_color,sizeof(color)));
  uint16_t dark_color[]={0,0x00c0,0x1082,0x001f,0}; /* saturated green24 */
  const uint16_t want_dark[]={0,0x00c0,0x1082,0x001f,0};
  pet_s3_clean_video_background(dark_color,5);
  assert(!memcmp(dark_color,want_dark,sizeof(dark_color)));
  /* A row without black at both edges is not an optically black background. */
  uint16_t scene[]={0x8410,0x1082,0x2104,0x8410},copy[4];
  memcpy(copy,scene,sizeof(scene));
  pet_s3_clean_video_background(scene,4);
  assert(!memcmp(copy,scene,sizeof(scene)));
  uint16_t cut_off[]={0x1082,0xffff,0};
  pet_s3_clean_video_background(cut_off,3);
  assert(cut_off[0]==0x1082);
  /* Do not erase a fine fur edge brighter than the bounded shadow knee. */
  uint16_t fine[]={0,0x2945,0x2104,0xffff,0};
  pet_s3_clean_video_background(fine,5);
  assert(fine[1]==0x2945 && fine[2]==0x2104);
  uint16_t guard[]={0xdead,0,0xbeef};
  pet_s3_clean_video_background(guard+1,1);
  assert(guard[0]==0xdead && guard[1]==0 && guard[2]==0xbeef);
  pet_s3_clean_video_background(NULL,10);
  pet_s3_clean_video_background(guard,0);
  return 0;
}
''')
    exe = tmp_path/'background'
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
                    '-I',str(ROOT/'s3'),str(source),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
