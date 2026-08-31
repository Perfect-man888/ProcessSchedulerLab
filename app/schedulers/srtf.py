from typing import Iterable

from app.models.process import Process
from app.schedulers.base import BaseScheduler, SchedulerCategory


class SRTFScheduler(BaseScheduler):
    """最短剩余时间优先：仅当候选剩余时间严格更短时抢占。"""

    name = "SRTF"
    category = SchedulerCategory.BATCH
    preemptive = True

    @staticmethod
    def _selection_key(process: Process) -> tuple[int, int, str]:
        return process.remaining_time, process.arrival_time, process.pid

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
        candidate = self.choose_next(ready, current, now)
        return (
            candidate is not None
            and candidate.remaining_time < current.remaining_time
        )
