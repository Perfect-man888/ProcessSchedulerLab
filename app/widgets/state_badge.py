from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from app.models.process import ProcessState
from app.styles.theme import COLORS, rgba


class StateBadge(QWidget):
    """同时使用颜色、圆点与文字表达进程状态。"""

    def __init__(self, state: ProcessState, parent=None):
        super().__init__(parent)

        colors = {
            ProcessState.NEW: COLORS["cyan"],
            ProcessState.READY: COLORS["ready"],
            ProcessState.RUNNING: COLORS["running"],
            ProcessState.BLOCKED: COLORS["blocked"],
            ProcessState.SUSPENDED: COLORS["suspended"],
            ProcessState.FINISHED: COLORS["finished"],
        }

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        badge = QLabel(f"●  {state.value}")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setToolTip(state.display_name)

        color = colors[state]
        background = rgba(color, 24)
        border = rgba(color, 53)
        badge.setStyleSheet(
            f"""
            QLabel {{
                color: {color};
                background-color: {background};
                border: 1px solid {border};
                border-radius: 10px;
                padding: 4px 9px;
                font-size: 9px;
                font-weight: 700;
            }}
            """
        )

        layout.addStretch()
        layout.addWidget(badge)
        layout.addStretch()
