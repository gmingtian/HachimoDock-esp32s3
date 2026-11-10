# ESP32-S3 A4 接线与构建

当前目标为果云 ESP32-S3 N16R8（16MiB Flash / 8MiB PSRAM）、A4 载板、三颗按键＋四向摇杆、240×320 ST7789 横装为 320×240。固件替换原小智功能，配套客户端为 0.1.203。历史 1.54 寸方屏和纯三键操作不是本次交付目标。

## 接线

| 模块 | GPIO / 接口 |
| --- | --- |
| LCD | CLK21、MOSI47、RST45、DC40、CS41、背光42；VCC3V3/GND |
| INMP441 | WS4、BCLK5、DIN6 |
| MAX98357A | DOUT7、BCLK15、LRCK16；喇叭接功放 SPK+/SPK−，SPK− 不接地 |
| SW1 / SW2 / SW3 | 39 / 38 / 0，按下接 GND，内部上拉 |
| 摇杆 X / Y / 按下 | 1 / 2 / 8 |

GPIO0 上电/复位时松开。屏幕正视排线在左，建议短线；80MHz SPI 在本机已验收，其他屏幕/线材需自行核验。按键默认语义、摇杆校准及游戏操作见 [A4 控件](ESP32-S3-A4-Controls.md)，原理图、PCB 和装配针序见 [A4 硬件](../hardware/s3-carrier/README.md)。

## 构建

加载 ESP-IDF 6.1 环境后，在仓库根目录构建。默认横屏、40MHz；当前发行版使用已实测的 80MHz，命令中显式指定：

```sh
source /path/to/esp-idf/export.sh
HACHIMO_S3_DISPLAY_PROFILE=landscape-left HACHIMO_S3_LCD_SPI_HZ=80000000 bash firmware/tools/build_s3.sh
```

脚本生成 `artifacts/s3-landscape-left/hachimodock-s3-factory.bin` 与 `hachimodock-s3-app.bin`，不会连接或刷写设备。要明确复现 80MHz 的应用构建，可单独执行：

```sh
idf.py -C firmware -B artifacts/s3-a4-80m-build \
  -DIDF_TARGET=esp32s3 -DPET_S3_DISPLAY_PROFILE=landscape-left \
  -DPET_S3_LCD_SPI_HZ=80000000 build
```

单独 `idf.py` 只构建应用及 IDF 输出，不等于已经生成完整 factory 资源包。发布附件和当前版本字符串以 Release 构建清单为准，不要把默认脚本输出冒充已经验证的 r16c 冻结镜像。Linux 客户端环境与构建见 [原生客户端](../pc/docs/linux-native.md)；Docker 是可选构建环境，不是游戏运行依赖。

## 分区与升级

| 区域 | 容量 |
| --- | ---: |
| 应用 A/B | 各 3MiB |
| 组件与配置存储 | 3.875MiB |
| 内置/自定义形象槽 | 各 3MiB |
| 引导/分区/NVS/OTA 元数据等 | 剩余空间 |

PSRAM 为运行缓存，不能当作额外 Flash。双应用分区供升级/回滚，双形象槽供事务更新；镜像、素材和缓存都需符合各自上限。共享组件仍可使用 640×480 逻辑坐标，最终物理输出为 320×240。

只有完整 factory 镜像从 `0x0` 写入；应用镜像用于匹配的应用分区或客户端 OTA，不能写入 `0x0`。首次改刷会覆盖旧固件、配置及资源，先保存自己的恢复包。S3 升级器核对芯片与独立项目名，拒绝 P4 镜像。安装客户端不会自动刷机，详细流程见 [安装与恢复](INSTALLATION.md)。

## 功能与验收边界

当前保留原生合成、80MHz、动画与返回首页恢复优化；恢复云端跳一跳、像素方块、蛙蛙养成，并支持设备离线五子棋/中国象棋。组件安装/修复需要配套客户端；只刷应用不会补齐旧资源。

用户已确认本机画面、象棋引导和按键正常；r16c 的搜索一致性与设备自动验收见 [记录](ESP32-S3-r16c-Xiangqi-Speed.md)。成功编译不能替代另一块板的屏幕、音频、USB/Wi-Fi、持续运行和供电验收。当前 S3 语音为半双工，未声明校准后的全双工/AEC；Linux 不支持跨应用自动定位输入框、填字或发送。
