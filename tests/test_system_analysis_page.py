import pytest
from PySide6.QtCore import QUrl

from app.ui.main_window import MainWindow
from app.ui.system_analysis_page import SYSTEM_PROFILES, SystemAnalysisPage


def test_system_analysis_covers_four_systems_with_official_sources(qapp):
    page = SystemAnalysisPage()

    assert [profile.name for profile in SYSTEM_PROFILES] == [
        "Windows",
        "Linux",
        "Android",
        "iOS",
    ]
    assert all(len(profile.sources) >= 2 for profile in SYSTEM_PROFILES)
    assert all(source.url.startswith("https://") for profile in SYSTEM_PROFILES for source in profile.sources)
    assert page.comparison_table.rowCount() == 5
    assert page.comparison_table.columnCount() == 5


def test_system_selector_updates_detail_and_checked_state(qapp):
    page = SystemAnalysisPage()

    page.select_system(2)

    assert page.detail_stack.currentIndex() == 2
    assert page.system_buttons[2].isChecked()
    assert sum(button.isChecked() for button in page.system_buttons) == 1
    with pytest.raises(IndexError):
        page.select_system(10)


def test_official_source_opening_validates_https(qapp, monkeypatch):
    opened = []
    monkeypatch.setattr(
        "app.ui.system_analysis_page.QDesktopServices.openUrl",
        lambda url: opened.append(url) or True,
    )

    assert not SystemAnalysisPage.open_source("file:///unsafe")
    assert SystemAnalysisPage.open_source("https://docs.kernel.org/scheduler/")
    assert opened == [QUrl("https://docs.kernel.org/scheduler/")]


def test_main_window_uses_real_system_analysis_page(qapp):
    window = MainWindow()

    assert isinstance(window.stack.widget(4), SystemAnalysisPage)

    window.close()
