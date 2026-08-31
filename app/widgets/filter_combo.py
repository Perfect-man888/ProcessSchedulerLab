from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMenu, QToolButton


class FilterCombo(QToolButton):
    """基于 QMenu 的稳定筛选器，避开平台相关下拉箭头绘制。"""

    currentIndexChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FilterCombo")
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        self._items: list[str] = []
        self._current_index = -1
        self._menu = QMenu(self)
        self.setMenu(self._menu)

    def addItems(self, items: list[str]):
        for text in items:
            index = len(self._items)
            self._items.append(text)
            action = self._menu.addAction(text)
            action.triggered.connect(
                lambda checked=False, item_index=index: self.setCurrentIndex(
                    item_index
                )
            )
        if self._current_index < 0 and self._items:
            self.setCurrentIndex(0, emit_signal=False)

    def clear(self) -> None:
        """清空全部选项，供依赖其他筛选器的动态列表复用。"""

        self._menu.clear()
        self._items.clear()
        self._current_index = -1
        self.setText("")

    def setCurrentIndex(self, index: int, emit_signal: bool = True):
        if not 0 <= index < len(self._items):
            return
        if index == self._current_index:
            return
        self._current_index = index
        self.setText(f"{self._items[index]}  ▾")
        if emit_signal:
            self.currentIndexChanged.emit(index)

    def currentText(self) -> str:
        if self._current_index < 0:
            return ""
        return self._items[self._current_index]

    def currentIndex(self) -> int:
        return self._current_index
