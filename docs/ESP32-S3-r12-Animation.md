# S3 r12 动画优化实机记录（2026-11-07）

当前设备运行 `0.7.103-s3-r12-80m-l320`，OTA_1，LCD SPI 保持 80MHz。
用户实物确认：“显示正常，动画更顺畅”。原 r11/80MHz 保留在 OTA_0。

## 本轮结果

同机、同一已安装宠物、首页 `main`、待机 `idle` 状态，串口每两秒查询一次。
每组采集约 38 秒，丢弃前 10 秒；各取 14 个诊断样本。FPS 使用 LCD 实际
提交帧数的差值除以设备 uptime 差值，而非 SPI 理论带宽或素材标称帧率。

| 指标 | 原 r11 渲染路径（诊断版 r12p） | r12 优化后 |
| --- | ---: | ---: |
| 实际提交帧率 | 5.732 FPS | 6.814 FPS |
| 整帧中位耗时 | 165.083ms | 135.172ms |
| 颜色转换/放大中位耗时 | 91.121ms | 64.540ms |
| 解码中位耗时 | 32.364ms | 28.469ms |
| UI 合成中位耗时 | 9.761ms | 9.944ms |
| 缩小/旋转中位耗时 | 10.608ms | 10.395ms |
| LCD 传输中位耗时 | 20.093ms | 20.828ms |

本场景帧率提升约 **18.88%**，颜色转换耗时降低约 **29%**。解码时间也随
素材帧和调度变化，不能将其差值都归因于转换代码。各阶段中位数来自独立
统计，不能逐项相加还原整帧中位数。这不是所有组件、语音或交互场景的
帧率保证；素材最高 15fps 不代表设备已达到 15fps。

诊断基线 `0.7.103-s3-r12p-80m-l320` 只在 r11 代码上增加只读计时字段，
未改变颜色转换路径；较早 r11 工作状态下测得的约 5.92fps 不作为本次
待机状态对照。原始采样和计算脚本位于 `.build-tools/s3-r12/`。

## 修改范围与验证

`scale_h264_frame_cpu()` 对最终恰好放大两倍、宽度不超过 320 的 S3 I420
素材，先在 320 像素（640 字节）的局部行缓冲中按原 BT.709 算法转换并
处理近黑背景，然后复制到已有 640×480 逻辑画布。减少放大后重复处理和
PSRAM 访问。旧尺寸继续走通用路径，P4 路径保持原样。

未增加全帧缓冲、改变素材质量、颜色公式、按键映射、音频参数或调度节奏。
`runtime.renderStages` 在既有计时边界采样，和 `renderLastUs` 是同一个
已完成帧。`decodeUs`/`convertUs` 包含于 `assetUs`，`gapUs` 是绘帧前间隔，
不要把它们额外加到整帧总耗时中。

- 新回归先在旧代码上因重复背景扫描超出工作量上限而失败，优化后通过。
- 逐像素比较随机及近黑边缘、内部暗色细节、带 stride/storage 填充、
  横竖留边和旧尺寸；MSVC AddressSanitizer 执行通过。
- 已有 `s3_video_performance_test.py` 中 P4、S3 两套真实函数测试经本机
  MSVC AddressSanitizer 执行通过。没有把 Windows ASAN 冒充 UBSAN。
- 审查发现的两处旧 metrics 测试桩已补齐 `last_stages`，新增同帧替换及清零
  断言；普通、保留峰值阶段、节点峰值三组计时配置通过 MSVC ASAN。
  本机测试仅兼容处理 GNU 内联属性，不据此证明 IRAM 放置行为。
- ESP-IDF 6.1 编译通过；编译器内联后 `render_asset_pet_frame` 静态栈 3088
  字节、`pet_p4_renderer_render` 400 字节，主任务配置 16384 字节。这两个
  静态数值不是完整调用图或实机高水位证明。
- 实机 `runtimeReady=true`、`pendingVerify=false`；`imageState=undefined`，
  不将其称为 OTA valid。累计历史故障数保持 1，最后 USB 复位为非故障。
- A4 输入模型 `s3-a4-buttons-joystick-v1`、16 项绑定验收通过。
- 用户实物确认显示正常、动画更顺畅。

启动时组件目录恢复本身约需 16 秒，随后才初始化串口 RX。启动采样等待
70 秒再查询，避免把过早查询产生的串口超时误判为崩溃。

## 固件、备份与开发接续

应用：`artifacts/s3-animation-r12/hachimodock-s3-r12-optimized.bin`，2,581,120 字节。

SHA256：`5e9d3494fc683a5ee2efab10bd36a6e39cc18bc99f75e33075fd17cc984ceeba`。

仅写入 OTA_1（0x310000），使用官方 otatool 切换启动项；写入前先选回原
r11/OTA_0，保证写入失败仍有原应用可启动。未擦除 NVS、形象和组件存储。
回退在工作区根目录运行 `.build-tools/s3-r12/switch.ps1 -Slot 0`；将设备
切回 r12 使用 `-Slot 1`。串口操作前关闭桌面端以释放 COM3。

刷写前 16MiB 完整 Flash 备份及分区表位于 `artifacts/a4-flash-backup/`：
`before-r12-backup-receipt.json` 记录路径、分区和摘要。备份 SHA256 为
`80c349a26c823963022b039eac6d085a83d00af2e37fed156e27ee48939d21e4`。
备份和串口原始日志含设备/用户数据，不随公开固件发布。

重建本次 80MHz 应用，在工作区根目录执行：

```powershell
.build-tools/s3-r12/build.ps1 -Version '0.7.103-s3-r12-80m-l320' -OutputName optimized
```

该入口显式指定 ESP32-S3、landscape-left、`PET_S3_LCD_SPI_HZ=80000000`。
常规 `build-local.ps1 -Target S3` 默认标签更新为 r12-l320，仍显式指定
40MHz，不能用于重建此 80MHz 镜像；本轮未重新构建或测量 40MHz 版本。
SDK、MSVC、原生测试和实机日志保留在本地，未依赖 Docker 或远程代码传输。

桌面端 0.1.201 可读取新增的可选诊断字段，无需因本轮固件优化重装。
客户端内置固件继续保留已验收的 r10/40MHz，不将这次试验版自动打包推广。
本轮没有提交、推送或发布代码。
