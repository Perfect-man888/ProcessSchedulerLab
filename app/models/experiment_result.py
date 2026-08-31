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

    def __post_init__(self):
        if not self.dataset_name.strip():
            raise ValueError("实验数据集名称不能为空。")
        names = [result.algorithm_name for result in self.results]
        if len(names) != len(set(names)):
            raise ValueError("同一实验报告不能包含重复算法。")

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
        notes = [
            f"{self._names(wait)} 的平均等待时间最低。",
            f"{self._names(response)} 的平均响应时间最低。",
            f"{self._names(switches)} 的上下文切换次数最少。",
            f"{self._names(utilization)} 的 CPU 利用率最高。",
            f"{self._names(throughput)} 的吞吐量最高。",
        ]

        realtime = [result for result in self.results if result.algorithm_name == "EDF"]
        if realtime:
            result = realtime[0]
            notes.append(
                f"EDF 本次产生 {result.deadline_miss_count} 个 Deadline Miss，"
                f"Miss Rate 为 {result.deadline_miss_rate * 100:.1f}%。"
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
