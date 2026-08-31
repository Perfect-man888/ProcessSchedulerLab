from typing import Iterable

from app.models.process import Process
from app.schedulers.base import BaseScheduler, SchedulerCategory


class SJFScheduler(BaseScheduler):
    """短作业优先：CPU 空闲时选择服务时间最短的进程。"""

    name = "SJF"
    category = SchedulerCategory.BATCH
    preemptive = False

    def choose_next(
        self,
        ready: Iterable[Process],
        current: Process | None,
        now: int,
    ) -> Process | None:
        candidates = self._ready_list(ready)
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda process: (
                process.burst_time,
                process.arrival_time,
                process.pid,
            ),
        )
