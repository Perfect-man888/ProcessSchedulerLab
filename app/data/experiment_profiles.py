from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExperimentProfile:
    """性能实验的数据集教学说明，供 UI 与报告提示统一复用。"""

    key: str
    name: str
    purpose: str
    recommended_algorithms: tuple[str, ...]
    metrics: tuple[str, ...]
    notes: str
    report_suggestion: str


EXPERIMENT_PROFILES = {
    profile.key: profile
    for profile in (
        ExperimentProfile(
            "current",
            "当前进程集",
            "使用进程管理页面建立的当前 PCB 进行综合实验，验证同一任务集在不同调度算法下的性能差异。",
            ("全部算法",),
            ("Waiting", "Turnaround", "Response", "CPU Utilization", "Context Switch", "Throughput"),
            "适合综合调度表现、用户自定义实验和多算法统一比较。",
            "用于说明自定义 PCB 的构成，并在相同初始数据与参数下比较多种调度策略。",
        ),
        ExperimentProfile(
            "classic_mix",
            "经典混合负载",
            "构造长短作业混合的典型任务集，比较不同调度策略对平均等待时间和平均周转时间的影响。",
            ("FCFS", "SJF", "SRTF"),
            ("Average Waiting", "Average Turnaround", "Response"),
            "适合观察长短作业调度差异，以及非抢占与抢占短作业策略的表现。",
            "用于比较 FCFS、SJF 与 SRTF 对平均等待时间和平均周转时间的影响。",
        ),
        ExperimentProfile(
            "interactive",
            "分时交互负载",
            "模拟大量短交互任务，验证分时系统中响应速度、公平性以及时间片设置对系统性能的影响。",
            ("Round Robin", "MLFQ"),
            ("Response", "Context Switch", "Quantum", "CPU Utilization", "Fairness"),
            "上下文切换更少通常开销更低，但应与交互响应和公平性共同评价。",
            "用于分析 RR 时间片大小对响应时间、周转时间和上下文切换次数的影响。",
        ),
        ExperimentProfile(
            "realtime",
            "实时截止期负载",
            "构造带 Deadline 的实时任务，比较实时调度算法对截止时间满足能力的影响。",
            ("EDF", "RMS"),
            ("Deadline Miss", "Miss Rate", "Deadline Satisfaction", "Response"),
            "EDF 使用动态截止期优先；RMS 使用周期固定优先级，结论仅针对当前任务集。",
            "用于比较 EDF 与 RMS 对实时任务截止时间满足能力的影响。",
        ),
        ExperimentProfile(
            "convoy",
            "护航效应负载",
            "验证长作业先到达时 FCFS 的 Convoy Effect，并比较短作业策略对等待和周转时间的改善。",
            ("FCFS", "SJF", "SRTF"),
            ("Average Waiting", "Average Turnaround", "Long-job Blocking"),
            "Convoy Effect：长任务先获得 CPU，使后续多个短任务排队，可能提高整体等待时间。",
            "用于验证 FCFS 护航效应，并与 SJF/SRTF 比较平均等待时间及平均周转时间。",
        ),
        ExperimentProfile(
            "priority_contention",
            "优先级竞争负载",
            "构造高、低优先级任务竞争场景，观察 Priority 调度中的饥饿风险与 Aging 的缓解作用。",
            ("Priority", "Priority + Aging"),
            ("Average Waiting", "Max Waiting", "Response", "Starvation Risk"),
            "静态优先级可能使低优先级任务长期等待；Aging 会随等待逐步提升有效优先级。",
            "用于比较不同 Aging 周期下最大等待时间，并分析其缓解饥饿风险的作用。",
        ),
        ExperimentProfile(
            "mlfq_mixed",
            "MLFQ 混合负载",
            "混合短交互任务和 CPU 密集型长任务，验证 MLFQ 对交互响应和长任务执行之间的平衡。",
            ("MLFQ", "Round Robin"),
            ("Response", "Waiting", "Queue Migration", "Context Switch", "Fairness"),
            "MLFQ 通过多级队列、降级和周期 Boost 平衡交互任务与长任务。",
            "用于分析 MLFQ 队列反馈与 Boost 对交互响应、公平性和切换开销的影响。",
        ),
        ExperimentProfile(
            "rms_periodic",
            "RMS 周期实时负载",
            "构造多个不同 Period 的周期实时任务，验证 RMS 中周期越短、固定优先级越高的调度特性。",
            ("RMS", "EDF"),
            ("Deadline Satisfaction", "Deadline Miss", "Response", "Context Switch"),
            "当前实现以周期任务的单次作业样本比较 RMS 固定优先级与 EDF 动态优先级。",
            "用于比较 RMS 与 EDF 的截止期满足率，并解释 Period 对 RMS 固定优先级的影响。",
        ),
    )
}

