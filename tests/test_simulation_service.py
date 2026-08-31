import pytest

from app.models.process import ProcessState
from app.models.schedule_segment import ScheduleSegment
from app.models.simulation_event import SimulationEventType
from app.models.simulation_state import SimulationStatus
from app.schedulers import PreemptionReason
from app.services.process_manager import ProcessManager
from app.services.resource_manager import ResourceManager
from app.services.simulation_service import SimulationService


def make_manager(processes):
    manager = ProcessManager(ResourceManager())
    for values in processes:
        manager.create_process(
            name=values.get("name", values["pid"]),
            arrival_time=values["arrival"],
            burst_time=values["burst"],
            priority=values.get("priority", 1),
            memory_mb=values.get("memory", 64),
            io_devices=values.get("io", 0),
            deadline=values.get("deadline"),
        )
    return manager


def run_until_finished(service, limit=1000):
    ticks = 0
    while service.state.status is not SimulationStatus.FINISHED:
        assert service.step()
        ticks += 1
        assert ticks < limit
    return service.build_result()


def test_load_establishes_new_and_ready_sets_at_t_zero(qapp):
    manager = make_manager(
        [
            {"pid": "P1", "arrival": 0, "burst": 2},
            {"pid": "P2", "arrival": 3, "burst": 1},
        ]
    )
    service = SimulationService(manager)

    service.load("fcfs")

    assert service.state.clock == 0
    assert service.state.status is SimulationStatus.IDLE
    assert [p.pid for p in service.state.ready_queue] == ["P001"]
    assert [p.pid for p in service.state.new_processes] == ["P002"]
    assert manager.get_process("P001").state is ProcessState.READY
    assert manager.get_process("P002").state is ProcessState.NEW
    assert [event.event_type for event in service.state.events] == [
        SimulationEventType.LOAD,
        SimulationEventType.ARRIVE,
    ]


def test_fcfs_tick_engine_records_idle_metrics_and_resource_release(qapp):
    manager = make_manager(
        [
            {"pid": "P1", "arrival": 0, "burst": 2, "memory": 128},
            {"pid": "P2", "arrival": 3, "burst": 1, "memory": 256},
        ]
    )
    service = SimulationService(manager)
    service.load("fcfs")

    result = run_until_finished(service)

    assert result.segments == (
        ScheduleSegment(0, 2, "P001"),
        ScheduleSegment(2, 3),
        ScheduleSegment(3, 4, "P002"),
    )
    assert result.total_elapsed_ticks == 4
    assert result.busy_ticks == 3
    assert result.cpu_utilization == 0.75
    assert result.context_switches == 1
    assert manager.resource_manager.resource.used_memory_mb == 0
    assert all(not p.resources_allocated for p in manager.processes)
    assert service.state.events[-1].event_type is SimulationEventType.FINISH


def test_srtf_service_matches_deterministic_case_a(qapp):
    manager = make_manager(
        [
            {"pid": "P1", "arrival": 0, "burst": 5},
            {"pid": "P2", "arrival": 1, "burst": 3},
            {"pid": "P3", "arrival": 2, "burst": 1},
        ]
    )
    service = SimulationService(manager)
    service.load("srtf")

    result = run_until_finished(service)

    assert result.segments == (
        ScheduleSegment(0, 1, "P001"),
        ScheduleSegment(1, 2, "P002"),
        ScheduleSegment(2, 3, "P003"),
        ScheduleSegment(3, 5, "P002"),
        ScheduleSegment(5, 9, "P001"),
    )
    assert result.context_switches == 4
    assert sum(
        event.event_type is SimulationEventType.PREEMPT
        for event in result.events
    ) == 2


