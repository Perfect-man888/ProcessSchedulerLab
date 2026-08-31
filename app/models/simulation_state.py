from dataclasses import dataclass, field
from enum import Enum

from app.models.process import Process
from app.models.schedule_segment import ScheduleSegment
from app.models.simulation_event import SimulationEvent


class SimulationStatus(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    FINISHED = "FINISHED"


@dataclass(slots=True)
class SimulationState:
    """SimulationService 将维护的唯一可变运行状态。"""

    clock: int = 0
    status: SimulationStatus = SimulationStatus.IDLE
    current_process: Process | None = None
    ready_queue: list[Process] = field(default_factory=list)
    new_processes: list[Process] = field(default_factory=list)
    finished_processes: list[Process] = field(default_factory=list)
    segments: list[ScheduleSegment] = field(default_factory=list)
    events: list[SimulationEvent] = field(default_factory=list)
    context_switches: int = 0
    busy_ticks: int = 0
    total_ticks: int = 0

    @property
    def cpu_utilization(self) -> float:
        if self.total_ticks == 0:
            return 0.0
        return self.busy_ticks / self.total_ticks

    @property
    def is_complete(self) -> bool:
        return (
            self.current_process is None
            and not self.ready_queue
            and not self.new_processes
        )

    def reset_runtime(self):
        self.clock = 0
        self.status = SimulationStatus.IDLE
        self.current_process = None
        self.ready_queue.clear()
        self.new_processes.clear()
        self.finished_processes.clear()
        self.segments.clear()
        self.events.clear()
        self.context_switches = 0
        self.busy_ticks = 0
        self.total_ticks = 0
