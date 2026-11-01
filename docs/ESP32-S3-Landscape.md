# ESP32-S3 · ST7789 240×320 左排线横屏

适用于原有 ESP32-S3 N16R8 接线，屏幕更换为 ST7789 240×320。
正面看屏幕时，FPC 排线在左侧，输出为 320×240 横屏。
使用控制器的交换 XY 与 X 镜像，零偏移。根据本屏实机反馈，已将首版横屏方向再旋转 180°；不同模块的原生扫描方向仍需实机确认。

主页、会话卡片、组件中心和组件共用原版 640×480 画布，按 1/2 缩小铺满屏幕。
三键的动作菜单、组件附加操作和软件光标保留；菜单宽度适配 320 像素。
动画素材沿用 240×180、最高 15fps，显示时等比例缩放，解码容量限制保持原值。
这不是保证达到 15fps 的性能声明。

## 构建

```sh
HACHIMO_S3_DISPLAY_PROFILE=landscape-left bash firmware/tools/build_s3.sh
python3 firmware/tools/package_s3_release.py \
  --factory artifacts/s3-landscape-left/hachimodock-s3-factory.bin \
  --app artifacts/s3-landscape-left/hachimodock-s3-app.bin \
  --display-profile landscape-left \
  --output artifacts/s3-landscape-left/HachimoDock-S3-320x240-left_Factory.zip \
  --upgrade-output artifacts/s3-landscape-left/HachimoDock-S3-320x240-left_App.bin
```

使用独立构建目录和输出目录；不替换客户端内置的方屏固件。
固件版本 `0.7.103-s3-r6-l320`，应用工程名仍为 `pet_manager_s3_runtime`。
hello 的逻辑画布为 640×480，物理输出报告为 320×240。
默认 `square` 构建仍为原 240×240 中文布局。

## 刷入

已有设备优先通过客户端手动选择横屏应用镜像升级，以保留配网、形象和配置。
若使用串口烧录应用，先确认活动分区：`ota_0` 地址 `0x10000`，`ota_1` 地址 `0x310000`。
不可把应用镜像写到 `0x0`，也不要在保留数据升级时整片擦除。
完整包中的 `hachimodock-s3-factory.bin` 用于 `0x0` 完整刷机，会替换资源和配置。
主机测试和编译不能验证屏幕实际旋转方向、颜色或完整硬件性能；刷入后需确认四角和文字方向。

修正组件中心：仅方屏使用原生列表覆盖；横屏执行原版卡片绘制，避免只显示黄色背景。