def test_round_robin_service_preserves_time_slice_boundaries(qapp):
    manager = make_manager(
        [
            {"pid": "P1", "arrival": 0, "burst": 5},
            {"pid": "P2", "arrival": 0, "burst": 3},
            {"pid": "P3", "arrival": 1, "burst": 4},
        ]
    )
    service = SimulationService(manager)
    service.load("rr", quantum=2)

    result = run_until_finished(service)

    assert result.segments == (
        ScheduleSegment(0, 2, "P001"),
        ScheduleSegment(2, 4, "P002"),
        ScheduleSegment(4, 6, "P003"),
        ScheduleSegment(6, 8, "P001"),
        ScheduleSegment(8, 9, "P002"),
        ScheduleSegment(9, 11, "P003"),
        ScheduleSegment(11, 12, "P001"),
    )
    assert sum(
        event.event_type is SimulationEventType.TIMESLICE
        for event in result.events
    ) == 4


def test_edf_validation_happens_before_runtime_mutation(qapp):
    manager = make_manager([{"pid": "P1", "arrival": 0, "burst": 1}])
    service = SimulationService(manager)
    process = manager.processes[0]

    with pytest.raises(ValueError, match="缺少"):
        service.load("edf")

    assert process.state is ProcessState.READY
    assert process.remaining_time == 1
    assert manager.resource_manager.resource.used_memory_mb == 64


def test_edf_service_reports_deadline_miss(qapp):
    manager = make_manager(
        [
            {"pid": "P1", "arrival": 0, "burst": 3, "deadline": 5},
            {"pid": "P2", "arrival": 1, "burst": 2, "deadline": 4},
            {"pid": "P3", "arrival": 2, "burst": 4, "deadline": 8},
        ]
    )
    service = SimulationService(manager)
    service.load("edf")

    result = run_until_finished(service)

    assert result.deadline_missed_processes == ("P003",)
    assert result.deadline_miss_rate == pytest.approx(1 / 3)


def test_mlfq_service_exposes_queue_levels_in_timeline(qapp):
    manager = make_manager(
        [
            {"pid": "P1", "arrival": 0, "burst": 6},
            {"pid": "P2", "arrival": 0, "burst": 2},
        ]
    )
    service = SimulationService(manager)
    service.load("mlfq", quanta=(1, 2, 4), boost_interval=100)

    result = run_until_finished(service)

    assert result.segments == (
        ScheduleSegment(0, 1, "P001", queue_level=0),
        ScheduleSegment(1, 2, "P002", queue_level=0),
        ScheduleSegment(2, 4, "P001", queue_level=1),
        ScheduleSegment(4, 5, "P002", queue_level=1),
        ScheduleSegment(5, 8, "P001", queue_level=2),
    )


@pytest.mark.parametrize(
    ("algorithm", "options"),
    [
        ("fcfs", {}),
        ("sjf", {}),
        ("srtf", {}),
        ("priority", {"preemptive": True}),
        ("round_robin", {"quantum": 2}),
        ("edf", {}),
        ("mlfq", {"quanta": (1, 2, 4), "boost_interval": 6}),
    ],
)
def test_every_registered_algorithm_completes_through_service(
    qapp,
    algorithm,
    options,
):
    manager = make_manager(
        [
            {
                "pid": "P1",
                "arrival": 0,
                "burst": 4,
                "priority": 3,
                "deadline": 12,
            },
            {
                "pid": "P2",
                "arrival": 1,
                "burst": 2,
                "priority": 1,
                "deadline": 8,
            },
            {
                "pid": "P3",
                "arrival": 3,
                "burst": 1,
                "priority": 2,
                "deadline": 10,
            },
        ]
    )
    service = SimulationService(manager)
    completed_results = []
    service.completed.connect(completed_results.append)

    service.load(algorithm, **options)
    result = run_until_finished(service)

    assert len(result.process_metrics) == 3
    assert result.busy_ticks == 7
    assert all(process.state is ProcessState.FINISHED for process in manager.processes)
    assert completed_results == [result]


def test_load_rejects_non_scheduler_object_without_mutating_runtime(qapp):
    manager = make_manager([{"pid": "P1", "arrival": 0, "burst": 1}])

    with pytest.raises(TypeError, match="BaseScheduler"):
        SimulationService(manager).load(object())

    process = manager.processes[0]
    assert process.state is ProcessState.READY
    assert process.resources_allocated


