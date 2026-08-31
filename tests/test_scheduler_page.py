from app.models.schedule_segment import ScheduleSegment
from app.models.simulation_state import SimulationStatus
from app.schedulers.base import PreemptionReason
from app.schedulers.mlfq import MLFQScheduler
from app.schedulers.round_robin import RoundRobinScheduler
from app.services.process_manager import ProcessManager
from app.services.resource_manager import ResourceManager
from app.services.simulation_service import SimulationService
from app.ui.main_window import MainWindow
from app.ui.process_page import ProcessPage
from app.ui.scheduler_page import SchedulerPage
from app.widgets.dialogs import MessageDialog
from app.widgets.gantt_chart import GanttChart


def add_process(
    manager,
    name="Worker",
    *,
    arrival=0,
    burst=3,
    priority=1,
    deadline=None,
    period=None,
):
    return manager.create_process(
        name=name,
        arrival_time=arrival,
        burst_time=burst,
        priority=priority,
        deadline=deadline,
        period=period,
        memory_mb=64,
        io_devices=0,
    )


def make_page():
    manager = ProcessManager(ResourceManager())
    service = SimulationService(manager)
    return manager, service, SchedulerPage(manager, service)


def test_scheduler_page_initial_state_and_algorithm_parameter_pages(qapp):
    manager, service, page = make_page()

    assert page.run_status_label.text() == "●  尚未加载"
    assert not page.load_button.isEnabled()
    assert not page.start_button.isEnabled()
    assert page.parameter_stack.currentIndex() == 0

    page.algorithm_combo.setCurrentIndex(3)
    assert page.parameter_stack.currentIndex() == 1
    page.algorithm_combo.setCurrentIndex(4)
    assert page.parameter_stack.currentIndex() == 2
    page.algorithm_combo.setCurrentIndex(6)
    assert page.parameter_stack.currentIndex() == 0
    page.algorithm_combo.setCurrentIndex(7)
    assert page.parameter_stack.currentIndex() == 3

    add_process(manager)
    assert page.load_button.isEnabled()
    assert service.scheduler is None


def test_round_robin_controls_drive_service_and_live_views(qapp):
    manager, service, page = make_page()
    add_process(manager, "Alpha", burst=3)
    add_process(manager, "Beta", burst=2)
    page.algorithm_combo.setCurrentIndex(4)
    page.quantum_input.setValue(1)

    assert page.load_experiment()
    assert isinstance(service.scheduler, RoundRobinScheduler)
    assert service.scheduler.quantum == 1
    assert page.run_status_label.text() == "●  实验就绪"
    assert page.start_button.isEnabled()
    assert page.step_button.isEnabled()
    assert page.ready_queue_layout.count() == 3  # 两个 Token + stretch

    assert page.step_simulation()

    assert service.state.status is SimulationStatus.PAUSED
    assert page.run_status_label.text() == "●  已暂停"
    assert page.clock_card.value_label.text() == "T = 1"
    assert page.cpu_card.value_label.text() == "IDLE"
    assert page.gantt_chart.segments == (ScheduleSegment(0, 1, "P001"),)
    assert page.event_table.rowCount() >= 4
    assert page.process_table.rowCount() == 2
    assert page.start_button.text() == "▶  继续运行"


def test_start_pause_and_reset_button_state_machine(qapp):
    manager, service, page = make_page()
    add_process(manager, burst=2)
    assert page.load_experiment()

    page.start_simulation()
    assert service.state.status is SimulationStatus.RUNNING
    assert service.timer.isActive()
    assert not page.load_button.isEnabled()
    assert page.pause_button.isEnabled()
    assert not page.step_button.isEnabled()

    page.pause_simulation()
    assert service.state.status is SimulationStatus.PAUSED
    assert not service.timer.isActive()
    assert page.step_button.isEnabled()

    page.step_simulation()
    page.step_simulation()
    assert service.state.status is SimulationStatus.FINISHED
    assert page.run_status_label.text() == "●  已完成"
    assert not page.start_button.isEnabled()
    assert not page.step_button.isEnabled()
    assert page.process_table.item(0, 5).text() == "2"
    assert page.process_table.item(0, 6).text() == "0"

    page.reset_simulation()
    assert service.state.status is SimulationStatus.IDLE
    assert service.state.clock == 0
    assert page.gantt_chart.segments == ()


def test_edf_validation_error_is_presented_without_partial_load(qapp, monkeypatch):
    manager, service, page = make_page()
    add_process(manager, deadline=None)
    page.algorithm_combo.setCurrentIndex(5)
    errors = []
    monkeypatch.setattr(
        MessageDialog,
        "show_error",
        lambda parent, title, message: errors.append((title, message)),
    )

    assert not page.load_experiment()
    assert service.scheduler is None
    assert errors and "Deadline" in errors[0][1]


