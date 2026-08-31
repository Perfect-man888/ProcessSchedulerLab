import pytest

from app.models.schedule_segment import ScheduleSegment
from app.schedulers.base import PreemptionReason
from app.schedulers.mlfq import MLFQScheduler
from tests.scheduler_harness import make_process, run_scheduler


def test_mlfq_demotes_cpu_bound_processes_across_three_queues():
    result = run_scheduler(
        MLFQScheduler(quanta=(1, 2, 4), boost_interval=100),
        [
            make_process("P001", 0, 6),
            make_process("P002", 0, 2),
        ],
    )

    assert result.segments == (
        ScheduleSegment(0, 1, "P001"),
        ScheduleSegment(1, 2, "P002"),
        ScheduleSegment(2, 4, "P001"),
        ScheduleSegment(4, 5, "P002"),
        ScheduleSegment(5, 8, "P001"),
    )


def test_mlfq_new_top_queue_process_preempts_lower_queue():
    result = run_scheduler(
        MLFQScheduler(quanta=(1, 2, 4), boost_interval=100),
        [
            make_process("P001", 0, 6),
            make_process("P002", 2, 1),
        ],
    )

    assert result.segments == (
        ScheduleSegment(0, 1, "P001"),
        ScheduleSegment(1, 2, "P001"),
        ScheduleSegment(2, 3, "P002"),
        ScheduleSegment(3, 4, "P001"),
        ScheduleSegment(4, 7, "P001"),
    )


def test_mlfq_priority_boost_restores_all_known_processes():
    scheduler = MLFQScheduler(quanta=(1, 2, 4), boost_interval=10)
    first = make_process("P001", 0, 5)
    second = make_process("P002", 0, 5)
    scheduler.on_ready(first, 0)
    scheduler.on_ready(second, 0)

    scheduler.on_tick(first, 0)
    reason = scheduler.preemption_reason(first, [second], 1)
    assert reason is PreemptionReason.TIME_SLICE
    scheduler.on_preempt(first, 1, reason)
    assert scheduler.queue_level(first) == 1

    scheduler.choose_next([first, second], None, 10)

    assert scheduler.queue_level(first) == 0
    assert scheduler.queue_level(second) == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"quanta": ()},
        {"quanta": (1, 0, 4)},
        {"boost_interval": 0},
    ],
)
def test_mlfq_rejects_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        MLFQScheduler(**kwargs)