def test_step_pause_resume_speed_and_reset_controls(qapp):
    manager = make_manager([{"pid": "P1", "arrival": 0, "burst": 2}])
    service = SimulationService(manager, base_interval_ms=1000)
    service.load("fcfs")

    service.set_speed(2)
    assert service.speed == 2.0
    assert service.timer.interval() == 500

    service.start()
    assert service.state.status is SimulationStatus.RUNNING
    assert service.timer.isActive()

    service.pause()
    assert service.state.status is SimulationStatus.PAUSED
    assert not service.timer.isActive()

    service.resume()
    assert service.state.status is SimulationStatus.RUNNING
    service.pause()

    service.step()
    assert service.state.clock == 1
    assert service.state.status is SimulationStatus.PAUSED

    service.reset()
    process = manager.processes[0]
    assert service.state.clock == 0
    assert process.remaining_time == process.burst_time
    assert process.start_time is None
    assert process.finish_time is None
    assert process.state is ProcessState.READY
    assert process.resources_allocated
    assert manager.resource_manager.resource.used_memory_mb == 64


def test_timer_timeout_advances_without_blocking_gui_thread(qapp):
    manager = make_manager([{"pid": "P1", "arrival": 0, "burst": 2}])
    service = SimulationService(manager)
    service.load("fcfs")
    service.start()

    service._on_timeout()

    assert service.state.clock == 1
    assert service.state.status is SimulationStatus.RUNNING
    assert service.state.current_process.pid == "P001"
    service.pause()


def test_suspend_running_process_removes_it_from_cpu_candidates(qapp):
    manager = make_manager(
        [
            {"pid": "P1", "arrival": 0, "burst": 3},
            {"pid": "P2", "arrival": 0, "burst": 1},
        ]
    )
    service = SimulationService(manager)
    service.load("fcfs")
    service.step()

    service.suspend_process("P001")

    assert manager.get_process("P001").state is ProcessState.SUSPENDED
    assert service.state.current_process is None
    assert all(p.pid != "P001" for p in service.state.ready_queue)

    service.step()
    assert manager.get_process("P002").state is ProcessState.FINISHED

    service.activate_process("P001")
    assert manager.get_process("P001").state is ProcessState.READY
    assert any(p.pid == "P001" for p in service.state.ready_queue)


def test_future_process_activation_returns_to_new_with_matching_activity(qapp):
    manager = make_manager([{"pid": "P1", "arrival": 5, "burst": 1}])
    service = SimulationService(manager)
    activities = []
    manager.activity.connect(lambda *values: activities.append(values))
    service.load("fcfs")

    service.suspend_process("P001")
    service.activate_process("P001")

    process = manager.get_process("P001")
    assert process.state is ProcessState.NEW
    assert process in service.state.new_processes
    assert process not in service.state.ready_queue
    assert activities[-1][3] == "SUSPENDED → NEW"


def test_revoking_finished_process_does_not_release_other_resources_twice(qapp):
    manager = make_manager(
        [
            {"pid": "P1", "arrival": 0, "burst": 1, "memory": 128},
            {"pid": "P2", "arrival": 5, "burst": 1, "memory": 256},
        ]
    )
    service = SimulationService(manager)
    service.load("fcfs")
    service.step()

    assert manager.get_process("P001").state is ProcessState.FINISHED
    assert manager.resource_manager.resource.used_memory_mb == 256

    manager.revoke_process("P001")

    assert manager.resource_manager.resource.used_memory_mb == 256


def test_external_process_set_change_requires_reload_or_reset(qapp):
    manager = make_manager([{"pid": "P1", "arrival": 0, "burst": 1}])
    service = SimulationService(manager)
    service.load("fcfs")
    manager.create_process(
        name="Late addition",
        arrival_time=0,
        burst_time=1,
        priority=1,
        memory_mb=64,
        io_devices=0,
    )

    with pytest.raises(ValueError, match="进程集合"):
        service.step()

    service.reset()
    result = run_until_finished(service)
    assert {metrics.pid for metrics in result.process_metrics} == {"P001", "P002"}


