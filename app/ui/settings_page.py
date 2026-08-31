from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.services.settings_service import SettingsService
from app.widgets.dialogs import MessageDialog
from app.widgets.filter_combo import FilterCombo
from app.widgets.number_input import NumberInput


class SettingsPage(QWidget):
    """仿真环境参数、示例数据和重置操作的统一入口。"""

    def __init__(self, settings_service: SettingsService, parent=None):
        super().__init__(parent)
        self.settings_service = settings_service
        self._build_ui()
        settings_service.changed.connect(self.refresh)
        settings_service.simulation_service.changed.connect(self.refresh)
        settings_service.process_manager.resource_manager.changed.connect(self.refresh)
        self._load_values()
        self.refresh()

    def _load_values(self) -> None:
        resource = self.settings_service.process_manager.resource_manager.resource
        self.memory_input.setValue(resource.total_memory_mb)
        self.io_input.setValue(resource.total_io_devices)
        self.quantum_input.setValue(self.settings_service.default_quantum)
        self.speed_combo.setCurrentIndex(
            self.settings_service.SPEEDS.index(self.settings_service.default_speed)
        )

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("SettingsPageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        container.setObjectName("PageContainer")
        root = QVBoxLayout(container)
        root.setContentsMargins(34, 28, 34, 34)
        root.setSpacing(18)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("系统设置")
        title.setObjectName("PageTitle")
        subtitle = QLabel("配置仿真资源与默认参数，统一管理示例数据和系统重置。")
        subtitle.setObjectName("PageSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()
        self.lock_label = QLabel()
        self.lock_label.setObjectName("SettingsStatusPill")
        self.lock_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lock_label.setMinimumWidth(160)
        self.lock_label.setFixedHeight(36)
        header.addWidget(self.lock_label)
        root.addLayout(header)

        root.addWidget(self._build_resources_panel())
        root.addWidget(self._build_defaults_panel())
        root.addWidget(self._build_data_panel())
        root.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll)

    @staticmethod
    def _panel(title_text: str, subtitle_text: str) -> tuple[QFrame, QVBoxLayout]:
        panel = QFrame()
        panel.setObjectName("SettingsPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 21, 24, 22)
        layout.setSpacing(14)
        title = QLabel(title_text)
        title.setObjectName("PanelTitle")
        subtitle = QLabel(subtitle_text)
        subtitle.setObjectName("PanelSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        return panel, layout

    def _build_resources_panel(self) -> QFrame:
        panel, layout = self._panel(
            "系统资源容量",
            "新容量不能低于当前已用量，修改将立即联动 Dashboard 与进程创建校验。",
        )
        row = QHBoxLayout()
        row.setSpacing(14)
        self.memory_input = NumberInput(256, 65536, 8192, "MB")
        self.io_input = NumberInput(0, 128, 8, "Devices")
        row.addWidget(self._field("系统总内存", self.memory_input), 1)
        row.addWidget(self._field("I/O 设备总数", self.io_input), 1)
        self.resource_usage_label = QLabel()
        self.resource_usage_label.setObjectName("SettingsUsageCard")
        self.resource_usage_label.setWordWrap(True)
        row.addWidget(self.resource_usage_label, 2)
        layout.addLayout(row)
        return panel

    def _build_defaults_panel(self) -> QFrame:
        panel, layout = self._panel(
            "默认实验参数",
            "新建调度实验和性能比较将采用这些默认值，页面内仍可临时调整。",
        )
        row = QHBoxLayout()
        row.setSpacing(14)
        self.quantum_input = NumberInput(1, 20, 2, "Tick")
        self.speed_combo = FilterCombo()
        self.speed_combo.setObjectName("SettingsCombo")
        self.speed_combo.addItems(["0.5×", "1×", "2×", "5×"])
        row.addWidget(self._field("Round Robin 默认时间片", self.quantum_input), 2)
        row.addWidget(self._field("默认仿真速度", self.speed_combo), 2)
        row.addStretch()
        self.restore_defaults_button = self._button("恢复默认", "SecondaryButton")
        self.apply_button = self._button("应用设置", "PrimaryButton")
        self.restore_defaults_button.clicked.connect(self.restore_defaults)
        self.apply_button.clicked.connect(self.apply_settings)
        row.addWidget(self.restore_defaults_button, 0, Qt.AlignmentFlag.AlignBottom)
        row.addWidget(self.apply_button, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(row)
        self.feedback_label = QLabel("修改后点击“应用设置”生效。")
        self.feedback_label.setObjectName("SettingsFeedback")
        layout.addWidget(self.feedback_label)
        return panel

    def _build_data_panel(self) -> QFrame:
        panel, layout = self._panel(
            "数据维护",
            "恢复示例会替换当前 PCB；全部重置会清空 PCB、调度进度与资源占用。两项操作均需二次确认。",
        )
        row = QHBoxLayout()
        self.restore_example_button = self._button("恢复示例数据", "SecondaryButton")
        self.reset_all_button = self._button("清空全部数据", "DangerButton")
        self.restore_example_button.clicked.connect(self.restore_examples)
        self.reset_all_button.clicked.connect(self.reset_all)
        row.addWidget(self.restore_example_button)
        row.addWidget(self.reset_all_button)
        row.addStretch()
        warning = QLabel("建议在重置前先从“进程管理”保存 JSON 数据集。")
        warning.setObjectName("SettingsWarning")
        row.addWidget(warning)
        layout.addLayout(row)
        return panel

    @staticmethod
    def _field(title: str, control: QWidget) -> QWidget:
        field = QWidget()
        layout = QVBoxLayout(field)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        label = QLabel(title)
        label.setObjectName("SchedulerFieldLabel")
        layout.addWidget(label)
        layout.addWidget(control)
        return field

    @staticmethod
    def _button(text: str, object_name: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(object_name)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumHeight(40)
        return button

    def apply_settings(self) -> bool:
        try:
            self.settings_service.apply(
                total_memory_mb=self.memory_input.value(),
                total_io_devices=self.io_input.value(),
                default_quantum=self.quantum_input.value(),
                default_speed=SettingsService.SPEEDS[self.speed_combo.currentIndex()],
            )
        except ValueError as error:
            MessageDialog.show_error(self, "无法应用设置", str(error))
            return False
        self.feedback_label.setText("✓ 设置已应用，各页面已同步。")
        return True

    def restore_defaults(self) -> None:
        try:
            self.settings_service.restore_defaults()
        except ValueError as error:
            MessageDialog.show_error(self, "无法恢复默认", str(error))
            return
        self._load_values()
        self.feedback_label.setText("✓ 已恢复默认参数。")

    def restore_examples(self) -> None:
        if not MessageDialog.confirm_danger(
            self,
            "恢复示例数据",
            "这将替换当前全部 PCB 并清空调度进度。",
            "确认恢复",
        ):
            return
        try:
            self.settings_service.restore_example_dataset()
        except ValueError as error:
            MessageDialog.show_error(self, "恢复失败", str(error))
            return
        self.feedback_label.setText("✓ 已恢复 4 个可直接演示的示例进程。")

    def reset_all(self) -> None:
        if not MessageDialog.confirm_danger(
            self,
            "清空全部数据",
            "所有 PCB、调度进度和资源占用都将被清空。",
            "确认清空",
        ):
            return
        try:
            self.settings_service.reset_all_data()
        except ValueError as error:
            MessageDialog.show_error(self, "重置失败", str(error))
            return
        self.feedback_label.setText("✓ 系统已回到空白初始状态。")

    def refresh(self) -> None:
        resource = self.settings_service.process_manager.resource_manager.resource
        locked = self.settings_service.is_locked
        self.lock_label.setText("●  运行中已锁定" if locked else "●  可安全修改")
        self.lock_label.setProperty("state", "locked" if locked else "ready")
        self.lock_label.style().unpolish(self.lock_label)
        self.lock_label.style().polish(self.lock_label)
        self.resource_usage_label.setText(
            f"当前已用\n{resource.used_memory_mb} MB 内存  ·  "
            f"{resource.used_io_devices} 个 I/O\n"
            f"尚有 {resource.free_memory_mb} MB / {resource.free_io_devices} 个可分配"
        )
        for control in (
            self.memory_input,
            self.io_input,
            self.quantum_input,
            self.speed_combo,
            self.apply_button,
            self.restore_defaults_button,
            self.restore_example_button,
            self.reset_all_button,
        ):
            control.setEnabled(not locked)
