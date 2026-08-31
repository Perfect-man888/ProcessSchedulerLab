from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ProcessState(str, Enum):
    """进程生命周期状态。"""

    NEW = "NEW"
    READY = "READY"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    SUSPENDED = "SUSPENDED"
    FINISHED = "FINISHED"

    @property
    def display_name(self) -> str:
        names = {
            ProcessState.NEW: "新建",
            ProcessState.READY: "就绪",
            ProcessState.RUNNING: "运行",
            ProcessState.BLOCKED: "阻塞",
            ProcessState.SUSPENDED: "挂起",
            ProcessState.FINISHED: "完成",
        }

        return names[self]


@dataclass
class Process:
    """
    Process Control Block（PCB）
    """

    pid: str
    name: str

    arrival_time: int
    burst_time: int
    priority: int

    deadline: int | None = None
    period: int | None = None

    memory_mb: int = 256
    io_devices: int = 0

    io_interval: int | None = None
    io_duration: int | None = None

    resources_allocated: bool = True

    state: ProcessState = ProcessState.NEW

    remaining_time: int = field(
        init=False
    )
    io_remaining: int = field(
        init=False
    )
    io_ticks_run: int = field(
        init=False
    )
    ready_waiting_ticks: int = field(
        init=False
    )

    start_time: int | None = None
    finish_time: int | None = None

    waiting_time: int | None = None
    turnaround_time: int | None = None
    weighted_turnaround_time: float | None = None
    response_time: int | None = None

    created_at: datetime = field(
        default_factory=datetime.now, compare=False
    )

    def __post_init__(self):
        self.remaining_time = self.burst_time
        self.io_remaining = 0
        self.io_ticks_run = 0
        self.ready_waiting_ticks = 0

    @property
    def is_active(self) -> bool:
        return (
            self.state
            != ProcessState.FINISHED
        )

    @property
    def deadline_text(self) -> str:
        if self.deadline is None:
            return "—"

        return str(self.deadline)

    @property
    def period_text(self) -> str:
        if self.period is None:
            return "—"

        return str(self.period)
