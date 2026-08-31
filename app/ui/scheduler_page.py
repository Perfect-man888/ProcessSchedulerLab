from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.process import Process, ProcessState
from app.models.simulation_event import SimulationEventType
from app.models.simulation_state import SimulationStatus
from app.services.export_service import ExportService
from app.services.process_manager import ProcessManager
from app.services.settings_service import SettingsService
from app.services.simulation_service import SimulationService
from app.styles.theme import COLORS
from app.widgets.dialogs import MessageDialog
from app.widgets.filter_combo import FilterCombo
from app.widgets.flow_layout import FlowLayout
from app.widgets.gantt_chart import GanttChart
from app.widgets.number_input import NumberInput
from app.widgets.stat_card import StatCard

SWITCH_COSTS = (("0 Tick", 0), ("1 Tick", 1), ("2 Tick", 2), ("3 Tick", 3))


class SchedulerPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SchedulerPanel")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(22)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(15, 23, 42, 16))
        self.setGraphicsEffect(shadow)


class SchedulerPage(QWidget):
    """调度算法选择、运行控制和逐 Tick 可视化实验主界面。"""

    ALGORITHMS = (
        ("FCFS · 先来先服务", "fcfs"),
        ("SJF · 短作业优先", "sjf"),
        ("SRTF · 最短剩余时间", "srtf"),
        ("Priority · 优先级", "priority"),
        ("Round Robin · 时间片轮转", "round_robin"),
        ("EDF · 最早截止时间", "edf"),
        ("RMS · 单调速率调度", "rms"),
        ("MLFQ · 多级反馈队列", "mlfq"),
    )
    SPEEDS = (("0.5×", 0.5), ("1×", 1.0), ("2×", 2.0), ("5×", 5.0))

    DESCRIPTIONS = {
        "fcfs": "按到达顺序运行，规则直观且不会发生策略抢占。",
        "sjf": "CPU 空闲时优先选择服务时间最短的就绪进程。",
        "srtf": "新进程到达时，可抢占剩余时间更长的当前进程。",
        "priority": "数字越小优先级越高，可选择抢占式或非抢占式。",
        "round_robin": "按固定时间片循环分配 CPU，适合分时交互场景。",
        "edf": "优先执行绝对截止时间最早的任务，要求全部进程填写 Deadline。",
        "rms": "周期越短优先级越高，静态优先级实时调度，要求全部进程填写 Period。",
        "mlfq": "新任务从高优先级队列开始，时间片耗尽后逐级下沉。",
    }

    def __init__(
        self,
        process_manager: ProcessManager,
        simulation_service: SimulationService,
        settings_service: SettingsService | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.process_manager = process_manager
        self.simulation_service = simulation_service
        self.settings_service = settings_service

        self._build_ui()
        if self.settings_service is not None:
            self.settings_service.changed.connect(self._sync_setting_defaults)
            self._sync_setting_defaults()
        self.process_manager.changed.connect(self.refresh)
        self.simulation_service.changed.connect(self.refresh)
        self.algorithm_combo.currentIndexChanged.connect(
            self._on_algorithm_changed
        )
        self.speed_combo.currentIndexChanged.connect(self._on_speed_changed)
        self._on_algorithm_changed(0)
        self.refresh()

    def _sync_setting_defaults(self) -> None:
        if self.settings_service is None:
            return
        self.quantum_input.setValue(self.settings_service.default_quantum)
        speed_index = self.settings_service.SPEEDS.index(
            self.settings_service.default_speed
        )
        self.speed_combo.setCurrentIndex(speed_index)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setObjectName("SchedulerPageScroll")
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
        root.addLayout(self._build_stat_cards())
        root.addWidget(self._build_timeline_panel())

        lower = QHBoxLayout()
        lower.setSpacing(16)
        lower.addWidget(self._build_queue_panel(), 4)
        lower.addWidget(self._build_event_panel(), 6)
        root.addLayout(lower)
        root.addWidget(self._build_process_panel())
        root.addStretch()

        scroll.setWidget(container)
        outer.addWidget(scroll)

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(5)
        title = QLabel("调度仿真")
        title.setObjectName("PageTitle")
        subtitle = QLabel("选择算法并逐 Tick 观察 CPU 派发、抢占、队列变化与性能指标。")
        subtitle.setObjectName("PageSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()

        self.run_status_label = QLabel("●  尚未加载")
        self.run_status_label.setObjectName("SimulationStatusPill")
        self.run_status_label.setProperty("state", "empty")
        self.run_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.run_status_label.setMinimumWidth(150)
        self.run_status_label.setFixedHeight(36)
        header.addWidget(self.run_status_label)
        return header

    def _build_control_panel(self) -> SchedulerPanel:
        panel = SchedulerPanel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 21, 24, 22)
        layout.setSpacing(14)

        heading = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("实验控制台")
        title.setObjectName("PanelTitle")
        self.algorithm_description = QLabel()
        self.algorithm_description.setObjectName("PanelSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(self.algorithm_description)
        heading.addLayout(title_box)
        heading.addStretch()
        self.process_hint = QLabel()
        self.process_hint.setObjectName("SchedulerProcessHint")
        heading.addWidget(self.process_hint)
        layout.addLayout(heading)

        config = QGridLayout()
        config.setSpacing(12)
        self.algorithm_combo = FilterCombo()
        self.algorithm_combo.setObjectName("SchedulerCombo")
        self.algorithm_combo.addItems([name for name, _ in self.ALGORITHMS])
        config.addWidget(self._field("调度算法", self.algorithm_combo), 0, 0)

        self.parameter_stack = QStackedWidget()
        self.parameter_stack.setObjectName("ParameterStack")
        self.parameter_stack.setFixedHeight(66)
        self._build_parameter_pages()
        config.addWidget(self.parameter_stack, 0, 1)

        self.speed_combo = FilterCombo()
        self.speed_combo.setObjectName("SchedulerCombo")
        self.speed_combo.addItems([name for name, _ in self.SPEEDS])
        self.speed_combo.setCurrentIndex(1)
        config.addWidget(self._field("仿真速度", self.speed_combo), 1, 0)

        self.switch_cost_combo = FilterCombo()
        self.switch_cost_combo.setObjectName("SchedulerCombo")
        self.switch_cost_combo.addItems([name for name, _ in SWITCH_COSTS])
        self.switch_cost_combo.currentIndexChanged.connect(self._on_switch_cost_changed)
        config.addWidget(self._field("上下文切换开销", self.switch_cost_combo), 1, 1)
        config.setColumnStretch(0, 2)
        config.setColumnStretch(1, 3)
        layout.addLayout(config)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.load_button = self._button("加载 / 应用算法", "SecondaryButton")
        self.start_button = self._button("▶  开始运行", "SuccessButton")
        self.pause_button = self._button("Ⅱ  暂停", "SecondaryButton")
        self.step_button = self._button("▸|  单步", "SecondaryButton")
        self.reset_button = self._button("↺  重置实验", "SecondaryButton")
        self.load_button.clicked.connect(self.load_experiment)
        self.start_button.clicked.connect(self.start_simulation)
        self.pause_button.clicked.connect(self.pause_simulation)
        self.step_button.clicked.connect(self.step_simulation)
        self.reset_button.clicked.connect(self.reset_simulation)
        for button in (
            self.load_button,
            self.start_button,
            self.pause_button,
            self.step_button,
            self.reset_button,
        ):
            actions.addWidget(button)
        self.loaded_algorithm_label = QLabel("当前算法：—")
        self.loaded_algorithm_label.setObjectName("LoadedAlgorithmLabel")
        layout.addLayout(actions)
        layout.addWidget(
            self.loaded_algorithm_label,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )
        return panel

    def _build_parameter_pages(self) -> None:
        neutral = QLabel("此算法无需额外参数")
        neutral.setObjectName("ParameterHint")
        neutral.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.parameter_stack.addWidget(neutral)

        priority = QWidget()
        priority_row = QHBoxLayout(priority)
        priority_row.setContentsMargins(0, 0, 0, 0)
        priority_row.setSpacing(8)
        self.priority_mode_combo = FilterCombo()
        self.priority_mode_combo.setObjectName("SchedulerCombo")
        self.priority_mode_combo.addItems(["抢占式", "非抢占式"])
        self.priority_aging_combo = FilterCombo()
        self.priority_aging_combo.setObjectName("SchedulerCombo")
        self.priority_aging_combo.addItems(
            ["关闭 Aging", "Aging 2 Tick", "Aging 4 Tick", "Aging 6 Tick"]
        )
        priority_row.addWidget(self.priority_mode_combo)
        priority_row.addWidget(self.priority_aging_combo)
        self.parameter_stack.addWidget(self._field("优先级模式 / 饥饿防止", priority))

        self.quantum_input = NumberInput(1, 20, 2, "Tick")
        self.parameter_stack.addWidget(self._field("时间片 Quantum", self.quantum_input))

        mlfq = QWidget()
        row = QHBoxLayout(mlfq)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.mlfq_inputs = (
            NumberInput(1, 20, 1, "Q1"),
            NumberInput(1, 20, 2, "Q2"),
            NumberInput(1, 20, 4, "Q3"),
        )
        self.boost_input = NumberInput(1, 100, 10, "Boost")
        for control in (*self.mlfq_inputs, self.boost_input):
            row.addWidget(control)
        self.parameter_stack.addWidget(self._field("MLFQ 时间片 / 提升周期", mlfq))

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

    @staticmethod
    def _button(text: str, object_name: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(object_name)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumHeight(38)
        return button

    def _build_stat_cards(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(14)
        self.clock_card = StatCard("SIMULATION CLOCK", "T = 0", "等待实验加载", "CLK", COLORS["primary"])
        self.cpu_card = StatCard("CURRENT CPU", "IDLE", "暂无运行进程", "CPU", COLORS["success"])
        self.utilization_card = StatCard("CPU UTILIZATION", "0.0%", "0 个忙碌 Tick", "USE", COLORS["cyan"])
        self.switch_card = StatCard("CONTEXT SWITCH", "0", "进程切换次数", "CTX", COLORS["purple"])
        for card in (self.clock_card, self.cpu_card, self.utilization_card, self.switch_card):
            layout.addWidget(card)
        return layout

    def _build_timeline_panel(self) -> SchedulerPanel:
        panel = SchedulerPanel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 21, 24, 22)
        layout.setSpacing(13)
        top = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("CPU 甘特时间线")
        title.setObjectName("PanelTitle")
        subtitle = QLabel("彩色区间表示进程执行，灰色区间表示 CPU 空闲；MLFQ 同时标注队列层级。")
        subtitle.setObjectName("PanelSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        top.addLayout(title_box)
        top.addStretch()
        self.export_gantt_button = QPushButton("导出 PNG")
        self.export_gantt_button.setObjectName("SecondaryButton")
        self.export_gantt_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_gantt_button.clicked.connect(self.export_gantt_png)
        top.addWidget(self.export_gantt_button)
        self.timeline_summary = QLabel("0 SEGMENTS")
        self.timeline_summary.setObjectName("TimelineTime")
        top.addWidget(self.timeline_summary)
        layout.addLayout(top)

        self.gantt_chart = GanttChart()
        timeline_scroll = QScrollArea()
        timeline_scroll.setObjectName("GanttScroll")
        timeline_scroll.setWidgetResizable(True)
        timeline_scroll.setFrameShape(QFrame.Shape.NoFrame)
        timeline_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        timeline_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        timeline_scroll.setWidget(self.gantt_chart)
        timeline_scroll.setFixedHeight(166)
        layout.addWidget(timeline_scroll)
        return panel

    def _build_queue_panel(self) -> SchedulerPanel:
        panel = SchedulerPanel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(11)
        title = QLabel("调度队列")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)
        self.queue_rule_label = QLabel("排序依据：—")
        self.queue_rule_label.setObjectName("PanelSubtitle")
        layout.addWidget(self.queue_rule_label)

        self.ready_queue_widget = QWidget()
        ready_layout = QVBoxLayout(self.ready_queue_widget)
        ready_layout.setContentsMargins(0, 0, 0, 0)
        ready_layout.setSpacing(7)
        ready_layout.addWidget(self._small_label("READY QUEUE"))
        self.ready_queue_layout = FlowLayout()
        ready_layout.addLayout(self.ready_queue_layout)
        layout.addWidget(self.ready_queue_widget)

        self.mlfq_queue_widget = QWidget()
        mlfq_layout = QVBoxLayout(self.mlfq_queue_widget)
        mlfq_layout.setContentsMargins(0, 0, 0, 0)
        mlfq_layout.setSpacing(7)
        self.mlfq_queue_layouts = []
        for level in range(3):
            mlfq_layout.addWidget(self._small_label(f"Q{level} · LEVEL {level}"))
            queue_layout = FlowLayout()
            self.mlfq_queue_layouts.append(queue_layout)
            mlfq_layout.addLayout(queue_layout)
        self.mlfq_queue_widget.hide()
        layout.addWidget(self.mlfq_queue_widget)

        layout.addWidget(self._small_label("等待 I/O / BLOCKED"))
        self.blocked_queue_layout = FlowLayout()
        layout.addLayout(self.blocked_queue_layout)

        layout.addWidget(self._small_label("尚未到达 / NEW"))
        self.new_queue_layout = FlowLayout()
        layout.addLayout(self.new_queue_layout)
        layout.addStretch()
        return panel

    @staticmethod
    def _small_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SchedulerFieldLabel")
        return label

    def _build_event_panel(self) -> SchedulerPanel:
        panel = SchedulerPanel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)
        title = QLabel("实时事件流")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)
        self.event_table = QTableWidget(0, 4)
        self.event_table.setObjectName("SimulationTable")
        self.event_table.setHorizontalHeaderLabels(["时刻", "事件", "PID", "说明"])
        self._configure_table(self.event_table)
        self.event_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.event_table.setMinimumHeight(210)
        layout.addWidget(self.event_table)
        return panel

    def _build_process_panel(self) -> SchedulerPanel:
        panel = SchedulerPanel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 20, 22, 22)
        layout.setSpacing(10)
        title = QLabel("PCB 实时指标")
        title.setObjectName("PanelTitle")
        subtitle = QLabel("完成后自动给出等待、周转与响应时间；未产生的指标显示为 —。")
        subtitle.setObjectName("PanelSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        self.process_table = QTableWidget(0, 9)
        self.process_table.setObjectName("SimulationTable")
        self.process_table.setHorizontalHeaderLabels(
            ["PID", "状态", "剩余", "到达", "开始", "完成", "等待", "周转", "响应"]
        )
        self._configure_table(self.process_table)
        self.process_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.process_table.setMinimumHeight(230)
        layout.addWidget(self.process_table)
        return panel

    @staticmethod
    def _configure_table(table: QTableWidget) -> None:
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setShowGrid(False)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(36)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

    def _on_algorithm_changed(self, index: int) -> None:
        key = self.ALGORITHMS[index][1]
        page = {"priority": 1, "round_robin": 2, "mlfq": 3}.get(key, 0)
        self.parameter_stack.setCurrentIndex(page)
        self.algorithm_description.setText(self.DESCRIPTIONS[key])

    def _on_speed_changed(self, index: int) -> None:
        self.simulation_service.set_speed(self.SPEEDS[index][1])

    def _on_switch_cost_changed(self, index: int) -> None:
        self.simulation_service.set_switch_cost(SWITCH_COSTS[index][1])

    def _scheduler_selection(self) -> tuple[str, dict]:
        key = self.ALGORITHMS[self.algorithm_combo.currentIndex()][1]
        options = {}
        if key == "priority":
            options["preemptive"] = self.priority_mode_combo.currentIndex() == 0
            options["aging_interval"] = (None, 2, 4, 6)[
                self.priority_aging_combo.currentIndex()
            ]
        elif key == "round_robin":
            options["quantum"] = self.quantum_input.value()
        elif key == "mlfq":
            options["quanta"] = tuple(control.value() for control in self.mlfq_inputs)
            options["boost_interval"] = self.boost_input.value()
        return key, options

    def load_experiment(self) -> bool:
        try:
            key, options = self._scheduler_selection()
            self.simulation_service.load(key, **options)
        except (TypeError, ValueError) as error:
            MessageDialog.show_error(self, "无法加载实验", str(error))
            return False
        self.refresh()
        return True

    def start_simulation(self) -> None:
        try:
            self.simulation_service.start()
        except ValueError as error:
            MessageDialog.show_error(self, "无法开始运行", str(error))

    def pause_simulation(self) -> None:
        try:
            self.simulation_service.pause()
        except ValueError as error:
            MessageDialog.show_error(self, "无法暂停", str(error))

    def step_simulation(self) -> bool:
        try:
            return self.simulation_service.step()
        except ValueError as error:
            MessageDialog.show_error(self, "无法单步运行", str(error))
            return False

    def reset_simulation(self) -> None:
        try:
            self.simulation_service.reset()
        except ValueError as error:
            MessageDialog.show_error(self, "无法重置", str(error))

    def refresh(self) -> None:
        state = self.simulation_service.state
        scheduler = self.simulation_service.scheduler
        loaded = scheduler is not None

        self.process_hint.setText(f"当前实验集 · {len(self.process_manager.processes)} 个进程")
        self.loaded_algorithm_label.setText(
            f"当前算法：{scheduler.name}" if loaded else "当前算法：—"
        )
        self.clock_card.set_value(f"T = {state.clock}")
        self.clock_card.set_subtitle(
            "统一离散仿真时钟" if loaded else "等待实验加载"
        )
        current = state.current_process
        self.cpu_card.set_value(current.pid if current else "IDLE")
        self.cpu_card.set_subtitle(
            f"{current.name} · 剩余 {current.remaining_time} Tick"
            if current
            else "暂无运行进程"
        )
        self.utilization_card.set_value(f"{state.cpu_utilization * 100:.1f}%")
        self.utilization_card.set_subtitle(
            f"{state.effective_busy_ticks} / {state.total_ticks} 有效忙碌 Tick"
        )
        self.switch_card.set_value(str(state.context_switches))
        self.gantt_chart.set_segments(state.segments)
        self.timeline_summary.setText(f"{len(state.segments)} SEGMENTS · T={state.clock}")
        self.export_gantt_button.setEnabled(bool(state.segments))

        self._refresh_status(loaded, state.status)
        self._refresh_queues(state.ready_queue, state.blocked_processes, state.new_processes)
        self._refresh_events()
        self._refresh_processes()
        self._sync_controls(loaded, state.status)

    def _refresh_status(self, loaded: bool, status: SimulationStatus) -> None:
        if not loaded:
            text, state_name = "●  尚未加载", "empty"
        else:
            text = {
                SimulationStatus.IDLE: "●  实验就绪",
                SimulationStatus.RUNNING: "●  正在运行",
                SimulationStatus.PAUSED: "●  已暂停",
                SimulationStatus.FINISHED: "●  已完成",
            }[status]
            state_name = status.value.lower()
        self.run_status_label.setText(text)
        if self.run_status_label.property("state") != state_name:
            self.run_status_label.setProperty("state", state_name)
            self.run_status_label.style().unpolish(self.run_status_label)
            self.run_status_label.style().polish(self.run_status_label)

    def _refresh_queues(
        self,
        ready: list[Process],
        blocked: list[Process],
        new: list[Process],
    ) -> None:
        scheduler = self.simulation_service.scheduler
        scheduler_name = scheduler.name if scheduler is not None else ""
        ordered, rule, detail = self._ordered_ready_queue(ready, scheduler_name)
        if scheduler_name.startswith("Priority") and scheduler is not None:
            now = self.simulation_service.state.clock
            ordered = sorted(
                ready,
                key=lambda process: (
                    scheduler.effective_priority(process, now),
                    process.arrival_time,
                    process.pid,
                ),
            )
            if getattr(scheduler, "aging_interval", None):
                rule = f"有效优先级升序 · 每 {scheduler.aging_interval} Tick Aging"
                def detail(process):
                    return (
                        f"有效 {scheduler.effective_priority(process, now)} / "
                        f"原始 {process.priority}"
                    )
        self.queue_rule_label.setText(f"排序依据：{rule}")

        is_mlfq = scheduler_name == "MLFQ"
        self.ready_queue_widget.setVisible(not is_mlfq)
        self.mlfq_queue_widget.setVisible(is_mlfq)
        if is_mlfq and scheduler is not None:
            for level, layout in enumerate(self.mlfq_queue_layouts):
                processes = [
                    process
                    for process in ready
                    if scheduler.queue_level(process) == level
                ]
                self._fill_queue(layout, processes, "空", lambda process: f"剩余 {process.remaining_time}")
        else:
            self._fill_queue(self.ready_queue_layout, ordered, "就绪队列为空", detail)
        self._fill_queue(
            self.blocked_queue_layout,
            blocked,
            "没有 I/O 等待中的进程",
            lambda process: f"剩余 I/O {process.io_remaining}",
        )
        self._fill_queue(self.new_queue_layout, new, "没有等待到达的进程")

    @staticmethod
    def _ordered_ready_queue(ready: list[Process], scheduler_name: str):
        if scheduler_name == "SJF":
            return sorted(ready, key=lambda p: (p.burst_time, p.arrival_time, p.pid)), "CPU 服务时间升序", lambda p: f"服务 {p.burst_time}"
        if scheduler_name == "SRTF":
            return sorted(ready, key=lambda p: (p.remaining_time, p.arrival_time, p.pid)), "剩余时间升序", lambda p: f"剩余 {p.remaining_time}"
        if scheduler_name.startswith("Priority"):
            return sorted(ready, key=lambda p: (p.priority, p.arrival_time, p.pid)), "优先级数字升序", lambda p: f"优先级 {p.priority}"
        if scheduler_name == "EDF":
            return sorted(ready, key=lambda p: (p.deadline if p.deadline is not None else float("inf"), p.arrival_time, p.pid)), "Deadline 升序", lambda p: f"D={p.deadline_text}"
        if scheduler_name == "RMS":
            return sorted(ready, key=lambda p: (p.period if p.period is not None else float("inf"), p.arrival_time, p.pid)), "Period 升序", lambda p: f"T={p.period_text}"
        if scheduler_name == "MLFQ":
            return list(ready), "队列层级 + 层内 FIFO", lambda p: f"剩余 {p.remaining_time}"
        rule = "到达 / 入队顺序（FIFO）" if scheduler_name else "加载算法后显示"
        return list(ready), rule, lambda p: f"剩余 {p.remaining_time}"

    @staticmethod
    def _fill_queue(
        layout: FlowLayout,
        processes: list[Process],
        empty: str,
        detail=None,
    ) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()
                item.widget().deleteLater()
        if not processes:
            label = QLabel(empty)
            label.setObjectName("QueueEmpty")
            layout.addWidget(label)
        else:
            for position, process in enumerate(processes, start=1):
                secondary = detail(process) if detail else f"剩余 {process.remaining_time}"
                label = QLabel(f"{position:02d}  {process.pid}\n{secondary}")
                label.setObjectName("QueueToken")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(label)

    def _refresh_events(self) -> None:
        events = list(reversed(self.simulation_service.state.events[-50:]))
        self.event_table.setRowCount(len(events))
        colors = {
            SimulationEventType.DISPATCH: COLORS["success"],
            SimulationEventType.PREEMPT: COLORS["danger"],
            SimulationEventType.TIMESLICE: COLORS["warning"],
            SimulationEventType.FINISH: COLORS["primary"],
        }
        for row, event in enumerate(events):
            values = (event.time_text, event.event_type.display_name, event.pid or "—", event.detail or "—")
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 1:
                    item.setForeground(QColor(colors.get(event.event_type, COLORS["text_secondary"])))
                self.event_table.setItem(row, column, item)

    def _refresh_processes(self) -> None:
        processes = sorted(self.process_manager.processes, key=lambda process: process.pid)
        self.process_table.setRowCount(len(processes))
        for row, process in enumerate(processes):
            values = (
                process.pid,
                process.state.display_name,
                process.remaining_time,
                process.arrival_time,
                self._metric(process.start_time),
                self._metric(process.finish_time),
                self._metric(process.waiting_time),
                self._metric(process.turnaround_time),
                self._metric(process.response_time),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column == 1:
                    color = {
                        ProcessState.NEW: COLORS["cyan"],
                        ProcessState.READY: COLORS["ready"],
                        ProcessState.RUNNING: COLORS["running"],
                    ProcessState.BLOCKED: COLORS["blocked"],
                    ProcessState.SUSPENDED: COLORS["suspended"],
                    ProcessState.FINISHED: COLORS["finished"],
                }[process.state]
                    item.setForeground(QColor(color))
                self.process_table.setItem(row, column, item)

    @staticmethod
    def _metric(value) -> str:
        return "—" if value is None else str(value)

    def _sync_controls(self, loaded: bool, status: SimulationStatus) -> None:
        running = status is SimulationStatus.RUNNING
        finished = status is SimulationStatus.FINISHED
        has_processes = bool(self.process_manager.processes)
        self.load_button.setEnabled(has_processes and not running)
        self.start_button.setEnabled(loaded and not running and not finished)
        self.pause_button.setEnabled(loaded and running)
        self.step_button.setEnabled(loaded and not running and not finished)
        self.reset_button.setEnabled(loaded and not running)
        self.start_button.setText(
            "▶  继续运行" if status is SimulationStatus.PAUSED else "▶  开始运行"
        )
        for control in (
            self.algorithm_combo,
            self.priority_mode_combo,
            self.priority_aging_combo,
            self.quantum_input,
            *self.mlfq_inputs,
            self.boost_input,
            self.switch_cost_combo,
        ):
            control.setEnabled(not running)

    def export_gantt_png(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出甘特图",
            "gantt_timeline.png",
            "PNG Images (*.png)",
        )
        if not path:
            return
        try:
            ExportService.save_widget_png(self.gantt_chart, path)
        except (OSError, ValueError) as error:
            MessageDialog.show_error(self, "导出失败", str(error))
