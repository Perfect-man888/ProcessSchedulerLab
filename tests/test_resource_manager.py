import pytest

from app.services.resource_manager import ResourceManager


def test_allocate_and_release_resources():
    manager = ResourceManager()

    manager.allocate(512, 2)

    assert manager.resource.used_memory_mb == 512
    assert manager.resource.used_io_devices == 2
    assert manager.resource.free_memory_mb == 7680
    assert manager.resource.free_io_devices == 6

    manager.release(256, 1)

    assert manager.resource.used_memory_mb == 256
    assert manager.resource.used_io_devices == 1


@pytest.mark.parametrize(
    ("memory_mb", "io_devices", "message"),
    [
        (0, 0, "内存需求必须大于"),
        (128, -1, "不能为负数"),
        (8193, 0, "可用内存不足"),
        (128, 9, "I/O 设备不足"),
    ],
)
def test_allocate_rejects_invalid_or_excessive_requests(
    memory_mb,
    io_devices,
    message,
):
    manager = ResourceManager()

    with pytest.raises(ValueError, match=message):
        manager.allocate(memory_mb, io_devices)

    assert manager.resource.used_memory_mb == 0
    assert manager.resource.used_io_devices == 0


def test_reset_clears_usage():
    manager = ResourceManager()
    manager.allocate(1024, 3)

    manager.reset()

    assert manager.resource.used_memory_mb == 0
    assert manager.resource.used_io_devices == 0


def test_configure_totals_is_validated_and_atomic():
    manager = ResourceManager()
    manager.allocate(1024, 2)

    with pytest.raises(ValueError, match="已用"):
        manager.configure_totals(512, 8)
    assert manager.resource.total_memory_mb == 8192
    assert manager.resource.total_io_devices == 8

    manager.configure_totals(4096, 4)
    assert manager.resource.total_memory_mb == 4096
    assert manager.resource.total_io_devices == 4
    assert manager.resource.free_memory_mb == 3072
