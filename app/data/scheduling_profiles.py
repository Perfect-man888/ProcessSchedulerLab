"""课程系统类型、算法说明和实验展示元数据的单一配置源。"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SystemTypeProfile:
    key: str
    name: str
    short_name: str
    description: str
    algorithm_keys: tuple[str, ...]
    default_algorithm: str
    focus_metrics: tuple[str, ...]
    recommended_datasets: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AlgorithmProfile:
    key: str
    name: str
    short_name: str
    description: str
    parameter_hint: str


ALGORITHM_PROFILES = {
    "fcfs": AlgorithmProfile(
        "fcfs",
        "FCFS · 先来先服务",
        "FCFS",
        "按就绪队列到达顺序执行；实现简单、公平直观，但可能产生护航效应。",
        "此算法无需额外参数",
    ),
    "sjf": AlgorithmProfile(
        "sjf",
        "SJF · 短作业优先",
        "SJF",
        "优先执行服务时间较短的进程，通常可降低平均等待和周转时间；长进程可能等待较久。",
        "此算法无需额外参数",
    ),
    "srtf": AlgorithmProfile(
        "srtf",
        "SRTF · 最短剩余时间",
        "SRTF",
        "SJF 的抢占式版本；当更短的任务就绪时，可以抢占当前进程。",
        "此算法无需额外参数",
    ),
    "priority": AlgorithmProfile(
        "priority",
        "Priority · 优先级调度",
        "Priority",
        "通用优先级调度扩展；数字越小优先级越高，支持 Aging 缓解低优先级进程饥饿。",
        "配置抢占方式与 Aging 周期",
    ),
    "round_robin": AlgorithmProfile(
        "round_robin",
        "Round Robin · 时间片轮转",
        "Round Robin",
        "每个进程最多连续运行一个 Quantum；时间片越小响应越快，但上下文切换通常越多。",
        "配置时间片 Quantum（建议 1–8 Tick）",
    ),
    "mlfq": AlgorithmProfile(
        "mlfq",
        "MLFQ · 多级反馈队列",
        "MLFQ",
        "使用多级队列和不同时间片动态调整优先级，兼顾短交互任务与长 CPU 密集任务。",
        "配置三级队列时间片与 Priority Boost 周期",
    ),
    "edf": AlgorithmProfile(
        "edf",
        "EDF · 最早截止时间优先",
        "EDF",
        "动态实时调度；优先执行绝对 Deadline 最早的任务，重点观察 Deadline Miss 与满足率。",
        "需要全部进程填写有效 Deadline",
    ),
    "rms": AlgorithmProfile(
        "rms",
        "RMS · 单调速率调度",
        "RMS",
        "固定优先级实时调度；Period 越短、执行频率越高，RMS 优先级越高。",
        "需要全部进程填写有效 Period",
    ),
}


SYSTEM_TYPE_PROFILES = (
    SystemTypeProfile(
        "batch",
        "批处理系统",
        "批处理",
        "适合成批提交、强调吞吐量和平均周转时间的任务。本实验使用 FCFS、SJF、SRTF 以及 Priority 比较调度特性。",
        ("fcfs", "sjf", "srtf", "priority"),
        "fcfs",
        ("平均等待", "平均周转", "带权周转", "吞吐量", "CPU 利用率"),
        ("经典混合负载", "护航效应负载", "优先级竞争负载"),
    ),
    SystemTypeProfile(
        "timesharing",
        "分时系统",
        "分时",
        "强调多个任务公平共享 CPU，并尽可能提高交互响应速度。本实验使用 Round Robin 和 MLFQ 模拟典型分时调度。",
        ("round_robin", "mlfq"),
        "round_robin",
        ("平均响应", "上下文切换", "公平性", "CPU 利用率", "时间片影响"),
        ("分时交互负载", "MLFQ 混合负载"),
    ),
    SystemTypeProfile(
        "realtime",
        "实时系统",
        "实时",
        "强调任务在规定截止时间内完成。本实验使用 EDF 与 RMS 比较动态截止期调度和固定周期优先级调度。",
        ("edf", "rms"),
        "edf",
        ("Deadline Miss", "Miss Rate", "满足率", "平均响应", "实时任务完成率"),
        ("实时截止期负载", "RMS 周期实时负载"),
    ),
)

SYSTEM_TYPE_BY_KEY = {profile.key: profile for profile in SYSTEM_TYPE_PROFILES}
ALL_ALGORITHM_KEYS = (
    "fcfs",
    "sjf",
    "srtf",
    "priority",
    "round_robin",
    "edf",
    "rms",
    "mlfq",
)

ADVANCED_PROFILE = SystemTypeProfile(
    "all",
    "全部算法 / 高级模式",
    "高级",
    "用于跨系统算法总览和高级对比；课程验收主路径仍建议按批处理、分时、实时系统分类演示。",
    ALL_ALGORITHM_KEYS,
    "fcfs",
    ("等待", "周转", "响应", "CPU 利用率", "上下文切换"),
    ("经典混合负载", "实时截止期负载"),
)

ANALYSIS_PROFILES = (ADVANCED_PROFILE, *SYSTEM_TYPE_PROFILES)
ANALYSIS_PROFILE_BY_KEY = {profile.key: profile for profile in ANALYSIS_PROFILES}

COURSE_COVERAGE_TEXT = (
    "✓ 批处理：FCFS / SJF / SRTF / Priority\n"
    "✓ 分时：Round Robin / MLFQ\n"
    "✓ 实时：EDF / RMS\n"
    "✓ 动态 CPU、Ready Queue、时间线与 Context Switch"
)


def algorithms_for(system_type_key: str) -> tuple[AlgorithmProfile, ...]:
    """返回指定系统类型的有序算法配置。"""

    profile = ANALYSIS_PROFILE_BY_KEY[system_type_key]
    return tuple(ALGORITHM_PROFILES[key] for key in profile.algorithm_keys)
