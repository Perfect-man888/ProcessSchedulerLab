from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.process import ProcessState
from app.models.simulation_state import SimulationStatus
from app.services.export_service import ExportService
from app.services.process_manager import ProcessManager
from app.services.simulation_service import SimulationService
from app.styles.theme import COLORS
from app.widgets.dialogs import MessageDialog
from app.widgets.filter_combo import FilterCombo
from app.widgets.number_input import NumberInput
from app.widgets.stat_card import StatCard
from app.widgets.state_badge import StateBadge


class CreateProcessDialog(QDialog):
    """
    创建进程弹窗。
    """

    def __init__(
        self,
        manager: ProcessManager,
        parent=None,
    ):
        super().__init__(parent)

        self.manager = manager

        self.setWindowTitle("创建新进程")
        self.setModal(True)
        self.setMinimumWidth(720)

        self.setObjectName(
            "CreateProcessDialog"
        )

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(
            28,
            26,
            28,
            26,
        )
        root.setSpacing(14)

        # Header
        title = QLabel("创建新进程")
        title.setObjectName("DialogTitle")

        subtitle = QLabel(
            "设置 PCB、调度参数及系统资源需求。"
        )
        subtitle.setObjectName("DialogSubtitle")

        root.addWidget(title)
        root.addWidget(subtitle)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(
            "例如：Compiler"
        )

        self.arrival_input = NumberInput(0, 9999, 0, "tick")
        self.burst_input = NumberInput(1, 9999, 5, "tick")
        self.priority_input = NumberInput(1, 99, 5)
        resource = self.manager.resource_manager.resource
        self.memory_input = NumberInput(
            64,
            resource.total_memory_mb,
            min(256, resource.total_memory_mb),
            "MB",
        )
        self.io_input = NumberInput(0, resource.total_io_devices, 0, "台")
        self.deadline_input = NumberInput(1, 99999, 10, "tick")
        self.period_input = NumberInput(1, 99999, 20, "tick")

        basic_section, basic_form = self._form_section("基础调度参数")
        basic_form.addRow("进程名称", self.name_input)
        basic_form.addRow("到达时间", self.arrival_input)
        basic_form.addRow("服务时间", self.burst_input)
        basic_form.addRow("优先级", self.priority_input)
        root.addWidget(basic_section)

        resource_section, resource_form = self._form_section("系统资源")
        resource_form.addRow("内存需求", self.memory_input)
        resource_form.addRow("I/O 设备", self.io_input)

        available = QLabel(
            f"当前可用：{resource.free_memory_mb} MB 内存 · "
            f"{resource.free_io_devices} 台 I/O 设备"
        )
        available.setObjectName("AvailableResourceLabel")
        resource_form.addRow("可用资源", available)

        realtime_section, realtime_form = self._form_section("实时调度参数")
        self.realtime_toggle = QCheckBox("启用 Deadline / Period")
        self.realtime_toggle.setObjectName("RealtimeToggle")
        realtime_form.addRow("实时任务", self.realtime_toggle)
        realtime_form.addRow("Deadline", self.deadline_input)
        realtime_form.addRow("Period（扩展字段）", self.period_input)
        secondary_sections = QHBoxLayout()
        secondary_sections.setSpacing(14)
        secondary_sections.addWidget(resource_section, 1)
        secondary_sections.addWidget(realtime_section, 1)
        root.addLayout(secondary_sections)

        self.deadline_input.setEnabled(False)
        self.period_input.setEnabled(False)
        self.realtime_toggle.toggled.connect(self._toggle_realtime)

        note = QLabel(
            "提示：优先级数字越小表示优先级越高；"
            "Deadline 参与 EDF；当前采用单次作业模型，Period 作为周期任务扩展元数据保存。"
        )
        note.setWordWrap(True)
        note.setObjectName("DialogNote")

        root.addWidget(note)

        buttons = QHBoxLayout()

        cancel_button = QPushButton("取消")
        cancel_button.setObjectName(
            "SecondaryButton"
        )

        create_button = QPushButton(
            "创建进程"
        )
        create_button.setObjectName(
            "PrimaryButton"
        )

        cancel_button.clicked.connect(
            self.reject
        )

        create_button.clicked.connect(
            self._create_process
        )
        create_button.setDefault(True)

        buttons.addStretch()
        buttons.addWidget(cancel_button)
        buttons.addWidget(create_button)

        root.addLayout(buttons)

        self.name_input.setFocus()

    def _form_section(self, title: str):
        section = QFrame()
        section.setObjectName("DialogSection")

        layout = QVBoxLayout(section)
        layout.setContentsMargins(18, 15, 18, 17)
        layout.setSpacing(12)

        heading = QLabel(title)
        heading.setObjectName("DialogSectionTitle")
        layout.addWidget(heading)

        form = QFormLayout()
        form.setSpacing(9)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.addLayout(form)
        return section, form

    def _toggle_realtime(self, enabled: bool):
        self.deadline_input.setEnabled(enabled)
        self.period_input.setEnabled(enabled)

    def _create_process(self):

        try:
            realtime_enabled = self.realtime_toggle.isChecked()
            deadline = self.deadline_input.value() if realtime_enabled else None
            period = self.period_input.value() if realtime_enabled else None

            self.manager.create_process(
                name=self.name_input.text(),
                arrival_time=(
                    self.arrival_input.value()
                ),
                burst_time=(
                    self.burst_input.value()
                ),
                priority=(
                    self.priority_input.value()
                ),
                memory_mb=(
                    self.memory_input.value()
                ),
                io_devices=(
                    self.io_input.value()
                ),
                deadline=deadline,
                period=period,
            )

        except ValueError as error:

            MessageDialog.show_error(self, "无法创建进程", str(error))

            return

        self.accept()


