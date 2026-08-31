import pytest

from app.services.random_process_generator import RandomConfig, RandomProcessGenerator


def test_generator_is_deterministic_with_seed():
    first = RandomProcessGenerator(RandomConfig(count=8, seed=42)).generate()
    second = RandomProcessGenerator(RandomConfig(count=8, seed=42)).generate()

    assert first == second
    assert [p.pid for p in first] == ["R001", "R002", "R003", "R004", "R005", "R006", "R007", "R008"]


def test_generator_different_seeds_produce_different_sets():
    config_a = RandomConfig(count=12, seed=7)
    config_b = RandomConfig(count=12, seed=8)

    set_a = RandomProcessGenerator(config_a).generate()
    set_b = RandomProcessGenerator(config_b).generate()

    assert set_a != set_b


def test_generated_processes_respect_configured_ranges():
    processes = RandomProcessGenerator(
        RandomConfig(
            count=200,
            seed=1,
            arrival_rate=1.0,
            burst_min=2,
            burst_max=10,
            priority_min=1,
            priority_max=4,
        )
    ).generate()

    assert len(processes) == 200
    # 泊松到达时间非降序，且首个进程在 T=0 到达
    arrivals = [p.arrival_time for p in processes]
    assert arrivals[0] == 0
    assert all(left <= right for left, right in zip(arrivals, arrivals[1:]))
    assert all(2 <= p.burst_time <= 10 for p in processes)
    assert all(1 <= p.priority <= 4 for p in processes)
    # 服务时间分布不应全部落在同一值
    assert len({p.burst_time for p in processes}) > 1


def test_realtime_mode_derives_deadline_and_period():
    processes = RandomProcessGenerator(
        RandomConfig(
            count=30,
            seed=5,
            include_realtime=True,
            deadline_factor=3.0,
            period_factor=4.0,
        )
    ).generate()

    assert all(p.deadline is not None for p in processes)
    assert all(p.period is not None for p in processes)
    for process in processes:
        assert process.deadline > process.arrival_time
        assert process.period == round(process.burst_time * 4.0)
        assert process.deadline == process.arrival_time + round(process.burst_time * 3.0)


def test_io_mode_adds_reproducible_blocking_parameters():
    processes = RandomProcessGenerator(
        RandomConfig(
            count=5,
            seed=9,
            include_io=True,
            io_interval=3,
            io_duration=2,
        )
    ).generate()

    assert all(process.io_interval == 3 for process in processes)
    assert all(process.io_duration == 2 for process in processes)

    disabled = RandomProcessGenerator(
        RandomConfig(count=2, seed=9, include_io=False)
    ).generate()
    assert all(process.io_interval is None for process in disabled)
    assert all(process.io_duration is None for process in disabled)


def test_generator_rejects_invalid_configs():
    with pytest.raises(ValueError, match="数量"):
        RandomConfig(count=0)
    with pytest.raises(ValueError, match="到达率"):
        RandomConfig(arrival_rate=0)
    with pytest.raises(ValueError, match="服务时间"):
        RandomConfig(burst_min=0)
    with pytest.raises(ValueError, match="最大服务时间"):
        RandomConfig(burst_min=5, burst_max=3)
    with pytest.raises(ValueError, match="优先级"):
        RandomConfig(priority_min=0)
    with pytest.raises(ValueError, match="Period"):
        RandomConfig(deadline_factor=5.0, period_factor=4.0)
    with pytest.raises(ValueError, match="I/O 请求间隔"):
        RandomConfig(io_interval=0)
    with pytest.raises(ValueError, match="I/O 持续时间"):
        RandomConfig(io_duration=0)
