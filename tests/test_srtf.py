from app.models.schedule_segment import ScheduleSegment
from app.schedulers.srtf import SRTFScheduler
from tests.scheduler_harness import make_process, run_scheduler


def test_srtf_preempts_for_strictly_shorter_remaining_time():
    result = run_scheduler(
        SRTFScheduler(),
        [
            make_process("P001", 0, 5),
            make_process("P002", 1, 3),
            make_process("P003", 2, 1),
        ],
    )

    assert result.segments == (
        ScheduleSegment(0, 1, "P001"),
        ScheduleSegment(1, 2, "P002"),
        ScheduleSegment(2, 3, "P003"),
        ScheduleSegment(3, 5, "P002"),
        ScheduleSegment(5, 9, "P001"),
    )
    assert result.context_switches == 4


def test_srtf_does_not_preempt_on_equal_remaining_time():
    scheduler = SRTFScheduler()
    current = make_process("P002", 0, 4)
    current.remaining_time = 2
    candidate = make_process("P001", 1, 2)

    assert not scheduler.should_preempt(current, [candidate], 1)


def test_srtf_selection_ties_by_arrival_then_pid():
    scheduler = SRTFScheduler()
    candidates = [
        make_process("P002", 0, 2),
        make_process("P001", 0, 2),
    ]

    assert scheduler.choose_next(candidates, None, 0).pid == "P001"
