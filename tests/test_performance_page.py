from PySide6.QtCore import QEventLoop, Qt, QTimer

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
    assert "实验目的" in page.profile_purpose.text()
    assert "报告建议" in page.profile_report.text()


def test_preset_runs_all_algorithms_and_populates_analysis(qapp):
    manager, page = make_page()
    page.dataset_combo.setCurrentIndex(1)

    assert page.run_comparison()

    assert page.report is not None
    assert len(page.report.results) == 7
    assert page.table.rowCount() == 7
    assert page.algorithm_card.value_label.text() == "7"
    assert page.status_label.text() == "●  比较完成"
    assert page.skip_label.text() == "跳过 RMS"
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
    assert page.skip_label.text() == "跳过 EDF · 跳过 RMS"
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


def test_realtime_scope_runs_only_edf_and_rms(qapp):
    manager, page = make_page()
    page.dataset_combo.setCurrentIndex(3)
    page.analysis_scope_combo.setCurrentIndex(3)

    assert page.run_comparison()

    assert [result.algorithm_name for result in page.report.results] == ["EDF", "RMS"]
    assert page.table.rowCount() == 2
    assert page.table.columnCount() == 12
    assert page.table.item(0, 10).text().endswith("%")
    assert page.table.item(0, 11).text().endswith("%")
    assert "实时重点" in page.scope_hint.text()


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


def test_performance_page_supports_aging_and_background_run(qapp):
    manager, page = make_page()
    page.dataset_combo.setCurrentIndex(1)
    page.aging_combo.setCurrentIndex(1)
    page.start_comparison()
    assert page._thread is not None
    assert not page.cancel_button.isHidden()

    loop = QEventLoop()
    thread = page._thread
    thread.finished.connect(loop.quit)
    QTimer.singleShot(5000, loop.quit)
    loop.exec()
    qapp.processEvents()

    assert page.report is not None
    assert any("+ Aging" in result.algorithm_name for result in page.report.results)
    assert page.status_label.text() == "●  比较完成"
    assert page._thread is None


def test_performance_page_runs_quantum_scan_in_background(qapp):
    manager, page = make_page()
    page.dataset_combo.setCurrentIndex(1)
    page.start_quantum_scan()
    assert page._thread is not None
    assert not page.cancel_button.isHidden()

    loop = QEventLoop()
    thread = page._thread
    thread.finished.connect(loop.quit)
    QTimer.singleShot(8000, loop.quit)
    loop.exec()
    qapp.processEvents()

    assert page._thread is None
    assert page.status_label.text() == "●  扫描完成"
    assert "Quantum=" in page.quantum_observation.text()
    assert "Quantum =" in page.quantum_recommendation_value.text()
    assert "Response 40%" in page.quantum_recommendation_weights.text()
    assert page.copy_conclusion_button.isEnabled()
    # 扫描图应绘制出曲线（主坐标轴两条折线）
    assert len(page.quantum_chart.figure.axes[0].lines) == 2


def test_copy_conclusions_produces_report_ready_plain_text(qapp):
    manager, page = make_page()
    page.dataset_combo.setCurrentIndex(2)
    _, processes = page._selected_dataset()
    data = ExperimentService().run_quantum_scan(processes, quantum_range=(1, 2, 3))
    page._render_quantum_scan(data)

    page.copy_conclusions()

    copied = qapp.clipboard().text()
    assert "数据集：分时交互负载" in copied
    assert "推荐折中 Quantum" in copied
    assert "Response 40%" in copied
    assert "当前数据集、当前参数和当前评价权重" in copied


def test_metric_table_headers_have_centralized_chinese_tooltips(qapp):
    manager, page = make_page()

    assert "进程 PID" in page.table.horizontalHeaderItem(7).toolTip()
    assert "Miss 数" in page.table.horizontalHeaderItem(10).toolTip()


def test_switching_dataset_clears_previous_analysis(qapp):
    manager, page = make_page()
    page.dataset_combo.setCurrentIndex(1)
    assert page.run_comparison()
    assert page.table.rowCount() > 0
    assert page.export_csv_button.isEnabled()

    page.dataset_combo.setCurrentIndex(0)

    assert page.report is None
    assert page.table.rowCount() == 0
    assert page.skip_label.text() == "尚未运行"
    assert page.quantum_observation.text() == "尚未运行 RR 时间片扫描。"
    assert page.algorithm_card.value_label.text() == "—"
    assert not page.export_csv_button.isEnabled()
    assert not page.export_charts_button.isEnabled()
    assert not page.export_pdf_button.isEnabled()


def test_async_callbacks_are_ignored_after_window_closed(qapp):
    manager, page = make_page()
    page._closed = True

    # 窗口关闭后线程兜底信号回传，不得再触碰已销毁的 UI 状态。
    page._on_async_success(object())
    page._on_async_failure("boom")

    assert page.report is None
    assert page.status_label.text() == "●  等待实验"
    assert page.table.rowCount() == 0


def test_shutdown_worker_reaps_thread_and_clears_references(qapp):
    manager = ProcessManager(ResourceManager())
    manager.create_process(
        name="Worker", arrival_time=0, burst_time=1, priority=1,
        memory_mb=64, io_devices=0,
    )
    page = PerformancePage(manager, ExperimentService())
    page.start_comparison()
    assert page._thread is not None

    page.shutdown_worker()

    assert page._closed
    assert page._worker is None
    assert page._thread is None


def test_main_window_close_stops_simulation_timer(qapp):
    window = MainWindow()
    window.process_manager.create_process(
        name="Worker", arrival_time=0, burst_time=5, priority=1,
        memory_mb=64, io_devices=0,
    )
    window.simulation_service.load("fcfs")
    window.simulation_service.start()
    assert window.simulation_service.timer.isActive()

    window.close()

    assert not window.simulation_service.timer.isActive()
