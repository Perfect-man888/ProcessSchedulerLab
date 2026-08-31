from dataclasses import dataclass

from app.models.schedule_result import ScheduleResult


@dataclass(frozen=True, slots=True)
class AlgorithmSkip:
    algorithm_key: str
    display_name: str
    reason: str


@dataclass(frozen=True, slots=True)
class ExperimentReport:
    """同一输入数据集上的多算法比较结果。"""

    dataset_name: str
    results: tuple[ScheduleResult, ...]
    skipped: tuple[AlgorithmSkip, ...] = ()
    parameters: tuple[tuple[str, str], ...] = ()

    def __post_init__(self):
        if not self.dataset_name.strip():
            raise ValueError("实验数据集名称不能为空。")
        names = [result.algorithm_name for result in self.results]
        if len(names) != len(set(names)):
            raise ValueError("同一实验报告不能包含重复算法。")
        if len({name for name, _ in self.parameters}) != len(self.parameters):
            raise ValueError("实验参数名称不能重复。")

    def best(self, metric: str, *, maximize: bool = False) -> tuple[ScheduleResult, ...]:
        if not self.results:
            return ()
        values = [getattr(result, metric) for result in self.results]
        target = max(values) if maximize else min(values)
        return tuple(
            result
            for result in self.results
            if abs(getattr(result, metric) - target) < 1e-9
        )

    @property
    def observations(self) -> tuple[str, ...]:
        if not self.results:
            return ("没有可比较的算法结果。",)

        wait = self.best("average_waiting_time")
        response = self.best("average_response_time")
        switches = self.best("context_switches")
        utilization = self.best("cpu_utilization", maximize=True)
        throughput = self.best("throughput", maximize=True)
        makespan = self.best("makespan")
        notes = [
            f"在当前数据集“{self.dataset_name}”与当前参数下，"
            f"{self._names(wait)} 的平均等待时间最低，为 "
            f"{wait[0].average_waiting_time:.2f} Tick。",
            f"当前实验中，{self._names(response)} 的平均响应时间最低，为 "
            f"{response[0].average_response_time:.2f} Tick。",
            f"当前实验中，{self._names(switches)} 的上下文切换次数最少，为 "
            f"{switches[0].context_switches} 次；更少通常意味着调度开销更低，"
            "但应结合响应性与公平性共同评价。",
            f"当前实验中，{self._names(utilization)} 的 CPU 利用率最高，为 "
            f"{utilization[0].cpu_utilization * 100:.1f}%。",
            f"当前实验中，{self._names(throughput)} 的吞吐量最高，为 "
            f"{throughput[0].throughput:.3f} 个/Tick。",
            f"当前实验中，{self._names(makespan)} 的 Makespan 最短，为 "
            f"{makespan[0].makespan} Tick。",
        ]

        realtime = [
            result
            for result in self.results
            if result.algorithm_name in {"EDF", "RMS"}
        ]
        for result in realtime:
            notes.append(
                f"在当前数据集与当前参数下，{result.algorithm_name} 产生 "
                f"{result.deadline_miss_count} 个 "
                f"Deadline Miss，Miss Rate 为 {result.deadline_miss_rate * 100:.1f}%，"
                f"满足率为 {result.deadline_satisfaction_rate * 100:.1f}%。"
            )
        priority = [
            result for result in self.results if result.algorithm_name.startswith("Priority")
        ]
        if priority:
            notes.append(
                f"当前实验中，{priority[0].algorithm_name} 的最大等待时间为 "
                f"{priority[0].maximum_waiting_time} Tick，可用于观察潜在饥饿风险。"
            )
        if self.skipped:
            notes.append(
                "未纳入比较："
                + "；".join(f"{item.display_name}（{item.reason}）" for item in self.skipped)
                + "。"
            )
        return tuple(notes)

    @staticmethod
    def _names(results: tuple[ScheduleResult, ...]) -> str:
        if len(results) > 3:
            return f"全部 {len(results)} 种算法"
        return "、".join(result.algorithm_name for result in results)
