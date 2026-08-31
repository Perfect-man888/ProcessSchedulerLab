from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.services.experiment_service import ExperimentService
from app.services.process_manager import ProcessManager
from app.services.resource_manager import ResourceManager
from app.services.settings_service import SettingsService
from app.services.simulation_service import SimulationService
from app.styles.theme import (
    APP_NAME,
    APP_SUBTITLE,
    APP_VERSION,
    WINDOW_DEFAULT_HEIGHT,
    WINDOW_DEFAULT_WIDTH,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
)
from app.ui.dashboard_page import DashboardPage
from app.ui.help_about_page import HelpAboutPage
from app.ui.performance_page import PerformancePage
from app.ui.process_page import ProcessPage
from app.ui.scheduler_page import SchedulerPage
from app.ui.settings_page import SettingsPage
from app.ui.system_analysis_page import SystemAnalysisPage


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.resource_manager = ResourceManager()

        self.process_manager = ProcessManager(
            self.resource_manager
        )

        self.simulation_service = SimulationService(
            self.process_manager
        )

        self.experiment_service = ExperimentService()

        self.settings_service = SettingsService(
            self.process_manager,
            self.simulation_service,
            persist=True,
        )

        self.setWindowTitle(
            f"{APP_NAME} - {APP_SUBTITLE}"
        )

        self.setMinimumSize(
            WINDOW_MIN_WIDTH,
            WINDOW_MIN_HEIGHT,
        )

        self.resize(
            WINDOW_DEFAULT_WIDTH,
            WINDOW_DEFAULT_HEIGHT,
        )

        self.nav_buttons: list[
            QPushButton
        ] = []

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("MainRoot")

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = self._build_sidebar()

        self.stack = QStackedWidget()
        self.stack.setObjectName("ContentStack")

        self._create_pages()

        root.addWidget(sidebar)
        root.addWidget(self.stack, 1)

        self.setCentralWidget(central)

        self.nav_buttons[0].setChecked(True)
        self.stack.setCurrentIndex(0)

    # =============================================================
    # Sidebar
    # =============================================================

    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(250)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 22, 18, 20)
        layout.setSpacing(8)

        # Brand
        brand_layout = QHBoxLayout()
        brand_layout.setSpacing(12)

        mark = QLabel("PS")
        mark.setObjectName("BrandMark")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(44, 44)

        brand_text = QVBoxLayout()
        brand_text.setSpacing(1)

        brand_name = QLabel("ProcessScheduler")
        brand_name.setObjectName("BrandName")

        brand_subtitle = QLabel("OS Simulation Lab")
        brand_subtitle.setObjectName("BrandSubtitle")

        brand_text.addWidget(brand_name)
        brand_text.addWidget(brand_subtitle)

        brand_layout.addWidget(mark)
        brand_layout.addLayout(brand_text)
        brand_layout.addStretch()

        layout.addLayout(brand_layout)

        layout.addSpacing(25)

        section = QLabel("WORKSPACE")
        section.setObjectName("SidebarSection")
        layout.addWidget(section)

        nav_items = [
            ("⌂", "系统概览"),
            ("▦", "进程管理"),
            ("▶", "调度仿真"),
            ("▤", "性能分析"),
            ("◈", "系统分析"),
            ("⚙", "系统设置"),
            ("?", "帮助与关于"),
        ]

        for index, (icon, text) in enumerate(nav_items):
            button = QPushButton(
                f"{icon}    {text}"
            )

            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setCursor(
                Qt.CursorShape.PointingHandCursor
            )

            button.clicked.connect(
                lambda checked=False, i=index:
                self._navigate(i)
            )

            self.nav_buttons.append(button)
            layout.addWidget(button)

        layout.addStretch()

        divider = QFrame()
        divider.setObjectName("SidebarDivider")
        divider.setFrameShape(QFrame.Shape.HLine)

        layout.addWidget(divider)

        course = QLabel("OPERATING SYSTEM COURSE DESIGN")
        course.setObjectName("CourseLabel")
        course.setWordWrap(True)

        version = QLabel(
            f"ProcessSchedulerLab  ·  v{APP_VERSION}"
        )
        version.setObjectName("VersionLabel")

        layout.addWidget(course)
        layout.addWidget(version)

        return sidebar

    # =============================================================
    # Pages
    # =============================================================

    def _create_pages(self):
        self.stack.addWidget(
            DashboardPage(
                self.process_manager,
                self.simulation_service,
            )
        )

        self.stack.addWidget(
            ProcessPage(
                self.process_manager,
                self.simulation_service,
            )
        )

        self.stack.addWidget(
            SchedulerPage(
                self.process_manager,
                self.simulation_service,
                self.settings_service,
            )
        )

        self.performance_page = PerformancePage(
            self.process_manager,
            self.experiment_service,
            self.settings_service,
        )
        self.stack.addWidget(self.performance_page)

        self.stack.addWidget(SystemAnalysisPage())

        self.stack.addWidget(SettingsPage(self.settings_service))

        self.stack.addWidget(HelpAboutPage(self._navigate))

    # =============================================================
    # Navigation
    # =============================================================

    def _navigate(self, index: int):
        for i, button in enumerate(
            self.nav_buttons
        ):
            button.setChecked(i == index)

        self.stack.setCurrentIndex(index)

    def closeEvent(self, event) -> None:
        self.performance_page.shutdown_worker()
        super().closeEvent(event)
