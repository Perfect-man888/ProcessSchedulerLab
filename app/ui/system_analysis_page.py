from dataclasses import dataclass

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
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

from app.styles.theme import COLORS


@dataclass(frozen=True)
class OfficialSource:
    title: str
    url: str


@dataclass(frozen=True)
class SystemProfile:
    name: str
    kernel: str
    positioning: str
    core_mechanism: str
    realtime: str
    energy: str
    technical_reason: str
    economic_reason: str
    lab_mapping: str
    highlights: tuple[str, ...]
    sources: tuple[OfficialSource, ...]


SYSTEM_PROFILES = (
    SystemProfile(
        name="Windows",
        kernel="Windows NT",
        positioning="桌面 / 服务器，强调交互响应与广泛兼容",
        core_mechanism="线程级抢占优先级；每个优先级维护就绪队列，同级时间片轮转",
        realtime="16–31 为实时优先级区间，高优先级就绪线程可立即抢占",
        energy="QoS 可影响异构核选择与处理器功耗策略",
        technical_reason="动态优先级提升照顾前台输入和 I/O 唤醒，兼顾交互性并减少饥饿。",
        economic_reason="统一桌面与服务器内核需覆盖消费端响应、企业吞吐和大量历史应用兼容。",
        lab_mapping="Priority（抢占）+ Round Robin + 动态提升思想",
        highlights=("抢占优先级", "同级 RR", "Priority Boost", "线程调度"),
        sources=(
            OfficialSource("调度优先级", "https://learn.microsoft.com/en-us/windows/win32/procthread/scheduling-priorities"),
            OfficialSource("优先级提升", "https://learn.microsoft.com/en-us/windows/win32/procthread/priority-boosts"),
            OfficialSource("上下文切换", "https://learn.microsoft.com/en-us/windows/win32/procthread/context-switches"),
        ),
    ),
    SystemProfile(
        name="Linux",
        kernel="Linux",
        positioning="通用开源内核，覆盖服务器、桌面、嵌入式与实时场景",
        core_mechanism="普通公平类向 EEVDF 演进：从有资格任务中选择最早虚拟截止时间",
        realtime="SCHED_FIFO、SCHED_RR 与 SCHED_DEADLINE；Deadline 类结合 EDF 和 CBS",
        energy="多核负载均衡与平台能效策略协同，可适应异构 CPU",
        technical_reason="EEVDF 用 lag 表示公平份额，用虚拟 deadline 改善延迟敏感任务响应。",
        economic_reason="模块化调度类使同一内核适应云服务、工业实时和移动终端，降低平台维护成本。",
        lab_mapping="SJF/SRTF 的短任务响应思想 + RR + EDF",
        highlights=("EEVDF", "SCHED_FIFO", "SCHED_RR", "SCHED_DEADLINE"),
        sources=(
            OfficialSource("EEVDF Scheduler", "https://docs.kernel.org/scheduler/sched-eevdf.html"),
            OfficialSource("Deadline Scheduling", "https://docs.kernel.org/scheduler/sched-deadline.html"),
            OfficialSource("CFS 设计文档", "https://docs.kernel.org/scheduler/sched-design-CFS.html"),
        ),
    ),
    SystemProfile(
        name="Android",
        kernel="Linux + Android Framework",
        positioning="移动终端，前台流畅、电池续航与广泛 SoC 适配并重",
        core_mechanism="继承 Linux 调度，通过 cgroup/cpuset 与 task profile 对前台、后台等任务分组约束",
        realtime="可使用 Linux 实时调度类；系统框架通常优先保证 UI、音频等延迟敏感工作",
        energy="结合 EAS、cpuset、Power HAL 和持续性能提示平衡大小核、温控与续航",
        technical_reason="task profile 将上层工作负载意图与具体 cgroup 实现解耦，便于 OEM 按芯片调优。",
        economic_reason="手机竞争同时受制于续航、散热和硬件成本，调度需把计算资源优先给用户可感知工作。",
        lab_mapping="MLFQ 的交互/批处分层 + Priority + 资源分组",
        highlights=("Linux 调度", "Task Profiles", "cgroups/cpusets", "能效约束"),
        sources=(
            OfficialSource("Cgroup 抽象层", "https://source.android.com/docs/core/perf/cgroups"),
            OfficialSource("性能管理", "https://source.android.com/docs/core/power/performance"),
            OfficialSource("容量型卡顿分析", "https://source.android.com/docs/core/tests/debug/jank_capacity"),
        ),
    ),
    SystemProfile(
        name="iOS",
        kernel="XNU / Mach",
        positioning="Apple 移动生态，用统一软硬件协同追求响应、能效与可预测体验",
        core_mechanism="QoS 将工作分为交互、用户发起、实用和后台；Clutch/Edge 按 QoS 桶、线程组和线程分层决策",
        realtime="XNU 存在实时、固定优先级与分时模式；普通 App 主要通过 QoS 表达意图",
        energy="QoS 同时影响 CPU/I/O 吞吐、定时器延迟和能源分配；异构核上由 Edge 考虑迁移延迟",
        technical_reason="分层调度先区分工作重要性，再在工作负载内做公平与优先级选择。",
        economic_reason="Apple 垂直整合硬件与系统，通过 QoS 约束开发者表达意图，以可控能耗换取稳定交互体验。",
        lab_mapping="Priority + MLFQ 的层级思想 + 不同时间片",
        highlights=("QoS Classes", "Clutch/Edge", "Mach Timeshare", "异构核"),
        sources=(
            OfficialSource("Dispatch QoS", "https://developer.apple.com/documentation/dispatch/dispatchqos"),
            OfficialSource("iOS 能效与 QoS", "https://developer.apple.com/library/archive/documentation/Performance/Conceptual/EnergyGuide-iOS/PrioritizeWorkWithQoS.html"),
            OfficialSource("XNU Clutch/Edge", "https://github.com/apple-oss-distributions/xnu/blob/main/doc/scheduler/sched_clutch_edge.md"),
        ),
    ),
)


