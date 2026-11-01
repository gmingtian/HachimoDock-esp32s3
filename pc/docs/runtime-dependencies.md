# 原生运行时依赖 / Native runtime dependencies

客户端 0.1.170 统一为 S3 生成 320×240 / 15fps / CRF27 形象，不再选择方屏
配置。标准 `firmware/esp32-s3/firmware.bin` 是横屏固件；P4 的芯片分流仍保留。
安装包另含独立的 `s3-landscape-ui`，用于保持全部 25 个内置组件的原生图片。
普通组件包仍先通过原校验；仅源文件与内置清单完全一致时替换设备图片，
不会按相同组件 ID 覆盖用户修改的内容。

原生构建的资源检查覆盖应用版本、固定固件摘要、组件资源清单和真实
320×240 转换/解码。Windows 包自带转换器和独立 FFmpeg/x264，无需用户
安装 Python。Linux 开发包仍依赖主机 Python3 和支持 libx264 的 FFmpeg。

已有固件的一键升级版本比较暂按核心版本号执行；同核心版本的修订包
需要从设备页手动选择固件镜像。应用升级只改程序，新的组件图片通过
重新安装/修复组件发送，默认宠物也可重新同步；不会要求整片擦除配置。

Node.js 使用对应系统/架构的官方可重定位发行包，通过 `PET_MANAGER_NODE_BIN` 指定可执行文件。不要使用依赖 Homebrew 动态库的 Node 构建打包分发。

FFmpeg 为独立可执行文件。可从 HachimiDock **v0.1.167** 正常公开版安装包取得配套文件（在干净环境解包，先核对 Release 的 SHA-256）。macOS DMG 中位于 `HachimiDock.app/Contents/Resources/tools/`；Windows 安装目录位于 `tools/`。源码压缩包也作为该 Release 独立附件提供。不需要安装或启动客户端来构建源码。

将下列环境变量指向对应系统与架构的文件：

| 变量 / Variable | 文件 / File |
|---|---|
| `PET_MANAGER_NODE_BIN` | 官方 Node 可执行文件 / official relocatable Node executable |
| `PET_MANAGER_FFMPEG_BIN` | `ffmpeg` 或 `ffmpeg.exe` |
| `PET_MANAGER_FFMPEG_README` | `ffmpeg.README` |
| `PET_MANAGER_FFMPEG_LICENSE` | `ffmpeg.LICENSE` |
| `PET_MANAGER_FFMPEG_SOURCE_ARCHIVE` | `FFmpeg-8.1.2-source.tar.xz`（或随包同内容源码） |
| `PET_MANAGER_ZLIB_LICENSE` | Windows 所需 `zlib.LICENSE` |

准备脚本会校验架构、版本和 SHA-256，并将文件复制到 `src-tauri/generated-runtime/`。该目录为自动生成的构建资源，无需加入版本控制。

需要自行重编译 FFmpeg 时，使用随包 README 的完整构建参数及对应源码，并在审查后更新 `scripts/prepare-desktop-resources.mjs` 中目标哈希；不要删除来源与许可校验。自行编译的文件可能具有不同的 SHA-256，需要同步更新校验值。

编译客户端不需要云服务 Key；运行语音识别或形象生成时，再在客户端配置所用服务。

电脑状态组件使用 `sysinfo`（锁定版本见 Cargo.lock），只启用 system/network 功能；只刷新 CPU、内存与网络计数，不枚举进程、用户名、主机名或文件。上游接口说明见 [System](https://docs.rs/sysinfo/0.39.6/sysinfo/struct.System.html) 与 [Networks](https://docs.rs/sysinfo/0.39.6/sysinfo/struct.Networks.html)。其 MIT 版权声明随 macOS / Windows 安装资源的 `licenses/sysinfo-LICENSE.txt` 一起保留。
