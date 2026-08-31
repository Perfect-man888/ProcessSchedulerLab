from app.models.process import Process
from app.models.schedule_result import ProcessMetrics, ScheduleResult
from app.models.schedule_segment import ScheduleSegment, append_segment
from app.schedulers.base import BaseScheduler, PreemptionReason


def make_process(
    pid: str,
    arrival: int,
    burst: int,
    priority: int = 1,
) -> Process:
    return Process(
        pid=pid,
        name=pid,
        arrival_time=arrival,
        burst_time=burst,
        priority=priority,
    )


def run_scheduler(
    scheduler: BaseScheduler,
    processes: list[Process],
) -> ScheduleResult:
    """仅供策略单测使用的最小逐 Tick 驱动器。"""

    scheduler.reset()
    clock = 0
    current: Process | None = None
    ready: list[Process] = []
    pending = sorted(processes, key=lambda p: (p.arrival_time, p.pid))
    finished: list[Process] = []
    segments: list[ScheduleSegment] = []
    context_switches = 0
    last_pid: str | None = None
    preserve_boundary = False

    while len(finished) < len(processes):
        arrivals = [p for p in pending if p.arrival_time == clock]
        for process in arrivals:
            pending.remove(process)
            ready.append(process)
            scheduler.on_ready(process, clock)

        reason = None
        if current is not None:
            reason = scheduler.preemption_reason(current, ready, clock)
        if current is not None and reason is not None:
            scheduler.on_preempt(current, clock, reason)
            ready.append(current)
            current = None
            preserve_boundary = reason is PreemptionReason.TIME_SLICE

        if current is None:
            current = scheduler.choose_next(ready, None, clock)
            if current is not None:
                ready.remove(current)
                if last_pid is not None and last_pid != current.pid:
                    context_switches += 1
                last_pid = current.pid
                if current.start_time is None:
                    current.start_time = clock
                scheduler.on_dispatch(current, clock)

        if current is None:
            append_segment(segments, ScheduleSegment(clock, clock + 1))
            clock += 1
            continue

        current.remaining_time -= 1
        scheduler.on_tick(current, clock)
        append_segment(
            segments,
            ScheduleSegment(clock, clock + 1, current.pid),
            preserve_boundary=preserve_boundary,
        )
        preserve_boundary = False
        clock += 1

        if current.remaining_time == 0:
            current.finish_time = clock
            scheduler.on_finish(current, clock)
            finished.append(current)
            current = None

    metrics = tuple(
        ProcessMetrics.from_process(process)
        for process in sorted(finished, key=lambda p: p.pid)
    )
    return ScheduleResult(
        algorithm_name=scheduler.name,
        segments=tuple(segments),
        process_metrics=metrics,
        context_switches=context_switches,
    )
