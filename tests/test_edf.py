import pytest

from app.models.schedule_segment import ScheduleSegment
from app.schedulers.edf import EDFScheduler
from tests.scheduler_harness import make_process, run_scheduler


def realtime_process(pid, arrival, burst, deadline):
    process = make_process(pid, arrival, burst)
    process.deadline = deadline
    return process


def test_edf_preempts_for_earlier_absolute_deadline():
    result = run_scheduler(
        EDFScheduler(),
        [
            realtime_process("P001", 0, 3, 5),
            realtime_process("P002", 1, 2, 4),
            realtime_process("P003", 2, 4, 10),
        ],
    )

    assert result.segments == (
        ScheduleSegment(0, 1, "P001"),
        ScheduleSegment(1, 3, "P002"),
        ScheduleSegment(3, 5, "P001"),
        ScheduleSegment(5, 9, "P003"),
    )
    assert result.deadline_miss_count == 0


def test_edf_records_deadline_miss_from_finish_boundary():
    result = run_scheduler(
        EDFScheduler(),
        [
            realtime_process("P001", 0, 3, 5),
            realtime_process("P002", 1, 2, 4),
            realtime_process("P003", 2, 4, 8),
        ],
    )

    assert result.deadline_missed_processes == ("P003",)
    assert result.deadline_miss_rate == pytest.approx(1 / 3)


def test_edf_does_not_preempt_on_equal_deadline():
    scheduler = EDFScheduler()
    current = realtime_process("P002", 0, 3, 5)
    candidate = realtime_process("P001", 1, 1, 5)

    assert not scheduler.should_preempt(current, [candidate], 1)


def test_edf_rejects_process_without_deadline():
    scheduler = EDFScheduler()

    with pytest.raises(ValueError, match="缺少"):
        scheduler.choose_next([make_process("P001", 0, 1)], None, 0)
