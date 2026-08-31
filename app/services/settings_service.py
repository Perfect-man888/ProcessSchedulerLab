from PySide6.QtCore import QObject, QSettings, Signal

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
        *,
        persist: bool = False,
        store: QSettings | None = None,
    ):
        super().__init__(parent)
        self.process_manager = process_manager
        self.simulation_service = simulation_service
        self._store = store or (
            QSettings("ProcessSchedulerLab", "ProcessSchedulerLab")
            if persist
            else None
        )
        self.default_quantum = 2
        self.default_speed = 1.0
        self._load_persistent()

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

        processes = self.process_manager.processes
        required_memory = sum(process.memory_mb for process in processes)
        required_io = sum(process.io_devices for process in processes)
        if total_memory_mb < required_memory:
            raise ValueError(
                f"总内存不能小于现有进程重置所需的 {required_memory} MB。"
            )
        if total_io_devices < required_io:
            raise ValueError(
                f"I/O 总数不能小于现有进程重置所需的 {required_io} 个。"
            )

        # 资源管理器内部先完成全部校验，避免部分更新。
        self.process_manager.resource_manager.configure_totals(
            total_memory_mb,
            total_io_devices,
        )
        self.default_quantum = default_quantum
        self.default_speed = float(default_speed)
        self.simulation_service.set_speed(self.default_speed)
        self._save_persistent()
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

    def _load_persistent(self) -> None:
        if self._store is None:
            return
        resource = self.process_manager.resource_manager.resource

        def read_int(key: str, default: int) -> int:
            try:
                return int(self._store.value(key, default))
            except (TypeError, ValueError):
                return default

        def read_float(key: str, default: float) -> float:
            try:
                return float(self._store.value(key, default))
            except (TypeError, ValueError):
                return default

        # 逐键独立读取与校验，单个损坏键只回退该项，不拖垮全部设置。
        memory = read_int("resources/total_memory_mb", resource.total_memory_mb)
        io_devices = read_int("resources/total_io_devices", resource.total_io_devices)
        quantum = read_int("simulation/default_quantum", 2)
        speed = read_float("simulation/default_speed", 1.0)
        if not 1 <= quantum <= 20:
            quantum = 2
        if speed not in self.SPEEDS:
            speed = 1.0

        try:
            self.process_manager.resource_manager.configure_totals(memory, io_devices)
        except ValueError:
            # 容量配置不合法（如小于已占用），保留当前值即可。
            pass

        self.default_quantum = quantum
        self.default_speed = speed
        self.simulation_service.set_speed(speed)

    def _save_persistent(self) -> None:
        if self._store is None:
            return
        resource = self.process_manager.resource_manager.resource
        self._store.setValue("resources/total_memory_mb", resource.total_memory_mb)
        self._store.setValue("resources/total_io_devices", resource.total_io_devices)
        self._store.setValue("simulation/default_quantum", self.default_quantum)
        self._store.setValue("simulation/default_speed", self.default_speed)
        self._store.sync()
