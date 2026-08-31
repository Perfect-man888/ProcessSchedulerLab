from typing import Iterable

from app.models.process import Process
from app.schedulers.base import BaseScheduler, SchedulerCategory


class RMSScheduler(BaseScheduler):
    """单调速率调度（Rate Monotonic Scheduling）：周期越短优先级越高。

    RMS 是静态优先级实时调度策略。进程周期越小，优先级越高；
    新到达的高优先级进程可抢占当前进程。
    """

    name = "RMS"
    category = SchedulerCategory.REAL_TIME
    preemptive = True

    @staticmethod
    def _period(process: Process) -> int:
        if process.period is None:
            raise ValueError(
                f"RMS 要求所有进程提供 Period：{process.pid} 缺少该参数。"
            )
        return process.period

    def _selection_key(self, process: Process) -> tuple[int, int, str]:
        return self._period(process), process.arrival_time, process.pid

    def validate_processes(self, processes: Iterable[Process]) -> None:
        for process in processes:
            self._period(process)

    def choose_next(
        self,
        ready: Iterable[Process],
        current: Process | None,
        now: int,
    ) -> Process | None:
        candidates = self._ready_list(ready)
        if not candidates:
            return None
        return min(candidates, key=self._selection_key)

    def should_preempt(
        self,
        current: Process,
        ready: Iterable[Process],
        now: int,
    ) -> bool:
        current_period = self._period(current)
        candidate = self.choose_next(ready, current, now)
        return (
            candidate is not None
            and self._period(candidate) < current_period
        )