def test_mlfq_configuration_is_forwarded_to_scheduler(qapp):
    manager, service, page = make_page()
    add_process(manager)
    page.algorithm_combo.setCurrentIndex(7)
    for control, value in zip(page.mlfq_inputs, (2, 4, 8)):
        control.setValue(value)
    page.boost_input.setValue(16)

    assert page.load_experiment()
    assert isinstance(service.scheduler, MLFQScheduler)
    assert service.scheduler.quanta == (2, 4, 8)
    assert service.scheduler.boost_interval == 16


def test_priority_aging_configuration_is_forwarded_and_visualized(qapp):
    manager, service, page = make_page()
    add_process(manager, priority=5)
    add_process(manager, priority=2)
    page.algorithm_combo.setCurrentIndex(3)
    page.priority_aging_combo.setCurrentIndex(2)

    assert page.load_experiment()
    assert service.scheduler.aging_interval == 4
    assert "Aging" in page.queue_rule_label.text()


def test_mlfq_ready_processes_are_split_into_three_visible_queues(qapp):
    manager, service, page = make_page()
    first = add_process(manager, "Alpha", burst=5)
    add_process(manager, "Beta", burst=5)
    page.algorithm_combo.setCurrentIndex(7)

    assert page.load_experiment()
    assert page.mlfq_queue_widget.isVisibleTo(page)
    assert not page.ready_queue_widget.isVisibleTo(page)
    assert "队列层级" in page.queue_rule_label.text()
    assert page.mlfq_queue_layouts[0].count() == 3
    assert page.mlfq_queue_layouts[1].count() == 2  # 空态文案 + stretch
    assert page.mlfq_queue_layouts[2].count() == 2

    service.scheduler.on_preempt(first, 0, PreemptionReason.TIME_SLICE)
    page.refresh()
    assert page.mlfq_queue_layouts[0].count() == 2
    assert page.mlfq_queue_layouts[1].count() == 2
    assert "P001" in page.mlfq_queue_layouts[1].itemAt(0).widget().text()


def test_priority_queue_is_visualized_in_policy_order(qapp):
    manager, service, page = make_page()
    add_process(manager, "Low", priority=8)
    add_process(manager, "High", priority=1)
    page.algorithm_combo.setCurrentIndex(3)

    assert page.load_experiment()
    assert "优先级" in page.queue_rule_label.text()
    assert "P002" in page.ready_queue_layout.itemAt(0).widget().text()
    assert "优先级 1" in page.ready_queue_layout.itemAt(0).widget().text()


def test_rms_queue_is_visualized_in_period_order(qapp):
    manager, service, page = make_page()
    add_process(manager, "Slow", period=20)
    add_process(manager, "Fast", period=5)
    page.algorithm_combo.setCurrentIndex(6)

    assert page.load_experiment()
    assert "Period" in page.queue_rule_label.text()
    assert "P002" in page.ready_queue_layout.itemAt(0).widget().text()
    assert "T=5" in page.ready_queue_layout.itemAt(0).widget().text()


def test_gantt_chart_scales_for_long_timelines(qapp):
    chart = GanttChart()
    segments = (
        ScheduleSegment(0, 4, "P001"),
        ScheduleSegment(4, 7),
        ScheduleSegment(7, 20, "P002", queue_level=2),
    )

    chart.set_segments(segments)

    assert chart.segments == segments
    assert chart.minimumWidth() >= 20 * 56
    assert chart.minimumHeight() == 138


def test_scheduler_page_exports_gantt_png(qapp, monkeypatch, tmp_path):
    manager, service, page = make_page()
    add_process(manager, burst=1)
    assert page.load_experiment()
    assert page.step_simulation()
    target = tmp_path / "timeline.png"
    monkeypatch.setattr(
        "app.ui.scheduler_page.QFileDialog.getSaveFileName",
        lambda *args: (str(target), "PNG Images (*.png)"),
    )

    page.export_gantt_png()

    assert target.exists()
    assert target.stat().st_size > 0


def test_main_window_uses_real_scheduler_page(qapp):
    window = MainWindow()

    assert isinstance(window.stack.widget(2), SchedulerPage)
    assert window.stack.widget(2).simulation_service is window.simulation_service

    window.close()


def test_process_management_is_locked_while_simulation_runs(qapp, monkeypatch):
    manager = ProcessManager(ResourceManager())
    add_process(manager)
    service = SimulationService(manager)
    page = ProcessPage(manager, service)
    service.load("fcfs")
    service.start()
    errors = []
    monkeypatch.setattr(
        MessageDialog,
        "show_error",
        lambda parent, title, message: errors.append((title, message)),
    )

    assert not page.create_button.isEnabled()
    page.open_create_dialog()
    assert errors and "正在运行" in errors[0][1]

    service.pause()
    assert page.create_button.isEnabled()
