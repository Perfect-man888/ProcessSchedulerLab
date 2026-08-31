PCB_HEADER_TOOLTIPS = {
    "PID": "进程编号：系统中用于唯一标识进程的编号。",
    "NAME": "进程名称：用于描述或区分模拟任务。",
    "STATE": "进程状态：当前生命周期状态，例如 READY、RUNNING、SUSPENDED 或 FINISHED。",
    "ARRIVAL": "到达时间：进程进入系统并开始具备参与调度条件的时间点。",
    "BURST": "CPU 服务时间：进程完成全部执行总共需要的 CPU 时间。",
    "REMAIN": "剩余执行时间：进程当前尚未完成的 CPU 服务时间。",
    "PRIORITY": "调度优先级：本系统数字越小表示优先级越高；Priority 与 Aging 使用该参数。",
    "MEMORY": "内存需求：进程运行期间申请的模拟内存；FINISHED 时仅保留需求记录，不表示仍占用。",
    "I/O": "I/O 资源：进程运行时所需的模拟 I/O 资源数量。",
    "DEADLINE": "截止时间：实时任务期望完成的绝对时间，主要用于 EDF 和实时性能评价。",
    "PERIOD": "任务周期：周期实时任务的运行周期，主要用于 RMS；Period 越短，固定优先级越高。",
}

METRIC_TOOLTIPS = {
    "Algorithm": "调度算法：本行实验结果对应的调度策略。",
    "Waiting Time": "等待时间：进程处于 READY 队列的累计 Tick；无 I/O 阻塞时等于周转时间减服务时间。",
    "Turnaround Time": "周转时间：从进程到达到最终完成的耗时，即 Finish Time - Arrival Time。",
    "Weighted Turnaround Time": "带权周转时间：周转时间 / CPU 服务时间，用于比较不同长度任务的相对延迟。",
    "Response Time": "响应时间：从进程到达到第一次获得 CPU 的等待时间。",
    "CPU Utilization": "CPU 利用率：Busy Tick 占从 T=0 到全部任务完成这一有效仿真时间的比例。",
    "Throughput": "吞吐量：单位模拟时间内完成的进程数量，即完成进程数 / Makespan。",
    "Context Switch": "上下文切换次数：CPU 从一个进程 PID 切换到另一不同 PID 的次数；IDLE 进入或退出不计。频繁切换通常增加开销，但可能改善分时响应。",
    "Makespan": "总完成时间：从 T=0 到最后一个任务完成经历的模拟时间，包含前导空闲和中途空闲。",
    "Deadline Miss": "截止期违约：进程完成时间超过 Deadline 时计为一次 Miss。",
    "Deadline Miss Rate": "截止期违约率：Miss 数 / 含 Deadline 的任务数。",
    "Deadline Satisfaction": "截止期满足率：按时完成的实时任务占含 Deadline 任务的比例。",
    "Quantum": "RR 时间片大小：每个进程最多连续运行指定 Tick 后重新参与调度。",
    "Aging": "老化机制：进程等待达到指定周期后提高有效优先级，用于缓解低优先级任务饥饿。",
    "MLFQ Boost": "优先级提升：按固定周期将未完成任务提升到最高队列，避免长任务长期滞留低队列。",
}

PERFORMANCE_TABLE_METRICS = (
    ("算法", "Algorithm"),
    ("等待", "Waiting Time"),
    ("周转", "Turnaround Time"),
    ("带权周转", "Weighted Turnaround Time"),
    ("响应", "Response Time"),
    ("CPU", "CPU Utilization"),
    ("吞吐量", "Throughput"),
    ("切换", "Context Switch"),
    ("Makespan", "Makespan"),
    ("Miss", "Deadline Miss"),
    ("Miss Rate", "Deadline Miss Rate"),
    ("满足率", "Deadline Satisfaction"),
)

ALGORITHM_THEORY_NOTES = {
    "FCFS": "实现简单，但长任务先到达时可能发生 Convoy Effect。",
    "SJF": "通常有利于短任务等待时间，但需要已知或估计服务时间。",
    "SRTF": "能抢占以响应新短任务，但抢占可能增加上下文切换。",
    "Priority": "优先处理重要任务，但静态优先级可能产生 Starvation。",
    "Round Robin": "强调分时响应与公平性，但过小 Quantum 会增加切换开销。",
    "EDF": "按绝对 Deadline 动态选择最紧迫的实时任务。",
    "RMS": "按 Period 设置固定优先级，Period 越短优先级越高。",
    "MLFQ": "通过多级队列和反馈机制兼顾交互任务与长任务。",
}

