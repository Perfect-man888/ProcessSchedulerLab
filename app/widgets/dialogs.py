from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.data.help_texts import METRIC_TOOLTIPS


class MessageDialog(QDialog):
    """与应用设计系统一致的通用消息弹窗。"""

    def __init__(
        self,
        title: str,
        message: str,
        *,
        kind: str = "info",
        confirm_text: str = "知道了",
        cancel_text: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("MessageDialog")
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(430)

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 22)
        root.setSpacing(16)

        top = QHBoxLayout()
        top.setSpacing(13)

        icon = QLabel("!" if kind in {"warning", "danger"} else "i")
        icon.setObjectName("DialogMessageIcon")
        icon.setProperty("kind", kind)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(38, 38)

        text_box = QVBoxLayout()
        text_box.setSpacing(5)

        title_label = QLabel(title)
        title_label.setObjectName("DialogMessageTitle")

        message_label = QLabel(message)
        message_label.setObjectName("DialogMessageText")
        message_label.setWordWrap(True)

        text_box.addWidget(title_label)
        text_box.addWidget(message_label)
        top.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        top.addLayout(text_box, 1)
        root.addLayout(top)

        buttons = QHBoxLayout()
        buttons.addStretch()

        if cancel_text:
            cancel = QPushButton(cancel_text)
            cancel.setObjectName("SecondaryButton")
            cancel.clicked.connect(self.reject)
            buttons.addWidget(cancel)

        confirm = QPushButton(confirm_text)
        confirm.setObjectName(
            "DangerButton" if kind == "danger" else "PrimaryButton"
        )
        confirm.clicked.connect(self.accept)
        confirm.setDefault(True)
        buttons.addWidget(confirm)

        root.addLayout(buttons)

    @classmethod
    def show_error(cls, parent: QWidget, title: str, message: str):
        cls(title, message, kind="warning", parent=parent).exec()

    @classmethod
    def confirm_danger(
        cls,
        parent: QWidget,
        title: str,
        message: str,
        confirm_text: str,
    ) -> bool:
        dialog = cls(
            title,
            message,
            kind="danger",
            confirm_text=confirm_text,
            cancel_text="取消",
            parent=parent,
        )
        return dialog.exec() == QDialog.DialogCode.Accepted


class MetricHelpDialog(QDialog):
    """课程答辩友好的性能指标速查表。"""

    METRICS = (
        "Waiting Time",
        "Turnaround Time",
        "Weighted Turnaround Time",
        "Response Time",
        "CPU Utilization",
        "Throughput",
        "Context Switch",
        "Makespan",
        "Deadline Miss",
        "Deadline Miss Rate",
        "Deadline Satisfaction",
        "Quantum",
        "Aging",
        "MLFQ Boost",
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MetricHelpDialog")
        self.setWindowTitle("性能指标说明")
        self.setModal(True)
        self.resize(760, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(13)
        title = QLabel("性能指标与实验术语")
        title.setObjectName("DialogMessageTitle")
        subtitle = QLabel("表格、图表和实验结论采用同一统计口径。")
        subtitle.setObjectName("DialogMessageText")
        root.addWidget(title)
        root.addWidget(subtitle)

        table = QTableWidget(len(self.METRICS), 2)
        table.setObjectName("MetricHelpTable")
        table.setHorizontalHeaderLabels(("术语", "中文解释与统计口径"))
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setWordWrap(True)
        for row, metric in enumerate(self.METRICS):
            table.setItem(row, 0, QTableWidgetItem(metric))
            table.setItem(row, 1, QTableWidgetItem(METRIC_TOOLTIPS[metric]))
            table.setRowHeight(row, 52)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        root.addWidget(table, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        close = QPushButton("知道了")
        close.setObjectName("PrimaryButton")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        root.addLayout(buttons)
