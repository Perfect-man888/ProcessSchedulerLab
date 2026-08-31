import pytest

from app.models.process import ProcessState
from app.services.export_service import ExportService
from app.services.process_manager import ProcessManager
from app.services.resource_manager import ResourceManager
from app.services.simulation_service import SimulationService
from app.ui.main_window import MainWindow
from app.ui.process_page import CreateProcessDialog, ProcessPage, RandomProcessDialog
from app.widgets.dialogs import MessageDialog
from app.widgets.filter_combo import FilterCombo
from app.widgets.number_input import NumberInput
from app.widgets.state_badge import StateBadge


def test_number_input_clamps_values(qapp):
    control = NumberInput(1, 10, 5, "tick")

    control.setValue(99)
    assert control.value() == 10

    control.editor.clear()
    control._normalize()
    assert control.value() == 1


def test_filter_combo_has_deterministic_selection(qapp):
    control = FilterCombo()
    control.addItems(["全部状态", "就绪", "挂起"])

    assert control.currentText() == "全部状态"

    control.setCurrentIndex(2)
    assert control.currentText() == "挂起"

    control.clear()
    control.addItems(["批处理", "分时"])
    assert control.currentText() == "批处理"


def test_create_dialog_realtime_toggle_and_submission(qapp):
    manager = ProcessManager(ResourceManager())
    dialog = CreateProcessDialog(manager)

    assert not dialog.deadline_input.isEnabled()
    assert not dialog.period_input.isEnabled()

    dialog.name_input.setText("RealtimeWorker")
    dialog.arrival_input.setValue(2)
    dialog.realtime_toggle.setChecked(True)
    dialog.deadline_input.setValue(12)
    dialog.period_input.setValue(20)
    dialog._create_process()

    process = manager.processes[0]
    assert process.deadline == 12
    assert process.period == 20
    assert dialog.result() == dialog.DialogCode.Accepted


def test_edit_dialog_prefills_and_updates_all_process_parameters(qapp):
    manager = ProcessManager(ResourceManager())
    process = manager.create_process(
        name="Worker",
        arrival_time=0,
        burst_time=5,
        priority=3,
        memory_mb=128,
        io_devices=0,
    )
    dialog = CreateProcessDialog(manager, process=process)

    assert dialog.windowTitle() == "编辑进程 · P001"
    assert dialog.name_input.text() == "Worker"
    assert dialog.submit_button.text() == "保存修改"
    dialog.name_input.setText("Edited")
    dialog.io_toggle.setChecked(True)
    dialog.io_interval_input.setValue(3)
    dialog.io_duration_input.setValue(2)
    dialog._create_process()

    assert manager.get_process("P001") is process
    assert process.name == "Edited"
    assert process.io_interval == 3
    assert process.io_duration == 2
    assert dialog.result() == dialog.DialogCode.Accepted


def test_create_dialog_fits_minimum_supported_screen(qapp):
    dialog = CreateProcessDialog(ProcessManager(ResourceManager()))

    assert dialog.sizeHint().height() <= 720
    assert dialog.sizeHint().width() <= 1200


def test_create_dialog_uses_configured_resource_limits(qapp):
    resources = ResourceManager()
    resources.configure_totals(65536, 128)
    dialog = CreateProcessDialog(ProcessManager(resources))

    assert dialog.memory_input.maximum == 65536
    assert dialog.io_input.maximum == 128


def test_random_dialog_configures_distribution_parameters(qapp):
    manager = ProcessManager(ResourceManager())
    dialog = RandomProcessDialog(manager)

    dialog.count_input.setValue(5)
    dialog.interval_input.setValue(2)
    dialog.burst_min_input.setValue(2)
    dialog.burst_max_input.setValue(6)
    dialog.seed_toggle.setChecked(False)
    config = dialog._config()

    assert config.count == 5
    assert config.arrival_rate == pytest.approx(0.5)
    assert config.burst_min == 2
    assert config.burst_max == 6
    assert config.seed is None

    dialog.seed_toggle.setChecked(True)
    dialog.seed_input.setValue(99)
    assert dialog._config().seed == 99

    dialog.realtime_toggle.setChecked(True)
    assert dialog._config().include_realtime
    dialog.io_toggle.setChecked(True)
    dialog.io_interval_input.setValue(4)
    dialog.io_duration_input.setValue(3)
    assert dialog._config().include_io
    assert dialog._config().io_interval == 4
    assert dialog._config().io_duration == 3


def test_random_dialog_generates_and_adds_processes(qapp):
    manager = ProcessManager(ResourceManager())
    dialog = RandomProcessDialog(manager)

    dialog.count_input.setValue(5)
    dialog.interval_input.setValue(2)
    dialog.burst_min_input.setValue(2)
    dialog.burst_max_input.setValue(6)
    dialog._generate()

    assert len(manager.processes) == 5
    assert all(2 <= process.burst_time <= 6 for process in manager.processes)
    assert dialog.result() == dialog.DialogCode.Accepted


