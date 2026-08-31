import pytest

from app.models.process import ProcessState
from app.services.process_manager import ProcessManager
from app.services.resource_manager import ResourceManager


@pytest.fixture
def manager():
    return ProcessManager(ResourceManager())


def create_process(manager, **overrides):
    values = {
        "name": "Compiler",
        "arrival_time": 0,
        "burst_time": 8,
        "priority": 3,
        "memory_mb": 512,
        "io_devices": 1,
        "deadline": 15,
        "period": 20,
    }
    values.update(overrides)
    return manager.create_process(**values)


def test_create_process_assigns_pid_state_and_resources(manager):
    first = create_process(manager)
    second = create_process(manager, name="Editor", deadline=None, period=None)

    assert first.pid == "P001"
    assert second.pid == "P002"
    assert first.state is ProcessState.READY
    assert first.remaining_time == first.burst_time
    assert manager.resource_manager.resource.used_memory_mb == 1024
    assert manager.resource_manager.resource.used_io_devices == 2


def test_suspend_activate_and_revoke_process(manager):
    process = create_process(manager)

    manager.suspend_process(process.pid)
    assert process.state is ProcessState.SUSPENDED

    manager.activate_process(process.pid)
    assert process.state is ProcessState.READY

    manager.revoke_process(process.pid)
    assert manager.get_process(process.pid) is None
    assert manager.resource_manager.resource.used_memory_mb == 0
    assert manager.resource_manager.resource.used_io_devices == 0


def test_invalid_state_transitions_are_rejected(manager):
    process = create_process(manager)

    with pytest.raises(ValueError, match="只有挂起进程"):
        manager.activate_process(process.pid)

    manager.suspend_process(process.pid)
    with pytest.raises(ValueError, match="已经处于挂起状态"):
        manager.suspend_process(process.pid)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"name": "  "}, "名称不能为空"),
        ({"arrival_time": -1}, "到达时间不能小于"),
        ({"burst_time": 0}, "服务时间必须大于"),
        ({"priority": 0}, "优先级必须大于"),
        ({"memory_mb": 0}, "内存需求必须大于"),
        ({"io_devices": -1}, "不能小于"),
    ],
)
def test_create_rejects_invalid_fields_without_allocating(
    manager,
    overrides,
    message,
):
    with pytest.raises(ValueError, match=message):
        create_process(manager, **overrides)

    assert manager.processes == []
    assert manager.resource_manager.resource.used_memory_mb == 0


def test_create_rejects_resource_shortage_atomically(manager):
    with pytest.raises(ValueError, match="可用内存不足"):
        create_process(manager, memory_mb=9000)

    assert manager.processes == []
    assert manager.resource_manager.resource.used_memory_mb == 0
    assert manager.resource_manager.resource.used_io_devices == 0


def test_duplicate_or_blank_pid_does_not_leak_resources(manager):
    create_process(manager, pid="P001", memory_mb=100, io_devices=1)

    for invalid_pid in ("P001", "   "):
        with pytest.raises(ValueError):
            create_process(
                manager,
                pid=invalid_pid,
                memory_mb=200,
                io_devices=2,
            )

    assert len(manager.processes) == 1
    assert manager.resource_manager.resource.used_memory_mb == 100
    assert manager.resource_manager.resource.used_io_devices == 1


def test_future_arrival_remains_new_until_simulation_admits_it(manager):
    process = create_process(manager, arrival_time=5, deadline=10)

    assert process.state is ProcessState.NEW
    assert manager.state_counts()[ProcessState.NEW] == 1

    manager.suspend_process(process.pid)
    manager.activate_process(process.pid)
    assert process.state is ProcessState.NEW


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"arrival_time": 5, "deadline": 5}, "Deadline 必须大于"),
        ({"period": 0}, "Period 必须大于"),
    ],
)
def test_create_rejects_invalid_realtime_parameters(
    manager,
    overrides,
    message,
):
    with pytest.raises(ValueError, match=message):
        create_process(manager, **overrides)

    assert manager.processes == []
    assert manager.resource_manager.resource.used_memory_mb == 0


def test_state_counts_include_all_states(manager):
    create_process(manager)
    suspended = create_process(manager, name="Editor")
    manager.suspend_process(suspended.pid)

    counts = manager.state_counts()

    assert counts[ProcessState.READY] == 1
    assert counts[ProcessState.SUSPENDED] == 1
    assert counts[ProcessState.NEW] == 0
    assert counts[ProcessState.RUNNING] == 0
    assert counts[ProcessState.FINISHED] == 0
