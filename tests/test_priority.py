from app.models.schedule_segment import ScheduleSegment
from app.schedulers.priority import PriorityScheduler
from tests.scheduler_harness import make_process, run_scheduler


def priority_processes():
    return [
        make_process("P001", 0, 4, priority=3),
        make_process("P002", 1, 2, priority=1),
        make_process("P003", 1, 1, priority=1),
    ]


def test_preemptive_priority_interrupts_for_strictly_higher_priority():
    result = run_scheduler(
        PriorityScheduler(preemptive=True),
        priority_processes(),
    )

    assert result.segments == (
        ScheduleSegment(0, 1, "P001"),
        ScheduleSegment(1, 3, "P002"),
        ScheduleSegment(3, 4, "P003"),
        ScheduleSegment(4, 7, "P001"),
    )


def test_non_preemptive_priority_waits_for_current_process():
    result = run_scheduler(
        PriorityScheduler(preemptive=False),
        priority_processes(),
    )

    assert result.segments == (
        ScheduleSegment(0, 4, "P001"),
        ScheduleSegment(4, 6, "P002"),
        ScheduleSegment(6, 7, "P003"),
    )


def test_priority_does_not_preempt_on_equal_priority():
    scheduler = PriorityScheduler(preemptive=True)
    current = make_process("P002", 0, 4, priority=1)
    candidate = make_process("P001", 1, 1, priority=1)

    assert not scheduler.should_preempt(current, [candidate], 1)


def test_priority_aging_improves_waiting_process_effective_priority():
    scheduler = PriorityScheduler(preemptive=True, aging_interval=2)
    waiting = make_process("P001", 0, 1, priority=5)
    newcomer = make_process("P002", 6, 1, priority=3)
    scheduler.on_ready(waiting, 0)
    scheduler.on_ready(newcomer, 6)

    assert scheduler.effective_priority(waiting, 6) == 2
    assert scheduler.effective_priority(newcomer, 6) == 3
    assert scheduler.choose_next([newcomer, waiting], None, 6) is waiting


def test_priority_aging_can_trigger_policy_preemption():
    scheduler = PriorityScheduler(preemptive=True, aging_interval=2)
    current = make_process("P001", 0, 8, priority=3)
    waiting = make_process("P002", 0, 2, priority=5)
    scheduler.on_ready(waiting, 0)

    assert not scheduler.should_preempt(current, [waiting], 2)
    assert scheduler.should_preempt(current, [waiting], 6)


def test_priority_aging_validates_interval():
    import pytest

    with pytest.raises(ValueError, match="Aging"):
        PriorityScheduler(aging_interval=0)
