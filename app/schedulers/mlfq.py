from typing import Iterable

from app.models.process import Process
from app.schedulers.base import (
    BaseScheduler,
    PreemptionReason,
    SchedulerCategory,
    SchedulerNotice,
    SchedulerNoticeType,
)


class MLFQScheduler(BaseScheduler):
    """三级反馈队列：时间片耗尽降级，周期性提升避免饥饿。"""

    name = "MLFQ"
    category = SchedulerCategory.TIME_SHARING
    preemptive = True

    def __init__(
        self,
        quanta: tuple[int, ...] = (1, 2, 4),
        boost_interval: int = 10,
    ):
        if not quanta or any(quantum <= 0 for quantum in quanta):
            raise ValueError("MLFQ 每级时间片都必须大于 0。")
        if boost_interval <= 0:
            raise ValueError("MLFQ Priority Boost 周期必须大于 0。")

        self.quanta = quanta
        self.boost_interval = boost_interval
        self._levels: dict[str, int] = {}
        self._slice_used: dict[str, int] = {}
        self._last_boost_at = 0

    def reset(self) -> None:
        self._levels.clear()
        self._slice_used.clear()
        self._last_boost_at = 0

    def on_ready(self, process: Process, now: int) -> None:
        self._levels.setdefault(process.pid, 0)
        self._slice_used.setdefault(process.pid, 0)

    def queue_level(self, process: Process) -> int:
        return self._levels.get(process.pid, 0)

    def _apply_priority_boost(self, now: int) -> bool:
        if (
            now > 0
            and now % self.boost_interval == 0
            and now != self._last_boost_at
        ):
            for pid in self._levels:
                self._levels[pid] = 0
                self._slice_used[pid] = 0
            self._last_boost_at = now
            return True
        return False

    def on_clock(self, ready, current, now: int) -> tuple[SchedulerNotice, ...]:
        if self._apply_priority_boost(now):
            return (
                SchedulerNotice(
                    SchedulerNoticeType.BOOST,
                    f"Priority Boost：全部活动任务提升至 Q0（周期 {self.boost_interval} Tick）",
                ),
            )
        return ()

    def choose_next(
        self,
        ready: Iterable[Process],
        current: Process | None,
        now: int,
    ) -> Process | None:
        self._apply_priority_boost(now)
        candidates = self._ready_list(ready)
        if not candidates:
            return None

        # min 保留 iterable 中的原始次序，形成每层 FIFO。
        return min(candidates, key=self.queue_level)

    def on_tick(self, process: Process, now: int) -> None:
        self._slice_used[process.pid] = self._slice_used.get(process.pid, 0) + 1

    def preemption_reason(
        self,
        current: Process,
        ready: Iterable[Process],
        now: int,
    ) -> PreemptionReason | None:
        self._apply_priority_boost(now)
        candidates = self._ready_list(ready)
        current_level = self.queue_level(current)

        if candidates:
            best_level = min(self.queue_level(process) for process in candidates)
            if best_level < current_level:
                return PreemptionReason.HIGHER_QUEUE

        quantum = self.quanta[current_level]
        if self._slice_used.get(current.pid, 0) >= quantum:
            return PreemptionReason.TIME_SLICE
        return None

    def on_preempt(
        self,
        process: Process,
        now: int,
        reason: PreemptionReason,
    ) -> None:
        if reason is PreemptionReason.TIME_SLICE:
            current_level = self.queue_level(process)
            self._levels[process.pid] = min(
                current_level + 1,
                len(self.quanta) - 1,
            )
            self._slice_used[process.pid] = 0

    def on_finish(self, process: Process, now: int) -> None:
        self._levels.pop(process.pid, None)
        self._slice_used.pop(process.pid, None)
