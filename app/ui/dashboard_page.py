from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.process import ProcessState
from app.schedulers.registry import SCHEDULER_FACTORIES
from app.services.process_manager import ProcessManager
from app.services.simulation_service import SimulationService
from app.styles.theme import COLORS, TOTAL_IO_DEVICES, TOTAL_MEMORY_MB
from app.widgets.resource_bar import ResourceBar
from app.widgets.stat_card import StatCard


class Panel(QFrame):
    """Dashboard 通用白色面板。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Panel")

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(15, 23, 42, 18))
        self.setGraphicsEffect(shadow)


class DashboardPage(QWidget):

    def __init__(
        self,
        process_manager: ProcessManager,
        simulation_service: SimulationService | None = None,
        parent=None,
    ):
        super().__init__(parent)

        self.process_manager = process_manager
        self.resource_manager = process_manager.resource_manager
        self.simulation_service = simulation_service
        self.state_count_labels: dict[ProcessState, QLabel] = {}
        self.info_values: dict[str, QLabel] = {}

        self._build_ui()

        self.process_manager.changed.connect(self.refresh)
        self.resource_manager.changed.connect(self.refresh)
        self.process_manager.activity.connect(self._record_activity)
        if self.simulation_service is not None:
            self.simulation_service.changed.connect(self.refresh)

        self.refresh()

    def _build_ui(self):
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        container = QWidget()
        container.setObjectName("PageContainer")

        root = QVBoxLayout(container)
        root.setContentsMargins(34, 28, 34, 34)
        root.setSpacing(22)

        # =========================================================
        # 页面标题
        # =========================================================

        header = QHBoxLayout()

        title_box = QVBoxLayout()
        title_box.setSpacing(5)

        title = QLabel("系统概览")
        title.setObjectName("PageTitle")

        subtitle = QLabel(
            "实时查看 CPU、进程状态与系统资源，为调度实验提供统一运行视图。"
        )
        subtitle.setObjectName("PageSubtitle")

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        header.addLayout(title_box)
        header.addStretch()

        self.status_label = QLabel("●  Simulation Ready")
        self.status_label.setObjectName("ReadyPill")
        self.status_label.setProperty("state", "ready")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setMinimumWidth(160)
        self.status_label.setFixedHeight(36)

        header.addWidget(self.status_label)

        root.addLayout(header)

        # =========================================================
        # 统计卡片
        # =========================================================

        stat_layout = QHBoxLayout()
        stat_layout.setSpacing(16)

        self.cpu_card = StatCard(
            "CPU STATUS",
            "IDLE",
            "等待调度任务",
            "CPU",
            COLORS["success"],
        )

        self.memory_card = StatCard(
            "MEMORY",
            f"0 / {TOTAL_MEMORY_MB} MB",
            "当前使用率 0%",
            "RAM",
            COLORS["primary"],
        )

        self.ready_card = StatCard(
            "READY QUEUE",
            "0",
            "暂无就绪进程",
            "RQ",
            COLORS["warning"],
        )

        self.process_card = StatCard(
            "TOTAL PROCESS",
            "0",
            "系统当前无活动进程",
            "PCB",
            COLORS["purple"],
        )

        stat_layout.addWidget(self.cpu_card)
        stat_layout.addWidget(self.memory_card)
        stat_layout.addWidget(self.ready_card)
        stat_layout.addWidget(self.process_card)

        root.addLayout(stat_layout)

        # =========================================================
        # 系统资源 + 进程状态
        # =========================================================

        middle_layout = QHBoxLayout()
        middle_layout.setSpacing(18)

        resources_panel = self._build_resources_panel()
        states_panel = self._build_states_panel()

        middle_layout.addWidget(resources_panel, 3)
        middle_layout.addWidget(states_panel, 2)

        root.addLayout(middle_layout)

        # =========================================================
        # CPU Timeline
        # =========================================================

        root.addWidget(self._build_timeline_panel())

        # =========================================================
        # 最近活动 + 系统信息
        # =========================================================

        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(18)

        bottom_layout.addWidget(
            self._build_activity_panel(),
            3,
        )

        bottom_layout.addWidget(
            self._build_system_info_panel(),
            2,
        )

        root.addLayout(bottom_layout)

        root.addStretch()

        scroll.setWidget(container)
        page_layout.addWidget(scroll)

    # =============================================================
    # System Resources
    # =============================================================

    def _build_resources_panel(self):
        panel = Panel()

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(17)

        title = QLabel("系统资源")
        title.setObjectName("PanelTitle")

        subtitle = QLabel(
            "资源占用将在创建、撤销和调度进程时实时更新"
        )
        subtitle.setObjectName("PanelSubtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        layout.addSpacing(6)

        self.memory_bar = ResourceBar(
            "Physical Memory",
            0,
            TOTAL_MEMORY_MB,
            "MB",
            COLORS["primary"],
        )

        self.cpu_bar = ResourceBar(
            "CPU Utilization",
            0,
            100,
            "%",
            COLORS["success"],
        )

        self.io_bar = ResourceBar(
            "I/O Devices",
            0,
            TOTAL_IO_DEVICES,
            "",
            COLORS["warning"],
        )

        layout.addWidget(self.memory_bar)
        layout.addWidget(self.cpu_bar)
        layout.addWidget(self.io_bar)

        return panel

    # =============================================================
    # Process Distribution
    # =============================================================

    def _build_states_panel(self):
        panel = Panel()

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(14)

        title = QLabel("进程状态分布")
        title.setObjectName("PanelTitle")

        subtitle = QLabel("当前 PCB 生命周期状态")
        subtitle.setObjectName("PanelSubtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(6)

        layout.addLayout(
            self._state_row(
                ProcessState.NEW,
                COLORS["cyan"],
                "New",
                "等待到达模拟时刻",
                "0",
            )
        )

        layout.addLayout(
            self._state_row(
                ProcessState.RUNNING,
                COLORS["running"],
                "Running",
                "正在占用 CPU",
                "0",
            )
        )

        layout.addLayout(
            self._state_row(
                ProcessState.READY,
                COLORS["ready"],
                "Ready",
                "等待 CPU 调度",
                "0",
            )
        )

        layout.addLayout(
            self._state_row(
                ProcessState.BLOCKED,
                COLORS["blocked"],
                "Blocked",
                "等待 I/O 完成",
                "0",
            )
        )

        layout.addLayout(
            self._state_row(
                ProcessState.SUSPENDED,
                COLORS["suspended"],
                "Suspended",
                "已挂起进程",
                "0",
            )
        )

        layout.addLayout(
            self._state_row(
                ProcessState.FINISHED,
                COLORS["finished"],
                "Finished",
                "已完成进程",
                "0",
            )
        )

        layout.addStretch()

        return panel

    def _state_row(
        self,
        state: ProcessState,
        color: str,
        name: str,
        description: str,
        count: str,
    ):
        row = QHBoxLayout()
        row.setSpacing(12)

        dot = QLabel("●")
        dot.setStyleSheet(
            f"""
            color: {color};
            font-size: 17px;
            """
        )

        text_box = QVBoxLayout()
        text_box.setSpacing(2)

        name_label = QLabel(name)
        name_label.setObjectName("StateName")

        description_label = QLabel(description)
        description_label.setObjectName("StateDescription")

        text_box.addWidget(name_label)
        text_box.addWidget(description_label)

        count_label = QLabel(count)
        count_label.setObjectName("StateCount")
        self.state_count_labels[state] = count_label

        row.addWidget(dot)
        row.addLayout(text_box)
        row.addStretch()
        row.addWidget(count_label)

        return row

    # =============================================================
    # Timeline
    # =============================================================

    def _build_timeline_panel(self):
        panel = Panel()

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(15)

        top = QHBoxLayout()

        title_box = QVBoxLayout()
        title_box.setSpacing(3)

        title = QLabel("CPU 执行时间线")
        title.setObjectName("PanelTitle")

        subtitle = QLabel(
            "运行调度模拟后，这里将动态生成进程执行甘特图"
        )
        subtitle.setObjectName("PanelSubtitle")

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        self.timeline_time_label = QLabel("T = 0")
        self.timeline_time_label.setObjectName("TimelineTime")

        top.addLayout(title_box)
        top.addStretch()
        top.addWidget(self.timeline_time_label)

        layout.addLayout(top)

        timeline = QFrame()
        timeline.setObjectName("TimelineTrack")
        timeline.setMinimumHeight(74)

        self.timeline_layout = QHBoxLayout(timeline)
        self.timeline_layout.setContentsMargins(8, 8, 8, 8)
        self.timeline_layout.setSpacing(4)

        self.timeline_idle_label = QLabel("CPU IDLE  ·  等待开始调度实验")
        self.timeline_idle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timeline_idle_label.setObjectName("TimelineIdle")

        self.timeline_layout.addWidget(self.timeline_idle_label)

        layout.addWidget(timeline)

        return panel

    # =============================================================
    # Activity
    # =============================================================

    def _build_activity_panel(self):
        panel = Panel()

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(14)

        title = QLabel("最近调度活动")
        title.setObjectName("PanelTitle")

        subtitle = QLabel(
            "记录进程创建、状态变化与 CPU 调度事件"
        )
        subtitle.setObjectName("PanelSubtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.activity_table = QTableWidget(1, 4)
        self.activity_table.setObjectName("ActivityTable")

        self.activity_table.setHorizontalHeaderLabels(
            [
                "TIME",
                "EVENT",
                "PROCESS",
                "DETAIL",
            ]
        )

        self.activity_table.verticalHeader().setVisible(False)
        self.activity_table.verticalHeader().setDefaultSectionSize(38)
        self.activity_table.setShowGrid(False)
        self.activity_table.setAlternatingRowColors(False)
        self.activity_table.setSelectionMode(
            QTableWidget.SelectionMode.NoSelection
        )
        self.activity_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        header = self.activity_table.horizontalHeader()
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )

        values = [
            "00:00",
            "SYSTEM",
            "—",
            "ProcessSchedulerLab 初始化完成，等待创建进程。",
        ]

        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            self.activity_table.setItem(0, column, item)

        self.activity_table.setMinimumHeight(170)

        layout.addWidget(self.activity_table)

        return panel

    # =============================================================
    # System Information
    # =============================================================

    def _build_system_info_panel(self):
        panel = Panel()

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(13)

        title = QLabel("仿真环境")
        title.setObjectName("PanelTitle")

        subtitle = QLabel("当前实验系统参数")
        subtitle.setObjectName("PanelSubtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(5)

        layout.addLayout(
            self._info_row(
                "Simulation",
                "Ready",
            )
        )

        layout.addLayout(
            self._info_row(
                "Scheduler",
                "Not Selected",
            )
        )

        layout.addLayout(
            self._info_row(
                "System Memory",
                f"{TOTAL_MEMORY_MB} MB",
            )
        )

        layout.addLayout(
            self._info_row(
                "I/O Devices",
                str(TOTAL_IO_DEVICES),
            )
        )

        layout.addLayout(
            self._info_row(
                "Time Unit",
                "1 tick",
            )
        )

        layout.addLayout(
            self._info_row(
                "Algorithms",
                f"{len(SCHEDULER_FACTORIES)} implemented",
            )
        )

        layout.addStretch()

        return panel

    def _info_row(self, key: str, value: str):
        row = QHBoxLayout()

        key_label = QLabel(key)
        key_label.setObjectName("InfoKey")

        value_label = QLabel(value)
        value_label.setObjectName("InfoValue")
        self.info_values[key] = value_label

        row.addWidget(key_label)
        row.addStretch()
        row.addWidget(value_label)

        return row

    # =============================================================
    # Shared state synchronization
    # =============================================================

    def refresh(self):
        """从共享 Manager 读取快照，不在页面内部维护业务状态。"""

        processes = self.process_manager.processes
        counts = self.process_manager.state_counts()
        resource = self.resource_manager.resource

        total = len(processes)
        ready = counts[ProcessState.READY]
        suspended = counts[ProcessState.SUSPENDED]

        simulation = self.simulation_service
        simulation_loaded = (
            simulation is not None
            and simulation.scheduler is not None
        )
        if simulation_loaded:
            ready = len(simulation.state.ready_queue)

        self.process_card.set_value(str(total))
        self.process_card.set_subtitle(
            "系统当前无活动进程"
            if total == 0
            else f"{total} 个 PCB 正在系统中"
        )

        self.ready_card.set_value(str(ready))
        self.ready_card.set_subtitle(
            "暂无就绪进程"
            if ready == 0
            else f"{ready} 个进程等待 CPU"
        )

        memory_percent = resource.memory_usage_percent
        self.memory_card.set_value(
            f"{resource.used_memory_mb} / {resource.total_memory_mb} MB"
        )
        self.memory_card.set_subtitle(
            f"当前使用率 {memory_percent:.1f}%"
        )

        self.memory_bar.set_usage(resource.used_memory_mb)
        self.io_bar.set_usage(resource.used_io_devices)

        current = simulation.state.current_process if simulation_loaded else None
        cpu_percent = (
            simulation.state.cpu_utilization * 100
            if simulation_loaded
            else 0
        )
        self.cpu_card.set_value(current.pid if current is not None else "IDLE")
        self.cpu_card.set_subtitle(
            f"{current.name} · RUNNING"
            if current is not None
            else (
                "等待调度任务"
                if ready == 0
                else f"就绪队列中有 {ready} 个候选进程"
            )
        )
        self.cpu_bar.set_usage(round(cpu_percent))

        for state, label in self.state_count_labels.items():
            label.setText(str(counts[state]))

        clock = (
            simulation.state.clock
            if simulation_loaded
            else self.process_manager.simulation_time
        )
        self.timeline_time_label.setText(f"T = {clock}")

        if simulation_loaded:
            self.info_values["Simulation"].setText(
                simulation.state.status.value.title()
            )
            self.info_values["Scheduler"].setText(simulation.scheduler.name)

        self._refresh_status_pill(simulation_loaded)
        self._refresh_timeline(simulation_loaded)

        if suspended and not ready:
            self.ready_card.set_subtitle(
                f"{suspended} 个进程已挂起"
            )

    def _refresh_status_pill(self, simulation_loaded: bool) -> None:
        if not simulation_loaded:
            text, state = "●  Simulation Ready", "ready"
        else:
            status = self.simulation_service.state.status.value
            text = {
                "IDLE": "●  Experiment Ready",
                "RUNNING": "●  Simulation Running",
                "PAUSED": "●  Simulation Paused",
                "FINISHED": "●  Simulation Finished",
            }[status]
            state = status.lower()

        self.status_label.setText(text)
        if self.status_label.property("state") != state:
            self.status_label.setProperty("state", state)
            self.status_label.style().unpolish(self.status_label)
            self.status_label.style().polish(self.status_label)

    def _refresh_timeline(self, simulation_loaded: bool) -> None:
        while self.timeline_layout.count():
            item = self.timeline_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()
                item.widget().deleteLater()

        segments = (
            self.simulation_service.state.segments
            if simulation_loaded
            else []
        )
        if not segments:
            self.timeline_idle_label = QLabel(
                "CPU IDLE  ·  等待开始调度实验"
            )
            self.timeline_idle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.timeline_idle_label.setObjectName("TimelineIdle")
            self.timeline_layout.addWidget(self.timeline_idle_label)
            return

        palette = ("#4F6EF7", "#16A36A", "#8B5CF6", "#0EA5E9", "#F59E0B")
        for segment in segments[-12:]:
            if segment.is_idle:
                text = f"IDLE\n{segment.start}–{segment.end}"
                background = "#98A2B3"
            else:
                text = f"{segment.pid}\n{segment.start}–{segment.end}"
                color_index = sum(ord(char) for char in segment.pid) % len(palette)
                background = palette[color_index]

            label = QLabel(text)
            label.setObjectName("TimelineSegment")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setToolTip(
                f"{segment.display_name}: T={segment.start} 到 T={segment.end}"
            )
            label.setStyleSheet(f"background-color: {background};")
            self.timeline_layout.addWidget(label, segment.duration)

    def _record_activity(
        self,
        time: str,
        event: str,
        pid: str,
        detail: str,
    ):
        """将共享事件流以最新优先顺序显示在 Dashboard。"""

        self.activity_table.insertRow(0)

        values = [time, event, pid, detail]
        event_colors = {
            "CREATE": COLORS["primary"],
            "STATE": COLORS["cyan"],
            "SUSPEND": COLORS["purple"],
            "ACTIVATE": COLORS["success"],
            "REVOKE": COLORS["danger"],
        }

        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            if column == 1:
                item.setForeground(
                    QColor(event_colors.get(event, COLORS["text_secondary"]))
                )
            self.activity_table.setItem(0, column, item)

        # 仅保留最近 50 条，避免长期运行时 UI 表格无限增长。
        if self.activity_table.rowCount() > 50:
            self.activity_table.setRowCount(50)

        self.activity_table.scrollToTop()
