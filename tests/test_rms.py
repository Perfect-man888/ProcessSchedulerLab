import pytest

from app.models.process import Process
from app.schedulers.rms import RMSScheduler


def test_rms_chooses_shorter_period_first():
    scheduler = RMSScheduler()
    processes = [
        Process(
            pid="P1",
            name="A",
            arrival_time=0,
            burst_time=3,
            priority=1,
            period=20,
        ),
        Process(
            pid="P2",
            name="B",
            arrival_time=0,
            burst_time=2,
            priority=1,
            period=10,
        ),
    ]
    chosen = scheduler.choose_next(processes, None, 0)
    assert chosen.pid == "P2"


def test_rms_preempts_lower_priority_by_period():
    scheduler = RMSScheduler()
    current = Process(
        pid="P1",
        name="A",
        arrival_time=0,
        burst_time=5,
        priority=1,
        period=20,
    )
    ready = [
        Process(
            pid="P2",
            name="B",
            arrival_time=1,
            burst_time=2,
            priority=1,
            period=10,
        )
    ]
    assert scheduler.should_preempt(current, ready, 1)


def test_rms_rejects_missing_period():
    scheduler = RMSScheduler()
    with pytest.raises(ValueError, match="Period"):
        scheduler.validate_processes(
            [
                Process(
                    pid="P1",
                    name="A",
                    arrival_time=0,
                    burst_time=1,
                    priority=1,
                )
            ]
        )
