from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from app.models.schedule_result import ScheduleResult


class PerformanceChart(FigureCanvasQTAgg):
    """与应用主题一致的 Matplotlib 算法对比图。"""

    COLORS = ("#4F6EF7", "#16A36A", "#F59E0B")

    def __init__(self, mode: str, parent=None):
        if mode not in {"latency", "system"}:
            raise ValueError("未知性能图模式。")
        self.mode = mode
        self.figure = Figure(figsize=(6.0, 3.3), dpi=100)
        super().__init__(self.figure)
        self.setParent(parent)
        self.setMinimumHeight(285)
        self.update_results(())

    def update_results(self, results: tuple[ScheduleResult, ...]) -> None:
        self.figure.clear()
        self.figure.patch.set_facecolor("#FFFFFF")
        axis = self.figure.add_subplot(111)
        axis.set_facecolor("#FFFFFF")
        if not results:
            axis.axis("off")
            axis.text(
                0.5,
                0.5,
                "Run comparison to generate chart",
                ha="center",
                va="center",
                color="#98A2B3",
                fontsize=10,
            )
        elif self.mode == "latency":
            self._draw_latency(axis, results)
        else:
            self._draw_system(axis, results)
        self.figure.tight_layout(pad=1.7)
        self.draw_idle()

    def _draw_latency(self, axis, results: tuple[ScheduleResult, ...]) -> None:
        names = [self._short_name(result.algorithm_name) for result in results]
        x = list(range(len(results)))
        width = 0.24
        series = (
            ("Waiting", [result.average_waiting_time for result in results]),
            ("Turnaround", [result.average_turnaround_time for result in results]),
            ("Response", [result.average_response_time for result in results]),
        )
        for offset, ((label, values), color) in enumerate(zip(series, self.COLORS)):
            positions = [value + (offset - 1) * width for value in x]
            axis.bar(positions, values, width, label=label, color=color, alpha=0.9)
        self._style_axis(axis, names, x)
        axis.set_ylabel("Average ticks", color="#667085", fontsize=8)
        axis.legend(frameon=False, fontsize=8, ncol=3, loc="upper center")

    def _draw_system(self, axis, results: tuple[ScheduleResult, ...]) -> None:
        names = [self._short_name(result.algorithm_name) for result in results]
        x = list(range(len(results)))
        switches = [result.context_switches for result in results]
        utilization = [result.cpu_utilization * 100 for result in results]
        throughput = [result.throughput * 100 for result in results]
        axis.bar(x, switches, width=0.56, color="#8B5CF6", alpha=0.88, label="Switches")
        axis.set_ylabel("Context switches", color="#667085", fontsize=8)
        self._style_axis(axis, names, x)

        right = axis.twinx()
        right.plot(
            x,
            utilization,
            color="#16A36A",
            marker="o",
            linewidth=2.0,
            label="CPU utilization",
        )
        right.plot(
            x,
            throughput,
            color="#0EA5E9",
            marker="s",
            linestyle="--",
            linewidth=1.7,
            label="Throughput x100",
        )
        right.set_ylim(0, 108)
        right.set_ylabel("CPU use (%) / Throughput x100", color="#667085", fontsize=8)
        right.tick_params(colors="#98A2B3", labelsize=7)
        right.spines["top"].set_visible(False)
        right.spines["right"].set_color("#E7ECF3")

        handles1, labels1 = axis.get_legend_handles_labels()
        handles2, labels2 = right.get_legend_handles_labels()
        axis.legend(
            handles1 + handles2,
            labels1 + labels2,
            frameon=False,
            fontsize=8,
            ncol=2,
            loc="upper center",
        )

    @staticmethod
    def _style_axis(axis, names: list[str], x: list[int]) -> None:
        axis.set_xticks(x, names, rotation=22, ha="right", fontsize=7)
        axis.grid(axis="y", color="#E9EDF3", linewidth=0.8)
        axis.set_axisbelow(True)
        axis.tick_params(axis="y", colors="#98A2B3", labelsize=7)
        axis.tick_params(axis="x", colors="#667085")
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.spines["left"].set_color("#E7ECF3")
        axis.spines["bottom"].set_color("#E7ECF3")

    @staticmethod
    def _short_name(name: str) -> str:
        return {
            "Priority (Preemptive)": "Priority-P",
            "Round Robin": "RR",
        }.get(name, name)
