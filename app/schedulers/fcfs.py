from typing import Iterable

from app.models.process import Process
from app.schedulers.base import BaseScheduler, SchedulerCategory


class FCFSScheduler(BaseScheduler):
    """先来先服务：非抢占，按到达时间与 PID 稳定排序。"""

    name = "FCFS"
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
        return min(candidates, key=self._arrival_pid_key)
