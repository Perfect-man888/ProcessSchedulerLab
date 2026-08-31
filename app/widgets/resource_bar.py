from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
)


class ResourceBar(QFrame):
    """系统资源使用情况组件。"""

    def __init__(
        self,
        title: str,
        used: int,
        total: int,
        unit: str,
        accent: str,
        parent=None,
    ):
        super().__init__(parent)

        self.total = max(total, 1)
        self.unit = unit
        self.accent = accent

        self.setObjectName("ResourceBar")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(9)

        header = QHBoxLayout()

        self.title_label = QLabel(title)
        self.title_label.setObjectName("ResourceTitle")

        self.value_label = QLabel()
        self.value_label.setObjectName("ResourceValue")

        header.addWidget(self.title_label)
        header.addStretch()
        header.addWidget(self.value_label)

        layout.addLayout(header)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(9)

        self.progress.setStyleSheet(
            f"""
            QProgressBar::chunk {{
                background-color: {accent};
                border-radius: 4px;
            }}
            """
        )

        layout.addWidget(self.progress)

        self.set_usage(used)

    def set_usage(self, used: int):
        used = max(0, min(used, self.total))

        percent = round(used / self.total * 100)

        self.progress.setValue(percent)

        self.value_label.setText(
            f"{used} / {self.total} {self.unit}   ·   {percent}%"
        )