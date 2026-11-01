#!/usr/bin/env python3
"""Create the minimal S3 factory ZIP; optionally export a separate OTA image."""
import argparse
import hashlib
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PREFIX = 'HachimoDock-esp32s3/'


def package(factory, app, output, upgrade_output=None, display_profile="square"):
    if display_profile not in ("square", "landscape-left"):
        raise ValueError("Unsupported S3 display profile")
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
    text = f'''HachimoDock-esp32s3\n固件版本：{version}\n\n适用硬件\nESP32-S3 N16R8（16MiB Flash / 8MiB PSRAM）、240×240 ST7789、\n原 I2S 麦克风、MAX98357A 与 GPIO39 / 38 / 0 三按键。\n\n首次刷机\n1. 保存原小智完整固件，用于恢复。\n2. 将 hachimodock-s3-factory.bin 从地址 0x0 写入，Flash 容量选择 16MB。\n   完整刷机会替换原固件、资源和配置。上电或复位时松开 GPIO0。\n3. 安装对应系统的电脑客户端，使用支持数据传输的 USB 线连接设备。\n4. 在客户端配置 Agent、语音和其他所需服务。\n\n三键操作\nGPIO39：短按上一项，长按返回。\nGPIO38：短按下一项，长按组件菜单。\nGPIO0：短按确认，按住录音、松开结束。\n\n应用升级\n应用分区固件在下载页面单独提供，交由客户端的 S3 固件升级入口使用；\n不能将应用分区镜像从 0x0 写入。客户端内也包含配套 S3 应用固件。\n\n下载、接线和兼容性\nhttps://github.com/gmingtian/HachimoDock-esp32s3/releases\nhttps://github.com/gmingtian/HachimoDock-esp32s3/blob/main/docs/INSTALLATION.md\nhttps://github.com/gmingtian/HachimoDock-esp32s3/blob/main/docs/COMPATIBILITY.md\n\nSHA256SUMS 用于核对文件摘要；许可证与原作者声明保存在 licenses 目录。\n原项目：YizhengWw/HachimoDock，原作者 Yizheng Wang。\n'''
    base_version = version.removesuffix('-l320')
    if base_version.endswith(('-r1', '-r3', '-r4', '-r6')):
        text += "\nWi-Fi\n先通过 USB 连接客户端 0.1.168 或更新版本，在设备连接中配置 2.4GHz Wi-Fi，\n然后绑定此电脑，选择使用 Wi-Fi。两端需处于可互访局域网。\n设备记住显式选择；已有连接不被抢占，无线断线清理后尝试同板 USB。\n配网与清除操作使用 USB；首次完整刷机和 ROM 恢复仍使用 USB。\nS3 预置 25 个三键兼容组件，游戏保留贪吃蛇、双键接球和像素飞鸟。\nhttps://github.com/gmingtian/HachimoDock-esp32s3/blob/main/docs/WIFI.md\n"
    if base_version.endswith('-r6') and display_profile == 'square':
        text += '\n动画素材\n配合客户端 0.1.169 或更新版本，新转换的动画为 240×180、15fps。\n兼容旧 10fps 素材；已有设备升级应用后，需要重新同步形象才能使用 15fps 素材。\n每段上限 320 帧（15fps 时约 21.3 秒）、384KiB；形象槽仍为 3MiB。\n素材帧率不代表实机保证播放帧率。本版本仍使用现有 240×240 屏幕接线。\n'
    if display_profile == "landscape-left":
        text = text.replace("240×240 ST7789", "240×320 ST7789（320×240 横屏，正视屏幕时排线在左侧）")
        text = text.replace("本版本仍使用现有 240×240 屏幕接线。", "本版本使用 320×240 左排线横屏配置，GPIO 接线保持不变。")
        text += "\n横屏版本保留原版 640×480 UI 布局，等比例缩小至 320×240；三键操作菜单仍可使用。\n"
        text += ('\n完整包预置 16 组 320×240 / 15fps 动画，由原始高清视频直接缩小编码，'
                 '使用 Lanczos 和 CRF 27；兼容已有 240×180 形象。\n'
                 '仅刷应用包不会替换已有形象；本完整包写入 0x0 会替换配置和资源。\n'
                 '旧客户端仍按 240×180 转码，再次同步会替换预置高清形象。\n'
                 '待机极暗背景归黑，UI 布局保留；素材 15fps 不代表实机保证帧率。\n')
        text += ('完整包另包含全部 25 个内置组件的横屏图片适配：原生背景、'
                 '按实际尺寸重采样的图标/装饰/缩略图、精确 A8 字体图集和木鱼图层。\n'
                 '保留原版布局和操作区域。仅更新应用不会替换设备已存组件图片；'
                 '旧客户端重新安装组件可能换回原图片资源。\n')
    files = {'hachimodock-s3-factory.bin': full,
             '使用说明.txt': text.encode('utf-8-sig'),
             'licenses/LICENSE': (ROOT / 'LICENSE').read_bytes(),
             'licenses/THIRD_PARTY_NOTICES.md': (ROOT / 'THIRD_PARTY_NOTICES.md').read_text().replace('(licenses/', '(').encode()}
    for path in sorted((ROOT / 'licenses').glob('*')):
        if path.is_file():
            files['licenses/' + path.name] = path.read_bytes()
    files['SHA256SUMS'] = ''.join(hashlib.sha256(data).hexdigest() + '  ' + name + '\n' for name, data in sorted(files.items())).encode()
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
    parser.add_argument("--display-profile", choices=("square", "landscape-left"), default="square")
    args = parser.parse_args()
    package(args.factory, args.app, args.output, args.upgrade_output, args.display_profile)
