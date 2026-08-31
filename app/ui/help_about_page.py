from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
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

from app.styles.theme import APP_NAME, APP_SUBTITLE, APP_VERSION


class HelpAboutPage(QWidget):
    """面向演示和初次使用者的应用内帮助与项目说明。"""

    def __init__(self, navigate=None, parent=None):
        super().__init__(parent)
        self.navigate = navigate
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("HelpPageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        container.setObjectName("PageContainer")
        root = QVBoxLayout(container)
        root.setContentsMargins(34, 28, 34, 34)
        root.setSpacing(18)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("使用帮助与关于")
        title.setObjectName("PageTitle")
        subtitle = QLabel("从创建 PCB 到完成算法对比的演示指南与概念速查。")
        subtitle.setObjectName("PageSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()
        version = QLabel(f"VERSION  {APP_VERSION}")
        version.setObjectName("HelpVersionPill")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setFixedHeight(36)
        version.setMinimumWidth(130)
        header.addWidget(version)
        root.addLayout(header)

        root.addWidget(self._build_quick_start())
        root.addWidget(self._build_algorithm_reference())
        lower = QHBoxLayout()
        lower.setSpacing(16)
        lower.addWidget(self._build_faq(), 3)
        lower.addWidget(self._build_about(), 2)
        root.addLayout(lower)
        root.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll)

    @staticmethod
    def _panel() -> tuple[QFrame, QVBoxLayout]:
        panel = QFrame()
        panel.setObjectName("HelpPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 20, 22, 22)
        layout.setSpacing(11)
        return panel, layout

    def _build_quick_start(self) -> QFrame:
        panel, layout = self._panel()
        title = QLabel("四步完成一次调度实验")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)
        row = QHBoxLayout()
        row.setSpacing(12)
        steps = (
            ("01", "创建 PCB", "在进程管理中填写到达、服务、优先级与资源。", 1),
            ("02", "加载算法", "进入调度仿真，选择策略及时间片等参数。", 2),
            ("03", "观察过程", "用单步查看 CPU、队列、事件和甘特图的联动。", 2),
            ("04", "对比指标", "在性能分析中一键运行全部算法并导出报告。", 3),
        )
        for number, heading, body, target in steps:
            card = QFrame()
            card.setObjectName("HelpStepCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 14, 16, 15)
            number_label = QLabel(number)
            number_label.setObjectName("HelpStepNumber")
            heading_label = QLabel(heading)
            heading_label.setObjectName("SystemFactLabel")
            body_label = QLabel(body)
            body_label.setObjectName("SystemFactBody")
            body_label.setWordWrap(True)
            card_layout.addWidget(number_label)
            card_layout.addWidget(heading_label)
            card_layout.addWidget(body_label)
            if self.navigate is not None:
                button = QPushButton("前往页面  →")
                button.setObjectName("SourceLinkButton")
                button.clicked.connect(lambda checked=False, i=target: self.navigate(i))
                card_layout.addWidget(button)
            row.addWidget(card, 1)
        layout.addLayout(row)
        return panel

    def _build_algorithm_reference(self) -> QFrame:
        panel, layout = self._panel()
        title = QLabel("调度算法速查")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)
        rows = (
            ("FCFS", "批处理", "非抢占", "到达顺序", "简单，可能护航"),
            ("SJF", "批处理", "非抢占", "最短服务", "低平均等待"),
            ("SRTF", "批处理", "抢占", "最短剩余", "新短任务响应快"),
            ("Priority", "通用", "可选", "优先级 + Aging", "体现等级与饥饿"),
            ("Round Robin", "分时", "时间片", "FIFO 轮转", "交互响应好"),
            ("EDF", "实时", "抢占", "最早 Deadline", "直接关注截止期"),
            ("RMS", "实时", "抢占", "最短周期优先", "静态优先级，适合周期任务"),
            ("MLFQ", "高级分时", "抢占", "多级队列反馈", "兼顾交互与批处理"),
        )
        table = QTableWidget(len(rows), 5)
        table.setObjectName("SystemComparisonTable")
        table.setHorizontalHeaderLabels(["算法", "类型", "调度方式", "选择规则", "主要特点"])
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setShowGrid(False)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(36)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for r, values in enumerate(rows):
            for c, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(r, c, item)
        table.setMinimumHeight(300)
        layout.addWidget(table)
        self.algorithm_table = table
        return panel

    def _build_faq(self) -> QFrame:
        panel, layout = self._panel()
        title = QLabel("常见问题")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)
        faqs = (
            ("为什么 EDF 被跳过？", "当前进程集存在未填 Deadline 的 PCB，EDF 无法进行同条件比较。"),
            ("为什么运行中不能修改数据？", "为保证单一可信状态与指标正确，需先暂停再修改 PCB 或设置。"),
            ("Aging 有什么作用？", "等待进程每过固定 Tick 提升一级有效优先级，用于减少低优先级饥饿。"),
            ("Period 会重复创建任务吗？", "当前采用单次作业模型；Period 会随数据集保存，作为周期任务扩展元数据，不会自动重复释放。"),
            ("如何复现实验？", "选择固定预设或导入 JSON，记录算法参数，再导出 CSV/PDF 即可复现。"),
        )
        for question, answer in faqs:
            q = QLabel(question)
            q.setObjectName("HelpQuestion")
            a = QLabel(answer)
            a.setObjectName("HelpAnswer")
            a.setWordWrap(True)
            layout.addWidget(q)
            layout.addWidget(a)
        layout.addStretch()
        return panel

    def _build_about(self) -> QFrame:
        panel, layout = self._panel()
        title = QLabel("关于项目")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)
        name = QLabel(APP_NAME)
        name.setObjectName("HelpAboutName")
        subtitle = QLabel(APP_SUBTITLE)
        subtitle.setObjectName("PanelSubtitle")
        subtitle.setWordWrap(True)
        description = QLabel(
            "基于 Python 3.11.9、PySide6 与 Matplotlib 的操作系统课程设计。\n\n"
            "核心目标是以统一逐 Tick 仿真语义，可视化展示进程状态、资源占用、"
            "CPU 切换和不同调度策略的量化差异。"
        )
        description.setObjectName("HelpAnswer")
        description.setWordWrap(True)
        stack = QLabel("Python 3.11.9  ·  PySide6  ·  Matplotlib  ·  Pytest")
        stack.setObjectName("MechanismChip")
        stack.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name)
        layout.addWidget(subtitle)
        layout.addWidget(description)
        layout.addStretch()
        layout.addWidget(stack)
        return panel
