from typing import Iterable

from app.models.process import Process
from app.schedulers.base import BaseScheduler, SchedulerCategory


class EDFScheduler(BaseScheduler):
    """最早绝对截止时间优先的抢占式实时调度。"""

    name = "EDF"
    category = SchedulerCategory.REAL_TIME
    preemptive = True

    @staticmethod
    def _deadline(process: Process) -> int:
        if process.deadline is None:
            raise ValueError(
                f"EDF 要求所有进程提供 Deadline：{process.pid} 缺少该参数。"
            )
        return process.deadline

    def _selection_key(self, process: Process) -> tuple[int, int, str]:
        return self._deadline(process), process.arrival_time, process.pid

    def validate_processes(self, processes: Iterable[Process]) -> None:
        for process in processes:
            self._deadline(process)

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
        current_deadline = self._deadline(current)
        candidate = self.choose_next(ready, current, now)
        return (
            candidate is not None
            and self._deadline(candidate) < current_deadline
        )
