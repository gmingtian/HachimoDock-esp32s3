# 安装与使用

HachimoDock-esp32s3 提供 Windows、macOS 和 Linux 客户端，配套 ESP32-S3 N16R8 三键固件。

## 下载安装

从[本仓库 Releases](https://github.com/gmingtian/HachimoDock-esp32s3/releases) 下载对应系统的文件。安装包和系统要求如下；具体文件以各版本附件为准。

| 平台 | 下载文件 | 系统要求 |
|---|---|---|
| Windows | `HachimoDock-esp32s3_Windows-x64.exe` | x64 Windows；安装程序会准备 WebView2，首次安装可能需要联网 |
| macOS | `HachimoDock-esp32s3_macOS-arm64.dmg` | Apple 芯片，macOS 12 或更高版本 |
| Linux | `HachimoDock-esp32s3_Linux-x86_64.tar.gz` | x86_64、glibc ≥ 2.39，GTK3、WebKitGTK 4.1、ALSA、udev、OpenSSL 3 |
| 首次刷机 | `HachimoDock-esp32s3_Firmware-r1.zip` | ESP32-S3 N16R8，240×240 ST7789 与指定 IO 接线 |
| 应用升级（可选） | `HachimoDock-esp32s3_App-r1.bin` | 通过配套客户端升级已有 S3 应用 |

Windows：运行安装程序，按向导完成安装。当前安装包未做商业代码签名。

macOS：打开 DMG，将 HachimiDock 拖入 Applications。应用采用 ad-hoc 签名，未做 Apple 公证。如系统阻止打开，核对下载来源与 SHA-256 后，在系统“隐私与安全性”中使用针对该应用的“仍要打开”。不要关闭系统整体安全保护。

Linux：解压后运行 `./launch.sh`。本包需要系统运行库，不是自包含 AppImage；自定义形象转换还需 Python 3.10+ 与包含 `libx264` 的 FFmpeg。依赖、构建和串口权限详见 [Linux 客户端](https://github.com/gmingtian/HachimoDock-esp32s3/blob/main/pc/docs/linux-native.md)。

Windows / macOS 包含 Node、媒体运行工具、S3 素材转换器以及对应源代码和许可，无需另装 Node、Python 或编译器。各系统的凭据和本机权限需要分别配置。

## 连接设备

1. 使用支持数据传输的 USB 线连接设备与电脑。
2. 启动客户端，在设备页选择 ESP32-S3 对应串口；连接信息应显示 S3、16MiB Flash、8MiB PSRAM 和 240×240 屏幕。
3. 在 Agent 页面配置并选择要跟随的会话。设备会显示工作、等待、完成、错误等状态和多会话气泡。
4. 在 API 设置中填写所需的语音、对话或形象生成服务凭据。macOS 的 Agent 输入框控制及麦克风使用需按提示授予相应系统权限。

安装或启动客户端不会自动刷写设备。

## 三键操作

| 按键 | 短按 | 长按 / 按住 |
|---|---|---|
| GPIO39 | 上一项 | 返回 |
| GPIO38 | 下一项 | 组件菜单 |
| GPIO0 | 确认 | 按住录音，松开结束 |

侧键位置以实际接线为准；GPIO0 在上电或复位时须松开。组件附加动作通过菜单与软件光标操作，完整说明见 [硬件接线](https://github.com/gmingtian/HachimoDock-esp32s3/blob/main/docs/ESP32-S3-Linux.md)。

## 固件安装与恢复

首次从小智改刷时，先保存原小智固件，再将固件 ZIP 内的 `hachimodock-s3-factory.bin` 从地址 `0x0` 写入。完整刷机会替换原固件及配置。应用分区镜像以 `HachimoDock-esp32s3_App-r1.bin` 单独提供，不能替代完整出厂镜像；官方 P4 镜像不适用于 S3。

固件 ZIP 根目录只包含 `hachimodock-s3-factory.bin`、`使用说明.txt`、`SHA256SUMS` 和 `licenses/`，日志、测试记录和开发元数据保留在源码与构建记录中。

接线、分区与固件构建见 [ESP32-S3 适配说明](https://github.com/gmingtian/HachimoDock-esp32s3/blob/main/docs/ESP32-S3-Linux.md)。平台差异与硬件状态见 [兼容性说明](https://github.com/gmingtian/HachimoDock-esp32s3/blob/main/docs/COMPATIBILITY.md)。

## Wi-Fi（S3 r1）

客户端 0.1.168 在设备页面提供“设备连接”：先通过 USB 配置 2.4GHz 网络并
绑定此电脑，再选择“使用 Wi-Fi”。无线可使用现有 S3 运行时功能；首次刷机和
ROM 恢复继续使用 USB。详细配网、优先级和恢复步骤见 [Wi-Fi 使用说明](WIFI.md)。

## 当前 r1 的已知问题

此 r1 是发布编号重置，包含原 r4 的启动和 USB 修复。设备连上路由器后，
电脑仍需通过 USB 绑定再切换 Wi-Fi。部分 Windows 使用中，绑定被“资源或
固件正在传输”拦截，原因尚待定位；不承诺无线绑定或重启后无线恢复已通过实机验收。