def test_external_state_change_cannot_silently_corrupt_ready_queue(qapp):
    manager = make_manager([{"pid": "P1", "arrival": 0, "burst": 1}])
    service = SimulationService(manager)
    service.load("fcfs")
    manager.suspend_process("P001")

    with pytest.raises(ValueError, match="外部改变"):
        service.step()


def test_unload_clears_algorithm_and_runtime_but_preserves_dataset(qapp):
    manager = make_manager([{"pid": "P1", "arrival": 0, "burst": 2}])
    service = SimulationService(manager)
    service.load("fcfs")
    service.step()

    service.unload()

    assert service.scheduler is None
    assert service.state.status is SimulationStatus.IDLE
    assert service.state.clock == 0
    assert service.state.segments == []
    assert len(manager.processes) == 1
    assert manager.get_process("P001").burst_time == 2


def test_switch_cost_inserts_context_switch_ticks(qapp):
    manager = make_manager(
        [
            {"pid": "P1", "arrival": 0, "burst": 2},
            {"pid": "P2", "arrival": 0, "burst": 2},
        ]
    )
    service = SimulationService(manager, switch_cost=1)
    service.load("fcfs")

    result = run_until_finished(service)

    assert result.total_elapsed_ticks == 5
    assert result.context_switch_ticks == 1
    assert result.context_switches == 1
    assert result.effective_busy_ticks == 4
    assert result.cpu_utilization == pytest.approx(4 / 5)
    assert any(segment.is_context_switch for segment in result.segments)
    assert not result.segments[-1].is_context_switch


def test_io_blocking_releases_cpu_and_resumes(qapp):
    manager = ProcessManager(ResourceManager())
    manager.create_process(
        name="CPU", arrival_time=0, burst_time=4, priority=1, memory_mb=64, io_devices=0
    )
    manager.create_process(
        name="IO",
        arrival_time=0,
        burst_time=4,
        priority=1,
        memory_mb=64,
        io_devices=1,
        io_interval=1,
        io_duration=2,
    )
    service = SimulationService(manager)
    service.load("fcfs")

    result = run_until_finished(service)

    io_process = manager.get_process("P002")
    assert io_process.state is ProcessState.FINISHED
    assert any(
        event.event_type is SimulationEventType.IO_REQUEST
        for event in result.events
    )
    assert any(
        event.event_type is SimulationEventType.IO_COMPLETE
        for event in result.events
    )
    # P001 先占 CPU 4 Tick；P002 每次运行 1 Tick 后按 io_duration=2 精确阻塞 2 Tick，
    # 共 3 次 I/O 等待（最后一次运行后直接完成），总耗时 4 + 4 + 3*2 = 14。
    assert result.total_elapsed_ticks == 14
    assert result.busy_ticks == 8
    assert result.cpu_utilization == pytest.approx(8 / 14)
    assert sum(
        event.event_type is SimulationEventType.IO_REQUEST
        for event in result.events
    ) == 3
    assert sum(
        event.event_type is SimulationEventType.IO_COMPLETE
        for event in result.events
    ) == 3


def test_fcfs_io_completion_rejoins_at_end_of_ready_queue(qapp):
    manager = ProcessManager(ResourceManager())
    manager.create_process(
        pid="P1", name="I/O", arrival_time=0, burst_time=3, priority=1,
        memory_mb=64, io_devices=1, io_interval=1, io_duration=1,
    )
    manager.create_process(
        pid="P2", name="CPU", arrival_time=0, burst_time=3, priority=1,
        memory_mb=64, io_devices=0,
    )
    manager.create_process(
        pid="P3", name="Waiting", arrival_time=1, burst_time=1, priority=1,
        memory_mb=64, io_devices=0,
    )
    service = SimulationService(manager)
    service.load("fcfs")

    result = run_until_finished(service)

    assert [segment.pid for segment in result.segments[:4]] == ["P1", "P2", "P3", "P1"]


