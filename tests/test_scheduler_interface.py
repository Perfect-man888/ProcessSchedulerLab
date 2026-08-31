import pytest

from app.schedulers import (
    BaseScheduler,
    EDFScheduler,
    FCFSScheduler,
    MLFQScheduler,
    PriorityScheduler,
    RoundRobinScheduler,
    SJFScheduler,
    SRTFScheduler,
    SchedulerCategory,
    create_scheduler,
)


@pytest.mark.parametrize(
    ("scheduler", "category", "preemptive"),
    [
        (FCFSScheduler(), SchedulerCategory.BATCH, False),
        (SJFScheduler(), SchedulerCategory.BATCH, False),
        (SRTFScheduler(), SchedulerCategory.BATCH, True),
        (RoundRobinScheduler(), SchedulerCategory.TIME_SHARING, True),
        (EDFScheduler(), SchedulerCategory.REAL_TIME, True),
        (MLFQScheduler(), SchedulerCategory.TIME_SHARING, True),
        (PriorityScheduler(), SchedulerCategory.GENERAL, True),
        (
            PriorityScheduler(preemptive=False),
            SchedulerCategory.GENERAL,
            False,
        ),
    ],
)
def test_scheduler_metadata_and_empty_ready_behavior(
    scheduler,
    category,
    preemptive,
):
    assert isinstance(scheduler, BaseScheduler)
    assert scheduler.category is category
    assert scheduler.preemptive is preemptive
    assert scheduler.choose_next([], None, 0) is None


@pytest.mark.parametrize(
    ("key", "expected_type"),
    [
        ("fcfs", FCFSScheduler),
        ("SJF", SJFScheduler),
        ("srtf", SRTFScheduler),
        ("priority", PriorityScheduler),
        ("rr", RoundRobinScheduler),
        ("round robin", RoundRobinScheduler),
        ("edf", EDFScheduler),
        ("mlfq", MLFQScheduler),
    ],
)
def test_scheduler_registry_creates_all_supported_algorithms(
    key,
    expected_type,
):
    assert isinstance(create_scheduler(key), expected_type)


def test_scheduler_registry_passes_configuration_and_rejects_unknown_key():
    scheduler = create_scheduler("rr", quantum=4)
    assert scheduler.quantum == 4

    with pytest.raises(ValueError, match="未知调度算法"):
        create_scheduler("lottery")
