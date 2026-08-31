from PySide6.QtCore import QObject, Signal

from app.models.process import Process
from app.models.simulation_state import SimulationStatus
from app.services.process_manager import ProcessManager
from app.services.simulation_service import SimulationService
from app.styles.theme import TOTAL_IO_DEVICES, TOTAL_MEMORY_MB


class SettingsService(QObject):
    """统一管理可调实验参数及高风险数据操作。"""

    changed = Signal()

    SPEEDS = (0.5, 1.0, 2.0, 5.0)

    def __init__(
        self,
        process_manager: ProcessManager,
        simulation_service: SimulationService,
        parent=None,
    ):
        super().__init__(parent)
        self.process_manager = process_manager
        self.simulation_service = simulation_service
        self.default_quantum = 2
        self.default_speed = 1.0

    @property
    def is_locked(self) -> bool:
        return self.simulation_service.state.status is SimulationStatus.RUNNING

    def apply(
        self,
        *,
        total_memory_mb: int,
        total_io_devices: int,
        default_quantum: int,
        default_speed: float,
    ) -> None:
        self._require_unlocked()
        if not 1 <= default_quantum <= 20:
            raise ValueError("默认时间片必须在 1–20 Tick 之间。")
        if default_speed not in self.SPEEDS:
            raise ValueError("仿真速度只能为 0.5×、1×、2× 或 5×。")

        # 资源管理器内部先完成全部校验，避免部分更新。
        self.process_manager.resource_manager.configure_totals(
            total_memory_mb,
            total_io_devices,
        )
        self.default_quantum = default_quantum
        self.default_speed = float(default_speed)
        self.simulation_service.set_speed(self.default_speed)
        self.changed.emit()

    def restore_defaults(self) -> None:
        self.apply(
            total_memory_mb=TOTAL_MEMORY_MB,
            total_io_devices=TOTAL_IO_DEVICES,
            default_quantum=2,
            default_speed=1.0,
        )

    def restore_example_dataset(self) -> None:
        self._require_unlocked()
        examples = (
            Process("P001", "Compiler", 0, 8, 3, memory_mb=512, io_devices=1),
            Process("P002", "Editor", 1, 4, 1, deadline=12, memory_mb=256, io_devices=1),
            Process("P003", "Logger", 2, 2, 4, deadline=10, memory_mb=128, io_devices=0),
            Process("P004", "Monitor", 3, 5, 2, deadline=18, memory_mb=256, io_devices=1),
        )
        self.process_manager.replace_processes(examples)
        self.simulation_service.unload()
        self.changed.emit()

    def reset_all_data(self) -> None:
        self._require_unlocked()
        self.process_manager.clear_processes()
        self.simulation_service.unload()
        self.changed.emit()

    def _require_unlocked(self) -> None:
        if self.is_locked:
            raise ValueError("调度仿真正在运行，请先暂停后再修改系统设置。")
