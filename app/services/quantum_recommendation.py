from dataclasses import dataclass
from math import isfinite
from typing import Iterable

from app.models.schedule_result import ScheduleResult

RR_SCORE_WEIGHTS = {
    "response": 0.40,
    "turnaround": 0.35,
    "switches": 0.25,
}


@dataclass(frozen=True, slots=True)
class QuantumScanPoint:
    quantum: int
    turnaround: float
    response: float
    switches: float


@dataclass(frozen=True, slots=True)
class QuantumScore:
    point: QuantumScanPoint
    normalized_response: float
    normalized_turnaround: float
    normalized_switches: float
    score: float


@dataclass(frozen=True, slots=True)
class QuantumRecommendation:
    recommended: QuantumScore
    scores: tuple[QuantumScore, ...]
    best_turnaround: QuantumScanPoint
    best_response: QuantumScanPoint
    best_switches: QuantumScanPoint


def normalize_minimize(values: Iterable[float]) -> tuple[float, ...]:
    """把越小越好的指标归一化到 [0, 1]；常量列统一为 0。"""

    source = tuple(values)
    if not source:
        raise ValueError("归一化数据不能为空。")
    if any(value is None or not isfinite(value) for value in source):
        raise ValueError("归一化指标必须是可用的有限数值。")
    lower, upper = min(source), max(source)
    if upper == lower:
        return tuple(0.0 for _ in source)
    return tuple((value - lower) / (upper - lower) for value in source)


def recommend_quantum(points: Iterable[QuantumScanPoint]) -> QuantumRecommendation:
    """按透明权重推荐当前扫描的折中 Quantum。

    并列时固定优先选择上下文切换更少者；仍并列时选择更小 Quantum，
    使相同结果下保持更细的调度粒度且规则稳定、可复现。
    """

    source = tuple(points)
    if not source:
        raise ValueError("RR 扫描数据不足，无法生成推荐。")
    if len({point.quantum for point in source}) != len(source):
        raise ValueError("RR 扫描 Quantum 不能重复。")
    for point in source:
        values = (point.turnaround, point.response, point.switches)
        if point.quantum <= 0:
            raise ValueError("Quantum 必须为正整数。")
        if any(value is None or not isfinite(value) or value < 0 for value in values):
            raise ValueError("RR 扫描指标缺失或不是有效非负数值。")

    normalized_response = normalize_minimize(point.response for point in source)
    normalized_turnaround = normalize_minimize(point.turnaround for point in source)
    normalized_switches = normalize_minimize(point.switches for point in source)
    scores = tuple(
        QuantumScore(
            point,
            response,
            turnaround,
            switches,
            response * RR_SCORE_WEIGHTS["response"]
            + turnaround * RR_SCORE_WEIGHTS["turnaround"]
            + switches * RR_SCORE_WEIGHTS["switches"],
        )
        for point, response, turnaround, switches in zip(
            source,
            normalized_response,
            normalized_turnaround,
            normalized_switches,
        )
    )
    recommended = min(
        scores,
        key=lambda item: (item.score, item.point.switches, item.point.quantum),
    )
    return QuantumRecommendation(
        recommended=recommended,
        scores=scores,
        best_turnaround=min(source, key=lambda point: (point.turnaround, point.quantum)),
        best_response=min(source, key=lambda point: (point.response, point.quantum)),
        best_switches=min(source, key=lambda point: (point.switches, point.quantum)),
    )


def recommend_from_results(
    data: Iterable[tuple[int, ScheduleResult]],
) -> QuantumRecommendation:
    return recommend_quantum(
        QuantumScanPoint(
            quantum,
            result.average_turnaround_time,
            result.average_response_time,
            result.context_switches,
        )
        for quantum, result in data
    )
