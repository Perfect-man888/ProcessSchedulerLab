from PySide6.QtCore import QObject, Signal

from app.models.system_resource import SystemResource
from app.styles.theme import (
    TOTAL_IO_DEVICES,
    TOTAL_MEMORY_MB,
)


class ResourceManager(QObject):
    """
    系统资源管理器。

    管理：
    - 内存
    - I/O 设备
    """

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.resource = SystemResource(
            total_memory_mb=TOTAL_MEMORY_MB,
            total_io_devices=TOTAL_IO_DEVICES,
        )

    def can_allocate(
        self,
        memory_mb: int,
        io_devices: int,
    ) -> bool:

        return (
            memory_mb
            <= self.resource.free_memory_mb
            and
            io_devices
            <= self.resource.free_io_devices
        )

    def allocate(
        self,
        memory_mb: int,
        io_devices: int,
    ):
        if memory_mb <= 0:
            raise ValueError(
                "进程内存需求必须大于 0 MB。"
            )

        if io_devices < 0:
            raise ValueError(
                "I/O 设备数量不能为负数。"
            )

        if (
            memory_mb
            > self.resource.free_memory_mb
        ):
            raise ValueError(
                "系统可用内存不足，"
                "无法创建该进程。"
            )

        if (
            io_devices
            > self.resource.free_io_devices
        ):
            raise ValueError(
                "系统可用 I/O 设备不足，"
                "无法创建该进程。"
            )

        self.resource.used_memory_mb += (
            memory_mb
        )

        self.resource.used_io_devices += (
            io_devices
        )

        self.changed.emit()

    def release(
        self,
        memory_mb: int,
        io_devices: int,
    ):
        self.resource.used_memory_mb = max(
            0,
            (
                self.resource.used_memory_mb
                - memory_mb
            ),
        )

        self.resource.used_io_devices = max(
            0,
            (
                self.resource.used_io_devices
                - io_devices
            ),
        )

        self.changed.emit()

    def reset(self):
        self.resource.used_memory_mb = 0
        self.resource.used_io_devices = 0

        self.changed.emit()

    def configure_totals(self, total_memory_mb: int, total_io_devices: int) -> None:
        """在不破坏已分配资源的前提下原子更新系统容量。"""

        if total_memory_mb <= 0:
            raise ValueError("系统总内存必须大于 0 MB。")
        if total_io_devices < 0:
            raise ValueError("I/O 设备总数不能为负数。")
        if total_memory_mb < self.resource.used_memory_mb:
            raise ValueError(
                f"总内存不能小于已用 {self.resource.used_memory_mb} MB。"
            )
        if total_io_devices < self.resource.used_io_devices:
            raise ValueError(
                f"I/O 总数不能小于已用 {self.resource.used_io_devices} 个。"
            )

        self.resource.total_memory_mb = total_memory_mb
        self.resource.total_io_devices = total_io_devices
        self.changed.emit()
