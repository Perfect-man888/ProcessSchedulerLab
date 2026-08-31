from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


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
