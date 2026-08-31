import csv
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Iterable

from app.models.experiment_result import ExperimentReport
from app.models.process import Process


class ExportService:
    """实验数据集、指标表与可视化文件的统一导入导出入口。"""

    DATASET_SCHEMA = "process-scheduler-lab.dataset"
    DATASET_VERSION = 1

    @classmethod
    def save_dataset_json(
        cls,
        path: str | Path,
        processes: Iterable[Process],
    ) -> Path:
        target = cls._target(path, ".json")
        payload = {
            "schema": cls.DATASET_SCHEMA,
            "version": cls.DATASET_VERSION,
            "exported_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "processes": [cls._process_record(process) for process in processes],
        }
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return target

    @classmethod
    def load_dataset_json(cls, path: str | Path) -> tuple[Process, ...]:
        source = Path(path)
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError(f"无法读取实验数据：{error}") from error

        if not isinstance(payload, dict):
            raise ValueError("实验数据根节点必须是 JSON 对象。")
        if payload.get("schema") != cls.DATASET_SCHEMA:
            raise ValueError("不是 ProcessSchedulerLab 实验数据文件。")
        if payload.get("version") != cls.DATASET_VERSION:
            raise ValueError("实验数据版本不受支持。")
        records = payload.get("processes")
        if not isinstance(records, list):
            raise ValueError("实验数据缺少 processes 数组。")

        processes = []
        for index, record in enumerate(records, start=1):
            if not isinstance(record, dict):
                raise ValueError(f"第 {index} 个进程记录格式错误。")
            try:
                process = Process(
                    pid=cls._text(record, "pid"),
                    name=cls._text(record, "name"),
                    arrival_time=cls._integer(record, "arrival_time", minimum=0),
                    burst_time=cls._integer(record, "burst_time", minimum=1),
                    priority=cls._integer(record, "priority", minimum=1),
                    deadline=cls._optional_integer(record, "deadline", minimum=1),
                    period=cls._optional_integer(record, "period", minimum=1),
                    memory_mb=cls._integer(record, "memory_mb", minimum=1),
                    io_devices=cls._integer(record, "io_devices", minimum=0),
                )
            except ValueError as error:
                raise ValueError(f"第 {index} 个进程记录无效：{error}") from error
            if process.deadline is not None and process.deadline <= process.arrival_time:
                raise ValueError(f"第 {index} 个进程的 Deadline 必须大于到达时间。")
            processes.append(process)

        pids = [process.pid for process in processes]
        if len(pids) != len(set(pids)):
            raise ValueError("实验数据中存在重复 PID。")
        return tuple(processes)

    @classmethod
    def export_report_csv(
        cls,
        report: ExperimentReport,
        summary_path: str | Path,
    ) -> tuple[Path, Path]:
        summary = cls._target(summary_path, ".csv")
        details = summary.with_name(f"{summary.stem}_process_metrics.csv")

        with summary.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "Algorithm",
                    "Average Waiting Time",
                    "Average Turnaround Time",
                    "Average Weighted Turnaround",
                    "Average Response Time",
                    "CPU Utilization",
                    "Throughput",
                    "Context Switches",
                    "Deadline Miss Count",
                    "Deadline Miss Rate",
                ]
            )
            for result in report.results:
                writer.writerow(
                    [
                        result.algorithm_name,
                        f"{result.average_waiting_time:.6f}",
                        f"{result.average_turnaround_time:.6f}",
                        f"{result.average_weighted_turnaround_time:.6f}",
                        f"{result.average_response_time:.6f}",
                        f"{result.cpu_utilization:.6f}",
                        f"{result.throughput:.6f}",
                        result.context_switches,
                        result.deadline_miss_count,
                        f"{result.deadline_miss_rate:.6f}",
                    ]
                )

        with details.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "Algorithm",
                    "PID",
                    "Arrival",
                    "Burst",
                    "Start",
                    "Finish",
                    "Waiting",
                    "Turnaround",
                    "Weighted Turnaround",
                    "Response",
                    "Deadline",
                    "Deadline Missed",
                ]
            )
            for result in report.results:
                for metrics in result.process_metrics:
                    writer.writerow(
                        [
                            result.algorithm_name,
                            metrics.pid,
                            metrics.arrival_time,
                            metrics.burst_time,
                            metrics.start_time,
                            metrics.finish_time,
                            metrics.waiting_time,
                            metrics.turnaround_time,
                            f"{metrics.weighted_turnaround_time:.6f}",
                            metrics.response_time,
                            "" if metrics.deadline is None else metrics.deadline,
                            "YES" if metrics.deadline_missed else "NO",
                        ]
                    )
        return summary, details

    @classmethod
    def save_figure_png(cls, figure, path: str | Path) -> Path:
        target = cls._target(path, ".png")
        figure.savefig(target, dpi=180, facecolor="white", bbox_inches="tight")
        return target

    @classmethod
    def save_widget_png(cls, widget, path: str | Path) -> Path:
        target = cls._target(path, ".png")
        pixmap = widget.grab()
        if pixmap.isNull() or not pixmap.save(str(target), "PNG"):
            raise ValueError("PNG 图像保存失败。")
        return target

    @classmethod
    def export_report_pdf(
        cls,
        report: ExperimentReport,
        path: str | Path,
        *,
        figures: Iterable | None = None,
    ) -> Path:
        """生成可独立阅读的多页实验报告，包含总表、图表、结论和进程明细。"""

        try:
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_CENTER
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import mm
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.platypus import (
                Image,
                PageBreak,
                Paragraph,
                SimpleDocTemplate,
                Spacer,
                Table,
                TableStyle,
            )
        except ImportError as error:
            raise ValueError("缺少 reportlab，请先安装 requirements.txt 中的依赖。") from error

        if not report.results:
            raise ValueError("实验报告没有可导出的算法结果。")
        target = cls._target(path, ".pdf")
        font_name = "Helvetica"
        for font_path in (
            Path("C:/Windows/Fonts/msyh.ttc"),
            Path("C:/Windows/Fonts/simsun.ttc"),
        ):
            if font_path.exists():
                try:
                    pdfmetrics.registerFont(TTFont("PSLChinese", str(font_path)))
                    font_name = "PSLChinese"
                    break
                except Exception:
                    continue

        page_size = landscape(A4)
        document = SimpleDocTemplate(
            str(target),
            pagesize=page_size,
            leftMargin=16 * mm,
            rightMargin=16 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
            title=f"ProcessSchedulerLab - {report.dataset_name}",
            author="ProcessSchedulerLab",
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "PSLTitle",
            parent=styles["Title"],
            fontName=font_name,
            fontSize=20,
            leading=25,
            textColor=colors.HexColor("#172033"),
            spaceAfter=5 * mm,
        )
        heading_style = ParagraphStyle(
            "PSLHeading",
            parent=styles["Heading2"],
            fontName=font_name,
            fontSize=13,
            leading=17,
            textColor=colors.HexColor("#3F5AE0"),
            spaceBefore=4 * mm,
            spaceAfter=2.5 * mm,
        )
        body_style = ParagraphStyle(
            "PSLBody",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=9,
            leading=14,
            textColor=colors.HexColor("#475467"),
            spaceAfter=1.5 * mm,
        )
        small_style = ParagraphStyle(
            "PSLSmall",
            parent=body_style,
            fontSize=7.5,
            leading=10,
            alignment=TA_CENTER,
        )
        detail_style = ParagraphStyle(
            "PSLDetail",
            parent=small_style,
            fontSize=6.5,
            leading=8,
        )

        def text(value, style=small_style):
            return Paragraph(str(value), style)

        table_style = TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F6EF7")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#DDE3EC")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )

        story = [
            Paragraph("ProcessSchedulerLab 调度算法实验报告", title_style),
            Paragraph(
                f"数据集：{report.dataset_name} · 算法数：{len(report.results)} · "
                f"生成时间：{datetime.now().astimezone().isoformat(timespec='seconds')}",
                body_style,
            ),
            Paragraph("一、算法指标总览", heading_style),
        ]
        summary_data = [[
            text("算法"), text("平均等待"), text("平均周转"),
            text("带权周转"), text("平均响应"), text("CPU 利用率"),
            text("吞吐率"), text("切换"), text("Miss"),
        ]]
        for result in report.results:
            summary_data.append([
                text(result.algorithm_name), text(f"{result.average_waiting_time:.2f}"),
                text(f"{result.average_turnaround_time:.2f}"),
                text(f"{result.average_weighted_turnaround_time:.2f}"),
                text(f"{result.average_response_time:.2f}"),
                text(f"{result.cpu_utilization * 100:.1f}%"),
                text(f"{result.throughput:.3f}"), text(result.context_switches),
                text(result.deadline_miss_count if result.algorithm_name == "EDF" else "-")
            ])
        summary_table = Table(
            summary_data,
            repeatRows=1,
            colWidths=[34 * mm, 25 * mm, 25 * mm, 25 * mm, 25 * mm, 25 * mm, 22 * mm, 18 * mm, 16 * mm],
        )
        summary_table.setStyle(table_style)
        story.extend([summary_table, Paragraph("二、自动分析结论", heading_style)])
        for index, observation in enumerate(report.observations, start=1):
            story.append(Paragraph(f"{index}. {observation}", body_style))

        chart_files = []
        with tempfile.TemporaryDirectory(prefix="psl_pdf_") as temp_dir:
            for index, figure in enumerate(figures or ()):
                chart_path = Path(temp_dir) / f"chart-{index}.png"
                figure.savefig(chart_path, dpi=160, facecolor="white", bbox_inches="tight")
                chart_files.append(chart_path)
            if chart_files:
                story.append(Paragraph("三、性能对比图表", heading_style))
                images = [Image(str(item), width=120 * mm, height=76 * mm) for item in chart_files[:2]]
                chart_table = Table([images], colWidths=[125 * mm] * len(images))
                chart_table.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
                story.append(chart_table)

            metrics = report.results[0].process_metrics
            story.append(Paragraph("实验口径与复现参数", heading_style))
            metadata = [
                [text("进程数"), text("总服务时间"), text("到达区间"), text("实时任务")],
                [
                    text(len(metrics)),
                    text(f"{sum(item.burst_time for item in metrics)} Tick"),
                    text(f"T={min(item.arrival_time for item in metrics)}–{max(item.arrival_time for item in metrics)}"),
                    text(sum(item.deadline is not None for item in metrics)),
                ],
            ]
            metadata_table = Table(metadata, colWidths=[60 * mm] * 4)
            metadata_table.setStyle(table_style)
            story.append(metadata_table)
            if report.parameters:
                story.append(
                    Paragraph(
                        " · ".join(f"{name}: {value}" for name, value in report.parameters),
                        body_style,
                    )
                )
            story.append(
                Paragraph(
                    "口径：当前采用单 CPU、离散 Tick、单次作业模型；等待时间 = 周转时间 - 服务时间，"
                    "CPU 利用率 = 忙碌 Tick / 总 Tick。Period 作为周期任务扩展元数据保存，不自动重复释放任务。",
                    body_style,
                )
            )

            story.extend([PageBreak(), Paragraph("四、各算法进程明细", title_style)])
            for algorithm_index, result in enumerate(report.results):
                story.append(Paragraph(result.algorithm_name, heading_style))
                def detail_text(value):
                    return text(value, detail_style)
                detail_data = [[
                    detail_text("PID"), detail_text("到达"), detail_text("服务"), detail_text("开始"), detail_text("完成"),
                    detail_text("等待"), detail_text("周转"), detail_text("带权周转"), detail_text("响应"), detail_text("Deadline"),
                ]]
                for metrics in result.process_metrics:
                    detail_data.append([
                        detail_text(metrics.pid), detail_text(metrics.arrival_time), detail_text(metrics.burst_time),
                        detail_text(metrics.start_time), detail_text(metrics.finish_time), detail_text(metrics.waiting_time),
                        detail_text(metrics.turnaround_time), detail_text(f"{metrics.weighted_turnaround_time:.2f}"),
                        detail_text(metrics.response_time), detail_text(metrics.deadline if metrics.deadline is not None else "-"),
                    ])
                detail_table = Table(
                    detail_data,
                    repeatRows=1,
                    colWidths=[24 * mm] * 10,
                )
                detail_table.setStyle(table_style)
                detail_table.setStyle(TableStyle([
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]))
                story.extend([detail_table, Spacer(1, 3 * mm)])
                if algorithm_index < len(report.results) - 1 and algorithm_index % 4 == 3:
                    story.append(PageBreak())

            def decorate_page(canvas, doc):
                canvas.saveState()
                canvas.setFont(font_name, 7.5)
                canvas.setFillColor(colors.HexColor("#98A2B3"))
                canvas.drawString(16 * mm, 8 * mm, "ProcessSchedulerLab · Reproducible Scheduling Experiment")
                canvas.drawRightString(page_size[0] - 16 * mm, 8 * mm, f"Page {doc.page}")
                canvas.restoreState()

            document.build(story, onFirstPage=decorate_page, onLaterPages=decorate_page)
        return target

    @staticmethod
    def _target(path: str | Path, suffix: str) -> Path:
        target = Path(path)
        if target.suffix.lower() != suffix:
            target = target.with_suffix(suffix)
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    @staticmethod
    def _process_record(process: Process) -> dict:
        return {
            "pid": process.pid,
            "name": process.name,
            "arrival_time": process.arrival_time,
            "burst_time": process.burst_time,
            "priority": process.priority,
            "deadline": process.deadline,
            "period": process.period,
            "memory_mb": process.memory_mb,
            "io_devices": process.io_devices,
        }

    @staticmethod
    def _text(record: dict, key: str) -> str:
        value = record.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} 必须是非空文本。")
        return value.strip()

    @staticmethod
    def _integer(record: dict, key: str, *, minimum: int) -> int:
        value = record.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ValueError(f"{key} 必须是不小于 {minimum} 的整数。")
        return value

    @classmethod
    def _optional_integer(cls, record: dict, key: str, *, minimum: int) -> int | None:
        if record.get(key) is None:
            return None
        return cls._integer(record, key, minimum=minimum)
