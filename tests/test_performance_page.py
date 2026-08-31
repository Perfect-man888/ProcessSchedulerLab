from PySide6.QtCore import Qt

from app.services.experiment_service import ExperimentService
from app.services.process_manager import ProcessManager
from app.services.resource_manager import ResourceManager
from app.ui.main_window import MainWindow
from app.ui.performance_page import PerformancePage


def add_process(manager, name, arrival, burst, priority, deadline=None):
    return manager.create_process(
        name=name,
        arrival_time=arrival,
        burst_time=burst,
        priority=priority,
        deadline=deadline,
        memory_mb=64,
        io_devices=0,
    )


def make_page():
    manager = ProcessManager(ResourceManager())
    return manager, PerformancePage(manager, ExperimentService())


def test_empty_current_dataset_and_preset_selection(qapp):
    manager, page = make_page()

    assert not page.run_button.isEnabled()
    assert "0 个 PCB" in page.dataset_description.text()

    page.dataset_combo.setCurrentIndex(1)

    assert page.run_button.isEnabled()
    assert "固定进程" in page.dataset_description.text()
    assert page.report is None


def test_preset_runs_all_algorithms_and_populates_analysis(qapp):
    manager, page = make_page()
    page.dataset_combo.setCurrentIndex(1)

    assert page.run_comparison()

    assert page.report is not None
    assert len(page.report.results) == 7
    assert page.table.rowCount() == 7
    assert page.algorithm_card.value_label.text() == "7"
    assert page.status_label.text() == "●  比较完成"
    assert page.skip_label.text() == "全部 7 种算法已完成"
    assert len(page.latency_chart.figure.axes[0].patches) == 21
    assert len(page.system_chart.figure.axes[0].patches) == 7
    assert page.observation_layout.count() >= 5


def test_current_dataset_skips_edf_and_preserves_processes(qapp):
    manager, page = make_page()
    first = add_process(manager, "A", 0, 4, 2)
    second = add_process(manager, "B", 1, 2, 1)
    before = [(p.pid, p.state, p.remaining_time) for p in manager.processes]

    assert page.run_comparison()

    assert len(page.report.results) == 6
    assert page.skip_label.text() == "跳过 EDF"
    assert page.table.rowCount() == 6
    assert before == [(p.pid, p.state, p.remaining_time) for p in manager.processes]
    assert first.start_time is None
    assert second.finish_time is None


def test_metric_table_uses_numeric_sorting(qapp):
    manager, page = make_page()
    page.dataset_combo.setCurrentIndex(2)
    page.run_comparison()

    page.table.sortItems(1, Qt.SortOrder.AscendingOrder)
    values = [
        page.table.item(row, 1).data(Qt.ItemDataRole.UserRole)
        for row in range(page.table.rowCount())
    ]
    assert values == sorted(values)


def test_main_window_uses_real_performance_page(qapp):
    window = MainWindow()

    page = window.stack.widget(3)
    assert isinstance(page, PerformancePage)
    assert page.process_manager is window.process_manager
    assert page.experiment_service is window.experiment_service

    window.close()


def test_performance_page_exports_csv_and_chart_pair(qapp, monkeypatch, tmp_path):
    manager, page = make_page()
    page.dataset_combo.setCurrentIndex(1)
    assert page.run_comparison()
    csv_path = tmp_path / "comparison.csv"
    chart_path = tmp_path / "latency.png"
    selections = iter(
        [
            (str(csv_path), "CSV Files (*.csv)"),
            (str(chart_path), "PNG Images (*.png)"),
        ]
    )
    monkeypatch.setattr(
        "app.ui.performance_page.QFileDialog.getSaveFileName",
        lambda *args: next(selections),
    )

    page.export_csv()
    page.export_charts()

    assert csv_path.exists()
    assert (tmp_path / "comparison_process_metrics.csv").exists()
    assert chart_path.exists()
    assert (tmp_path / "latency_system.png").exists()


def test_performance_page_exports_complete_pdf_report(qapp, monkeypatch, tmp_path):
    manager, page = make_page()
    page.dataset_combo.setCurrentIndex(1)
    assert page.run_comparison()
    target = tmp_path / "report.pdf"
    monkeypatch.setattr(
        "app.ui.performance_page.QFileDialog.getSaveFileName",
        lambda *args: (str(target), "PDF Files (*.pdf)"),
    )

    page.export_pdf()

    assert target.exists()
    assert target.stat().st_size > 50_000
    assert "PDF" in page.status_label.text()
