from app.models.process import ProcessState
from app.schedulers.registry import SCHEDULER_FACTORIES
from app.services.process_manager import ProcessManager
from app.services.resource_manager import ResourceManager
from app.services.simulation_service import SimulationService
from app.ui.dashboard_page import DashboardPage


def create_process(manager, name="Compiler"):
    return manager.create_process(
        name=name,
        arrival_time=0,
        burst_time=8,
        priority=3,
        memory_mb=512,
        io_devices=1,
    )


def test_dashboard_initial_empty_state(qapp):
    manager = ProcessManager(ResourceManager())
    page = DashboardPage(manager)

    assert page.process_card.value_label.text() == "0"
    assert page.ready_card.value_label.text() == "0"
    assert page.memory_card.value_label.text() == "0 / 8192 MB"
    assert page.memory_bar.progress.value() == 0
    assert page.io_bar.progress.value() == 0
    assert page.timeline_time_label.text() == "T = 0"


def test_dashboard_reacts_to_process_and_resource_changes(qapp):
    manager = ProcessManager(ResourceManager())
    page = DashboardPage(manager)

    process = create_process(manager)

    assert page.process_card.value_label.text() == "1"
    assert page.ready_card.value_label.text() == "1"
    assert page.memory_card.value_label.text() == "512 / 8192 MB"
    assert page.memory_bar.progress.value() == 6
    assert page.io_bar.progress.value() == 12
    assert page.state_count_labels[ProcessState.READY].text() == "1"

    manager.suspend_process(process.pid)

    assert page.ready_card.value_label.text() == "0"
    assert page.state_count_labels[ProcessState.SUSPENDED].text() == "1"

    manager.activate_process(process.pid)
    assert page.state_count_labels[ProcessState.READY].text() == "1"

    manager.revoke_process(process.pid)

    assert page.process_card.value_label.text() == "0"
    assert page.memory_bar.progress.value() == 0
    assert page.io_bar.progress.value() == 0


def test_dashboard_activity_log_is_latest_first(qapp):
    manager = ProcessManager(ResourceManager())
    page = DashboardPage(manager)

    process = create_process(manager)
    assert page.activity_table.item(0, 1).text() == "STATE"
    assert page.activity_table.item(0, 2).text() == process.pid

    manager.suspend_process(process.pid)
    assert page.activity_table.item(0, 1).text() == "SUSPEND"

    manager.activate_process(process.pid)
    assert page.activity_table.item(0, 1).text() == "ACTIVATE"

    manager.revoke_process(process.pid)
    assert page.activity_table.item(0, 1).text() == "REVOKE"
    assert "释放内存" in page.activity_table.item(0, 3).text()


def test_dashboard_activity_log_is_bounded(qapp):
    manager = ProcessManager(ResourceManager())
    page = DashboardPage(manager)

    for index in range(30):
        process = manager.create_process(
            name=f"Worker{index}",
            arrival_time=0,
            burst_time=1,
            priority=1,
            memory_mb=64,
            io_devices=0,
        )
        manager.revoke_process(process.pid)

    assert page.activity_table.rowCount() == 50
    assert page.activity_table.item(0, 1).text() == "REVOKE"


def test_dashboard_reads_live_simulation_state(qapp):
    manager = ProcessManager(ResourceManager())
    manager.create_process(
        name="Compiler",
        arrival_time=0,
        burst_time=2,
        priority=1,
        memory_mb=64,
        io_devices=0,
    )
    simulation = SimulationService(manager)
    page = DashboardPage(manager, simulation)

    simulation.load("fcfs")
    simulation.step()

    assert page.cpu_card.value_label.text() == "P001"
    assert page.cpu_bar.progress.value() == 100
    assert page.timeline_time_label.text() == "T = 1"
    assert page.info_values["Scheduler"].text() == "FCFS"
    assert page.info_values["Simulation"].text() == "Paused"
    assert page.status_label.text() == "●  Simulation Paused"
    assert page.timeline_layout.count() == 1
    assert page.timeline_layout.itemAt(0).widget().text() == "P001\n0–1"


def test_dashboard_reports_registered_algorithm_count(qapp):
    """算法数量文案必须与调度器注册表一致，不能回退为硬编码旧值。"""
    manager = ProcessManager(ResourceManager())
    page = DashboardPage(manager)

    assert page.info_values["Algorithms"].text() == (
        f"{len(SCHEDULER_FACTORIES)} implemented"
    )
