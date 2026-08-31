from app.models.schedule_segment import ScheduleSegment
from app.schedulers.sjf import SJFScheduler
from tests.scheduler_harness import make_process, run_scheduler


def test_sjf_selects_shortest_arrived_job_without_preemption():
    result = run_scheduler(
        SJFScheduler(),
        [
            make_process("P001", 0, 5),
            make_process("P002", 1, 3),
            make_process("P003", 2, 1),
        ],
    )

    assert result.segments == (
        ScheduleSegment(0, 5, "P001"),
        ScheduleSegment(5, 6, "P003"),
        ScheduleSegment(6, 9, "P002"),
    )


def test_sjf_ties_by_arrival_then_pid():
    scheduler = SJFScheduler()
    candidates = [
        make_process("P003", 1, 2),
        make_process("P002", 0, 2),
        make_process("P001", 0, 2),
    ]

    assert scheduler.choose_next(candidates, None, 3).pid == "P001"
