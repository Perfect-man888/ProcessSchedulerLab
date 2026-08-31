import pytest

from app.services.quantum_recommendation import (
    RR_SCORE_WEIGHTS,
    QuantumScanPoint,
    normalize_minimize,
    recommend_quantum,
)


def point(quantum, turnaround, response, switches):
    return QuantumScanPoint(quantum, turnaround, response, switches)


def test_normalize_minimize_maps_range_to_zero_and_one():
    assert normalize_minimize((10.0, 15.0, 20.0)) == (0.0, 0.5, 1.0)


def test_normalize_minimize_constant_metric_does_not_divide_by_zero():
    assert normalize_minimize((7.0, 7.0, 7.0)) == (0.0, 0.0, 0.0)


def test_rr_score_uses_documented_response_first_weights():
    result = recommend_quantum(
        (point(1, 10, 20, 30), point(2, 20, 10, 10))
    )
    first, second = result.scores

    assert RR_SCORE_WEIGHTS == {
        "response": 0.40,
        "turnaround": 0.35,
        "switches": 0.25,
    }
    assert first.score == pytest.approx(0.65)
    assert second.score == pytest.approx(0.35)


def test_recommend_quantum_selects_lowest_composite_score():
    result = recommend_quantum(
        (
            point(1, 9, 2, 20),
            point(2, 7, 4, 10),
            point(3, 10, 8, 5),
        )
    )

    assert result.recommended.point.quantum == 2
    assert result.best_turnaround.quantum == 2
    assert result.best_response.quantum == 1
    assert result.best_switches.quantum == 3


def test_score_tie_prefers_fewer_switches_then_smaller_quantum():
    all_equal_except_quantum = (
        point(4, 10, 10, 5),
        point(2, 10, 10, 5),
    )
    result = recommend_quantum(all_equal_except_quantum)
    assert result.recommended.point.quantum == 2

    # Quantum 1 与 8 综合分都为 0.25，固定先选择切换更少的 Quantum=8。
    switch_tie_break = (
        point(1, 0, 0, 10),
        point(8, 0, 5, 0),
        point(12, 0, 8, 0),
    )
    assert recommend_quantum(switch_tie_break).recommended.point.quantum == 8


@pytest.mark.parametrize(
    "points, message",
    [
        ((), "数据不足"),
        ((point(1, 1, None, 2),), "缺失"),
        ((point(1, 1, 2, float("nan")),), "缺失"),
        ((point(0, 1, 2, 3),), "正整数"),
        ((point(1, 1, 2, 3), point(1, 2, 3, 4)), "不能重复"),
    ],
)
def test_recommend_quantum_rejects_insufficient_or_invalid_metrics(points, message):
    with pytest.raises(ValueError, match=message):
        recommend_quantum(points)


def test_recommend_quantum_does_not_modify_original_scan_points():
    original = (point(3, 9, 5, 7), point(1, 7, 3, 10))
    snapshot = tuple(original)

    result = recommend_quantum(original)

    assert original == snapshot
    assert [item.quantum for item in original] == [3, 1]
    assert result.scores[0].point is original[0]
