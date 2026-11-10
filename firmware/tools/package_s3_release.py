#!/usr/bin/env python3
"""Create the minimal A4 S3 factory ZIP; optionally export a separate OTA image."""
import argparse
import hashlib
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PREFIX = 'HachimoDock-esp32s3/'
DISPLAY_PROFILES = ('square', 'landscape-left')


def release_notes(version, display_profile='landscape-left'):
    """Describe the selected A4 image directly, without historical replacements."""
    if display_profile not in DISPLAY_PROFILES:
        raise ValueError('Unsupported S3 display profile')
    if display_profile == 'landscape-left':
        display = ('240×320 ST7789（320×240 横屏，正视屏幕时排线在左侧）。\n'
                   '使用 320×240 原生合成及配套横屏资源。\n')
    else:
        display = ('240×240 ST7789；square 是显式选择的方屏配置，\n'
                   '必须使用配套方屏应用和资源。本次发布默认包为 A4 左排线横屏。\n')
    timing = ('本包屏幕 SPI 为 80MHz，已在当前 A4 PCB、屏幕与接线上验证；\n'
              '更换屏幕或线材后需重新核验显示稳定性。\n'
              if '-80m' in version and display_profile == 'landscape-left'
              else '屏幕 SPI 时钟以所选固件的编译配置为准，所选屏幕需单独核验。\n')
    return f'''HachimoDock-esp32s3
固件版本：{version}
显示配置：{display_profile}

适用硬件
A4 PCB，ESP32-S3 N16R8（16MiB Flash / 8MiB PSRAM）、
{display}I2S 麦克风、MAX98357A、GPIO39 / 38 / 0 按钮与 GPIO1 / 2 / 8 摇杆。
{timing}
A4 官方按钮摇杆操作
GPIO39（SW1 / 1 键）：短按确认；按住开始语音，松开结束。
GPIO38（SW2 / 2 键）：短按组件中心；长按聊天。
GPIO0（SW3 / 3 键）：返回 / 退出。
GPIO1 / 2：摇杆 X / Y；GPIO8：摇杆中按确认。
开机时摇杆保持居中；应用、游戏内操作以画面提示及各组件绑定为准。
旧版纯按键输入配置不适用于此包；请使用本次发布配套桌面客户端。

首次刷机
1. 保存设备现有完整固件和所需数据，用于恢复。
2. 将 hachimodock-s3-factory.bin 从地址 0x0 写入，Flash 容量选择 16MB。
   完整刷机会替换固件、资源和配置。上电或复位时松开 GPIO0。
3. 安装对应系统的配套电脑客户端，用支持数据传输的 USB 线连接设备。
4. 在客户端配置 Agent、语音及其他所需服务。

应用升级
应用分区镜像单独提供，交由客户端的 S3 固件升级入口使用；
它对应应用分区 0x10000，不能从 0x0 写入，不能替代完整工厂镜像。
仅升级应用不会替换设备已有形象和组件资源。
安装、启动客户端不会自动刷写设备，升级需通过固件升级入口操作。

动画与组件
完整包包含配套动画及组件资源；具体内容以本次包及其构建清单为准。
横屏形象应使用配套客户端转换、同步；素材帧率不代表实机保证播放帧率。
素材上限为 15fps、单段 320 帧及 384KiB，整包仍受应用形象分区容量限制。

Wi-Fi
先通过 USB 在配套客户端中配置 2.4GHz Wi-Fi 并绑定电脑，再选择 Wi-Fi。
设备与电脑需处于可互访局域网；首次完整刷机和 ROM 恢复仍使用 USB。

下载、接线和兼容性
https://github.com/gmingtian/HachimoDock-esp32s3/releases
https://github.com/gmingtian/HachimoDock-esp32s3/blob/main/docs/INSTALLATION.md
https://github.com/gmingtian/HachimoDock-esp32s3/blob/main/docs/ESP32-S3-A4-Controls.md
https://github.com/gmingtian/HachimoDock-esp32s3/blob/main/hardware/s3-carrier/README.md

SHA256SUMS 用于核对文件摘要；许可证与原作者声明保存在 licenses 目录。
原项目：YizhengWw/HachimoDock，原作者 Yizheng Wang。
'''


def package(factory, app, output, upgrade_output=None, display_profile='landscape-left'):
    if display_profile not in DISPLAY_PROFILES:
        raise ValueError('Unsupported S3 display profile')
    full = Path(factory).read_bytes()
    application = Path(app).read_bytes()
    if len(full) != 16 * 1024 * 1024:
        raise ValueError('Factory image must contain exactly 16MiB')
    for image in (full, application):
        if len(image) < 112 or image[0] != 0xe9 or image[12:14] != b'\x09\x00':
            raise ValueError('Both images must target ESP32-S3')
    if full[0x10000:0x10000 + len(application)] != application:
        raise ValueError('Factory application does not match the supplied OTA image')
    project = application[80:112].split(b'\0', 1)[0].decode('ascii')
    if project != 'pet_manager_s3_runtime':
        raise ValueError('Unexpected application project')
    version = application[48:80].split(b'\0', 1)[0].decode('ascii')
    if version.endswith('-l320') != (display_profile == 'landscape-left'):
        raise ValueError('Application display variant does not match selected profile')
    files = {'hachimodock-s3-factory.bin': full,
             '使用说明.txt': release_notes(version, display_profile).encode('utf-8-sig'),
             'licenses/LICENSE': (ROOT / 'LICENSE').read_bytes(),
             'licenses/THIRD_PARTY_NOTICES.md': (ROOT / 'THIRD_PARTY_NOTICES.md').read_text(encoding='utf-8').replace('(licenses/', '(').encode('utf-8')}
    for path in sorted((ROOT / 'licenses').glob('*')):
        if path.is_file():
            files['licenses/' + path.name] = path.read_bytes()
    files['SHA256SUMS'] = ''.join(hashlib.sha256(data).hexdigest() + '  ' + name + '\n' for name, data in sorted(files.items())).encode('utf-8')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + '.tmp')
    with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(PREFIX + name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    temporary.replace(output)
    if upgrade_output:
        upgrade_output = Path(upgrade_output)
        upgrade_output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(app, upgrade_output)
    print(f'{output}: {version}, {len(files)} files, four top-level entries')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--factory', required=True, type=Path)
    parser.add_argument('--app', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--upgrade-output', type=Path)
    parser.add_argument('--display-profile', choices=DISPLAY_PROFILES, default='landscape-left')
    args = parser.parse_args()
    package(args.factory, args.app, args.output, args.upgrade_output, args.display_profile)
