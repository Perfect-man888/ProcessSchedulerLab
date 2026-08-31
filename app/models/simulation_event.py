from dataclasses import dataclass
from enum import Enum


class SimulationEventType(str, Enum):
    LOAD = "LOAD"
    ARRIVE = "ARRIVE"
    DISPATCH = "DISPATCH"
    PREEMPT = "PREEMPT"
    TIMESLICE = "TIMESLICE"
    SUSPEND = "SUSPEND"
    ACTIVATE = "ACTIVATE"
    REVOKE = "REVOKE"
    FINISH = "FINISH"
    DEADLINE_MISS = "DEADLINE_MISS"
    AGING = "AGING"
    BOOST = "BOOST"
    CONTEXT_SWITCH = "CONTEXT_SWITCH"
    IO_REQUEST = "IO_REQUEST"
    IO_COMPLETE = "IO_COMPLETE"
    IDLE = "IDLE"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    RESET = "RESET"

    @property
    def display_name(self) -> str:
        names = {
            SimulationEventType.LOAD: "加载实验",
            SimulationEventType.ARRIVE: "进程到达",
            SimulationEventType.DISPATCH: "CPU 派发",
            SimulationEventType.PREEMPT: "抢占",
            SimulationEventType.TIMESLICE: "时间片结束",
            SimulationEventType.SUSPEND: "挂起",
            SimulationEventType.ACTIVATE: "激活",
            SimulationEventType.REVOKE: "撤销",
            SimulationEventType.FINISH: "完成",
            SimulationEventType.DEADLINE_MISS: "截止期违约",
            SimulationEventType.AGING: "优先级老化",
            SimulationEventType.BOOST: "队列提升",
            SimulationEventType.CONTEXT_SWITCH: "上下文切换",
            SimulationEventType.IO_REQUEST: "I/O 请求",
            SimulationEventType.IO_COMPLETE: "I/O 完成",
            SimulationEventType.IDLE: "CPU 空闲",
            SimulationEventType.PAUSE: "暂停",
            SimulationEventType.RESUME: "继续",
            SimulationEventType.RESET: "重置",
        }
        return names[self]


@dataclass(frozen=True, slots=True)
class SimulationEvent:
    """仿真过程中可复现、可导出的结构化事件。"""

    tick: int
    event_type: SimulationEventType
    pid: str | None = None
    detail: str = ""

    def __post_init__(self):
        if self.tick < 0:
            raise ValueError("事件时间不能小于 0。")
        if self.pid is not None and not self.pid.strip():
            raise ValueError("事件 PID 不能为空字符串。")

    @property
    def time_text(self) -> str:
        return f"T={self.tick}"
