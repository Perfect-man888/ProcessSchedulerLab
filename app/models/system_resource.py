from dataclasses import dataclass


@dataclass
class SystemResource:
    """仿真系统资源模型。"""

    total_memory_mb: int = 8192
    total_io_devices: int = 8

    used_memory_mb: int = 0
    used_io_devices: int = 0

    @property
    def free_memory_mb(self) -> int:
        return (
            self.total_memory_mb
            - self.used_memory_mb
        )

    @property
    def free_io_devices(self) -> int:
        return (
            self.total_io_devices
            - self.used_io_devices
        )

    @property
    def memory_usage_percent(
        self,
    ) -> float:

        if self.total_memory_mb <= 0:
            return 0.0

        return (
            self.used_memory_mb
            / self.total_memory_mb
            * 100
        )

    @property
    def io_usage_percent(
        self,
    ) -> float:

        if self.total_io_devices <= 0:
            return 0.0

        return (
            self.used_io_devices
            / self.total_io_devices
            * 100
        )