from typing import Iterable

from app.models.process import Process
from app.schedulers.base import (
    BaseScheduler,
    SchedulerCategory,
    SchedulerNotice,
    SchedulerNoticeType,
)


class PriorityScheduler(BaseScheduler):
    """数字越小优先级越高，可配置为抢占式或非抢占式。"""

    category = SchedulerCategory.GENERAL

    def __init__(
        self,
        *,
        preemptive: bool = True,
        aging_interval: int | None = None,
    ):
        if aging_interval is not None and aging_interval <= 0:
            raise ValueError("Aging 周期必须大于 0 Tick。")
        self.preemptive = preemptive
        self.aging_interval = aging_interval
        self._ready_since: dict[str, int] = {}
        self._last_effective: dict[str, int] = {}
        mode = "Priority (Preemptive)" if preemptive else "Priority"
        self.name = f"{mode} + Aging" if aging_interval else mode

    def reset(self) -> None:
        self._ready_since.clear()
        self._last_effective.clear()

    def on_clock(self, ready, current, now: int) -> tuple[SchedulerNotice, ...]:
        if self.aging_interval is None:
            return ()
        notices = []
        for process in ready:
            effective = self.effective_priority(process, now)
            previous = self._last_effective.get(process.pid, process.priority)
            if effective < previous:
                notices.append(
                    SchedulerNotice(
                        SchedulerNoticeType.AGING,
                        f"有效优先级 {previous} → {effective}",
                        process.pid,
                    )
                )
            self._last_effective[process.pid] = effective
        return tuple(notices)

    def effective_priority(self, process: Process, now: int) -> int:
        """返回等待 Aging 后的有效优先级，数字仍是越小越高。"""

        if self.aging_interval is None:
            return process.priority
        ready_since = self._ready_since.get(process.pid, now)
        improvement = max(0, now - ready_since) // self.aging_interval
        return max(1, process.priority - improvement)

    def _selection_key(self, process: Process, now: int) -> tuple[int, int, str]:
        return self.effective_priority(process, now), process.arrival_time, process.pid

    def choose_next(
        self,
        ready: Iterable[Process],
        current: Process | None,
        now: int,
    ) -> Process | None:
        candidates = self._ready_list(ready)
        if not candidates:
            return None
        return min(candidates, key=lambda process: self._selection_key(process, now))

    def should_preempt(
        self,
        current: Process,
        ready: Iterable[Process],
        now: int,
    ) -> bool:
        if not self.preemptive:
            return False
        candidate = self.choose_next(ready, current, now)
        return (
            candidate is not None
            and self.effective_priority(candidate, now) < current.priority
        )

    def on_ready(self, process: Process, now: int) -> None:
        self._ready_since.setdefault(process.pid, now)
        self._last_effective.setdefault(process.pid, process.priority)

    def on_preempt(self, process: Process, now: int, reason) -> None:
        self._ready_since[process.pid] = now

    def on_dispatch(self, process: Process, now: int) -> None:
        self._ready_since.pop(process.pid, None)
        self._last_effective.pop(process.pid, None)

    def on_finish(self, process: Process, now: int) -> None:
        self._ready_since.pop(process.pid, None)
        self._last_effective.pop(process.pid, None)
