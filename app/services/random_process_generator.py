import random
from dataclasses import dataclass

from app.models.process import Process


@dataclass(frozen=True, slots=True)
class RandomConfig:
    """随机进程生成参数。

    - 到达时间服从泊松过程（到达间隔为指数分布），arrival_rate 为平均每
      Tick 到达的进程数；
    - 服务时间服从截断指数分布，均值取 burst_min/burst_max 中点；
    - include_realtime 为 True 时按 deadline_factor/period_factor 推导
      绝对 Deadline 与 RMS Period。
    """

    count: int = 8
    seed: int | None = None
    arrival_rate: float = 2.0
    burst_min: int = 1
    burst_max: int = 12
    priority_min: int = 1
    priority_max: int = 8
    include_realtime: bool = False
    include_io: bool = False
    io_interval: int = 2
    io_duration: int = 2
    deadline_factor: float = 3.0
    period_factor: float = 4.0

    def __post_init__(self):
        if self.count < 1:
            raise ValueError("进程数量必须大于 0。")
        if self.arrival_rate <= 0:
            raise ValueError("到达率必须大于 0。")
        if self.burst_min < 1:
            raise ValueError("最小服务时间必须大于 0。")
        if self.burst_max < self.burst_min:
            raise ValueError("最大服务时间不能小于最小服务时间。")
        if self.priority_min < 1:
            raise ValueError("最小优先级必须大于 0。")
        if self.priority_max < self.priority_min:
            raise ValueError("最大优先级不能小于最小优先级。")
        if self.deadline_factor < 1:
            raise ValueError("Deadline 倍率必须不小于 1。")
        if self.period_factor < self.deadline_factor:
            raise ValueError("Period 倍率不能小于 Deadline 倍率。")
        if self.io_interval <= 0:
            raise ValueError("I/O 请求间隔必须大于 0。")
        if self.io_duration <= 0:
            raise ValueError("I/O 持续时间必须大于 0。")


class RandomProcessGenerator:
    """泊松到达 + 截断指数服务时间的随机进程生成器。

    同一 seed 生成完全确定的进程集，便于实验可复现；
    不同 seed（或 seed=None 使用系统随机源）用于蒙特卡洛重复实验。
    """

    def __init__(self, config: RandomConfig):
        self.config = config
        self._rng = random.Random(config.seed)

    def generate(self) -> tuple[Process, ...]:
        config = self.config
        arrivals = self._poisson_arrivals()
        processes = []
        for index, arrival in enumerate(arrivals, start=1):
            burst = self._truncated_exponential_burst()
            priority = self._rng.randint(config.priority_min, config.priority_max)
            deadline = None
            period = None
            if config.include_realtime:
                deadline = arrival + round(burst * config.deadline_factor)
                period = round(burst * config.period_factor)
            processes.append(
                Process(
                    pid=f"R{index:03d}",
                    name=f"Rand-{index:03d}",
                    arrival_time=arrival,
                    burst_time=burst,
                    priority=priority,
                    deadline=deadline,
                    period=period,
                    memory_mb=self._rng.choice((64, 128, 256)),
                    io_devices=0,
                    io_interval=config.io_interval if config.include_io else None,
                    io_duration=config.io_duration if config.include_io else None,
                )
            )
        return tuple(processes)

    def _poisson_arrivals(self) -> tuple[int, ...]:
        """以 T=0 为起点的泊松到达时刻序列（取整到 Tick）。"""
        config = self.config
        arrivals = [0]
        current = 0.0
        for _ in range(config.count - 1):
            # expovariate(lambd) 返回均值为 1/lambd 的指数分布样本
            current += self._rng.expovariate(config.arrival_rate)
            arrivals.append(int(round(current)))
        return tuple(arrivals)

    def _truncated_exponential_burst(self) -> int:
        config = self.config
        mean = (config.burst_min + config.burst_max) / 2.0
        sample = round(self._rng.expovariate(1.0 / mean))
        return min(config.burst_max, max(config.burst_min, sample))
