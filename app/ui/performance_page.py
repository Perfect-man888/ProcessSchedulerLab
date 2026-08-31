from threading import Event

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.experiment_result import ExperimentReport
from app.models.schedule_result import ScheduleResult
from app.services.experiment_service import (
    EXPERIMENT_PRESETS,
    ExperimentService,
)
from app.services.export_service import ExportService
from app.services.process_manager import ProcessManager
from app.services.settings_service import SettingsService
from app.styles.theme import COLORS
from app.widgets.dialogs import MessageDialog
from app.widgets.filter_combo import FilterCombo
from app.widgets.number_input import NumberInput
from app.widgets.performance_chart import PerformanceChart
from app.widgets.quantum_scan_chart import QuantumScanChart
from app.widgets.stat_card import StatCard


class AnalysisPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AnalysisPanel")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(22)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(15, 23, 42, 16))
        self.setGraphicsEffect(shadow)


class NumericItem(QTableWidgetItem):
    def __lt__(self, other):
        left = self.data(Qt.ItemDataRole.UserRole)
        right = other.data(Qt.ItemDataRole.UserRole)
        if left is not None and right is not None:
            return left < right
        return self.text().casefold() < other.text().casefold()


class ExperimentWorker(QObject):
    """在线程中运行批量实验，避免大数据集阻塞界面。

    当 scan_quanta 非空时执行 RR Quantum 灵敏度扫描，否则执行全算法比较。
    """

    progress = Signal(int, str)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, processes, options: dict, scan_quanta=(), parent=None):
        super().__init__(parent)
        self.processes = tuple(processes)
        self.options = dict(options)
        self.scan_quanta = tuple(scan_quanta)
        self._cancelled = Event()

    def cancel(self) -> None:
        self._cancelled.set()

    @Slot()
    def run(self) -> None:
        service = ExperimentService()
        service.progress.connect(self.progress.emit)
        try:
            if self.scan_quanta:
                payload = service.run_quantum_scan(
                    self.processes,
                    quantum_range=self.scan_quanta,
                    should_cancel=self._cancelled.is_set,
                )
            else:
                payload = service.run_all(
                    self.processes,
                    should_cancel=self._cancelled.is_set,
                    **self.options,
                )
        except Exception as error:  # noqa: BLE001 - 线程边界必须兜底，避免线程永不收尾。
            self.failed.emit(str(error))
            return
        self.succeeded.emit(payload)


