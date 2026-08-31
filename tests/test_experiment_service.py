import pytest

from app.models.process import Process, ProcessState
from app.services.experiment_service import (
    EXPERIMENT_PRESETS,
    ExperimentCancelled,
    ExperimentService,
)
from app.services.process_manager import ProcessManager
from app.services.resource_manager import ResourceManager


def make_process(pid, arrival, burst, priority=1, deadline=None, period=None):
    return Process(
        pid=pid,
        name=pid,
        arrival_time=arrival,
        burst_time=burst,
        priority=priority,
        deadline=deadline,
        period=period,
        memory_mb=64,
        io_devices=0,
        state=ProcessState.READY,
    )


def test_run_all_isolated_algorithms_with_realtime_dataset(qapp):
    source = [
        make_process("P010", 0, 5, 3, 12, 14),
        make_process("P020", 1, 2, 1, 7, 9),
        make_process("P030", 3, 1, 2, 9, 11),
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
    assert len(report.results) == 8
    assert not report.skipped
    assert {result.algorithm_name for result in report.results} == {
        "FCFS",
        "SJF",
        "SRTF",
        "Priority (Preemptive)",
        "Round Robin",
        "EDF",
        "RMS",
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


def test_edf_and_rms_are_skipped_when_realtime_fields_missing(qapp):
    source = [make_process("P001", 0, 2), make_process("P002", 1, 1)]

    report = ExperimentService().run_all(source)

    assert len(report.results) == 6
    skipped_keys = [item.algorithm_key for item in report.skipped]
    assert "edf" in skipped_keys
    assert "rms" in skipped_keys
    assert any("Deadline" in item.reason for item in report.skipped)
    assert any("Period" in item.reason for item in report.skipped)
    assert any("未纳入比较" in note for note in report.observations)


def test_presets_are_deterministic_and_support_edf(qapp):
    assert len(EXPERIMENT_PRESETS) == 6
    for preset in EXPERIMENT_PRESETS:
        first = preset.instantiate()
        second = preset.instantiate()
        assert first == second
        assert all(process.deadline is not None for process in first)
        report = ExperimentService().run_all(first, dataset_name=preset.name)
        # realtime 预设同时带 period，可运行 RMS；其它预设仅支持 EDF
        expected = 8 if preset.key == "realtime" else 7
        assert len(report.results) == expected


def test_experiment_report_best_supports_ties(qapp):
    processes = [make_process("P001", 0, 1, deadline=5, period=10)]
    report = ExperimentService().run_all(processes)

    assert len(report.best("average_waiting_time")) == 8
    assert "全部 8 种算法" in report.observations[0]


def test_rms_is_skipped_when_period_is_missing(qapp):
    source = [make_process("P001", 0, 2, deadline=10)]
    report = ExperimentService().run_all(source)

    assert any(item.algorithm_key == "rms" for item in report.skipped)
    assert len(report.results) == 7


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


def test_comparison_auto_sizes_isolated_resources(qapp):
    source = [
        Process("P001", "Large-A", 0, 2, 1, 10, 20, memory_mb=6000, io_devices=5),
        Process("P002", "Large-B", 1, 2, 2, 12, 24, memory_mb=6000, io_devices=5),
    ]

    report = ExperimentService().run_all(source)

    assert len(report.results) == 8


def test_priority_aging_option_is_forwarded_to_batch_experiment(qapp):
    source = [make_process("P001", 0, 3, 8, 20), make_process("P002", 1, 2, 1, 10)]

    report = ExperimentService().run_all(source, priority_aging_interval=2)

    assert any(result.algorithm_name == "Priority (Preemptive) + Aging" for result in report.results)
    assert ("Priority Aging", "2 Tick") in report.parameters


def test_batch_experiment_can_be_cancelled(qapp):
    source = [make_process("P001", 0, 3, deadline=10)]

    with pytest.raises(ExperimentCancelled, match="已取消"):
        ExperimentService().run_all(source, should_cancel=lambda: True)


def test_quantum_scan_returns_sorted_results_with_expected_trends(qapp):
    source = [
        make_process("P001", 0, 8),
        make_process("P002", 1, 4),
        make_process("P003", 2, 2),
    ]
    service = ExperimentService()
    scanned = service.run_quantum_scan(source, quantum_range=(1, 2, 3, 4))

    assert [quantum for quantum, _ in scanned] == [1, 2, 3, 4]
    assert all(result.algorithm_name == "Round Robin" for _, result in scanned)
    assert all(
        {metric.pid for metric in result.process_metrics} == {"P001", "P002", "P003"}
        for _, result in scanned
    )
    switches = [result.context_switches for _, result in scanned]
    assert switches[0] >= switches[-1]
    # 时间片越小抢占越频繁，首个片段（响应时间）也越短
    assert scanned[0][1].average_response_time <= scanned[-1][1].average_response_time


def test_quantum_scan_matches_single_rr_run(qapp):
    source = [make_process("P001", 0, 5), make_process("P002", 1, 3)]
    service = ExperimentService()

    scanned = service.run_quantum_scan(source, quantum_range=(2,))
    report = service.run_all(source, rr_quantum=2)
    rr = next(result for result in report.results if result.algorithm_name == "Round Robin")

    assert scanned[0][1] == rr


def test_quantum_scan_rejects_invalid_range(qapp):
    source = [make_process("P001", 0, 2)]

    with pytest.raises(ValueError, match="正整数"):
        ExperimentService().run_quantum_scan(source, quantum_range=(0, 1))

    with pytest.raises(ValueError, match="正整数"):
        ExperimentService().run_quantum_scan(source, quantum_range=())


def test_quantum_scan_can_be_cancelled(qapp):
    source = [make_process("P001", 0, 3)]

    with pytest.raises(ExperimentCancelled, match="已取消"):
        ExperimentService().run_quantum_scan(source, should_cancel=lambda: True)


def test_safe_tick_limit_budgets_io_blocking_time():
    source = (
        Process("P001", "Reader", 0, 6, 1, io_interval=2, io_duration=3),
        Process("P002", "Writer", 2, 4, 1, io_interval=1, io_duration=2),
    )

    limit = ExperimentService._safe_tick_limit(source)

    # 最晚到达 2 + 总服务 10 + I/O 预算 ((6-1)//2*3 + (4-1)//1*2) + 余量 100
    assert limit == 2 + 10 + (2 * 3 + 3 * 2) + 100


def test_safe_tick_limit_without_io_uses_service_budget():
    source = (
        Process("P001", "A", 0, 5, 1),
        Process("P002", "B", 3, 2, 1),
    )

    limit = ExperimentService._safe_tick_limit(source)

    assert limit == 3 + 7 + 100
