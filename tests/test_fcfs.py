from app.models.schedule_segment import ScheduleSegment
from app.schedulers.fcfs import FCFSScheduler
from tests.scheduler_harness import make_process, run_scheduler


def test_fcfs_runs_in_arrival_order():
    result = run_scheduler(
        FCFSScheduler(),
        [
            make_process("P001", 0, 5),
            make_process("P002", 1, 3),
            make_process("P003", 2, 1),
        ],
    )

    assert result.segments == (
        ScheduleSegment(0, 5, "P001"),
        ScheduleSegment(5, 8, "P002"),
        ScheduleSegment(8, 9, "P003"),
    )
    assert result.average_waiting_time == 10 / 3


def test_fcfs_records_idle_and_uses_pid_as_stable_tie_breaker():
    result = run_scheduler(
        FCFSScheduler(),
        [
            make_process("P002", 2, 1),
            make_process("P001", 2, 1),
        ],
    )

    assert result.segments == (
        ScheduleSegment(0, 2),
        ScheduleSegment(2, 3, "P001"),
        ScheduleSegment(3, 4, "P002"),
    )
    assert result.cpu_utilization == 0.5
