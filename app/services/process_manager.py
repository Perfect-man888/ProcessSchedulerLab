
from PySide6.QtCore import QObject, Signal

from app.models.process import Process, ProcessState
from app.services.resource_manager import ResourceManager


class ProcessManager(QObject):
    """
    进程生命周期统一管理器。

    负责：
    - 创建进程
    - 撤销进程
    - 挂起进程
    - 激活进程
    - 查询 PCB
    - PID 分配
    - 状态统计
    """

    changed = Signal()

    activity = Signal(
        str,  # time
        str,  # event
        str,  # pid
        str,  # detail
    )

    RESERVED_PIDS = frozenset({"SWITCH"})

    def __init__(
        self,
        resource_manager: ResourceManager,
        parent=None,
    ):
        super().__init__(parent)

        self.resource_manager = resource_manager

        self._processes: dict[str, Process] = {}

        self._next_pid = 1

        self.simulation_time = 0

    # =========================================================
    # 查询
    # =========================================================

    @property
    def processes(self) -> list[Process]:
        return list(self._processes.values())

    def get_process(
        self,
        pid: str,
    ) -> Process | None:
        return self._processes.get(pid)

    def state_counts(self) -> dict[ProcessState, int]:
        counts = {
            state: 0
            for state in ProcessState
        }

        for process in self._processes.values():
            counts[process.state] += 1

        return counts

    # =========================================================
    # 创建进程
    # =========================================================

    def create_process(
        self,
        *,
        pid: str | None = None,
        name: str,
        arrival_time: int,
        burst_time: int,
        priority: int,
        memory_mb: int,
        io_devices: int,
        deadline: int | None = None,
        period: int | None = None,
        io_interval: int | None = None,
        io_duration: int | None = None,
    ) -> Process:

        name = name.strip()

        if not name:
            raise ValueError("进程名称不能为空。")

        if arrival_time < 0:
            raise ValueError("到达时间不能小于 0。")

        if burst_time <= 0:
            raise ValueError("服务时间必须大于 0。")

        if priority <= 0:
            raise ValueError("优先级必须大于 0。")

        if memory_mb <= 0:
            raise ValueError(
                "内存需求必须大于 0 MB。"
            )

        if io_devices < 0:
            raise ValueError(
                "I/O 设备数量不能小于 0。"
            )

        if (
            deadline is not None
            and deadline <= arrival_time
        ):
            raise ValueError(
                "Deadline 必须大于到达时间。"
            )

        if period is not None and period <= 0:
            raise ValueError(
                "Period 必须大于 0。"
            )

        if io_interval is not None and io_interval <= 0:
            raise ValueError("I/O 请求间隔必须大于 0。")

        if io_duration is not None and io_duration <= 0:
            raise ValueError("I/O 持续时间必须大于 0。")

        if (io_interval is None) != (io_duration is None):
            raise ValueError("io_interval 与 io_duration 必须同时提供或同时为空。")

        automatic_pid = pid is None
        if automatic_pid:
            resolved_pid = f"P{self._next_pid:03d}"
        else:
            resolved_pid = pid.strip()
            if not resolved_pid:
                raise ValueError("PID 不能为空。")
            if resolved_pid.upper() in self.RESERVED_PIDS:
                raise ValueError(f"PID {resolved_pid} 是系统保留标识，不能用于进程。")
            if resolved_pid in self._processes:
                raise ValueError(f"PID {resolved_pid} 已存在。")

        process = Process(
            pid=resolved_pid,
            name=name,
            arrival_time=arrival_time,
            burst_time=burst_time,
            priority=priority,
            deadline=deadline,
            period=period,
            memory_mb=memory_mb,
            io_devices=io_devices,
            io_interval=io_interval,
            io_duration=io_duration,
            state=(
                ProcessState.READY
                if arrival_time <= self.simulation_time
                else ProcessState.NEW
            ),
        )

        # 全部字段和 PID 校验完成后才申请资源，保证失败操作不泄漏资源。
        self.resource_manager.allocate(memory_mb, io_devices)

        if automatic_pid:
            self._next_pid += 1
        elif resolved_pid.startswith("P") and resolved_pid[1:].isdigit():
            self._next_pid = max(self._next_pid, int(resolved_pid[1:]) + 1)

        self._processes[resolved_pid] = process

        self._emit_activity(
            "CREATE",
            resolved_pid,
            f"创建进程 {name}",
        )

        self._emit_activity(
            "STATE",
            resolved_pid,
            (
                "NEW → READY"
                if process.state is ProcessState.READY
                else f"保持 NEW，等待 T={arrival_time} 到达"
            ),
        )

        self.changed.emit()

        return process

    # =========================================================
    # 挂起
    # =========================================================

    def suspend_process(
        self,
        pid: str,
    ):
        process = self._require_process(pid)

        if process.state == ProcessState.SUSPENDED:
            raise ValueError(
                "该进程已经处于挂起状态。"
            )

        if process.state == ProcessState.FINISHED:
            raise ValueError(
                "已完成进程不能挂起。"
            )

        if process.state == ProcessState.BLOCKED:
            raise ValueError(
                "阻塞中的进程不能挂起，请等待 I/O 完成。"
            )

        old_state = process.state

        process.state = ProcessState.SUSPENDED

        self._emit_activity(
            "SUSPEND",
            pid,
            f"{old_state.value} → SUSPENDED",
        )

        self.changed.emit()

    # =========================================================
    # 激活
    # =========================================================

    def activate_process(
        self,
        pid: str,
        target_state: ProcessState | None = None,
    ):
        process = self._require_process(pid)

        if process.state != ProcessState.SUSPENDED:
            raise ValueError(
                "只有挂起进程才能执行激活操作。"
            )

        if target_state is None:
            target_state = (
                ProcessState.READY
                if process.arrival_time <= self.simulation_time
                else ProcessState.NEW
            )
        if target_state not in {ProcessState.NEW, ProcessState.READY}:
            raise ValueError("激活后的目标状态只能是 NEW 或 READY。")

        process.state = target_state

        self._emit_activity(
            "ACTIVATE",
            pid,
            f"SUSPENDED → {target_state.value}",
        )

        self.changed.emit()

    # =========================================================
    # 撤销
    # =========================================================

    def revoke_process(
        self,
        pid: str,
    ):
        process = self._require_process(pid)

        # 已完成进程的资源可能已由仿真服务释放，避免重复扣减。
        if process.resources_allocated:
            self.resource_manager.release(
                process.memory_mb,
                process.io_devices,
            )
            process.resources_allocated = False

        del self._processes[pid]

        self._emit_activity(
            "REVOKE",
            pid,
            (
                f"撤销进程 {process.name}，"
                "释放内存与 I/O 资源"
            ),
        )

        self.changed.emit()

    def replace_processes(self, processes: list[Process] | tuple[Process, ...]):
        """先在隔离管理器中完整验证，再原子替换当前进程集。"""

        source = tuple(processes)
        temporary_resources = ResourceManager()
        temporary_resources.resource.total_memory_mb = (
            self.resource_manager.resource.total_memory_mb
        )
        temporary_resources.resource.total_io_devices = (
            self.resource_manager.resource.total_io_devices
        )
        temporary = ProcessManager(temporary_resources)

        for process in source:
            temporary.create_process(
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

        self._processes = {
            process.pid: process for process in temporary.processes
        }
        self._next_pid = temporary._next_pid
        self.resource_manager.resource.used_memory_mb = (
            temporary_resources.resource.used_memory_mb
        )
        self.resource_manager.resource.used_io_devices = (
            temporary_resources.resource.used_io_devices
        )
        self.simulation_time = 0
        self._emit_activity(
            "IMPORT",
            "—",
            f"载入 {len(source)} 个进程的数据集",
        )
        self.resource_manager.changed.emit()
        self.changed.emit()

    def clear_processes(self) -> None:
        """清空全部 PCB，重置 PID 分配器和资源占用。"""

        count = len(self._processes)
        self._processes.clear()
        self._next_pid = 1
        self.simulation_time = 0
        self.resource_manager.reset()
        self._emit_activity("RESET", "—", f"清空 {count} 个进程并重置系统")
        self.changed.emit()

    # =========================================================
    # 工具函数
    # =========================================================

    def _require_process(
        self,
        pid: str,
    ) -> Process:

        process = self.get_process(pid)

        if process is None:
            raise ValueError(
                f"未找到进程 {pid}。"
            )

        return process

    def _emit_activity(
        self,
        event: str,
        pid: str,
        detail: str,
    ):
        self.activity.emit(
            f"T={self.simulation_time}",
            event,
            pid,
            detail,
        )

    def record_activity(
        self,
        event: str,
        pid: str,
        detail: str,
    ):
        """供仿真服务向全局活动流写入结构化事件。"""

        self._emit_activity(event, pid, detail)
