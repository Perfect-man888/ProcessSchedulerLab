import pytest

from app.models.process import Process
from app.models.schedule_result import ProcessMetrics, ScheduleResult
from app.models.schedule_segment import ScheduleSegment, append_segment
from app.models.simulation_event import SimulationEvent, SimulationEventType
from app.models.simulation_state import SimulationState, SimulationStatus


def test_schedule_segment_uses_half_open_interval():
    segment = ScheduleSegment(start=2, end=7, pid="P001")

    assert segment.duration == 5
    assert not segment.is_idle
    assert segment.display_name == "P001"

    idle = ScheduleSegment(start=7, end=9)
    assert idle.is_idle
    assert idle.display_name == "IDLE"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"start": -1, "end": 1},
        {"start": 1, "end": 1},
        {"start": 2, "end": 1},
        {"start": 0, "end": 1, "pid": " "},
        {"start": 0, "end": 1, "queue_level": -1},
    ],
)
def test_schedule_segment_rejects_invalid_boundaries(kwargs):
    with pytest.raises(ValueError):
        ScheduleSegment(**kwargs)


def test_append_segment_merges_only_compatible_neighbors():
    segments = [ScheduleSegment(0, 1, "P001")]

    append_segment(segments, ScheduleSegment(1, 2, "P001"))
    append_segment(segments, ScheduleSegment(2, 3, "P002"))
    append_segment(
        segments,
        ScheduleSegment(3, 4, "P002"),
        preserve_boundary=True,
    )

    assert segments == [
        ScheduleSegment(0, 2, "P001"),
        ScheduleSegment(2, 3, "P002"),
        ScheduleSegment(3, 4, "P002"),
    ]


def test_append_segment_rejects_overlap():
    segments = [ScheduleSegment(0, 3, "P001")]

    with pytest.raises(ValueError, match="重叠"):
        append_segment(segments, ScheduleSegment(2, 4, "P002"))


def test_simulation_event_is_structured_and_validated():
    event = SimulationEvent(
        tick=3,
        event_type=SimulationEventType.DISPATCH,
        pid="P002",
        detail="CPU dispatch",
    )

    assert event.time_text == "T=3"
    assert event.event_type.display_name == "CPU 派发"

    with pytest.raises(ValueError):
        SimulationEvent(-1, SimulationEventType.IDLE)


def test_process_metrics_follow_course_formulas():
    metrics = ProcessMetrics(
        pid="P002",
        arrival_time=1,
        burst_time=3,
        start_time=5,
        finish_time=8,
        deadline=7,
    )

    assert metrics.turnaround_time == 7
    assert metrics.weighted_turnaround_time == pytest.approx(7 / 3)
    assert metrics.waiting_time == 4
    assert metrics.response_time == 4
    assert metrics.deadline_missed


def test_process_metrics_can_be_created_from_finished_process():
    process = Process(
        pid="P001",
        name="Compiler",
        arrival_time=0,
        burst_time=5,
        priority=1,
    )
    process.start_time = 1
    process.finish_time = 7

    metrics = ProcessMetrics.from_process(process)

    assert metrics.waiting_time == 2
    assert metrics.response_time == 1


def test_process_metrics_reject_unfinished_or_impossible_process():
    process = Process(
        pid="P001",
        name="Compiler",
        arrival_time=0,
        burst_time=5,
        priority=1,
    )

    with pytest.raises(ValueError, match="尚未完成"):
        ProcessMetrics.from_process(process)

    with pytest.raises(ValueError, match="等待时间不能为负"):
        ProcessMetrics("P001", 0, 5, 0, 4)

    with pytest.raises(ValueError, match="Deadline 必须大于"):
        ProcessMetrics("P001", 2, 1, 2, 3, deadline=2)


def test_schedule_result_aggregates_deterministic_fcfs_metrics():
    result = ScheduleResult(
        algorithm_name="FCFS",
        segments=(
            ScheduleSegment(0, 5, "P001"),
            ScheduleSegment(5, 8, "P002"),
            ScheduleSegment(8, 9, "P003"),
        ),
        process_metrics=(
            ProcessMetrics("P001", 0, 5, 0, 5),
            ProcessMetrics("P002", 1, 3, 5, 8),
            ProcessMetrics("P003", 2, 1, 8, 9),
        ),
        context_switches=2,
    )

    assert result.total_elapsed_ticks == 9
    assert result.busy_ticks == 9
    assert result.cpu_utilization == 1.0
    assert result.throughput == pytest.approx(3 / 9)
    assert result.average_waiting_time == pytest.approx(10 / 3)
    assert result.average_turnaround_time == pytest.approx(19 / 3)
    assert result.average_response_time == pytest.approx(10 / 3)
    assert result.average_weighted_turnaround_time == pytest.approx(31 / 9)
    assert result.context_switches == 2


def test_schedule_result_counts_idle_and_deadline_misses():
    result = ScheduleResult(
        algorithm_name="EDF",
        segments=(
            ScheduleSegment(0, 2),
            ScheduleSegment(2, 5, "P001"),
            ScheduleSegment(5, 7, "P002"),
        ),
        process_metrics=(
            ProcessMetrics("P001", 2, 3, 2, 5, deadline=4),
            ProcessMetrics("P002", 5, 2, 5, 7, deadline=9),
        ),
    )

    assert result.total_elapsed_ticks == 7
    assert result.busy_ticks == 5
    assert result.cpu_utilization == pytest.approx(5 / 7)
    assert result.deadline_missed_processes == ("P001",)
    assert result.deadline_miss_count == 1
    assert result.deadline_miss_rate == 0.5


@pytest.mark.parametrize(
    "segments",
    [
        (ScheduleSegment(1, 2, "P001"),),
        (
            ScheduleSegment(0, 1, "P001"),
            ScheduleSegment(2, 3, "P001"),
        ),
    ],
)
def test_schedule_result_requires_explicit_continuous_timeline(segments):
    metrics = (ProcessMetrics("P001", 0, 1, 0, 1),)

    with pytest.raises(ValueError):
        ScheduleResult("FCFS", segments, metrics)


def test_simulation_state_tracks_runtime_and_resets():
    process = Process(
        pid="P001",
        name="Compiler",
        arrival_time=0,
        burst_time=2,
        priority=1,
    )
    state = SimulationState(
        clock=2,
        status=SimulationStatus.PAUSED,
        current_process=process,
        busy_ticks=2,
        total_ticks=3,
        context_switches=1,
    )
    state.segments.append(ScheduleSegment(0, 2, "P001"))

    assert state.cpu_utilization == pytest.approx(2 / 3)
    assert not state.is_complete

    state.reset_runtime()

    assert state.clock == 0
    assert state.status is SimulationStatus.IDLE
    assert state.cpu_utilization == 0.0
    assert state.is_complete
