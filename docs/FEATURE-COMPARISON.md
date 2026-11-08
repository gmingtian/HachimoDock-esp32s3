# S3 A4 与上游硬件的功能边界

本仓库基于 **Yizheng Wang / [YizhengWw/HachimoDock](https://github.com/YizhengWw/HachimoDock)**，当前适配发行源码为桌面端 0.1.202、S3 r16c。保留共享功能路径不代表所有云服务、外设批次和系统权限组合都已验证。

| 项目 | 当前 S3 A4 |
| --- | --- |
| 桌宠与 Agent 会话 | 原生 320×240 合成、中文、多会话气泡、动画与局部刷新优化 |
| 输入 | GPIO39/38/0 三颗按键＋GPIO1/2/8 摇杆；恢复官方操作方式 |
| 组件 | 共享组件路径，恢复像素方块、云端跳一跳、蛙蛙养成；鲜果一刀仍依赖触屏 |
| 五子棋 / 中国象棋 | 设备离线人机；象棋三档难度、全棋种合法落点引导、悔棋 |
| 自定义形象 | 转换为 S3 横屏规格，按槽容量、单段缓存、时长和音频限制校验 |
| 语音与生成 | 保留服务入口，需要凭据与网络；S3 为半双工，未声明经校准的全双工/AEC |
| USB / Wi-Fi | 串口与配对 TLS 局域网共用运行时协议；首次配置和 ROM 恢复使用 USB |
| 固件升级 | S3 芯片与独立项目校验、事务更新与回滚；P4 镜像不适用于 S3 |
| 桌面系统 | Windows x64、Apple Silicon macOS arm64、Linux x86_64 |

## 硬件差异

S3 N16R8 使用 16MiB Flash 和 8MiB PSRAM、320×240 ST7789 SPI 屏，不具备 P4 对应的显示加速和 USB High-Speed 480Mbps 能力。当前使用串口路径；S3 芯片的 USB 等级是 Full-Speed 12Mbps。共享游戏核心不意味着本次 S3 固件可刷入 P4。

部分共享组件仍从 640×480 逻辑布局适配；复杂组件的文字大小与操作体验可能有差异。80MHz 是这台屏幕的已试用配置，不是所有屏幕与线材的保证；素材规格不等于实测播放帧率。

## 桌面差异

Windows/macOS 的 Agent 输入控制依赖集成与系统权限；Linux 支持会话监测、串口、组件与独立语音路径，但暂不支持跨应用自动定位输入框、填字或发送。Linux 包需要系统库和外部 Python/FFmpeg。本分支不声明 macOS Apple 公证，也不发布 Intel Mac/Linux ARM 安装包。

历史 r1–r6 的方屏、25 个组件和纯三键筛选已被当前 A4 控件与组件策略取代；它们只在旧构建/版本记录中有历史意义。当前策略以 `firmware/s3/component-policy.json` 和 [A4 控件](ESP32-S3-A4-Controls.md)为准。

[安装与使用](INSTALLATION.md) · [兼容性](COMPATIBILITY.md) · [硬件交付](../hardware/README.md) · [许可证](../LICENSE) · [第三方声明](../THIRD_PARTY_NOTICES.md)