class PerformancePage(QWidget):
    """固定预设与当前 PCB 数据上的全算法量化比较页面。"""

    def __init__(
        self,
        process_manager: ProcessManager,
        experiment_service: ExperimentService,
        settings_service: SettingsService | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.process_manager = process_manager
        self.experiment_service = experiment_service
        self.settings_service = settings_service
        self.report: ExperimentReport | None = None
        self._thread: QThread | None = None
        self._worker: ExperimentWorker | None = None
        self._closed = False

        self._build_ui()
        if self.settings_service is not None:
            self.settings_service.changed.connect(self._sync_setting_defaults)
            self._sync_setting_defaults()
        self.process_manager.changed.connect(self._refresh_dataset_summary)
        self.dataset_combo.currentIndexChanged.connect(self._on_dataset_changed)
        self.experiment_service.progress.connect(self._on_progress)
        self._refresh_dataset_summary()

    def _sync_setting_defaults(self) -> None:
        if self.settings_service is not None:
            self.quantum_input.setValue(self.settings_service.default_quantum)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("PerformancePageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        container.setObjectName("PageContainer")
        root = QVBoxLayout(container)
        root.setContentsMargins(34, 28, 34, 34)
        root.setSpacing(20)
        root.addLayout(self._build_header())
        root.addWidget(self._build_control_panel())
        root.addLayout(self._build_cards())
        root.addWidget(self._build_table_panel())

        charts = QHBoxLayout()
        charts.setSpacing(16)
        charts.addWidget(self._build_chart_panel("时延指标", "等待、周转与响应时间", "latency"), 1)
        charts.addWidget(self._build_chart_panel("系统开销", "切换次数与 CPU 利用率", "system"), 1)
        root.addLayout(charts)
        root.addWidget(self._build_quantum_scan_panel())
        root.addWidget(self._build_observation_panel())
        root.addStretch()

        scroll.setWidget(container)
        outer.addWidget(scroll)

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        text = QVBoxLayout()
        text.setSpacing(5)
        title = QLabel("性能分析")
        title.setObjectName("PageTitle")
        subtitle = QLabel("对同一进程集运行全部算法，以量化数据解释调度策略差异。")
        subtitle.setObjectName("PageSubtitle")
        text.addWidget(title)
        text.addWidget(subtitle)
        header.addLayout(text)
        header.addStretch()
        self.status_label = QLabel("●  等待实验")
        self.status_label.setObjectName("AnalysisStatusPill")
        self.status_label.setProperty("state", "idle")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFixedHeight(36)
        self.status_label.setMinimumWidth(145)
        header.addWidget(self.status_label)
        return header

    def _build_control_panel(self) -> AnalysisPanel:
        panel = AnalysisPanel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 21, 24, 22)
        layout.setSpacing(14)
        title = QLabel("实验数据集")
        title.setObjectName("PanelTitle")
        self.dataset_description = QLabel()
        self.dataset_description.setObjectName("PanelSubtitle")
        layout.addWidget(title)
        layout.addWidget(self.dataset_description)

        row = QHBoxLayout()
        row.setSpacing(12)
        self.dataset_combo = FilterCombo()
        self.dataset_combo.setObjectName("AnalysisCombo")
        self.dataset_combo.addItems(
            ["当前进程集"] + [preset.name for preset in EXPERIMENT_PRESETS]
        )
        row.addWidget(self._field("数据来源", self.dataset_combo), 3)
        self.quantum_input = NumberInput(1, 20, 2, "Tick")
        row.addWidget(self._field("RR 时间片", self.quantum_input), 1)
        self.aging_combo = FilterCombo()
        self.aging_combo.setObjectName("AnalysisCombo")
        self.aging_combo.addItems(["关闭", "2 Tick", "4 Tick", "6 Tick"])
        row.addWidget(self._field("Priority Aging", self.aging_combo), 1)
        self.run_button = QPushButton("▶  运行全部算法")
        self.run_button.setObjectName("SuccessButton")
        self.run_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.run_button.setMinimumHeight(42)
        self.run_button.clicked.connect(self.start_comparison)
        row.addWidget(self.run_button, 1, Qt.AlignmentFlag.AlignBottom)
        self.cancel_button = QPushButton("取消实验")
        self.cancel_button.setObjectName("SecondaryButton")
        self.cancel_button.setMinimumHeight(42)
        self.cancel_button.clicked.connect(self.cancel_comparison)
        self.cancel_button.setVisible(False)
        row.addWidget(self.cancel_button, 0, Qt.AlignmentFlag.AlignBottom)
        self.scan_button = QPushButton("⚡  RR 量子扫描")
        self.scan_button.setObjectName("SecondaryButton")
        self.scan_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_button.setMinimumHeight(42)
        self.scan_button.clicked.connect(self.start_quantum_scan)
        row.addWidget(self.scan_button, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(row)
        return panel

    @staticmethod
    def _field(title: str, control: QWidget) -> QWidget:
        field = QWidget()
        layout = QVBoxLayout(field)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        label = QLabel(title)
        label.setObjectName("SchedulerFieldLabel")
        layout.addWidget(label)
        layout.addWidget(control)
        return field

    def _build_cards(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(14)
        self.algorithm_card = StatCard("ALGORITHMS", "—", "等待批量实验", "ALG", COLORS["primary"])
        self.wait_card = StatCard("BEST WAITING", "—", "平均等待时间最低", "WT", COLORS["success"])
        self.response_card = StatCard("BEST RESPONSE", "—", "平均响应时间最低", "RT", COLORS["cyan"])
        self.utilization_card = StatCard("BEST CPU USE", "—", "CPU 利用率最高", "CPU", COLORS["purple"])
        for card in (self.algorithm_card, self.wait_card, self.response_card, self.utilization_card):
            layout.addWidget(card)
        return layout

    def _build_table_panel(self) -> AnalysisPanel:
        panel = AnalysisPanel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 20, 22, 22)
        layout.setSpacing(11)
        top = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("算法指标总表")
        title.setObjectName("PanelTitle")
        subtitle = QLabel("点击表头可按指标排序；时间类指标越低越好。")
        subtitle.setObjectName("PanelSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        top.addLayout(title_box)
        top.addStretch()
        self.export_csv_button = QPushButton("导出 CSV")
        self.export_csv_button.setObjectName("SecondaryButton")
        self.export_csv_button.clicked.connect(self.export_csv)
        self.export_csv_button.setEnabled(False)
        self.export_charts_button = QPushButton("导出图表")
        self.export_charts_button.setObjectName("SecondaryButton")
        self.export_charts_button.clicked.connect(self.export_charts)
        self.export_charts_button.setEnabled(False)
        self.export_pdf_button = QPushButton("导出 PDF 报告")
        self.export_pdf_button.setObjectName("PrimaryButton")
        self.export_pdf_button.clicked.connect(self.export_pdf)
        self.export_pdf_button.setEnabled(False)
        top.addWidget(self.export_csv_button)
        top.addWidget(self.export_charts_button)
        top.addWidget(self.export_pdf_button)
        self.skip_label = QLabel("尚未运行")
        self.skip_label.setObjectName("AnalysisSkipLabel")
        top.addWidget(self.skip_label)
        layout.addLayout(top)

        self.table = QTableWidget(0, 9)
        self.table.setObjectName("SimulationTable")
        self.table.setHorizontalHeaderLabels(
            ["算法", "等待", "周转", "带权周转", "响应", "CPU", "吞吐量", "切换", "Miss"]
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSortingEnabled(True)
        self.table.setMinimumHeight(300)
        layout.addWidget(self.table)
        return panel

    def _build_chart_panel(self, title_text: str, subtitle_text: str, mode: str) -> AnalysisPanel:
        panel = AnalysisPanel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 19, 20, 18)
        layout.setSpacing(8)
        title = QLabel(title_text)
        title.setObjectName("PanelTitle")
        subtitle = QLabel(subtitle_text)
        subtitle.setObjectName("PanelSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        chart = PerformanceChart(mode)
        if mode == "latency":
            self.latency_chart = chart
        else:
            self.system_chart = chart
        layout.addWidget(chart)
        return panel

    def _build_quantum_scan_panel(self) -> AnalysisPanel:
        panel = AnalysisPanel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 19, 20, 18)
        layout.setSpacing(8)
        title = QLabel("RR 时间片灵敏度扫描")
        title.setObjectName("PanelTitle")
        subtitle = QLabel(
            "固定数据集上扫描 Quantum 1–8，观察时间片大小对时延与切换开销的权衡。"
        )
        subtitle.setObjectName("PanelSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        self.quantum_chart = QuantumScanChart()
        layout.addWidget(self.quantum_chart)
        self.quantum_observation = QLabel("尚未运行 RR 时间片扫描。")
        self.quantum_observation.setObjectName("ObservationItem")
        self.quantum_observation.setWordWrap(True)
        layout.addWidget(self.quantum_observation)
        return panel

    def _build_observation_panel(self) -> AnalysisPanel:
        panel = AnalysisPanel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 20, 22, 22)
        layout.setSpacing(10)
        title = QLabel("自动实验观察")
        title.setObjectName("PanelTitle")
        subtitle = QLabel("结论根据当前结果动态生成，不预设某一种算法必然最好。")
        subtitle.setObjectName("PanelSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        self.observation_layout = QVBoxLayout()
        self.observation_layout.setSpacing(7)
        layout.addLayout(self.observation_layout)
        self._fill_observations(("运行比较后将在这里生成数据驱动的实验观察。",))
        return panel

    def _on_dataset_changed(self, index: int) -> None:
        self.report = None
        self._clear_analysis()
        self._refresh_dataset_summary()

    def _clear_analysis(self) -> None:
        """数据集切换后清空旧结果，避免表格/图表展示过期数据。"""

        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        self.table.setSortingEnabled(True)
        self.latency_chart.update_results(())
        self.system_chart.update_results(())
        self.quantum_chart.set_data(())
        self.quantum_observation.setText("尚未运行 RR 时间片扫描。")
        self._fill_observations(("运行比较后将在这里生成数据驱动的实验观察。",))
        self.skip_label.setText("尚未运行")
        self.algorithm_card.set_value("—")
        self.algorithm_card.set_subtitle("等待批量实验")
        self.wait_card.set_value("—")
        self.wait_card.set_subtitle("平均等待时间最低")
        self.response_card.set_value("—")
        self.response_card.set_subtitle("平均响应时间最低")
        self.utilization_card.set_value("—")
        self.utilization_card.set_subtitle("CPU 利用率最高")
        for button in (
            self.export_csv_button,
            self.export_charts_button,
            self.export_pdf_button,
        ):
            button.setEnabled(False)

    def _refresh_dataset_summary(self) -> None:
        index = self.dataset_combo.currentIndex()
        if index == 0:
            count = len(self.process_manager.processes)
            self.dataset_description.setText(
                f"使用进程管理页中的 {count} 个 PCB；比较过程基于独立副本，不修改当前仿真。"
            )
            self.run_button.setEnabled(count > 0)
            self.scan_button.setEnabled(count > 0)
        else:
            preset = EXPERIMENT_PRESETS[index - 1]
            self.dataset_description.setText(
                f"{preset.description} · {len(preset.processes)} 个固定进程"
            )
            self.run_button.setEnabled(True)
            self.scan_button.setEnabled(True)

    def _selected_dataset(self):
        index = self.dataset_combo.currentIndex()
        if index == 0:
            return "当前进程集", tuple(self.process_manager.processes)
        preset = EXPERIMENT_PRESETS[index - 1]
        return preset.name, preset.instantiate()

    def run_comparison(self) -> bool:
        name, processes = self._selected_dataset()
        self.run_button.setEnabled(False)
        self._set_status("●  正在计算", "running")
        try:
            report = self.experiment_service.run_all(
                processes,
                dataset_name=name,
                rr_quantum=self.quantum_input.value(),
                priority_aging_interval=self._aging_interval(),
            )
        except (ValueError, RuntimeError) as error:
            MessageDialog.show_error(self, "实验运行失败", str(error))
            self._set_status("●  运行失败", "error")
            self._refresh_dataset_summary()
            return False

        self.report = report
        self._render_report(report)
        self._set_status("●  比较完成", "finished")
        self._refresh_dataset_summary()
        return True

    def start_comparison(self) -> None:
        name, processes = self._selected_dataset()
        if not processes or self._thread is not None:
            return
        options = {
            "dataset_name": name,
            "rr_quantum": self.quantum_input.value(),
            "priority_aging_interval": self._aging_interval(),
        }
        self._launch_worker(processes, options)

    def start_quantum_scan(self) -> None:
        _, processes = self._selected_dataset()
        if not processes or self._thread is not None:
            return
        self._launch_worker(processes, {}, scan_quanta=range(1, 9))

    def _launch_worker(self, processes, options: dict, scan_quanta=()) -> None:
        self.report = None
        self._set_experiment_controls(True)
        self._set_status("●  正在计算", "running")

        thread = QThread(self)
        worker = ExperimentWorker(processes, options, scan_quanta=scan_quanta)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.succeeded.connect(self._on_async_success)
        worker.failed.connect(self._on_async_failure)
        worker.succeeded.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._clear_worker)
        self._thread = thread
        self._worker = worker
        thread.start()

    def cancel_comparison(self) -> None:
        if self._worker is None:
            return
        self._worker.cancel()
        self.cancel_button.setEnabled(False)
        self._set_status("●  正在取消", "running")

    @Slot(object)
    def _on_async_success(self, payload) -> None:
        if self._closed:
            return
        if isinstance(payload, ExperimentReport):
            self.report = payload
            self._render_report(payload)
        else:
            self._render_quantum_scan(payload)
        self._set_status("●  比较完成" if isinstance(payload, ExperimentReport) else "●  扫描完成", "finished")
        self._set_experiment_controls(False)
        self._refresh_dataset_summary()

    @Slot(str)
    def _on_async_failure(self, message: str) -> None:
        if self._closed:
            return
        cancelled = message == "实验已取消。"
        if not cancelled:
            MessageDialog.show_error(self, "实验运行失败", message)
        self._set_status("●  已取消" if cancelled else "●  运行失败", "idle" if cancelled else "error")
        self._set_experiment_controls(False)
        self._refresh_dataset_summary()

    @Slot()
    def _clear_worker(self) -> None:
        thread = self._thread
        self._worker = None
        self._thread = None
        if thread is not None:
            thread.deleteLater()

    def _set_experiment_controls(self, running: bool) -> None:
        self.dataset_combo.setEnabled(not running)
        self.quantum_input.setEnabled(not running)
        self.aging_combo.setEnabled(not running)
        self.run_button.setEnabled(not running)
        self.scan_button.setEnabled(not running)
        self.cancel_button.setVisible(running)
        self.cancel_button.setEnabled(running)
        for button in (
            self.export_csv_button,
            self.export_charts_button,
            self.export_pdf_button,
        ):
            button.setEnabled(not running and self.report is not None)

    def _aging_interval(self) -> int | None:
        return (None, 2, 4, 6)[self.aging_combo.currentIndex()]

    def shutdown_worker(self) -> None:
        self._closed = True
        if self._worker is not None:
            self._worker.cancel()
        if self._thread is not None:
            thread = self._thread
            thread.quit()
            if not thread.wait(5000):
                # 计算线程未在期限内退出，强制终止以免窗口销毁后回调悬空。
                thread.terminate()
                thread.wait(1000)
            self._worker = None
            self._thread = None

    def closeEvent(self, event) -> None:
        self.shutdown_worker()
        super().closeEvent(event)

    def _on_progress(self, percent: int, algorithm: str) -> None:
        if percent < 100:
            self.status_label.setText(f"●  {algorithm} · {percent}%")

    def _render_report(self, report: ExperimentReport) -> None:
        count = len(report.results)
        self.algorithm_card.set_value(str(count))
        self.algorithm_card.set_subtitle(f"{report.dataset_name} · 完成比较")
        self._set_best_card(self.wait_card, report.best("average_waiting_time"), "average_waiting_time", "Tick")
        self._set_best_card(self.response_card, report.best("average_response_time"), "average_response_time", "Tick")
        self._set_best_card(self.utilization_card, report.best("cpu_utilization", maximize=True), "cpu_utilization", "%")

        self.table.setSortingEnabled(False)
        self.table.setRowCount(count)
        for row, result in enumerate(report.results):
            values = (
                (result.algorithm_name, None),
                (f"{result.average_waiting_time:.2f}", result.average_waiting_time),
                (f"{result.average_turnaround_time:.2f}", result.average_turnaround_time),
                (f"{result.average_weighted_turnaround_time:.2f}", result.average_weighted_turnaround_time),
                (f"{result.average_response_time:.2f}", result.average_response_time),
                (f"{result.cpu_utilization * 100:.1f}%", result.cpu_utilization),
                (f"{result.throughput:.3f}", result.throughput),
                (str(result.context_switches), result.context_switches),
                (str(result.deadline_miss_count) if result.algorithm_name == "EDF" else "—", result.deadline_miss_count),
            )
            for column, (text, numeric) in enumerate(values):
                item = NumericItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if numeric is not None:
                    item.setData(Qt.ItemDataRole.UserRole, numeric)
                if column == 0:
                    item.setForeground(QColor(COLORS["primary"]))
                self.table.setItem(row, column, item)
        self.table.setSortingEnabled(True)

        self.skip_label.setText(
            f"全部 {len(self.experiment_service.DEFAULT_ALGORITHMS)} 种算法已完成"
            if not report.skipped
            else " · ".join(f"跳过 {item.display_name}" for item in report.skipped)
        )
        self.latency_chart.update_results(report.results)
        self.system_chart.update_results(report.results)
        self._fill_observations(report.observations)
        self.export_csv_button.setEnabled(True)
        self.export_charts_button.setEnabled(True)
        self.export_pdf_button.setEnabled(True)

    def _render_quantum_scan(self, data: tuple[tuple[int, ScheduleResult], ...]) -> None:
        if not data:
            return
        self.quantum_chart.set_data(data)
        best_turnaround = min(
            data, key=lambda item: item[1].average_turnaround_time
        )
        best_response = min(
            data, key=lambda item: item[1].average_response_time
        )
        best_switches = min(
            data, key=lambda item: item[1].context_switches
        )
        self.quantum_observation.setText(
            f"Quantum={best_turnaround[0]} 时平均周转时间最低"
            f"（{best_turnaround[1].average_turnaround_time:.2f} Tick）；"
            f"Quantum={best_response[0]} 时平均响应时间最低"
            f"（{best_response[1].average_response_time:.2f} Tick）；"
            f"Quantum={best_switches[0]} 时上下文切换最少"
            f"（{best_switches[1].context_switches} 次）。"
        )

    @staticmethod
    def _set_best_card(card, results, metric: str, suffix: str) -> None:
        names = (
            f"全部 {len(results)} 种算法并列"
            if len(results) > 3
            else " / ".join(result.algorithm_name for result in results)
        )
        value = getattr(results[0], metric)
        display = f"{value * 100:.1f}{suffix}" if metric == "cpu_utilization" else f"{value:.2f} {suffix}"
        card.set_value(display)
        card.set_subtitle(names)

    def _fill_observations(self, observations: tuple[str, ...]) -> None:
        while self.observation_layout.count():
            item = self.observation_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()
                item.widget().deleteLater()
        for index, observation in enumerate(observations, start=1):
            label = QLabel(f"{index:02d}   {observation}")
            label.setObjectName("ObservationItem")
            label.setWordWrap(True)
            self.observation_layout.addWidget(label)

    def _set_status(self, text: str, state: str) -> None:
        self.status_label.setText(text)
        if self.status_label.property("state") != state:
            self.status_label.setProperty("state", state)
            self.status_label.style().unpolish(self.status_label)
            self.status_label.style().polish(self.status_label)

    def export_csv(self) -> None:
        if self.report is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出算法指标",
            "algorithm_comparison.csv",
            "CSV Files (*.csv)",
        )
        if not path:
            return
        try:
            ExportService.export_report_csv(self.report, path)
        except (OSError, ValueError) as error:
            MessageDialog.show_error(self, "导出失败", str(error))
            return
        self._set_status("●  CSV 已导出", "finished")

    def export_charts(self) -> None:
        if self.report is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出性能图表",
            "performance_latency.png",
            "PNG Images (*.png)",
        )
        if not path:
            return
        try:
            target = ExportService.save_figure_png(self.latency_chart.figure, path)
            system_path = target.with_name(f"{target.stem}_system.png")
            ExportService.save_figure_png(self.system_chart.figure, system_path)
        except (OSError, ValueError) as error:
            MessageDialog.show_error(self, "导出失败", str(error))
            return
        self._set_status("●  图表已导出", "finished")

    def export_pdf(self) -> None:
        if self.report is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出完整实验报告",
            "scheduling_experiment_report.pdf",
            "PDF Files (*.pdf)",
        )
        if not path:
            return
        try:
            ExportService.export_report_pdf(
                self.report,
                path,
                figures=(self.latency_chart.figure, self.system_chart.figure),
            )
        except (OSError, ValueError) as error:
            MessageDialog.show_error(self, "导出失败", str(error))
            return
        self._set_status("●  PDF 报告已导出", "finished")
