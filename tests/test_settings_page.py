import pytest
from PySide6.QtCore import QSettings

from app.models.simulation_state import SimulationStatus
from app.services.process_manager import ProcessManager
from app.services.resource_manager import ResourceManager
from app.services.settings_service import SettingsService
from app.services.simulation_service import SimulationService
from app.ui.help_about_page import HelpAboutPage
from app.ui.main_window import MainWindow
from app.ui.settings_page import SettingsPage


def make_services():
    manager = ProcessManager(ResourceManager())
    simulation = SimulationService(manager)
    settings = SettingsService(manager, simulation)
    return manager, simulation, settings


def test_settings_apply_updates_resources_speed_and_default_quantum(qapp):
    manager, simulation, settings = make_services()

    settings.apply(
        total_memory_mb=16384,
        total_io_devices=16,
        default_quantum=4,
        default_speed=2.0,
    )

    resource = manager.resource_manager.resource
    assert resource.total_memory_mb == 16384
    assert resource.total_io_devices == 16
    assert settings.default_quantum == 4
    assert settings.default_speed == 2.0
    assert simulation.speed == 2.0


def test_settings_are_locked_only_while_simulation_is_running(qapp):
    manager, simulation, settings = make_services()
    manager.create_process(
        name="Worker", arrival_time=0, burst_time=2, priority=1,
        memory_mb=64, io_devices=0,
    )
    simulation.load("fcfs")
    simulation.start()

    assert settings.is_locked
    with pytest.raises(ValueError, match="正在运行"):
        settings.reset_all_data()

    simulation.pause()
    assert simulation.state.status is SimulationStatus.PAUSED
    settings.reset_all_data()
    assert manager.processes == []
    assert simulation.scheduler is None


def test_restore_example_dataset_is_reproducible_and_resettable(qapp):
    manager, simulation, settings = make_services()

    settings.restore_example_dataset()
    first = [(p.pid, p.name, p.burst_time) for p in manager.processes]
    settings.restore_example_dataset()

    assert first == [(p.pid, p.name, p.burst_time) for p in manager.processes]
    assert len(first) == 4
    assert simulation.scheduler is None
    settings.reset_all_data()
    assert manager.processes == []
    assert manager.resource_manager.resource.used_memory_mb == 0


def test_settings_page_applies_controls_and_reflects_lock(qapp):
    manager, simulation, settings = make_services()
    page = SettingsPage(settings)
    page.memory_input.setValue(12288)
    page.io_input.setValue(12)
    page.quantum_input.setValue(3)
    page.speed_combo.setCurrentIndex(2)

    assert page.apply_settings()
    assert settings.default_quantum == 3
    assert simulation.speed == 2.0
    assert "已应用" in page.feedback_label.text()

    manager.create_process(
        name="Worker", arrival_time=0, burst_time=2, priority=1,
        memory_mb=64, io_devices=0,
    )
    simulation.load("fcfs")
    simulation.start()
    assert not page.apply_button.isEnabled()
    assert "锁定" in page.lock_label.text()
    simulation.pause()


def test_help_page_and_main_window_have_no_placeholder_navigation(qapp):
    page = HelpAboutPage()
    assert page.algorithm_table.rowCount() == 7

    window = MainWindow()
    assert isinstance(window.stack.widget(5), SettingsPage)
    assert isinstance(window.stack.widget(6), HelpAboutPage)
    assert window.stack.count() == 7
    window.close()


def test_settings_can_persist_between_service_instances(qapp, tmp_path):
    path = str(tmp_path / "settings.ini")
    manager, simulation, _ = make_services()
    settings = SettingsService(
        manager,
        simulation,
        store=QSettings(path, QSettings.Format.IniFormat),
    )
    settings.apply(
        total_memory_mb=16384,
        total_io_devices=16,
        default_quantum=5,
        default_speed=2.0,
    )

    new_manager = ProcessManager(ResourceManager())
    new_simulation = SimulationService(new_manager)
    restored = SettingsService(
        new_manager,
        new_simulation,
        store=QSettings(path, QSettings.Format.IniFormat),
    )

    assert new_manager.resource_manager.resource.total_memory_mb == 16384
    assert new_manager.resource_manager.resource.total_io_devices == 16
    assert restored.default_quantum == 5
    assert restored.default_speed == 2.0
