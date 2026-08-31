from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScheduleSegment:
    """CPU 时间线中的半开区间 ``[start, end)``。"""

    start: int
    end: int
    pid: str | None = None
    queue_level: int | None = None
    reason: str | None = None

    def __post_init__(self):
        if self.start < 0:
            raise ValueError("调度片段开始时间不能小于 0。")
        if self.end <= self.start:
            raise ValueError("调度片段结束时间必须大于开始时间。")
        if self.pid is not None and not self.pid.strip():
            raise ValueError("调度片段 PID 不能为空字符串。")
        if self.queue_level is not None and self.queue_level < 0:
            raise ValueError("队列层级不能小于 0。")

    @property
    def duration(self) -> int:
        return self.end - self.start

    @property
    def is_idle(self) -> bool:
        return self.pid is None

    @property
    def display_name(self) -> str:
        return self.pid or "IDLE"

    def can_merge(self, other: "ScheduleSegment") -> bool:
        return (
            self.end == other.start
            and self.pid == other.pid
            and self.queue_level == other.queue_level
            and self.reason == other.reason
        )

    def merged_with(self, other: "ScheduleSegment") -> "ScheduleSegment":
        if not self.can_merge(other):
            raise ValueError("两个调度片段不连续或运行语义不同，不能合并。")
        return ScheduleSegment(
            start=self.start,
            end=other.end,
            pid=self.pid,
            queue_level=self.queue_level,
            reason=self.reason,
        )


def append_segment(
    segments: list[ScheduleSegment],
    segment: ScheduleSegment,
    *,
    preserve_boundary: bool = False,
) -> None:
    """按时间顺序追加片段，并按需合并相邻的同语义区间。"""

    if segments and segment.start < segments[-1].end:
        raise ValueError("调度片段不能与已有时间线重叠。")

    if (
        segments
        and not preserve_boundary
        and segments[-1].can_merge(segment)
    ):
        segments[-1] = segments[-1].merged_with(segment)
        return

    segments.append(segment)
