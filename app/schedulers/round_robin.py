from typing import Iterable

from app.models.process import Process
from app.schedulers.base import (
    BaseScheduler,
    PreemptionReason,
    SchedulerCategory,
)


class RoundRobinScheduler(BaseScheduler):
    """先进先出就绪队列上的可配置时间片轮转调度。"""

    name = "Round Robin"
    category = SchedulerCategory.TIME_SHARING
    preemptive = True

    def __init__(self, quantum: int = 2):
        if quantum <= 0:
            raise ValueError("Round Robin 时间片必须大于 0。")
        self.quantum = quantum
        self._slice_used = 0

    def reset(self) -> None:
        self._slice_used = 0

    def choose_next(
        self,
        ready: Iterable[Process],
        current: Process | None,
        now: int,
    ) -> Process | None:
        candidates = self._ready_list(ready)
        return candidates[0] if candidates else None

    def on_dispatch(self, process: Process, now: int) -> None:
        self._slice_used = 0

    def on_tick(self, process: Process, now: int) -> None:
        self._slice_used += 1

    def on_finish(self, process: Process, now: int) -> None:
        self._slice_used = 0

    def preemption_reason(
        self,
        current: Process,
        ready: Iterable[Process],
        now: int,
    ) -> PreemptionReason | None:
        candidates = self._ready_list(ready)
        if self._slice_used < self.quantum:
            return None
        if candidates:
            return PreemptionReason.TIME_SLICE

        # 没有竞争者时直接续发一个新时间片，不制造无意义切换。
        self._slice_used = 0
        return None

    def on_preempt(
        self,
        process: Process,
        now: int,
        reason: PreemptionReason,
    ) -> None:
        self._slice_used = 0
