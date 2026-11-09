# A4 硬件交付索引

当前配套：ESP32-S3 A4 载板、R4.4 上下盖、三颗按键＋四向摇杆（可按下）、320×240 横屏。目标发行 `v0.1.202-s3-a4-r16c`。

| 用途 | 当前文件 |
| --- | --- |
| PCB 制板 | [A4 Gerber ZIP](s3-carrier/output/HachimoDock-S3-carrier-A4-Gerber.zip)，双层、1.6mm，含铜层/阻焊/丝印/板框及 PTH/NPTH 钻孔 |
| 可编辑电路 | [KiCad PCB](s3-carrier/output/HachimoDock-S3-carrier-A4.kicad_pcb)、[原理图](s3-carrier/output/HachimoDock-S3-carrier-A4.kicad_sch)、同目录 `.kicad_pro`、`fp-lib-table`、`sym-lib-table`、`S3_Carrier.pretty/`、`S3_Carrier.kicad_sym`，需一起保存 |
| 装配 | [BOM](s3-carrier/output/BOM.csv)、[接线表](s3-carrier/output/connections.csv)、[原理图 PDF](s3-carrier/output/HachimoDock-S3-carrier-A4-schematic.pdf)、[方向图](s3-carrier/output/assembly-orientation.png) |
| 正式上盖 | [a4-upper-r4.4-hachimo.stl](enclosure-a4/output/r4-original-copy/full-r4.4/a4-upper-r4.4-hachimo.stl)，单位 mm |
| 正式下盖 | [a4-lower-r4.4-speaker.stl](enclosure-a4/output/r4-original-copy/full-r4.4/a4-lower-r4.4-speaker.stl)，单位 mm |
| 三键帽＋摇杆打印件 | [原版独立打印件](enclosure-a4/print-parts/README.md)：三键帽各一件、摇杆帽 A/B/盖板各一件，mm 原尺寸，附源 SHA 与逐件校验 |
| 可编辑壳体实体 | [working-r4.4-full.step](enclosure-a4/output/r4-original-copy/full-r4.4/working-r4.4-full.step) |
| 设计输入与过程源 | PCB `s3-carrier/reference/`、`tools/`、`tests/`；外壳 [原始 STEP](enclosure-a4/reference/original-assembly.STEP)、`enclosure-a4/` Python 和参数、`fusion/` 脚本、桥接插件与字标资产 |
| 完整性 | [release-manifest.json](release-manifest.json)，按相对仓库路径记录推荐交付文件的字节数及 SHA-256 |

制造输出的核心 SHA-256：

| 文件 | SHA-256 |
| --- | --- |
| A4 Gerber ZIP | `f37d6a4aacb843249476b656e248e3e576f963c258f840ecbc87fd694797cb69` |
| A4 KiCad PCB | `3ea5f653f6bf27bdb09c90290e1f22ae493803e0c346911ff89b9b5f40b8624e` |
| R4.4 上盖 STL | `01d77478ed527ab42ce805d199b169055bbe6fa60e9182cd0038c1b7b9c5825d` |
| R4.4 下盖 STL | `608fb8056016b028f99e9a6d6622f4be27979261779831fed110d7f0a131031a` |

## 装配与验证边界

PCB 已焊接，这台设备已装壳并完成画面、按键及摇杆操作反馈；[真实照片](../README.md#实物)保留原图。PCB 网络和制造 ZIP 未因本次发布整理而改变。原生 DRC、原理图网表和制造层校验与原文件哈希绑定；旧报告中的“尚未实物验证”是报告生成时状态，不冒充批量验收或认证。

R4.4 使用 H3/H4 两处 M2.5 热熔铜螺母固定、H1 定位，屏幕由四颗 M2 自攻固定。早期原壳 H1/H4 说明与示意只作历史参考。屏幕/USB/线束、热熔松紧、实际打印孔缩及极限摇杆行程应按自己器件确认。无线天线净空和原版摇杆与右键帽的既有边界见[PCB 说明](s3-carrier/README.md)与[外壳说明](enclosure-a4/README.md)。

## 文件选择

只使用上表推荐的 A4 / R4.4 制造件。早期 A0–A3、R0–R4.3、试装骨架、baseline/重复 assembly STL 和历史 3MF 仍可留在开发者本机，但不推荐为当前下载。当前没有 R4.4 F3D/3MF；STEP 为可移植编辑入口，STL 为切片入口。三颗键帽及摇杆多件结构已从原始命名 3MF 单独提取到 `enclosure-a4/print-parts/`，原打印机配置不随零件公开。

交付清单排除本机 Fusion IPC 队列、缓存、KiCad 本地偏好、日志和重复/历史制造输出。提供了原始几何、可编辑板图及实际制造件；Fusion 过程脚本依赖相应 CAD 和会话，不承诺一键无头复现。上游来源和许可见仓库 [LICENSE](../LICENSE)及[第三方声明](../THIRD_PARTY_NOTICES.md)，本次整理不改变其归属。
