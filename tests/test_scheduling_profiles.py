from app.data.scheduling_profiles import (
    ALGORITHM_PROFILES,
    SYSTEM_TYPE_BY_KEY,
    SYSTEM_TYPE_PROFILES,
    algorithms_for,
)


def test_course_system_types_map_to_all_eight_algorithms_once():
    assert SYSTEM_TYPE_BY_KEY["batch"].algorithm_keys == (
        "fcfs",
        "sjf",
        "srtf",
        "priority",
    )
    assert SYSTEM_TYPE_BY_KEY["timesharing"].algorithm_keys == (
        "round_robin",
        "mlfq",
    )
    assert SYSTEM_TYPE_BY_KEY["realtime"].algorithm_keys == ("edf", "rms")

    classified = tuple(
        key for profile in SYSTEM_TYPE_PROFILES for key in profile.algorithm_keys
    )
    assert len(classified) == len(set(classified)) == 8
    assert set(classified) == set(ALGORITHM_PROFILES)


def test_system_type_defaults_and_display_order_are_stable():
    assert [profile.default_algorithm for profile in SYSTEM_TYPE_PROFILES] == [
        "fcfs",
        "round_robin",
        "edf",
    ]
    assert [profile.key for profile in algorithms_for("timesharing")] == [
        "round_robin",
        "mlfq",
    ]
