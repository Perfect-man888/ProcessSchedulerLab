import pytest

from app.models.process import Process, ProcessState
from app.services.experiment_service import EXPERIMENT_PRESETS, ExperimentService
from app.services.process_manager import ProcessManager
from app.services.resource_manager import ResourceManager


def make_process(pid, arrival, burst, priority=1, deadline=None):
    return Process(
        pid=pid,
        name=pid,
        arrival_time=arrival,
        burst_time=burst,
        priority=priority,
        deadline=deadline,
        memory_mb=64,
        io_devices=0,
        state=ProcessState.READY,
    )


def test_run_all_isolated_algorithms_with_realtime_dataset(qapp):
    source = [
        make_process("P010", 0, 5, 3, 12),
        make_process("P020", 1, 2, 1, 7),
        make_process("P030", 3, 1, 2, 9),
    ]
    snapshots = [
        (process.pid, process.state, process.remaining_time, process.start_time)
        for process in source
    ]
    service = ExperimentService()
    progress = []
    service.progress.connect(lambda percent, name: progress.append((percent, name)))

    report = service.run_all(source, dataset_name="确定性用例")

    assert report.dataset_name == "确定性用例"
    assert len(report.results) == 7
    assert not report.skipped
    assert {result.algorithm_name for result in report.results} == {
        "FCFS",
        "SJF",
        "SRTF",
        "Priority (Preemptive)",
        "Round Robin",
        "EDF",
        "MLFQ",
    }
    assert all(
        {metric.pid for metric in result.process_metrics}
        == {"P010", "P020", "P030"}
        for result in report.results
    )
    assert snapshots == [
        (process.pid, process.state, process.remaining_time, process.start_time)
        for process in source
    ]
    assert progress[-1] == (100, "完成")


def test_edf_is_explicitly_skipped_when_deadlines_are_missing(qapp):
    source = [make_process("P001", 0, 2), make_process("P002", 1, 1)]

    report = ExperimentService().run_all(source)

    assert len(report.results) == 6
    assert [item.algorithm_key for item in report.skipped] == ["edf"]
    assert "Deadline" in report.skipped[0].reason
    assert any("未纳入比较" in note for note in report.observations)


def test_presets_are_deterministic_and_all_support_edf(qapp):
    assert len(EXPERIMENT_PRESETS) == 6
    for preset in EXPERIMENT_PRESETS:
        first = preset.instantiate()
        second = preset.instantiate()
        assert first == second
        assert all(process.deadline is not None for process in first)
        report = ExperimentService().run_all(first, dataset_name=preset.name)
        assert len(report.results) == 7


def test_experiment_report_best_supports_ties(qapp):
    processes = [make_process("P001", 0, 1, deadline=5)]
    report = ExperimentService().run_all(processes)

    assert len(report.best("average_waiting_time")) == 7
    assert "全部 7 种算法" in report.observations[0]


def test_explicit_pid_creation_advances_auto_allocator(qapp):
    manager = ProcessManager(ResourceManager())
    explicit = manager.create_process(
        pid="P010",
        name="Imported",
        arrival_time=0,
        burst_time=1,
        priority=1,
        memory_mb=64,
        io_devices=0,
    )
    automatic = manager.create_process(
        name="Next",
        arrival_time=0,
        burst_time=1,
        priority=1,
        memory_mb=64,
        io_devices=0,
    )

    assert explicit.pid == "P010"
    assert automatic.pid == "P011"


def test_experiment_rejects_empty_dataset(qapp):
    with pytest.raises(ValueError, match="不能为空"):
        ExperimentService().run_all([])
