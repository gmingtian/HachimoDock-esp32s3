# 当前接续：R4 原版实体复制

用户最终明确：以原版 STEP 实体为母版，外形只略放大；按键、摇杆、凹槽深度与原版接合结构照搬，内部空间和屏幕安装重新适配，左侧为双 Type-C。此前 R2/R3 完成记录和重画外形均已被本要求取代。

R4 复制原实体，在屏幕段 V=43 mm 插入原截面8.5 mm，总宽增3 mm；原版操作区实体恢复原尺寸和坐标。屏幕内装四个 M2 自攻圆柱，PCB H3/H4 为 M2.5×4×3.5 热熔螺母，H1 塑料定位。底部和上方收音孔同时保留。当前 R4 安装、面框视线、错误孔洞检查及最终 STL 导出回读完成。球帽18,360姿态无新增碰壳；未测枢轴的极限杆体模型仍有约0.268 mm³新增交集，保留原版操作区并明确为试装件。实物行程与USB插头尚待确认，不交付 R1/R2/R3。

以下为历史过程记录，不表示当前 R4 已最终验收。

---

# Fusion 外壳 API 接续 Implementation Plan

> **For agentic workers:** Execute inline in the current authorized workspace. The user already chose API execution. No subagents, new worktree, commit or push is needed for this local CAD task.

**Goal:** 接通 Fusion 主线程 API，修正圆形固定结构和连续屏幕过渡，导出并校核 STL。

**Architecture:** 会话插件读取本地请求队列，使用 Fusion CustomEvent 在主线程串行执行。参考文档保持只读，编辑在独立工作文档进行；几何接口输入输出均为毫米，内部转换为 Fusion 厘米。

**Tech Stack:** Fusion Python API、Python 标准库、现有 STL 验证工具。

**Spec:** `docs/superpowers/specs/2026-11-07-fusion-enclosure-api.md`

## Global Constraints

- 只交付 STL；现有原版文件不覆盖；不提交或推送。
- 不开网络端口，不执行 JSON 内的代码，不自动启动。
- 用户只需在 Fusion 内加载一次本地插件。
- 参考 STEP/3MF、PCB 坐标和原帽子保留；H3/H4 固定、H1 塑料定位按用户要求复核。

### Task 1: 会话协议与插件

Files: `hardware/enclosure-a4/fusion/FusionEnclosureBridge/{bridge_protocol.py,bridge_runtime.py,FusionEnclosureBridge.py,FusionEnclosureBridge.manifest}`; tests: `hardware/enclosure-a4/fusion/tests/test_bridge_protocol.py`.

- [x] 先测试 `mm_to_cm(25.4)==2.54`、非法数值拒绝、请求 ID 和操作白名单、越界路径拒绝、原子 JSON 写回；确认旧状态缺少协议模块导致失败。
- [x] 实现 `validate_request(data)->dict`、`mm_to_cm(value)->float`、`point_cm(values)->list`、`matrix_cm(values)->list`、`within_root(path,root)->Path`、`atomic_json(path,data)`。
- [x] 实现主线程事件、停止清理、会话 ID 去重和响应文件；`run(context)` 仅启动接口并写状态。
- [x] 运行 `python -m unittest discover -s hardware/enclosure-a4/fusion/tests -v` 和 `py_compile`；请求用户启动已准备好的插件。

### Task 2: Native CAD 操作与接通验收

Files: `hardware/enclosure-a4/fusion/FusionEnclosureBridge/fusion_ops.py`.

- [x] 实现白名单 `ping/import_step/new_document/inspect/copy_body/cylinder/box/combine/transform/fillet/export_stl/export_step/snapshot`。
- [x] `import_step` 注册只读参考文档，`new_document` 创建直接建模工作文档；所有修改拒绝未注册文档和参考文档。
- [x] 接通后提交 ping、导入原 STEP、读取孔轴和高度，写入 `output/r2-fusion/reference-inspection.json`。
- [x] 创建 10×20×30 mm 测试块并导出 STL，外部回读尺寸确认毫米转换正确。

### Task 3: 固定结构和一体造型

- [x] 从参考实体读取 H4 圆孔轴、孔深和贴 PCB 面高度，建立 H3 缺失的失败几何检查。
- [x] 在工作副本中将相关固定座改圆柱，补中间 H3，核对前后与 PCB 的孔轴和完整固定路径。
- [x] 消除分离面框台阶，以原曲面为边界做连续连接并圆角，保留屏幕内装柱和焊点空间。
- [x] 校核低位音频模块、双 USB、三键按压、原球帽新增结构包络和声孔。

### Task 4: STL 验证与交付

- [x] 导出 `a4-upper-r2-print.stl` 与 `a4-lower-r2-print.stl`，回读尺寸、实体数、封闭性、孔位和螺丝路径。
- [x] 在 Fusion 与原件对照检查内侧和外侧形状；仅提供 STL 链接和必要装配差异。

## Verification commands

```powershell
python -m unittest discover -s hardware/enclosure-a4/fusion/tests -v
python -m py_compile hardware/enclosure-a4/fusion/FusionEnclosureBridge/*.py
```

当前任务在原有工作区内继续，因为未提交的 CAD 参考和生成文件已位于该工作区；保存原件与旧版成果，新增 R2 输出目录。

验收完成：接口 11 项测试通过；10×20×30 mm 校准通过；实际导出 STL 的前壳 H3/H4 完整承座与螺丝路径通过；屏幕四柱和四角壁、模块/PCB、按键 0～4 mm 及 18,360 姿态摇杆检查通过。导出前后壳 STL，回读为毫米、封闭单实体。实物试装仍未进行；不提交、不推送。
