import csv
import json

import pytest

from app.models.process import Process
from app.models.schedule_segment import ScheduleSegment
from app.services.experiment_service import EXPERIMENT_PRESETS, ExperimentService
from app.services.export_service import ExportService
from app.services.process_manager import ProcessManager
from app.services.resource_manager import ResourceManager
from app.widgets.gantt_chart import GanttChart
from app.widgets.performance_chart import PerformanceChart


def test_dataset_json_round_trip_preserves_configuration(tmp_path):
    processes = EXPERIMENT_PRESETS[0].instantiate()
    target = ExportService.save_dataset_json(tmp_path / "课程实验", processes)

    restored = ExportService.load_dataset_json(target)

    assert target.suffix == ".json"
    assert [process.pid for process in restored] == [process.pid for process in processes]
    assert [process.name for process in restored] == [process.name for process in processes]
    assert [process.deadline for process in restored] == [process.deadline for process in processes]
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["schema"] == ExportService.DATASET_SCHEMA
    assert payload["version"] == 1


def test_invalid_dataset_is_rejected_with_clear_error(tmp_path):
    target = tmp_path / "bad.json"
    target.write_text('{"schema":"wrong","version":1,"processes":[]}', encoding="utf-8")

    with pytest.raises(ValueError, match="不是 ProcessSchedulerLab"):
        ExportService.load_dataset_json(target)


def test_replace_processes_is_transactional_on_resource_failure(qapp):
    manager = ProcessManager(ResourceManager())
    original = manager.create_process(
        name="Original",
        arrival_time=0,
        burst_time=1,
        priority=1,
        memory_mb=64,
        io_devices=0,
    )
    oversized = Process(
        pid="P100",
        name="Oversized",
        arrival_time=0,
        burst_time=1,
        priority=1,
        memory_mb=9000,
        io_devices=0,
    )

    with pytest.raises(ValueError, match="内存不足"):
        manager.replace_processes((oversized,))

    assert manager.processes == [original]
    assert manager.resource_manager.resource.used_memory_mb == 64


def test_export_report_writes_summary_and_process_csv(tmp_path, qapp):
    preset = EXPERIMENT_PRESETS[2]
    report = ExperimentService().run_all(preset.instantiate(), dataset_name=preset.name)

    summary, details = ExportService.export_report_csv(report, tmp_path / "comparison.csv")

    with summary.open(encoding="utf-8-sig", newline="") as handle:
        summary_rows = list(csv.reader(handle))
    with details.open(encoding="utf-8-sig", newline="") as handle:
        detail_rows = list(csv.reader(handle))
    assert len(summary_rows) == 8
    assert summary_rows[0][0] == "Algorithm"
    assert len(detail_rows) == 1 + 7 * len(preset.processes)
    assert detail_rows[0][1] == "PID"


def test_png_export_supports_matplotlib_and_qt_widget(tmp_path, qapp):
    report = ExperimentService().run_all(
        EXPERIMENT_PRESETS[0].instantiate(),
        dataset_name="PNG",
    )
    chart = PerformanceChart("latency")
    chart.update_results(report.results)
    chart_path = ExportService.save_figure_png(chart.figure, tmp_path / "chart")

    gantt = GanttChart()
    gantt.resize(900, 138)
    gantt.set_segments((ScheduleSegment(0, 2, "P001"), ScheduleSegment(2, 3)))
    gantt_path = ExportService.save_widget_png(gantt, tmp_path / "gantt.png")

    assert chart_path.stat().st_size > 10_000
    assert gantt_path.stat().st_size > 1_000


def test_pdf_export_contains_summary_charts_and_process_details(tmp_path, qapp):
    preset = EXPERIMENT_PRESETS[0]
    report = ExperimentService().run_all(preset.instantiate(), dataset_name=preset.name)
    latency = PerformanceChart("latency")
    system = PerformanceChart("system")
    latency.update_results(report.results)
    system.update_results(report.results)

    target = ExportService.export_report_pdf(
        report,
        tmp_path / "experiment-report",
        figures=(latency.figure, system.figure),
    )

    payload = target.read_bytes()
    assert target.suffix == ".pdf"
    assert payload.startswith(b"%PDF-")
    assert len(payload) > 50_000
