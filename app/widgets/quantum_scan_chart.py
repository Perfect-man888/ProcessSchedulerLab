from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from app.models.schedule_result import ScheduleResult


class QuantumScanChart(FigureCanvasQTAgg):
    """RR 时间片灵敏度折线图：横轴 Quantum，双轴展示时延与切换开销。"""

    def __init__(self, parent=None):
        self.figure = Figure(figsize=(6.0, 3.3), dpi=100)
        super().__init__(self.figure)
        self.setParent(parent)
        self.setMinimumHeight(285)
        self.set_data(())

    def set_data(self, data: tuple[tuple[int, ScheduleResult], ...]) -> None:
        self.figure.clear()
        self.figure.patch.set_facecolor("#FFFFFF")
        axis = self.figure.add_subplot(111)
        axis.set_facecolor("#FFFFFF")
        if not data:
            axis.axis("off")
            axis.text(
                0.5,
                0.5,
                "Run quantum scan to generate chart",
                ha="center",
                va="center",
                color="#98A2B3",
                fontsize=10,
            )
        else:
            self._draw_scan(axis, data)
        self.figure.tight_layout(pad=1.7)
        self.draw_idle()

    def _draw_scan(self, axis, data: tuple[tuple[int, ScheduleResult], ...]) -> None:
        quanta = [quantum for quantum, _ in data]
        turnaround = [result.average_turnaround_time for _, result in data]
        response = [result.average_response_time for _, result in data]

        axis.plot(
            quanta,
            turnaround,
            color="#4F6EF7",
            marker="o",
            linewidth=2.0,
            label="Turnaround",
        )
        axis.plot(
            quanta,
            response,
            color="#F59E0B",
            marker="s",
            linestyle="--",
            linewidth=1.8,
            label="Response",
        )
        axis.set_xlabel("Quantum (ticks)", color="#667085", fontsize=8)
        axis.set_ylabel("Average ticks", color="#667085", fontsize=8)
        axis.grid(axis="y", color="#E9EDF3", linewidth=0.8)
        axis.set_axisbelow(True)
        axis.tick_params(axis="y", colors="#98A2B3", labelsize=7)
        axis.tick_params(axis="x", colors="#667085")
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.spines["left"].set_color("#E7ECF3")
        axis.spines["bottom"].set_color("#E7ECF3")

        right = axis.twinx()
        right.plot(
            quanta,
            [result.context_switches for _, result in data],
            color="#16A36A",
            marker="^",
            linewidth=1.7,
            label="Switches",
        )
        right.set_ylabel("Context switches", color="#667085", fontsize=8)
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
            ncol=3,
            loc="upper center",
        )