def test_io_duration_blocks_exactly_n_full_ticks(qapp):
    """io_duration=N 必须阻塞 N 个完整 Tick，而不是 N-1 或 N+1。"""
    manager = make_manager(
        [
            {"pid": "P1", "arrival": 0, "burst": 2, "io": 1},
        ]
    )
    manager.processes[0].io_interval = 1
    manager.processes[0].io_duration = 2
    service = SimulationService(manager)
    service.load("fcfs")

    result = run_until_finished(service)

    # T0 运行 1 Tick 后请求 I/O；T1、T2 各阻塞 1 Tick（合并为一段空闲）；T3 恢复运行最后 1 Tick。
    assert result.segments == (
        ScheduleSegment(0, 1, "P001"),
        ScheduleSegment(1, 3),
        ScheduleSegment(3, 4, "P001"),
    )
    assert result.busy_ticks == 2
    assert result.total_elapsed_ticks == 4
    assert result.process_metrics[0].waiting_time == 0
    assert manager.get_process("P001").waiting_time == 0


def test_io_progress_is_not_double_counted_during_switch_tick(qapp):
    """切换 Tick 期间 I/O 进程的 io_remaining 只能扣减一次。"""
    manager = make_manager(
        [
            {"pid": "P1", "arrival": 0, "burst": 2, "io": 1},
            {"pid": "P2", "arrival": 0, "burst": 1},
        ]
    )
    manager.get_process("P001").io_interval = 1
    manager.get_process("P001").io_duration = 2
    service = SimulationService(manager, switch_cost=1)
    service.load("fcfs")

    # T0：P1 运行并进入 I/O 阻塞。
    service.step()
    assert service.state.current_process is None
    assert manager.get_process("P001").state is ProcessState.BLOCKED
    # T1：P1 扣减一次，P2 立即执行唯一的上下文切换 Tick。
    service.step()
    assert manager.get_process("P001").io_remaining == 1
    assert service.state.switch_remaining == 0
    assert service.state.segments[-1].is_context_switch
    # T2：派发 P2。I/O 进度每个真实 Tick 只扣减一次，P1 仍保持阻塞。
    service.step()
    assert manager.get_process("P001").io_remaining == 0
    assert manager.get_process("P001").state is ProcessState.BLOCKED
    assert manager.get_process("P001") not in service.state.ready_queue
    assert any(segment.is_context_switch for segment in service.state.segments)


def test_suspend_remaining_process_still_allows_natural_completion(qapp):
    """挂起唯一未完成进程后，其余进程完成即触发 FINISHED，而非卡死。"""
    manager = make_manager(
        [
            {"pid": "P1", "arrival": 0, "burst": 5},
            {"pid": "P2", "arrival": 0, "burst": 1},
        ]
    )
    service = SimulationService(manager)
    service.load("fcfs")
    service.suspend_process("P001")
    completed = []
    service.completed.connect(completed.append)

    result = run_until_finished(service)

    assert service.state.status is SimulationStatus.FINISHED
    assert manager.get_process("P001").state is ProcessState.SUSPENDED
    assert manager.get_process("P002").state is ProcessState.FINISHED
    # build_result 只为 FINISHED 的进程生成指标，挂起进程不进入最终结果。
    assert [metrics.pid for metrics in result.process_metrics] == ["P002"]
    assert completed == [result]


def test_suspend_single_process_can_be_activated_and_complete(qapp):
    manager = make_manager([{"pid": "P1", "arrival": 0, "burst": 2}])
    service = SimulationService(manager)
    service.load("fcfs")
    service.suspend_process("P001")

    service.step()

    # 唯一进程被挂起后没有可运行对象，仿真进入可恢复的 PAUSED 而非悬挂。
    assert service.state.status is SimulationStatus.PAUSED

    service.activate_process("P001")
    result = run_until_finished(service)
    assert {metrics.pid for metrics in result.process_metrics} == {"P001"}


