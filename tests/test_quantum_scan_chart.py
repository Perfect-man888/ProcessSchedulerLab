from app.models.schedule_result import ProcessMetrics, ScheduleResult
from app.models.schedule_segment import ScheduleSegment
from app.widgets.quantum_scan_chart import QuantumScanChart


def make_rr_result() -> ScheduleResult:
    return ScheduleResult(
        algorithm_name="Round Robin",
        segments=(
            ScheduleSegment(0, 2, "P001"),
            ScheduleSegment(2, 4, "P002"),
        ),
        process_metrics=(
            ProcessMetrics("P001", 0, 1, 0, 2),
            ProcessMetrics("P002", 2, 1, 2, 4),
        ),
        context_switches=2,
    )


def test_quantum_scan_chart_shows_placeholder_when_empty(qapp):
    chart = QuantumScanChart()

    chart.set_data(())

    axis = chart.figure.axes[0]
    assert not axis.lines
    assert "quantum scan" in axis.texts[0].get_text().lower()


def test_quantum_scan_chart_draws_trend_series(qapp):
    chart = QuantumScanChart()
    result = make_rr_result()

    chart.set_data(((1, result), (2, result), (3, result)))

    axis = chart.figure.axes[0]
    # 主坐标轴：平均周转时间 + 平均响应时间两条折线
    assert len(axis.lines) == 2
    # 副坐标轴：上下文切换次数
    assert len(chart.figure.axes[1].lines) == 1
    # 图例合并主副坐标轴，共 3 项
    assert len(axis.get_legend().get_lines()) == 3