def test_random_dialog_generates_optional_io_behavior(qapp):
    manager = ProcessManager(ResourceManager())
    dialog = RandomProcessDialog(manager)
    dialog.count_input.setValue(3)
    dialog.io_toggle.setChecked(True)
    dialog.io_interval_input.setValue(3)
    dialog.io_duration_input.setValue(2)

    dialog._generate()

    assert all(process.io_interval == 3 for process in manager.processes)
    assert all(process.io_duration == 2 for process in manager.processes)


def test_random_dialog_rejects_insufficient_memory(qapp, monkeypatch):
    resources = ResourceManager()
    resources.configure_totals(256, 8)
    manager = ProcessManager(resources)
    dialog = RandomProcessDialog(manager)
    dialog.count_input.setValue(5)
    errors = []
    monkeypatch.setattr(
        MessageDialog,
        "show_error",
        lambda parent, title, message: errors.append((title, message)),
    )

    dialog._generate()

    assert errors and "内存不足" in errors[0][0]
    assert len(manager.processes) == 0
    assert dialog.result() != dialog.DialogCode.Accepted


def test_process_page_refreshes_table_and_state_badge(qapp):
    manager = ProcessManager(ResourceManager())
    page = ProcessPage(manager)

    process = manager.create_process(
        name="Compiler",
        arrival_time=0,
        burst_time=8,
        priority=3,
        memory_mb=512,
        io_devices=1,
    )

    assert page.table.rowCount() == 1
    assert page.table.item(0, 0).text() == process.pid
    assert isinstance(page.table.cellWidget(0, 2), StateBadge)
    assert page.table.columnCount() == 11
    assert page.table.horizontalHeaderItem(10).text() == "PERIOD"
    assert "RMS" in page.table.horizontalHeaderItem(10).toolTip()
    assert page.ready_card.value_label.text() == "1"

    page.table.selectRow(0)
    assert page.edit_button.isEnabled()

    manager.suspend_process(process.pid)
    assert process.state is ProcessState.SUSPENDED
    assert page.suspended_card.value_label.text() == "1"


def test_process_page_search_and_state_filter(qapp):
    manager = ProcessManager(ResourceManager())
    page = ProcessPage(manager)
    manager.create_process(
        name="Compiler",
        arrival_time=0,
        burst_time=8,
        priority=3,
        memory_mb=512,
        io_devices=1,
    )
    editor = manager.create_process(
        name="Editor",
        arrival_time=1,
        burst_time=4,
        priority=1,
        memory_mb=256,
        io_devices=1,
    )
    manager.suspend_process(editor.pid)

    page.search_input.setText("compiler")
    assert page.table.rowCount() == 1

    page.search_input.clear()
    page.state_filter.setCurrentIndex(3)
    assert page.table.rowCount() == 1
    assert page.table.item(0, 1).text() == "Editor"


def test_main_window_smoke_at_supported_sizes(qapp):
    window = MainWindow()

    for width, height in [(1280, 760), (1480, 900), (1920, 1080)]:
        window.resize(width, height)
        window.show()
        qapp.processEvents()
        window._navigate(1)
        qapp.processEvents()
        assert window.stack.currentIndex() == 1

    window.close()


def test_process_page_import_replaces_dataset_and_unloads_scheduler(
    qapp, monkeypatch, tmp_path
):
    source = ProcessManager(ResourceManager())
    source.create_process(
        pid="P007",
        name="Imported",
        arrival_time=2,
        burst_time=4,
        priority=1,
        memory_mb=96,
        io_devices=0,
    )
    dataset = ExportService.save_dataset_json(tmp_path / "dataset.json", source.processes)

    manager = ProcessManager(ResourceManager())
    manager.create_process(
        name="Old",
        arrival_time=0,
        burst_time=1,
        priority=1,
        memory_mb=64,
        io_devices=0,
    )
    service = SimulationService(manager)
    service.load("fcfs")
    page = ProcessPage(manager, service)
    monkeypatch.setattr(
        "app.ui.process_page.QFileDialog.getOpenFileName",
        lambda *args: (str(dataset), "JSON Files (*.json)"),
    )
    monkeypatch.setattr(MessageDialog, "confirm_danger", lambda *args: True)
    monkeypatch.setattr(MessageDialog, "exec", lambda self: 1)

    page.import_dataset()

    assert [process.pid for process in manager.processes] == ["P007"]
    assert manager.processes[0].name == "Imported"
    assert service.scheduler is None
    assert page.table.rowCount() == 1


def test_editing_completed_process_confirms_and_resets_simulation(
    qapp, monkeypatch
):
    manager = ProcessManager(ResourceManager())
    process = manager.create_process(
        name="Completed",
        arrival_time=0,
        burst_time=2,
        priority=1,
        memory_mb=64,
        io_devices=0,
    )
    service = SimulationService(manager)
    service.load("fcfs")
    while service.step():
        pass
    page = ProcessPage(manager, service)
    page.table.selectRow(0)
    opened = []
    monkeypatch.setattr(MessageDialog, "confirm_danger", lambda *args: True)
    monkeypatch.setattr(
        CreateProcessDialog,
        "exec",
        lambda dialog: opened.append(dialog.process),
    )

    page.edit_selected()

    assert opened == [process]
    assert service.scheduler is None
    assert process.state is ProcessState.READY
    assert process.remaining_time == process.burst_time
    assert process.finish_time is None
    assert process.resources_allocated
