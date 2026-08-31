from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from app.styles.theme import rgba


class StatCard(QFrame):
    """Dashboard 顶部统计卡片。"""

    def __init__(
        self,
        title: str,
        value: str,
        subtitle: str,
        icon: str,
        accent: str,
        parent=None,
    ):
        super().__init__(parent)

        self.setObjectName("StatCard")
        self.setMinimumHeight(150)

        self._create_shadow()

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(10)

        self.icon_label = QLabel(icon)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(42, 42)
        self.icon_label.setStyleSheet(
            f"""
            QLabel {{
                background-color: {rgba(accent, 30)};
                color: {accent};
                border-radius: 12px;
                font-size: 18px;
                font-weight: 700;
            }}
            """
        )

        self.title_label = QLabel(title)
        self.title_label.setObjectName("StatCardTitle")

        header.addWidget(self.title_label)
        header.addStretch()
        header.addWidget(self.icon_label)

        root.addLayout(header)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("StatCardValue")
        root.addWidget(self.value_label)

        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("StatCardSubtitle")
        root.addWidget(self.subtitle_label)

    def _create_shadow(self):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(15, 23, 42, 20))
        self.setGraphicsEffect(shadow)

    def set_value(self, value: str):
        self.value_label.setText(value)

    def set_subtitle(self, subtitle: str):
        self.subtitle_label.setText(subtitle)