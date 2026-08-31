from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from app.models.process import Process


class SchedulerCategory(str, Enum):
    BATCH = "BATCH"
    GENERAL = "GENERAL"
    TIME_SHARING = "TIME_SHARING"
    REAL_TIME = "REAL_TIME"


class PreemptionReason(str, Enum):
    POLICY = "POLICY"
    TIME_SLICE = "TIME_SLICE"
    HIGHER_QUEUE = "HIGHER_QUEUE"


class SchedulerNoticeType(str, Enum):
    AGING = "AGING"
    BOOST = "BOOST"


@dataclass(frozen=True, slots=True)
class SchedulerNotice:
    notice_type: SchedulerNoticeType
    detail: str
    pid: str | None = None


class BaseScheduler(ABC):
    """调度策略接口；生命周期与时钟推进由仿真引擎负责。"""

    name: str
    category: SchedulerCategory
    preemptive: bool = False

    def reset(self) -> None:
        """清空算法内部状态；无状态算法无需覆盖。"""

    def validate_processes(self, processes: Iterable[Process]) -> None:
        """加载实验前验证算法特有输入约束。"""

    @abstractmethod
    def choose_next(
        self,
        ready: Iterable[Process],
        current: Process | None,
        now: int,
    ) -> Process | None:
        """CPU 空闲时，从已到达的就绪进程中选择下一个进程。"""

    def should_preempt(
        self,
        current: Process,
        ready: Iterable[Process],
        now: int,
    ) -> bool:
        """判断当前进程是否应被就绪集合中的进程抢占。"""

        return False

    def preemption_reason(
        self,
        current: Process,
        ready: Iterable[Process],
        now: int,
    ) -> PreemptionReason | None:
        if self.should_preempt(current, ready, now):
            return PreemptionReason.POLICY
        return None

    def on_ready(self, process: Process, now: int) -> None:
        """进程进入就绪集合时的策略回调。"""

    def on_preempt(
        self,
        process: Process,
        now: int,
        reason: PreemptionReason,
    ) -> None:
        """进程被抢占或时间片结束时的策略回调。"""

    def queue_level(self, process: Process) -> int | None:
        """返回算法内部队列层级，非多级队列算法返回 None。"""

        return None

    def on_tick(self, process: Process, now: int) -> None:
        """进程完成一个 Tick 后的策略回调。"""

    def on_clock(
        self,
        ready: Iterable[Process],
        current: Process | None,
        now: int,
    ) -> tuple[SchedulerNotice, ...]:
        """时钟边界策略通知；用于记录 Aging、Boost 等可解释事件。"""

        return ()

    def on_dispatch(self, process: Process, now: int) -> None:
        """进程获得 CPU 时的策略回调。"""

    def on_finish(self, process: Process, now: int) -> None:
        """进程完成时的策略回调。"""

    @staticmethod
    def _ready_list(ready: Iterable[Process]) -> list[Process]:
        return list(ready)

    @staticmethod
    def _arrival_pid_key(process: Process) -> tuple[int, str]:
        return process.arrival_time, process.pid
