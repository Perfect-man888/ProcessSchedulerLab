from collections.abc import Callable
from dataclasses import dataclass
from typing import Iterable

from PySide6.QtCore import QObject, Signal

from app.models.experiment_result import AlgorithmSkip, ExperimentReport
from app.models.process import Process
from app.models.schedule_result import ScheduleResult
from app.models.simulation_state import SimulationStatus
from app.schedulers.registry import SCHEDULER_FACTORIES
from app.services.process_manager import ProcessManager
from app.services.resource_manager import ResourceManager
from app.services.simulation_service import SimulationService
from app.styles.theme import TOTAL_IO_DEVICES, TOTAL_MEMORY_MB


@dataclass(frozen=True, slots=True)
class ProcessTemplate:
    name: str
    arrival_time: int
    burst_time: int
    priority: int
    deadline: int | None = None
    period: int | None = None
    memory_mb: int = 64
    io_devices: int = 0

    def instantiate(self, pid: str) -> Process:
        return Process(
            pid=pid,
            name=self.name,
            arrival_time=self.arrival_time,
            burst_time=self.burst_time,
            priority=self.priority,
            deadline=self.deadline,
            period=self.period,
            memory_mb=self.memory_mb,
            io_devices=self.io_devices,
        )


@dataclass(frozen=True, slots=True)
class ExperimentPreset:
    key: str
    name: str
    description: str
    processes: tuple[ProcessTemplate, ...]

    def instantiate(self) -> tuple[Process, ...]:
        return tuple(
            template.instantiate(f"P{index:03d}")
            for index, template in enumerate(self.processes, start=1)
        )


EXPERIMENT_PRESETS = (
    ExperimentPreset(
        "classic_mix",
        "经典混合负载",
        "长短作业交错到达，适合观察 SJF/SRTF 与 FCFS 的差异。",
        (
            ProcessTemplate("Batch-A", 0, 8, 4, 18),
            ProcessTemplate("Interactive-B", 1, 4, 1, 12),
            ProcessTemplate("Short-C", 2, 2, 2, 10),
            ProcessTemplate("Batch-D", 4, 5, 3, 22),
        ),
    ),
    ExperimentPreset(
        "interactive",
        "分时交互负载",
        "多个短任务密集到达，用于比较响应时间与上下文切换开销。",
        (
            ProcessTemplate("Editor", 0, 5, 2, 14),
            ProcessTemplate("Terminal", 0, 3, 1, 10),
            ProcessTemplate("Browser", 1, 4, 2, 13),
            ProcessTemplate("Sync", 2, 2, 3, 9),
            ProcessTemplate("Daemon", 3, 6, 5, 20),
        ),
    ),
    ExperimentPreset(
        "realtime",
        "实时截止期负载",
        "所有任务均带绝对 Deadline，可直接比较 EDF 的 Deadline Miss。",
        (
            ProcessTemplate("Sensor", 0, 3, 2, 6, 10),
            ProcessTemplate("Control", 1, 2, 1, 5, 8),
            ProcessTemplate("Telemetry", 2, 4, 3, 11, 12),
            ProcessTemplate("Logger", 4, 3, 4, 14, 15),
        ),
    ),
    ExperimentPreset(
        "convoy",
        "护航效应负载",
        "长作业最先到达，多个短作业紧随其后，用于对比 FCFS 与短作业策略。",
        (
            ProcessTemplate("Long-Batch", 0, 14, 3, 30),
            ProcessTemplate("Short-A", 1, 2, 2, 10),
            ProcessTemplate("Short-B", 2, 1, 1, 9),
            ProcessTemplate("Short-C", 3, 3, 2, 14),
        ),
    ),
    ExperimentPreset(
        "priority_contention",
        "优先级竞争负载",
        "高低优先级任务混合到达，用于观察抢占和低优先级饥饿。",
        (
            ProcessTemplate("Low-Background", 0, 10, 8, 28),
            ProcessTemplate("Urgent-A", 1, 3, 1, 8),
            ProcessTemplate("Urgent-B", 3, 2, 1, 11),
            ProcessTemplate("Normal", 4, 4, 4, 18),
            ProcessTemplate("Urgent-C", 6, 2, 2, 15),
        ),
    ),
    ExperimentPreset(
        "mlfq_mixed",
        "MLFQ 混合负载",
        "短交互任务与长 CPU 作业共存，用于观察队列降级与 Priority Boost。",
        (
            ProcessTemplate("CPU-Render", 0, 12, 5, 30),
            ProcessTemplate("Input", 0, 2, 1, 8),
            ProcessTemplate("Shell", 2, 3, 2, 12),
            ProcessTemplate("Index", 3, 8, 6, 27),
            ProcessTemplate("Notification", 5, 1, 1, 10),
        ),
    ),
)