class ProcessPage(QWidget):

    def __init__(
        self,
        manager: ProcessManager,
        simulation_service: SimulationService | None = None,
        parent=None,
    ):
        super().__init__(parent)

        self.manager = manager
        self.simulation_service = simulation_service

        self._build_ui()

        self.manager.changed.connect(
            self.refresh
        )

        self.manager.resource_manager.changed.connect(
            self.refresh
        )
        if self.simulation_service is not None:
            self.simulation_service.changed.connect(self.refresh)

        self.refresh()

    # =========================================================
    # UI
    # =========================================================

    def _build_ui(self):

        root = QVBoxLayout(self)
        root.setContentsMargins(
            34,
            28,
            34,
            34,
        )
        root.setSpacing(20)

        # -----------------------------------------------------
        # Header
        # -----------------------------------------------------

        header = QHBoxLayout()

        title_box = QVBoxLayout()
        title_box.setSpacing(5)

        title = QLabel("进程管理")
        title.setObjectName("PageTitle")

        subtitle = QLabel(
            "创建和管理 PCB，观察进程生命周期及系统资源变化。"
        )
        subtitle.setObjectName(
            "PageSubtitle"
        )

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        header.addLayout(title_box)
        header.addStretch()

        self.import_button = QPushButton("⇧  导入 JSON")
        self.import_button.setObjectName("SecondaryButton")
        self.import_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_button.clicked.connect(self.import_dataset)

        self.save_button = QPushButton("⇩  保存 JSON")
        self.save_button.setObjectName("SecondaryButton")
        self.save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_button.clicked.connect(self.save_dataset)

        self.create_button = QPushButton(
            "＋  创建进程"
        )
        self.create_button.setObjectName(
            "PrimaryButton"
        )
        self.create_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.create_button.clicked.connect(
            self.open_create_dialog
        )

        header.addWidget(self.import_button)
        header.addWidget(self.save_button)
        header.addWidget(self.create_button)

        root.addLayout(header)

        # -----------------------------------------------------
        # Statistics
        # -----------------------------------------------------

        cards = QHBoxLayout()
        cards.setSpacing(14)

        self.total_card = StatCard(
            "TOTAL PROCESS",
            "0",
            "当前 PCB 数量",
            "PCB",
            COLORS["primary"],
        )

        self.ready_card = StatCard(
            "READY",
            "0",
            "等待 CPU 调度",
            "RQ",
            COLORS["warning"],
        )

        self.suspended_card = StatCard(
            "SUSPENDED",
            "0",
            "当前挂起进程",
            "SUS",
            COLORS["purple"],
        )

        self.memory_card = StatCard(
            "MEMORY",
            "0 MB",
            f"系统总内存 {self.manager.resource_manager.resource.total_memory_mb} MB",
            "RAM",
            COLORS["success"],
        )

        cards.addWidget(self.total_card)
        cards.addWidget(self.ready_card)
        cards.addWidget(
            self.suspended_card
        )
        cards.addWidget(self.memory_card)

        root.addLayout(cards)

        # -----------------------------------------------------
        # Toolbar
        # -----------------------------------------------------

        toolbar = QFrame()
        toolbar.setObjectName(
            "ProcessToolbar"
        )

        toolbar_layout = QHBoxLayout(
            toolbar
        )

        toolbar_layout.setContentsMargins(
            16,
            12,
            16,
            12,
        )

        self.search_input = QLineEdit()
        self.search_input.setObjectName(
            "SearchInput"
        )
        self.search_input.setPlaceholderText(
            "搜索 PID 或进程名称..."
        )
        self.search_input.setMinimumWidth(280)

        self.state_filter = FilterCombo()

        self.state_filter.addItems(
            [
                "全部状态",
                "就绪",
                "运行",
                "挂起",
                "完成",
                "新建",
            ]
        )

        self.search_input.textChanged.connect(
            self.refresh
        )

        self.state_filter.currentIndexChanged.connect(
            self.refresh
        )

        toolbar_layout.addWidget(
            self.search_input
        )

        toolbar_layout.addWidget(
            self.state_filter
        )

        toolbar_layout.addStretch()

        root.addWidget(toolbar)

        # -----------------------------------------------------
        # Table panel
        # -----------------------------------------------------

        panel = QFrame()
        panel.setObjectName("Panel")

        panel_layout = QVBoxLayout(panel)

        panel_layout.setContentsMargins(
            20,
            18,
            20,
            18,
        )

        panel_layout.setSpacing(14)

        panel_header = QHBoxLayout()

        table_title = QLabel(
            "Process Control Blocks"
        )
        table_title.setObjectName(
            "PanelTitle"
        )

        self.table_info = QLabel(
            "0 processes"
        )
        self.table_info.setObjectName(
            "PanelSubtitle"
        )

        panel_header.addWidget(
            table_title
        )
        panel_header.addStretch()
        panel_header.addWidget(
            self.table_info
        )

        panel_layout.addLayout(
            panel_header
        )

        self.table = QTableWidget()
        self.table.setObjectName(
            "ProcessTable"
        )

        columns = [
            "PID",
            "NAME",
            "STATE",
            "ARRIVAL",
            "BURST",
            "REMAIN",
            "PRIORITY",
            "MEMORY",
            "I/O",
            "DEADLINE",
        ]

        self.table.setColumnCount(
            len(columns)
        )

        self.table.setHorizontalHeaderLabels(
            columns
        )

        self.table.verticalHeader().setVisible(
            False
        )
        self.table.verticalHeader().setDefaultSectionSize(46)
        self.table.verticalHeader().setMinimumSectionSize(46)

        self.table.setShowGrid(False)

        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        self.table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )

        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        header_view = (
            self.table.horizontalHeader()
        )

        for index in range(
            len(columns)
        ):
            header_view.setSectionResizeMode(
                index,
                QHeaderView.ResizeMode.Stretch,
            )

        header_view.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )

        self.table.setMinimumHeight(300)

        self.table.itemSelectionChanged.connect(
            self._update_action_buttons
        )

        panel_layout.addWidget(
            self.table
        )

        # -----------------------------------------------------
        # Actions
        # -----------------------------------------------------

        actions = QHBoxLayout()

        self.selected_label = QLabel(
            "请选择一个进程"
        )

        self.selected_label.setObjectName(
            "SelectedProcessLabel"
        )

        self.suspend_button = QPushButton(
            "挂起"
        )
        self.suspend_button.setObjectName(
            "WarningButton"
        )

        self.activate_button = QPushButton(
            "激活"
        )
        self.activate_button.setObjectName(
            "SuccessButton"
        )

        self.revoke_button = QPushButton(
            "撤销进程"
        )
        self.revoke_button.setObjectName(
            "DangerButton"
        )

        self.suspend_button.clicked.connect(
            self.suspend_selected
        )

        self.activate_button.clicked.connect(
            self.activate_selected
        )

        self.revoke_button.clicked.connect(
            self.revoke_selected
        )

        actions.addWidget(
            self.selected_label
        )

        actions.addStretch()

        actions.addWidget(
            self.suspend_button
        )

        actions.addWidget(
            self.activate_button
        )

        actions.addWidget(
            self.revoke_button
        )

        panel_layout.addLayout(actions)

        root.addWidget(panel, 1)

        self._update_action_buttons()

    # =========================================================
    # Dialog
    # =========================================================

    def open_create_dialog(self):

        if not self._allow_process_mutation("创建进程"):
            return

        dialog = CreateProcessDialog(
            self.manager,
            self,
        )

        dialog.exec()

    # =========================================================
    # Table
    # =========================================================

    def refresh(self):

        processes = self.manager.processes

        counts = self.manager.state_counts()

        resource = (
            self.manager
            .resource_manager
            .resource
        )

        self.total_card.set_value(
            str(len(processes))
        )

        self.ready_card.set_value(
            str(
                counts[
                    ProcessState.READY
                ]
            )
        )

        self.suspended_card.set_value(
            str(
                counts[
                    ProcessState.SUSPENDED
                ]
            )
        )

        self.memory_card.set_value(
            f"{resource.used_memory_mb} MB"
        )

        memory_percent = (
            resource.memory_usage_percent
        )

        self.memory_card.set_subtitle(
            
                f"{resource.used_memory_mb}"
                f" / "
                f"{resource.total_memory_mb} MB"
                f" · {memory_percent:.1f}%"
            
        )

        self.create_button.setEnabled(not self._simulation_running())
        self.import_button.setEnabled(not self._simulation_running())
        self.save_button.setEnabled(bool(processes))

        search = (
            self.search_input
            .text()
            .strip()
            .lower()
        )

        state_text = (
            self.state_filter
            .currentText()
        )

        state_mapping = {
            "新建": ProcessState.NEW,
            "就绪": ProcessState.READY,
            "运行": ProcessState.RUNNING,
            "挂起": ProcessState.SUSPENDED,
            "完成": ProcessState.FINISHED,
        }

        selected_state = (
            state_mapping.get(
                state_text
            )
        )

        filtered = []

        for process in processes:

            if search:
                match = (
                    search
                    in process.pid.lower()
                    or
                    search
                    in process.name.lower()
                )

                if not match:
                    continue

            if (
                selected_state is not None
                and
                process.state
                != selected_state
            ):
                continue

            filtered.append(process)

        # 先清空旧的 cell widgets，避免频繁刷新时状态胶囊残影。
        self.table.clearContents()
        self.table.setRowCount(0)
        self.table.setRowCount(len(filtered))

        for row, process in enumerate(
            filtered
        ):

            values = [
                process.pid,
                process.name,
                "",
                str(
                    process.arrival_time
                ),
                str(
                    process.burst_time
                ),
                str(
                    process.remaining_time
                ),
                str(
                    process.priority
                ),
                f"{process.memory_mb} MB",
                str(
                    process.io_devices
                ),
                process.deadline_text,
            ]

            for column, value in enumerate(
                values
            ):

                if column == 2:
                    continue

                item = QTableWidgetItem(
                    value
                )

                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter
                )

                self.table.setItem(
                    row,
                    column,
                    item,
                )

            self.table.setCellWidget(
                row,
                2,
                self._make_state_badge(
                    process.state
                ),
            )

            # 保存 PID
            pid_item = self.table.item(
                row,
                0,
            )

            if pid_item is not None:
                pid_item.setData(
                    Qt.ItemDataRole.UserRole,
                    process.pid,
                )

        self.table_info.setText(
            f"{len(filtered)} processes"
        )

        self._update_action_buttons()

    def _make_state_badge(
        self,
        state: ProcessState,
    ):
        return StateBadge(state)

    # =========================================================
    # Selected PID
    # =========================================================

    def _selected_pid(self):

        row = self.table.currentRow()

        if row < 0:
            return None

        item = self.table.item(
            row,
            0,
        )

        if item is None:
            return None

        return item.data(
            Qt.ItemDataRole.UserRole
        )

    def _update_action_buttons(self):

        pid = self._selected_pid()
        running = self._simulation_running()
        enabled = pid is not None and not running

        self.suspend_button.setEnabled(enabled)
        self.activate_button.setEnabled(enabled)
        self.revoke_button.setEnabled(enabled)

        if pid is None:
            self.selected_label.setText("请选择一个进程")
            return

        if running:
            self.selected_label.setText("仿真运行中 · 暂停后可管理进程")
            return

        process = self.manager.get_process(pid)
        if process is None:
            return

        self.selected_label.setText(f"已选择 {process.pid} · {process.name}")
        self.suspend_button.setEnabled(
            process.state not in (ProcessState.SUSPENDED, ProcessState.FINISHED)
        )
        self.activate_button.setEnabled(process.state == ProcessState.SUSPENDED)

    # =========================================================
    # Actions
    # =========================================================

    def suspend_selected(self):

        if not self._allow_process_mutation("挂起进程"):
            return

        pid = self._selected_pid()

        if pid is None:
            return

        try:
            if self.simulation_service is not None and self.simulation_service.scheduler:
                self.simulation_service.suspend_process(pid)
            else:
                self.manager.suspend_process(pid)

        except ValueError as error:

            MessageDialog.show_error(self, "无法挂起", str(error))

    def activate_selected(self):

        if not self._allow_process_mutation("激活进程"):
            return

        pid = self._selected_pid()

        if pid is None:
            return

        try:
            if self.simulation_service is not None and self.simulation_service.scheduler:
                self.simulation_service.activate_process(pid)
            else:
                self.manager.activate_process(pid)

        except ValueError as error:

            MessageDialog.show_error(self, "无法激活", str(error))

    def revoke_selected(self):

        if not self._allow_process_mutation("撤销进程"):
            return

        pid = self._selected_pid()

        if pid is None:
            return

        process = (
            self.manager
            .get_process(pid)
        )

        if process is None:
            return

        confirmed = MessageDialog.confirm_danger(
            self,
            "撤销进程",
            (
                f"确定要撤销 {process.pid} · {process.name} 吗？\n"
                "确认后将立即释放该进程占用的内存与 I/O 资源。"
            ),
            "确认撤销",
        )

        if not confirmed:
            return

        self.manager.revoke_process(
            pid
        )

    def _simulation_running(self) -> bool:
        return (
            self.simulation_service is not None
            and self.simulation_service.state.status is SimulationStatus.RUNNING
        )

    def _allow_process_mutation(self, action: str) -> bool:
        if not self._simulation_running():
            return True
        MessageDialog.show_error(
            self,
            f"无法{action}",
            "调度仿真正在运行，请先在调度仿真页面暂停实验。",
        )
        return False

    def save_dataset(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存实验数据集",
            "process_dataset.json",
            "JSON Files (*.json)",
        )
        if not path:
            return
        try:
            target = ExportService.save_dataset_json(path, self.manager.processes)
        except (OSError, ValueError) as error:
            MessageDialog.show_error(self, "保存失败", str(error))
            return
        MessageDialog(
            "保存成功",
            f"实验数据已保存至：\n{target}",
            parent=self,
        ).exec()

    def import_dataset(self):
        if not self._allow_process_mutation("导入实验数据"):
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "导入实验数据集",
            "",
            "JSON Files (*.json)",
        )
        if not path:
            return
        if self.manager.processes and not MessageDialog.confirm_danger(
            self,
            "替换当前进程集",
            "导入将替换当前全部 PCB，并清空现有调度进度。",
            "确认导入",
        ):
            return
        try:
            processes = ExportService.load_dataset_json(path)
            self.manager.replace_processes(processes)
            if self.simulation_service is not None:
                self.simulation_service.unload()
        except (OSError, ValueError) as error:
            MessageDialog.show_error(self, "导入失败", str(error))
            return
        MessageDialog(
            "导入成功",
            f"已载入 {len(processes)} 个进程，请重新选择调度算法。",
            parent=self,
        ).exec()
