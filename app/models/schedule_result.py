from dataclasses import dataclass, field
from statistics import fmean

from app.models.process import Process
from app.models.schedule_segment import ScheduleSegment
from app.models.simulation_event import SimulationEvent


@dataclass(frozen=True, slots=True)
class ProcessMetrics:
    """由原始时刻推导出的单进程调度指标。"""

    pid: str
    arrival_time: int
    burst_time: int
    start_time: int
    finish_time: int
    deadline: int | None = None

    def __post_init__(self):
        if not self.pid.strip():
            raise ValueError("指标 PID 不能为空。")
        if self.arrival_time < 0:
            raise ValueError("到达时间不能小于 0。")
        if self.burst_time <= 0:
            raise ValueError("服务时间必须大于 0。")
        if self.start_time < self.arrival_time:
            raise ValueError("开始时间不能早于到达时间。")
        if self.finish_time < self.start_time:
            raise ValueError("完成时间不能早于开始时间。")
        if self.deadline is not None and self.deadline <= self.arrival_time:
            raise ValueError("Deadline 必须大于到达时间。")
        if self.turnaround_time < self.burst_time:
            raise ValueError("完成时刻与服务时间不一致，等待时间不能为负。")

    @classmethod
    def from_process(cls, process: Process) -> "ProcessMetrics":
        if process.start_time is None or process.finish_time is None:
            raise ValueError(f"进程 {process.pid} 尚未完成，无法生成指标。")
        return cls(
            pid=process.pid,
            arrival_time=process.arrival_time,
            burst_time=process.burst_time,
            start_time=process.start_time,
            finish_time=process.finish_time,
            deadline=process.deadline,
        )

    @property
    def turnaround_time(self) -> int:
        return self.finish_time - self.arrival_time

    @property
    def weighted_turnaround_time(self) -> float:
        return self.turnaround_time / self.burst_time

    @property
    def waiting_time(self) -> int:
        return self.turnaround_time - self.burst_time

    @property
    def response_time(self) -> int:
        return self.start_time - self.arrival_time

    @property
    def deadline_missed(self) -> bool:
        return self.deadline is not None and self.finish_time > self.deadline


@dataclass(frozen=True, slots=True)
class ScheduleResult:
    """一次完整调度实验的算法无关结果。"""

    algorithm_name: str
    segments: tuple[ScheduleSegment, ...]
    process_metrics: tuple[ProcessMetrics, ...]
    events: tuple[SimulationEvent, ...] = field(default_factory=tuple)
    context_switches: int = 0

    def __post_init__(self):
        if not self.algorithm_name.strip():
            raise ValueError("调度算法名称不能为空。")
        if self.context_switches < 0:
            raise ValueError("上下文切换次数不能小于 0。")

        pids = [metrics.pid for metrics in self.process_metrics]
        if len(pids) != len(set(pids)):
            raise ValueError("同一结果中不能出现重复的进程指标。")

        if self.segments:
            if self.segments[0].start != 0:
                raise ValueError("完整调度时间线必须从 T=0 开始。")
            for previous, current in zip(self.segments, self.segments[1:]):
                if previous.end != current.start:
                    raise ValueError("完整调度时间线必须连续，空闲时间应记录为 IDLE。")

        timeline_pids = {
            segment.pid for segment in self.segments if segment.pid is not None
        }
        if timeline_pids != set(pids):
            raise ValueError("时间线中的进程与每进程指标必须完全一致。")

    @property
    def total_elapsed_ticks(self) -> int:
        return self.segments[-1].end if self.segments else 0

    @property
    def busy_ticks(self) -> int:
        return sum(segment.duration for segment in self.segments if not segment.is_idle)

    @property
    def cpu_utilization(self) -> float:
        if self.total_elapsed_ticks == 0:
            return 0.0
        return self.busy_ticks / self.total_elapsed_ticks

    @property
    def throughput(self) -> float:
        if self.total_elapsed_ticks == 0:
            return 0.0
        return len(self.process_metrics) / self.total_elapsed_ticks

    @property
    def deadline_missed_processes(self) -> tuple[str, ...]:
        return tuple(
            metrics.pid
            for metrics in self.process_metrics
            if metrics.deadline_missed
        )

    @property
    def deadline_miss_count(self) -> int:
        return len(self.deadline_missed_processes)

    @property
    def deadline_miss_rate(self) -> float:
        realtime = [m for m in self.process_metrics if m.deadline is not None]
        if not realtime:
            return 0.0
        return sum(m.deadline_missed for m in realtime) / len(realtime)

    @property
    def average_waiting_time(self) -> float:
        return self._average("waiting_time")

    @property
    def average_turnaround_time(self) -> float:
        return self._average("turnaround_time")

    @property
    def average_weighted_turnaround_time(self) -> float:
        return self._average("weighted_turnaround_time")

    @property
    def average_response_time(self) -> float:
        return self._average("response_time")

    def _average(self, attribute: str) -> float:
        if not self.process_metrics:
            return 0.0
        return fmean(getattr(metrics, attribute) for metrics in self.process_metrics)
