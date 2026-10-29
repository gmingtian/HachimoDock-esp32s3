#!/usr/bin/env python3
"""Create the minimal S3 factory ZIP; optionally export a separate OTA image."""
import argparse
import hashlib
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PREFIX = 'HachimoDock-esp32-s3/'


def package(factory, app, output, upgrade_output=None):
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
    text = f'''HachimoDock-esp32-s3\n固件版本：{version}\n\n适用硬件\nESP32-S3 N16R8（16MiB Flash / 8MiB PSRAM）、240×240 ST7789、\n原 I2S 麦克风、MAX98357A 与 GPIO39 / 38 / 0 三按键。\n\n首次刷机\n1. 保存原小智完整固件，用于恢复。\n2. 将 hachimodock-s3-factory.bin 从地址 0x0 写入，Flash 容量选择 16MB。\n   完整刷机会替换原固件、资源和配置。上电或复位时松开 GPIO0。\n3. 安装对应系统的电脑客户端，使用支持数据传输的 USB 线连接设备。\n4. 在客户端配置 Agent、语音和其他所需服务。\n\n三键操作\nGPIO39：短按上一项，长按返回。\nGPIO38：短按下一项，长按组件菜单。\nGPIO0：短按确认，按住录音、松开结束。\n\n应用升级\n应用分区固件在下载页面单独提供，交由客户端的 S3 固件升级入口使用；\n不能将应用分区镜像从 0x0 写入。客户端内也包含配套 S3 应用固件。\n\n下载、接线和兼容性\nhttps://github.com/gmingtian/HachimoDock-esp32-s3/releases\nhttps://github.com/gmingtian/HachimoDock-esp32-s3/blob/main/docs/INSTALLATION.md\nhttps://github.com/gmingtian/HachimoDock-esp32-s3/blob/main/docs/COMPATIBILITY.md\n\nSHA256SUMS 用于核对文件摘要；许可证与原作者声明保存在 licenses 目录。\n原项目：YizhengWw/HachimoDock，原作者 Yizheng Wang。\n'''
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
    args = parser.parse_args()
    package(args.factory, args.app, args.output, args.upgrade_output)
