"""Exercise square/landscape geometry and the complete production scaling path."""
from pathlib import Path
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize("landscape", [0, 1])
def test_display_geometry_and_frame_edges(tmp_path, landscape):
    harness = tmp_path / "display.c"
    harness.write_text(r'''#include <assert.h>
#include <stdlib.h>
#include "pet_s3_board.h"
#include "pet_s3_render.h"
#include "pet_target.h"
int main(void) {
#if PET_S3_LANDSCAPE_LEFT
 assert(PET_S3_LCD_WIDTH==320 && PET_S3_LCD_HEIGHT==240);
 assert(PET_S3_LCD_SWAP_XY && PET_S3_LCD_MIRROR_X && !PET_S3_LCD_MIRROR_Y);
 assert(!PET_S3_NATIVE_HOME);
#else
 assert(PET_S3_LCD_WIDTH==240 && PET_S3_LCD_HEIGHT==240);
 assert(!PET_S3_LCD_SWAP_XY && !PET_S3_LCD_MIRROR_X && !PET_S3_LCD_MIRROR_Y);
 assert(PET_S3_NATIVE_HOME);
#endif
 assert(PET_S3_PANEL_WIDTH==PET_S3_LCD_WIDTH);
 assert(PET_S3_PANEL_HEIGHT==PET_S3_LCD_HEIGHT);
 assert(PET_TARGET_PHYSICAL_WIDTH==PET_S3_LCD_WIDTH);
 assert(PET_TARGET_PHYSICAL_HEIGHT==PET_S3_LCD_HEIGHT);
 uint16_t *src=malloc(640*480*2);
 unsigned size=PET_S3_PANEL_WIDTH*PET_S3_PANEL_HEIGHT;
 uint16_t *out=malloc((size+2)*2);out[0]=0x1234;out[size+1]=0xabcd;
 for(int y=0;y<480;y++)for(int x=0;x<640;x++)src[y*640+x]=(uint16_t)(1+x+640*y);
 assert(pet_s3_scale_rgb565(src,640,480,640,out+1,PET_S3_PANEL_WIDTH,PET_S3_PANEL_HEIGHT));
 assert(out[0]==0x1234 && out[size+1]==0xabcd);
#if PET_S3_LANDSCAPE_LEFT
 for(int y=0;y<240;y++)for(int x=0;x<320;x++)assert(out[1+y*320+x]==src[y*2*640+x*2]);
 uint16_t *native=malloc(320*240*2);
 for(int i=0;i<320*240;i++)native[i]=(uint16_t)(i*31+7);
 pet_s3_expand_2x(native,320,src,320,240);
 assert(pet_s3_scale_rgb565(src,640,480,640,out+1,320,240));
 for(int i=0;i<320*240;i++)assert(out[1+i]==native[i]);
 free(native);
#else
 assert(out[1]==0 && out[size]==0);
#endif
 free(src);free(out);return 0;
}
''')
    exe=tmp_path / "display"
    subprocess.run(["cc","-std=c11","-Wall","-Wextra","-Werror","-fsanitize=undefined",
        "-DCONFIG_IDF_TARGET_ESP32S3=1",f"-DPET_S3_LANDSCAPE_LEFT={landscape}",
        "-I",str(ROOT/"main"),"-I",str(ROOT/"s3"),str(harness),"-o",str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

@pytest.mark.parametrize("landscape", [False, True])
def test_factory_zip_names_correct_panel_and_preserves_image(tmp_path, landscape):
    import importlib.util
    import zipfile
    spec=importlib.util.spec_from_file_location("package_s3", ROOT/"tools/package_s3_release.py")
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    app=bytearray(288);app[0]=0xe9;app[12]=9
    version="0.7.103-s3-r6"+("-l320" if landscape else "")
    app[48:48+len(version)]=version.encode()
    name=b"pet_manager_s3_runtime";app[80:80+len(name)]=name
    full=bytearray(16*1024*1024);full[0]=0xe9;full[12]=9;full[0x10000:0x10000+len(app)]=app
    factory=tmp_path/"factory.bin";factory.write_bytes(full)
    application=tmp_path/"app.bin";application.write_bytes(app)
    output=tmp_path/"release.zip"
    profile="landscape-left" if landscape else "square"
    mod.package(factory,application,output,display_profile=profile)
    with zipfile.ZipFile(output) as z:
        text=z.read(mod.PREFIX+"使用说明.txt").decode("utf-8-sig")
        assert ("320×240 横屏" in text)==landscape
        assert "15fps" in text and "Wi-Fi" in text
        assert ("本版本仍使用现有 240×240 屏幕接线" in text)==(not landscape)
        assert z.read(mod.PREFIX+"hachimodock-s3-factory.bin")==full
    with pytest.raises(ValueError,match="display variant"):
        mod.package(factory,application,tmp_path/"wrong.zip",display_profile="square" if landscape else "landscape-left")
