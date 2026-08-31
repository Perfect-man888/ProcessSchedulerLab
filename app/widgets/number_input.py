from PySide6.QtCore import Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit


class NumberInput(QFrame):
    """不依赖原生微调按钮的稳定整数输入控件。"""

    valueChanged = Signal(int)

    def __init__(
        self,
        minimum: int,
        maximum: int,
        value: int = 0,
        suffix: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("NumberInput")

        self.minimum = minimum
        self.maximum = maximum

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 10, 0)
        layout.setSpacing(7)

        self.editor = QLineEdit()
        self.editor.setObjectName("NumberInputEditor")
        self.editor.setValidator(QIntValidator(minimum, maximum, self))
        self.editor.setText(str(self._clamp(value)))
        self.editor.setAlignment(self.editor.alignment())

        self.suffix_label = QLabel(suffix)
        self.suffix_label.setObjectName("NumberInputSuffix")
        self.suffix_label.setVisible(bool(suffix))

        layout.addWidget(self.editor, 1)
        layout.addWidget(self.suffix_label)

        self.setFocusProxy(self.editor)
        self.editor.editingFinished.connect(self._normalize)
        self.editor.textChanged.connect(self._emit_if_valid)

    def _clamp(self, value: int) -> int:
        return max(self.minimum, min(value, self.maximum))

    def _normalize(self):
        text = self.editor.text().strip()
        value = self.minimum if not text else self._clamp(int(text))
        self.editor.setText(str(value))

    def _emit_if_valid(self, text: str):
        if not text:
            return
        value = int(text)
        if self.minimum <= value <= self.maximum:
            self.valueChanged.emit(value)

    def value(self) -> int:
        text = self.editor.text().strip()
        return self.minimum if not text else self._clamp(int(text))

    def setValue(self, value: int):
        self.editor.setText(str(self._clamp(value)))

    def setPlaceholderText(self, text: str):
        self.editor.setPlaceholderText(text)

    def setReadOnly(self, read_only: bool):
        self.editor.setReadOnly(read_only)