def test_activate_process_reopens_partial_finished_simulation(qapp):
    manager = make_manager(
        [
            {"pid": "P1", "arrival": 0, "burst": 5},
            {"pid": "P2", "arrival": 0, "burst": 1},
        ]
    )
    service = SimulationService(manager)
    service.load("fcfs")
    service.suspend_process("P001")
    partial = run_until_finished(service)
    assert [metrics.pid for metrics in partial.process_metrics] == ["P002"]

    service.activate_process("P001")

    assert service.state.status is SimulationStatus.PAUSED
    result = run_until_finished(service)
    assert {metrics.pid for metrics in result.process_metrics} == {"P001", "P002"}


def test_reset_capacity_failure_is_atomic(qapp):
    manager = make_manager(
        [
            {"pid": "P1", "arrival": 0, "burst": 1, "memory": 64},
            {"pid": "P2", "arrival": 0, "burst": 1, "memory": 64},
        ]
    )
    service = SimulationService(manager)
    service.load("fcfs")
    run_until_finished(service)
    manager.resource_manager.configure_totals(64, 8)
    before = [
        (process.state, process.remaining_time, process.resources_allocated)
        for process in manager.processes
    ]

    with pytest.raises(ValueError, match="共需 128 MB"):
        service.reset()

    assert service.state.status is SimulationStatus.FINISHED
    assert manager.resource_manager.resource.used_memory_mb == 0
    assert [
        (process.state, process.remaining_time, process.resources_allocated)
        for process in manager.processes
    ] == before


def test_suspend_process_cleans_scheduler_internal_state(qapp, monkeypatch):
    """挂起非 NEW 进程时必须以 POLICY 抢占通知调度器清理内部状态。"""
    manager = make_manager(
        [
            {"pid": "P1", "arrival": 0, "burst": 3},
            {"pid": "P2", "arrival": 0, "burst": 1},
        ]
    )
    service = SimulationService(manager)
    service.load("fcfs")
    service.step()

    calls = []
    monkeypatch.setattr(
        service._scheduler,
        "on_preempt",
        lambda process, clock, reason: calls.append((process.pid, reason)),
    )

    service.suspend_process("P001")

    assert ("P001", PreemptionReason.POLICY) in calls
    # 挂起后进程应退出全部运行集合。
    assert manager.get_process("P001").state is ProcessState.SUSPENDED
    assert service.state.current_process is None
    assert all(p.pid != "P001" for p in service.state.ready_queue)


def test_set_switch_cost_updates_runtime_even_after_load(qapp):
    """load 之后调整切换开销必须立即反映到运行时状态。"""
    manager = make_manager(
        [
            {"pid": "P1", "arrival": 0, "burst": 2},
            {"pid": "P2", "arrival": 0, "burst": 2},
        ]
    )
    service = SimulationService(manager, switch_cost=0)
    service.load("fcfs")
    service.step()

    service.set_switch_cost(1)

    assert service.state.switch_cost == 1
    result = run_until_finished(service)
    assert result.context_switch_ticks == 1


def test_context_switch_event_does_not_claim_stale_target(qapp):
    manager = make_manager(
        [
            {"pid": "P1", "arrival": 0, "burst": 2, "priority": 5},
            {"pid": "P2", "arrival": 1, "burst": 2, "priority": 4},
            {"pid": "P3", "arrival": 2, "burst": 1, "priority": 1},
        ]
    )
    service = SimulationService(manager, switch_cost=2)
    service.load("priority", preemptive=True)

    for _ in range(4):
        service.step()

    switch_event = next(
        event
        for event in service.state.events
        if event.event_type is SimulationEventType.CONTEXT_SWITCH
    )
    dispatches = [
        event
        for event in service.state.events
        if event.event_type is SimulationEventType.DISPATCH
    ]
    assert switch_event.pid is None
    assert "切换结束后" in switch_event.detail
    assert dispatches[-1].pid == "P003"
