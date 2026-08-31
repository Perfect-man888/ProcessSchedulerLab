from collections.abc import Sequence

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from app.models.schedule_segment import ScheduleSegment


class GanttChart(QWidget):
    """轻量绘制型 CPU 甘特图，长时间线由外层滚动区域承载。"""

    _COLORS = (
        "#4F6EF7",
        "#16A36A",
        "#8B5CF6",
        "#0EA5E9",
        "#F59E0B",
        "#E5484D",
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self._segments: tuple[ScheduleSegment, ...] = ()
        self.setMinimumHeight(138)
        self.setObjectName("GanttChart")

    @property
    def segments(self) -> tuple[ScheduleSegment, ...]:
        return self._segments

    def set_segments(self, segments: Sequence[ScheduleSegment]) -> None:
        self._segments = tuple(segments)
        total_ticks = self._segments[-1].end if self._segments else 0
        self.setMinimumWidth(max(760, total_ticks * 56 + 48))
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(self.minimumWidth(), 138)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#F8F9FC"))

        if not self._segments:
            painter.setPen(QColor("#98A2B3"))
            painter.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.DemiBold))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "等待加载并运行调度实验",
            )
            return

        left = 22.0
        top = 22.0
        height = 68.0
        total_ticks = self._segments[-1].end
        usable_width = max(1.0, self.width() - left * 2)
        unit = usable_width / total_ticks

        painter.setFont(QFont("Microsoft YaHei UI", 9, QFont.Weight.DemiBold))
        for segment in self._segments:
            x = left + segment.start * unit
            width = max(2.0, segment.duration * unit - 3.0)
            rect = QRectF(x, top, width, height)
            color = self._segment_color(segment)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(rect, 9, 9)

            if width >= 48:
                title = segment.display_name
                if segment.queue_level is not None:
                    title += f" · Q{segment.queue_level}"
                painter.setPen(QColor("#FFFFFF"))
                painter.drawText(
                    rect.adjusted(5, 6, -5, -6),
                    Qt.AlignmentFlag.AlignCenter,
                    f"{title}\n{segment.start}–{segment.end}",
                )

        axis_y = top + height + 22
        painter.setPen(QPen(QColor("#D9E0EA"), 1))
        painter.drawLine(int(left), int(axis_y), int(left + usable_width), int(axis_y))
        painter.setFont(QFont("Microsoft YaHei UI", 8))
        painter.setPen(QColor("#667085"))

        boundaries = {0, total_ticks}
        for segment in self._segments:
            boundaries.add(segment.start)
            boundaries.add(segment.end)
        for tick in sorted(boundaries):
            x = left + tick * unit
            painter.drawLine(int(x), int(axis_y - 4), int(x), int(axis_y + 4))
            painter.drawText(
                QRectF(x - 18, axis_y + 5, 36, 18),
                Qt.AlignmentFlag.AlignHCenter,
                str(tick),
            )

        # 最右端用独立色标出仿真当前时刻，与普通分段边界区分。
        now_x = left + total_ticks * unit
        painter.setPen(QPen(QColor("#E5484D"), 2))
        painter.drawLine(int(now_x), int(top - 8), int(now_x), int(axis_y + 5))
        painter.setFont(QFont("Microsoft YaHei UI", 8, QFont.Weight.Bold))
        painter.setPen(QColor("#E5484D"))
        painter.drawText(
            QRectF(now_x - 42, top - 20, 40, 16),
            Qt.AlignmentFlag.AlignRight,
            "NOW",
        )

    def _segment_color(self, segment: ScheduleSegment) -> QColor:
        if segment.is_context_switch:
            return QColor("#F97316")
        if segment.is_idle:
            return QColor("#98A2B3")
        index = sum(ord(char) for char in segment.pid) % len(self._COLORS)
        color = QColor(self._COLORS[index])
        if segment.queue_level is not None:
            color = color.darker(100 + segment.queue_level * 12)
        return color