class ExperimentCancelled(RuntimeError):
    """用户主动取消批量实验。"""


class ExperimentService(QObject):
    """在隔离副本上批量运行算法，保证当前交互仿真不被修改。"""

    progress = Signal(int, str)
    completed = Signal(object)

    DEFAULT_ALGORITHMS = tuple(SCHEDULER_FACTORIES)
    DISPLAY_NAMES = {
        "fcfs": "FCFS",
        "sjf": "SJF",
        "srtf": "SRTF",
        "priority": "Priority",
        "round_robin": "Round Robin",
        "edf": "EDF",
        "rms": "RMS",
        "mlfq": "MLFQ",
    }

    def run_all(
        self,
        processes: Iterable[Process],
        *,
        dataset_name: str = "当前进程集",
        rr_quantum: int = 2,
        priority_preemptive: bool = True,
        priority_aging_interval: int | None = None,
        mlfq_quanta: tuple[int, ...] = (1, 2, 4),
        mlfq_boost_interval: int = 10,
        should_cancel: Callable[[], bool] | None = None,
    ) -> ExperimentReport:
        source = tuple(processes)
        if not source:
            raise ValueError("实验数据集不能为空。")
        if rr_quantum <= 0:
            raise ValueError("Round Robin 时间片必须大于 0。")

        results = []
        skipped = []
        total = len(self.DEFAULT_ALGORITHMS)
        for index, key in enumerate(self.DEFAULT_ALGORITHMS, start=1):
            if should_cancel is not None and should_cancel():
                raise ExperimentCancelled("实验已取消。")
            display_name = self.DISPLAY_NAMES[key]
            self.progress.emit(round((index - 1) / total * 100), display_name)
            if key == "edf" and any(process.deadline is None for process in source):
                skipped.append(
                    AlgorithmSkip(key, display_name, "存在未填写 Deadline 的进程")
                )
                continue
            if key == "rms" and any(process.period is None for process in source):
                skipped.append(
                    AlgorithmSkip(key, display_name, "存在未填写 Period 的进程")
                )
                continue

            options = {}
            if key == "round_robin":
                options["quantum"] = rr_quantum
            elif key == "priority":
                options["preemptive"] = priority_preemptive
                options["aging_interval"] = priority_aging_interval
            elif key == "mlfq":
                options["quanta"] = mlfq_quanta
                options["boost_interval"] = mlfq_boost_interval

            manager = self._clone_manager(source)
            simulation = SimulationService(manager)
            simulation.load(key, **options)
            limit = self._safe_tick_limit(source)
            ticks = 0
            while simulation.state.status is not SimulationStatus.FINISHED:
                if should_cancel is not None and should_cancel():
                    raise ExperimentCancelled("实验已取消。")
                if not simulation.step():
                    raise RuntimeError(f"{display_name} 未能继续推进。")
                ticks += 1
                if ticks > limit:
                    raise RuntimeError(f"{display_name} 超过安全 Tick 上限。")
            results.append(simulation.build_result())

        report = ExperimentReport(
            dataset_name,
            tuple(results),
            tuple(skipped),
            (
                ("RR Quantum", str(rr_quantum)),
                ("Priority Mode", "Preemptive" if priority_preemptive else "Non-preemptive"),
                ("Priority Aging", f"{priority_aging_interval} Tick" if priority_aging_interval else "Off"),
                ("MLFQ Quanta", "/".join(str(value) for value in mlfq_quanta)),
                ("MLFQ Boost", f"{mlfq_boost_interval} Tick"),
            ),
        )
        self.progress.emit(100, "完成")
        self.completed.emit(report)
        return report

    def run_quantum_scan(
        self,
        processes: Iterable[Process],
        *,
        quantum_range: Iterable[int] = range(1, 9),
        should_cancel: Callable[[], bool] | None = None,
    ) -> tuple[tuple[int, ScheduleResult], ...]:
        """固定数据集上扫描 RR 时间片，返回 (quantum, 结果) 的有序序列。

        quantum 越小时间片切换越频繁，时延与切换开销随 quantum 增长而
        呈现不同的权衡曲线，用于观察 RR 量子对系统行为的影响。
        """
        source = tuple(processes)
        if not source:
            raise ValueError("实验数据集不能为空。")
        quanta = tuple(quantum_range)
        if not quanta or any(quantum <= 0 for quantum in quanta):
            raise ValueError("RR 时间片扫描范围必须为正整数。")

        limit = self._safe_tick_limit(source)
        scanned: list[tuple[int, ScheduleResult]] = []
        total = len(quanta)
        for index, quantum in enumerate(quanta, start=1):
            if should_cancel is not None and should_cancel():
                raise ExperimentCancelled("实验已取消。")
            self.progress.emit(round((index - 1) / total * 100), f"RR q={quantum}")

            manager = self._clone_manager(source)
            simulation = SimulationService(manager)
            simulation.load("round_robin", quantum=quantum)
            ticks = 0
            while simulation.state.status is not SimulationStatus.FINISHED:
                if should_cancel is not None and should_cancel():
                    raise ExperimentCancelled("实验已取消。")
                if not simulation.step():
                    raise RuntimeError(f"RR q={quantum} 未能继续推进。")
                ticks += 1
                if ticks > limit:
                    raise RuntimeError(f"RR q={quantum} 超过安全 Tick 上限。")
            scanned.append((quantum, simulation.build_result()))

        self.progress.emit(100, "完成")
        return tuple(scanned)

    @staticmethod
    def _safe_tick_limit(source: tuple[Process, ...]) -> int:
        """估算仿真推进的安全上限：到达时刻 + 总服务时间 + I/O 阻塞预算 + 余量。"""
        io_budget = sum(
            ((process.burst_time - 1) // process.io_interval) * process.io_duration
            for process in source
            if process.io_interval is not None and process.io_duration is not None
        )
        return max(process.arrival_time for process in source) + sum(
            process.burst_time for process in source
        ) + io_budget + 100

    @staticmethod
    def _clone_manager(source: tuple[Process, ...]) -> ProcessManager:
        resources = ResourceManager()
        # 性能实验是 CPU 调度隔离副本，不应被默认 8192 MB / 8 I/O
        # 意外拒绝；容量至少覆盖源数据集已经合法占用的资源。
        resources.configure_totals(
            max(TOTAL_MEMORY_MB, sum(process.memory_mb for process in source)),
            max(TOTAL_IO_DEVICES, sum(process.io_devices for process in source)),
        )
        manager = ProcessManager(resources)
        for process in source:
            manager.create_process(
                pid=process.pid,
                name=process.name,
                arrival_time=process.arrival_time,
                burst_time=process.burst_time,
                priority=process.priority,
                deadline=process.deadline,
                period=process.period,
                memory_mb=process.memory_mb,
                io_devices=process.io_devices,
                io_interval=process.io_interval,
                io_duration=process.io_duration,
            )
        return manager
