from collections.abc import Callable

from app.schedulers.base import BaseScheduler
from app.schedulers.edf import EDFScheduler
from app.schedulers.fcfs import FCFSScheduler
from app.schedulers.mlfq import MLFQScheduler
from app.schedulers.priority import PriorityScheduler
from app.schedulers.round_robin import RoundRobinScheduler
from app.schedulers.sjf import SJFScheduler
from app.schedulers.srtf import SRTFScheduler


SchedulerFactory = Callable[..., BaseScheduler]

SCHEDULER_FACTORIES: dict[str, SchedulerFactory] = {
    "fcfs": FCFSScheduler,
    "sjf": SJFScheduler,
    "srtf": SRTFScheduler,
    "priority": PriorityScheduler,
    "round_robin": RoundRobinScheduler,
    "edf": EDFScheduler,
    "mlfq": MLFQScheduler,
}

SCHEDULER_ALIASES = {
    "rr": "round_robin",
    "roundrobin": "round_robin",
    "round-robin": "round_robin",
}


def create_scheduler(key: str, **options) -> BaseScheduler:
    """通过稳定键创建调度器，供 UI、实验服务和持久化共同使用。"""

    normalized = key.strip().lower().replace(" ", "_")
    normalized = SCHEDULER_ALIASES.get(normalized, normalized)

    factory = SCHEDULER_FACTORIES.get(normalized)
    if factory is None:
        supported = ", ".join(SCHEDULER_FACTORIES)
        raise ValueError(f"未知调度算法 {key!r}，支持：{supported}。")
    return factory(**options)
