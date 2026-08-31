import pytest

from app.models.schedule_segment import ScheduleSegment
from app.schedulers.round_robin import RoundRobinScheduler
from tests.scheduler_harness import make_process, run_scheduler


def test_round_robin_rotates_fifo_queue_with_quantum_two():
    result = run_scheduler(
        RoundRobinScheduler(quantum=2),
        [
            make_process("P001", 0, 5),
            make_process("P002", 0, 3),
            make_process("P003", 1, 4),
        ],
    )

    assert result.segments == (
        ScheduleSegment(0, 2, "P001"),
        ScheduleSegment(2, 4, "P002"),
        ScheduleSegment(4, 6, "P003"),
        ScheduleSegment(6, 8, "P001"),
        ScheduleSegment(8, 9, "P002"),
        ScheduleSegment(9, 11, "P003"),
        ScheduleSegment(11, 12, "P001"),
    )
    assert result.context_switches == 6
    assert result.average_response_time == pytest.approx(5 / 3)


def test_round_robin_renews_quantum_without_meaningless_switch():
    result = run_scheduler(
        RoundRobinScheduler(quantum=2),
        [
            make_process("P001", 0, 5),
            make_process("P002", 4, 1),
        ],
    )

    assert result.segments == (
        ScheduleSegment(0, 4, "P001"),
        ScheduleSegment(4, 5, "P002"),
        ScheduleSegment(5, 6, "P001"),
    )
    assert result.context_switches == 2


def test_round_robin_rejects_non_positive_quantum():
    with pytest.raises(ValueError, match="时间片"):
        RoundRobinScheduler(0)