class SystemAnalysisPage(QWidget):
    """基于官方资料的典型操作系统调度机制对比页。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.select_system(0)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("SystemAnalysisScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        container.setObjectName("PageContainer")
        root = QVBoxLayout(container)
        root.setContentsMargins(34, 28, 34, 34)
        root.setSpacing(18)
        root.addLayout(self._build_header())
        root.addWidget(self._build_selector_panel())
        root.addWidget(self._build_detail_panel())
        root.addWidget(self._build_comparison_panel())
        root.addWidget(self._build_conclusion_panel())
        root.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll)

    def _build_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("典型系统调度分析")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Windows、Linux、Android 与 iOS 的机制、取舍及官方资料对照。")
        subtitle.setObjectName("PageSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box)
        layout.addStretch()
        badge = QLabel("4 SYSTEMS  ·  12 SOURCES")
        badge.setObjectName("SystemSourcePill")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedHeight(36)
        badge.setMinimumWidth(180)
        layout.addWidget(badge)
        return layout

    @staticmethod
    def _panel() -> QFrame:
        panel = QFrame()
        panel.setObjectName("SystemAnalysisPanel")
        shadow = QGraphicsDropShadowEffect(panel)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(15, 23, 42, 15))
        panel.setGraphicsEffect(shadow)
        return panel

    def _build_selector_panel(self) -> QFrame:
        panel = self._panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 19, 22, 20)
        layout.setSpacing(12)
        heading = QLabel("选择操作系统")
        heading.setObjectName("PanelTitle")
        layout.addWidget(heading)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.system_buttons = []
        for index, profile in enumerate(SYSTEM_PROFILES):
            button = QPushButton(f"{index + 1:02d}   {profile.name}\n{profile.kernel}")
            button.setObjectName("SystemSelectorButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked=False, i=index: self.select_system(i))
            self.system_buttons.append(button)
            row.addWidget(button)
        layout.addLayout(row)
        return panel

    def _build_detail_panel(self) -> QFrame:
        panel = self._panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 21, 24, 22)
        self.detail_stack = QStackedWidget()
        for profile in SYSTEM_PROFILES:
            self.detail_stack.addWidget(self._profile_widget(profile))
        layout.addWidget(self.detail_stack)
        return panel

    def _profile_widget(self, profile: SystemProfile) -> QWidget:
        widget = QWidget()
        root = QVBoxLayout(widget)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(13)
        top = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel(f"{profile.name} · {profile.kernel}")
        title.setObjectName("SystemProfileTitle")
        positioning = QLabel(profile.positioning)
        positioning.setObjectName("PanelSubtitle")
        positioning.setWordWrap(True)
        title_box.addWidget(title)
        title_box.addWidget(positioning)
        top.addLayout(title_box, 1)
        top.addStretch()
        root.addLayout(top)

        chips = QHBoxLayout()
        for text in profile.highlights:
            chip = QLabel(text)
            chip.setObjectName("MechanismChip")
            chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chips.addWidget(chip)
        chips.addStretch()
        root.addLayout(chips)

        facts = QHBoxLayout()
        facts.setSpacing(12)
        facts.addWidget(self._fact_card("核心机制", profile.core_mechanism), 1)
        facts.addWidget(self._fact_card("实时能力", profile.realtime), 1)
        facts.addWidget(self._fact_card("能效策略", profile.energy), 1)
        root.addLayout(facts)

        reasons = QHBoxLayout()
        reasons.setSpacing(12)
        reasons.addWidget(self._fact_card("技术原因", profile.technical_reason), 1)
        reasons.addWidget(self._fact_card("经济 / 产品原因", profile.economic_reason), 1)
        reasons.addWidget(self._fact_card("与本实验的映射", profile.lab_mapping, accent=True), 1)
        root.addLayout(reasons)

        source_row = QHBoxLayout()
        source_label = QLabel("官方 / 权威来源")
        source_label.setObjectName("SchedulerFieldLabel")
        source_row.addWidget(source_label)
        source_row.addStretch()
        for source in profile.sources:
            button = QPushButton(f"{source.title}  ↗")
            button.setObjectName("SourceLinkButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setProperty("sourceUrl", source.url)
            button.clicked.connect(lambda checked=False, url=source.url: self.open_source(url))
            source_row.addWidget(button)
        root.addLayout(source_row)
        return widget

    @staticmethod
    def _fact_card(label_text: str, body_text: str, *, accent: bool = False) -> QFrame:
        card = QFrame()
        card.setObjectName("SystemFactCard")
        card.setProperty("accent", accent)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(15, 13, 15, 14)
        layout.setSpacing(6)
        label = QLabel(label_text)
        label.setObjectName("SystemFactLabel")
        body = QLabel(body_text)
        body.setObjectName("SystemFactBody")
        body.setWordWrap(True)
        layout.addWidget(label)
        layout.addWidget(body)
        layout.addStretch()
        return card

    def _build_comparison_panel(self) -> QFrame:
        panel = self._panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 20, 22, 22)
        layout.setSpacing(10)
        title = QLabel("横向对比矩阵")
        title.setObjectName("PanelTitle")
        subtitle = QLabel("将课程算法概念映射到真实操作系统，避免把某个教学算法简化为完整内核实现。")
        subtitle.setObjectName("PanelSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        rows = (
            ("调度实体", "线程", "任务 / 调度实体", "Linux 任务 + 框架分组", "Mach 线程"),
            ("普通负载", "优先级 + 同级 RR", "EEVDF 公平类", "Linux 公平类 + profiles", "QoS + Clutch/Edge"),
            ("实时能力", "Realtime priorities", "FIFO / RR / DEADLINE", "继承 Linux 实时类", "Realtime / Fixed / Timeshare"),
            ("交互优化", "动态优先级提升", "虚拟 deadline / slice", "top-app / cpuset / boost", "User Interactive QoS"),
            ("主要取舍", "兼容 + 响应", "公平 + 通用", "流畅 + 续航", "体验 + 能效"),
        )
        self.comparison_table = QTableWidget(len(rows), 5)
        self.comparison_table.setObjectName("SystemComparisonTable")
        self.comparison_table.setHorizontalHeaderLabels(["维度", "Windows", "Linux", "Android", "iOS"])
        self.comparison_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.comparison_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.comparison_table.setShowGrid(False)
        self.comparison_table.verticalHeader().setVisible(False)
        self.comparison_table.verticalHeader().setDefaultSectionSize(42)
        self.comparison_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for row, values in enumerate(rows):
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column == 0:
                    item.setForeground(QColor(COLORS["primary"]))
                self.comparison_table.setItem(row, column, item)
        self.comparison_table.setMinimumHeight(260)
        layout.addWidget(self.comparison_table)
        return panel

    def _build_conclusion_panel(self) -> QFrame:
        panel = self._panel()
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(22, 18, 22, 18)
        title = QLabel("分析结论")
        title.setObjectName("SystemConclusionTitle")
        text = QLabel(
            "现代通用系统并非只使用单一 FCFS、RR 或 Priority，而是将抢占、公平、时间片、"
            "实时策略、工作负载分组和能效约束组合。本项目的 8 种算法用于分离演示这些核心思想。"
        )
        text.setObjectName("SystemConclusionText")
        text.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(text, 1)
        return panel

    def select_system(self, index: int) -> None:
        if not 0 <= index < len(SYSTEM_PROFILES):
            raise IndexError("操作系统索引越界。")
        self.detail_stack.setCurrentIndex(index)
        for position, button in enumerate(self.system_buttons):
            button.setChecked(position == index)

    @staticmethod
    def open_source(url: str) -> bool:
        parsed = QUrl(url)
        if parsed.scheme() != "https" or not parsed.host():
            return False
        return QDesktopServices.openUrl(parsed)
