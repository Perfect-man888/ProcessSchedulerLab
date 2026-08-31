from PySide6.QtCore import QObject, QTimer, Signal

from app.models.process import Process, ProcessState
from app.models.schedule_result import ProcessMetrics, ScheduleResult
from app.models.schedule_segment import ScheduleSegment, append_segment
from app.models.simulation_event import SimulationEvent, SimulationEventType
from app.models.simulation_state import SimulationState, SimulationStatus
from app.schedulers import BaseScheduler, PreemptionReason, create_scheduler
from app.services.process_manager import ProcessManager


class SimulationService(QObject):
    """以统一逐 Tick 语义驱动任意 BaseScheduler 的仿真引擎。"""

    changed = Signal()
    event_occurred = Signal(object)
    status_changed = Signal(str)
    completed = Signal(object)

    def __init__(
        self,
        process_manager: ProcessManager,
        parent=None,
        *,
        base_interval_ms: int = 800,
    ):
        super().__init__(parent)
        if base_interval_ms <= 0:
            raise ValueError("基础 Tick 间隔必须大于 0。")

        self.process_manager = process_manager
        self.resource_manager = process_manager.resource_manager
        self.state = SimulationState()

        self._scheduler: BaseScheduler | None = None
        self._loaded = False
        self._loaded_process_ids: set[str] = set()
        self._last_running_pid: str | None = None
        self._preserve_next_segment_boundary = False
        self._base_interval_ms = base_interval_ms
        self._speed = 1.0

        self.timer = QTimer(self)
        self.timer.setInterval(base_interval_ms)
        self.timer.timeout.connect(self._on_timeout)

    @property
    def scheduler(self) -> BaseScheduler | None:
        return self._scheduler

    @property
    def speed(self) -> float:
        return self._speed

    def load(
        self,
        scheduler: BaseScheduler | str,
        **scheduler_options,
    ) -> None:
        if self.state.status is SimulationStatus.RUNNING:
            raise ValueError("仿真运行中不能切换算法，请先暂停或重置。")

        processes = self.process_manager.processes
        if not processes:
            raise ValueError("请先创建至少一个进程再加载调度实验。")

        selected = (
            create_scheduler(scheduler, **scheduler_options)
            if isinstance(scheduler, str)
            else scheduler
        )
        if scheduler_options and not isinstance(scheduler, str):
            raise ValueError("传入调度器实例时不能再提供构造参数。")
        if not isinstance(selected, BaseScheduler):
            raise TypeError("scheduler 必须是算法键或 BaseScheduler 实例。")

        selected.validate_processes(processes)
        self._scheduler = selected
        self._loaded = True
        self._restore_runtime(SimulationEventType.LOAD)

    def reset(self) -> None:
        self._require_loaded()
        self._restore_runtime(SimulationEventType.RESET)

    def unload(self) -> None:
        """解除当前算法绑定，保留进程配置与资源占用。"""

        self.timer.stop()
        self.state.reset_runtime()
        self._scheduler = None
        self._loaded = False
        self._loaded_process_ids.clear()
        self._last_running_pid = None
        self._preserve_next_segment_boundary = False
        self.process_manager.simulation_time = 0
        self.process_manager.changed.emit()
        self.changed.emit()

    def _restore_runtime(self, event_type: SimulationEventType) -> None:
        self.timer.stop()
        self.state.reset_runtime()
        self._scheduler.reset()
        self._last_running_pid = None
        self._preserve_next_segment_boundary = False

        self.resource_manager.reset()
        processes = sorted(
            self.process_manager.processes,
            key=lambda process: (process.arrival_time, process.pid),
        )
        self._loaded_process_ids = {process.pid for process in processes}

        for process in processes:
            process.remaining_time = process.burst_time
            process.start_time = None
            process.finish_time = None
            process.waiting_time = None
            process.turnaround_time = None
            process.weighted_turnaround_time = None
            process.response_time = None
            process.state = ProcessState.NEW
            self.resource_manager.allocate(process.memory_mb, process.io_devices)
            process.resources_allocated = True

        self.state.new_processes.extend(processes)
        self.process_manager.simulation_time = 0
        self._emit_event(event_type, detail=f"{self._scheduler.name} 实验已就绪")
        self._admit_arrivals()
        self.process_manager.changed.emit()
        self._set_status(SimulationStatus.IDLE)
        self.changed.emit()

    def set_speed(self, multiplier: float) -> None:
        if multiplier <= 0:
            raise ValueError("仿真速度必须大于 0。")
        self._speed = float(multiplier)
        self.timer.setInterval(max(1, round(self._base_interval_ms / self._speed)))
        self.changed.emit()

    def start(self) -> None:
        self._require_loaded()
        self._require_runtime_consistent()
        if self.state.status is SimulationStatus.FINISHED:
            raise ValueError("实验已完成，请先重置。")
        if self.state.status is SimulationStatus.RUNNING:
            return
        self._set_status(SimulationStatus.RUNNING)
        self.timer.start()

    def pause(self) -> None:
        if self.state.status is not SimulationStatus.RUNNING:
            raise ValueError("只有运行中的仿真可以暂停。")
        self.timer.stop()
        self._set_status(SimulationStatus.PAUSED)
        self._emit_event(SimulationEventType.PAUSE, detail="仿真已暂停")
        self.changed.emit()

    def resume(self) -> None:
        if self.state.status is not SimulationStatus.PAUSED:
            raise ValueError("只有暂停中的仿真可以继续。")
        self._emit_event(SimulationEventType.RESUME, detail="仿真继续运行")
        self._set_status(SimulationStatus.RUNNING)
        self.timer.start()

    def step(self) -> bool:
        self._require_loaded()
        self._require_runtime_consistent()
        if self.state.status is SimulationStatus.RUNNING:
            raise ValueError("连续运行时不能单步，请先暂停。")
        if self.state.status is SimulationStatus.FINISHED:
            return False

        advanced = self._advance_one_tick()
        if self.state.status is not SimulationStatus.FINISHED:
            self._set_status(SimulationStatus.PAUSED)
        return advanced

    def _on_timeout(self) -> None:
        if self.state.status is SimulationStatus.RUNNING:
            try:
                self._require_runtime_consistent()
                self._advance_one_tick()
            except ValueError as error:
                self.timer.stop()
                self._set_status(SimulationStatus.PAUSED)
                self._emit_event(
                    SimulationEventType.PAUSE,
                    detail=str(error),
                )

    def _advance_one_tick(self) -> bool:
        self._admit_arrivals()
        self._apply_policy_preemption()
        self._dispatch_if_needed()

        current = self.state.current_process
        if current is None:
            if not self.state.new_processes and not self.state.ready_queue:
                self._handle_no_runnable_processes()
                return False
            self._run_idle_tick()
        else:
            self._run_process_tick(current)

        self._finish_or_pause_if_needed()
        self.process_manager.changed.emit()
        self.changed.emit()
        return True

    def _admit_arrivals(self) -> None:
        arrivals = [
            process
            for process in self.state.new_processes
            if process.arrival_time <= self.state.clock
        ]
        for process in arrivals:
            self.state.new_processes.remove(process)
            process.state = ProcessState.READY
            self.state.ready_queue.append(process)
            self._scheduler.on_ready(process, self.state.clock)
            self._emit_event(
                SimulationEventType.ARRIVE,
                process.pid,
                "NEW → READY",
            )

    def _apply_policy_preemption(self) -> None:
        current = self.state.current_process
        if current is None:
            return
        reason = self._scheduler.preemption_reason(
            current,
            self.state.ready_queue,
            self.state.clock,
        )
        if reason is not None:
            self._preempt_current(reason)

    def _preempt_current(self, reason: PreemptionReason) -> None:
        process = self.state.current_process
        if process is None:
            return
        self._scheduler.on_preempt(process, self.state.clock, reason)
        process.state = ProcessState.READY
        self.state.ready_queue.append(process)
        self.state.current_process = None
        event_type = (
            SimulationEventType.TIMESLICE
            if reason is PreemptionReason.TIME_SLICE
            else SimulationEventType.PREEMPT
        )
        self._emit_event(event_type, process.pid, reason.value)
        self._preserve_next_segment_boundary = (
            reason is PreemptionReason.TIME_SLICE
        )

    def _dispatch_if_needed(self) -> None:
        if self.state.current_process is not None:
            return
        selected = self._scheduler.choose_next(
            self.state.ready_queue,
            None,
            self.state.clock,
        )
        if selected is None:
            return

        self.state.ready_queue.remove(selected)
        selected.state = ProcessState.RUNNING
        if selected.start_time is None:
            selected.start_time = self.state.clock
        if (
            self._last_running_pid is not None
            and self._last_running_pid != selected.pid
        ):
            self.state.context_switches += 1
        self._last_running_pid = selected.pid
        self.state.current_process = selected
        self._scheduler.on_dispatch(selected, self.state.clock)
        self._emit_event(
            SimulationEventType.DISPATCH,
            selected.pid,
            f"{selected.pid} 获得 CPU",
        )

    def _run_idle_tick(self) -> None:
        if not self.state.segments or not self.state.segments[-1].is_idle:
            self._emit_event(SimulationEventType.IDLE, detail="CPU 空闲")
        append_segment(
            self.state.segments,
            ScheduleSegment(self.state.clock, self.state.clock + 1),
        )
        self.state.total_ticks += 1
        self._advance_clock()

    def _run_process_tick(self, process: Process) -> None:
        level = self._scheduler.queue_level(process)
        process.remaining_time -= 1
        self._scheduler.on_tick(process, self.state.clock)
        append_segment(
            self.state.segments,
            ScheduleSegment(
                self.state.clock,
                self.state.clock + 1,
                process.pid,
                queue_level=level,
            ),
            preserve_boundary=self._preserve_next_segment_boundary,
        )
        self._preserve_next_segment_boundary = False
        self.state.busy_ticks += 1
        self.state.total_ticks += 1
        self._advance_clock()

        if process.remaining_time == 0:
            self._finish_process(process)
            return

        reason = self._scheduler.preemption_reason(
            process,
            self.state.ready_queue,
            self.state.clock,
        )
        if reason is PreemptionReason.TIME_SLICE:
            self._preempt_current(reason)

    def _finish_process(self, process: Process) -> None:
        process.finish_time = self.state.clock
        process.state = ProcessState.FINISHED
        process.turnaround_time = process.finish_time - process.arrival_time
        process.waiting_time = process.turnaround_time - process.burst_time
        process.weighted_turnaround_time = (
            process.turnaround_time / process.burst_time
        )
        process.response_time = process.start_time - process.arrival_time
        self._scheduler.on_finish(process, self.state.clock)
        self.state.finished_processes.append(process)
        self.state.current_process = None

        if process.resources_allocated:
            self.resource_manager.release(process.memory_mb, process.io_devices)
            process.resources_allocated = False

        self._emit_event(
            SimulationEventType.FINISH,
            process.pid,
            f"完成于 T={self.state.clock}，资源已释放",
        )

    def _advance_clock(self) -> None:
        self.state.clock += 1
        self.process_manager.simulation_time = self.state.clock

    def _finish_or_pause_if_needed(self) -> None:
        if self.process_manager.processes and all(
            process.state is ProcessState.FINISHED
            for process in self.process_manager.processes
        ):
            self.timer.stop()
            self._set_status(SimulationStatus.FINISHED)
            self.completed.emit(self.build_result())
        elif (
            self.state.current_process is None
            and not self.state.ready_queue
            and not self.state.new_processes
        ):
            self._handle_no_runnable_processes()

    def _handle_no_runnable_processes(self) -> None:
        self.timer.stop()
        self._set_status(SimulationStatus.PAUSED)

    def suspend_process(self, pid: str) -> None:
        self._require_loaded()
        process = self.process_manager.get_process(pid)
        if process is None:
            raise ValueError(f"未找到进程 {pid}。")

        self.state.ready_queue = [p for p in self.state.ready_queue if p.pid != pid]
        self.state.new_processes = [p for p in self.state.new_processes if p.pid != pid]
        if self.state.current_process is process:
            self.state.current_process = None
        self.process_manager.suspend_process(pid)
        self._emit_event(
            SimulationEventType.SUSPEND,
            pid,
            "进程已退出 CPU 候选集合",
            publish_activity=False,
        )
        self.changed.emit()

    def activate_process(self, pid: str) -> None:
        self._require_loaded()
        process = self.process_manager.get_process(pid)
        if process is None:
            raise ValueError(f"未找到进程 {pid}。")

        if process.arrival_time <= self.state.clock:
            target_state = ProcessState.READY
            self.process_manager.activate_process(pid, target_state)
            self.state.ready_queue.append(process)
            self._scheduler.on_ready(process, self.state.clock)
        else:
            target_state = ProcessState.NEW
            self.process_manager.activate_process(pid, target_state)
            self.state.new_processes.append(process)
            self.state.new_processes.sort(
                key=lambda item: (item.arrival_time, item.pid)
            )

        self._emit_event(
            SimulationEventType.ACTIVATE,
            pid,
            f"SUSPENDED → {process.state.value}",
            publish_activity=False,
        )
        self.process_manager.changed.emit()
        self.changed.emit()

    def build_result(self) -> ScheduleResult:
        self._require_loaded()
        if not self.process_manager.processes or not all(
            process.state is ProcessState.FINISHED
            for process in self.process_manager.processes
        ):
            raise ValueError("仿真尚未完成，不能生成最终结果。")
        metrics = tuple(
            ProcessMetrics.from_process(process)
            for process in sorted(self.process_manager.processes, key=lambda p: p.pid)
        )
        return ScheduleResult(
            algorithm_name=self._scheduler.name,
            segments=tuple(self.state.segments),
            process_metrics=metrics,
            events=tuple(self.state.events),
            context_switches=self.state.context_switches,
        )

    def _emit_event(
        self,
        event_type: SimulationEventType,
        pid: str | None = None,
        detail: str = "",
        *,
        publish_activity: bool = True,
    ) -> SimulationEvent:
        event = SimulationEvent(self.state.clock, event_type, pid, detail)
        self.state.events.append(event)
        self.event_occurred.emit(event)
        if publish_activity:
            self.process_manager.record_activity(
                event_type.value,
                pid or "—",
                detail,
            )
        return event

    def _set_status(self, status: SimulationStatus) -> None:
        if self.state.status is status:
            return
        self.state.status = status
        self.status_changed.emit(status.value)
        self.changed.emit()

    def _require_loaded(self) -> None:
        if not self._loaded or self._scheduler is None:
            raise ValueError("尚未加载调度实验。")

    def _require_runtime_consistent(self) -> None:
        processes = self.process_manager.processes
        if {process.pid for process in processes} != self._loaded_process_ids:
            raise ValueError("进程集合已发生变化，请重新加载或重置实验。")

        expected_states: dict[str, ProcessState] = {}
        expected_states.update(
            (process.pid, ProcessState.NEW) for process in self.state.new_processes
        )
        expected_states.update(
            (process.pid, ProcessState.READY) for process in self.state.ready_queue
        )
        expected_states.update(
            (process.pid, ProcessState.FINISHED)
            for process in self.state.finished_processes
        )
        if self.state.current_process is not None:
            expected_states[self.state.current_process.pid] = ProcessState.RUNNING

        for process in processes:
            expected = expected_states.get(process.pid)
            if process.state is ProcessState.SUSPENDED and expected is None:
                continue
            if expected is not process.state:
                raise ValueError(
                    f"进程 {process.pid} 状态已在仿真外部改变，"
                    "请重新加载或重置实验。"
                )
