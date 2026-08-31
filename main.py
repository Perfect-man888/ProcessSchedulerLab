import sys
from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from app.styles.theme import (
    APP_FORM_QSS,
    APP_NAME,
)
from app.ui.main_window import MainWindow


def load_stylesheet() -> str:
    """加载全局 QSS 样式。"""

    qss_path = (
        Path(__file__).resolve().parent
        / "app"
        / "styles"
        / "app.qss"
    )

    return qss_path.read_text(
        encoding="utf-8"
    )


def main():
    app = QApplication(sys.argv)

    app.setApplicationName(APP_NAME)

    # 使用 Fusion，保证 Windows 下整体 UI 风格统一。
    app.setStyle("Fusion")

    # 中文字体
    app.setFont(
        QFont(
            "Microsoft YaHei UI",
            10,
        )
    )

    # =========================================================
    # 加载全局 UI 样式
    # =========================================================

    app.setStyleSheet(
        load_stylesheet()
        + "\n"
        + APP_FORM_QSS
    )

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()