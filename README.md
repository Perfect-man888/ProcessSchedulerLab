# ProcessSchedulerLab

基于 Python 3.11 + PySide6 的操作系统进程调度可视化课程设计。项目以统一的离散 Tick 仿真引擎驱动 PCB 状态、资源占用、调度队列、事件流、甘特图和性能指标。

## 已实现功能

- PCB 全生命周期管理：创建、挂起、激活、撤销、搜索与状态筛选。
- 内存与 I/O 资源容量校验、原子分配和释放。
- FCFS、SJF、SRTF、抢占/非抢占 Priority、Round Robin、EDF、RMS 和三级 MLFQ；Priority 支持可配置 Aging，避免低优先级进程长期饥饿，并可纳入批量实验对比。RMS 采用"周期越短优先级越高"的静态优先级实时调度。
- 可配置上下文切换开销（0–3 Tick），切换期间 CPU 进入 SWITCH 片段，切换开销计入 CPU 利用率分母。
- 支持 I/O 阻塞行为：进程周期性进入 BLOCKED 状态并释放 CPU，I/O 完成后回到就绪队列。
- 启动、暂停、继续、单步、重置与多倍速运行。
- CPU 甘特图、当前时刻标记、实时事件流、PCB 指标和算法规则排序队列（含等待 I/O 阻塞队列）。
- MLFQ Q0/Q1/Q2 独立队列可视化，支持时间片降级与周期性 Priority Boost。
- 6 组可复现实验预设与 8 种算法一键对比，输出等待、周转、带权周转、响应、CPU 利用率、吞吐率、上下文切换和 Jain's Fairness Index 等指标；批量计算在线程中执行，支持实时进度与取消。
- RR 时间片灵敏度扫描：固定数据集上扫描 Quantum 1–8，绘制周转/响应/切换开销随时间片变化的权衡曲线。
- 随机进程生成器：泊松到达（指数间隔）+ 截断指数服务时间，固定种子可完全复现，适合蒙特卡洛重复实验，可在进程页一键生成并加入当前 PCB 列表。
- Windows、Linux、Android 与 iOS 调度机制交互式分析，含技术/经济原因、横向对比矩阵及 12 个官方资料入口。
- JSON 实验数据集导入/导出，CSV 总表与进程明细导出，甘特图和性能图表 PNG 导出，以及包含实验配置、指标、结论、图表和逐进程明细的整页 PDF 报告。
- 系统设置支持总内存、I/O 设备数、默认时间片和仿真速度配置，提供持久化、合法性校验、运行中锁定、示例数据恢复和全部数据重置。
- 内置帮助与关于页面，集中说明使用流程、算法适用场景、常见问题和项目技术信息。
- 当前采用单 CPU、离散 Tick、单次作业模型；`Period` 作为周期任务扩展元数据保存，尚不自动重复释放任务。

## 运行

```powershell
python main.py
```

若使用项目虚拟环境，请先安装 `requirements.txt` 中的依赖；参与开发时安装 `requirements-dev.txt`。

## 测试

```powershell
pytest -q
```

当前自动化回归共 216 项，覆盖数据模型、资源事务、全部调度算法、Priority Aging、上下文切换开销、I/O 阻塞生命周期、RMS、公平性指标、RR 量子扫描、随机生成器、仿真状态机、后台实验、指标对比、数据导入导出、PDF 报告、持久化设置、系统分析与核心 UI 交互；语句与分支综合覆盖率超过 90%。无显示器环境可设置 `QT_QPA_PLATFORM=offscreen`。

```powershell
python -m ruff check app tests main.py
pytest --cov=app --cov-report=term-missing
```

GitHub Actions 会在 Windows + Python 3.11.9 环境中自动执行相同的静态检查、测试与 90% 覆盖率门禁。

## 项目结构

- `app/models`：PCB、调度分段、仿真状态和实验结果数据模型。
- `app/schedulers`：统一调度器接口及各算法实现。
- `app/services`：进程、资源、仿真、系统设置、对比实验和导入导出服务。
- `app/ui` 与 `app/widgets`：主页面和可复用可视化组件。
- `tests`：自动化单元、集成和 UI 冒烟测试。
- `docs/screenshots`：各阶段界面验收截图。
- `docs/ProcessSchedulerLab_使用说明书.docx`：安装、操作、实验、导出、排错和答辩演示的完整使用手册。
