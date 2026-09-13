# Gate 1：计量闭合、固定总显存、native batch 与并发发布

2026-09-13，用户要求“补齐”后、实现和 GPU 测量前登记。
保留 Gate 0 源码及所有观测。此轮是实验能力和普通强控制，不提出新算法。

## 新发现的旧口径问题

Gate 0 的 `OwnedEpoch::snapshot()` 每次调用 `OwnedHostDB::view()`，重新
遍历 popcount 数组建立 cumulative counts；它发生在 `QueryRuntime::run()`
内部服务计时之前。旧 service_ms 因而不包含这段 O(N) CPU 元数据工作。
旧报告不能当作 epoch 获取到完整输出返回的真实端到端请求延迟。
Gate 1 对不可变 run 一次缓存 bounds metadata，测量从 acquire epoch 到完整
结果物化/完成的整个路径，另外保留 kernel 子时钟；不与旧数字计算加速比。

## 本轮交付门禁

1. 内存：context/driver 预热后观察整卡已用值，预留安全余量，并一次分配固定
   device arena；run、descriptor、查询/结果 workspace 都从该 arena 分配。
   arena 占用与实际有效对象占用分列。全程观察整卡已用值，超过声明总预算
   立即使该尝试失效/停止，不能把显式分配额度叫成总 VRAM。
2. 版本：按唯一 run 身份统计 current-only、reader-only、shared、unreferenced
   可回收字节，不能累加两个 epoch 的逻辑大小重复计算共享 runs。回收后
   arena 空闲量必须恢复。记录从维护准备、可发布、最后 reader 完成到实际
   回收完成的时间线，单列 CPU staging/H2D/merge/reclaim。
3. 正确性：原子发布失败不改变 current epoch；测试分配/复制前后注入失败、
   超预算、输出溢出、旧 reader 仍有未完成 GPU 工作时发布/回收。人为 gate
   只用于正确性，不混入性能/维护暴露实验。memcheck、synccheck、leak-check
   和适用的 racecheck 分开记录，CPU 所有权测试不能替代 GPU 门禁。
4. 执行：共同 native batching，Q=1/8/64。一个融合 kernel 处理整批 query/run
   descriptors，共用完整输出 append buffer，并保留 query ID；不是 Q 次
   同步调用的包装。所有策略重新在这一共同执行层计时。

## 数据与普通控制

同一固定 SureChEMBL 指纹 artifact、六次自然到达时间线；使用相同稳定 ID
哈希，从 1/38 样本扩为 1/4 样本（约 10M），不改变指纹、不复制假 ID。
64 个非空固定查询：32 base，前五次 delta 各 4，最后 delta 12，按 cohort
中均匀间隔行选择。保持来源标签，不能叫作外部 holdout。
阈值 0.7/0.8，完整 uint64 ID/intersection/union，任何 batch 溢出明确失败。

普通控制仍为 all-delta、periodic2、相邻 doubling size-tiered、compact。
对合并不够预算时采用明示的普通 fallback：推迟合并、在可容纳时发布 delta；
若连 delta 也不可容纳，拒绝发布并保留旧 epoch。不能让某个策略通过超预算
或提前释放 reader 来获得优势。控制参数固定；没有完成独立开发 trace 调参
前，报告仍称为预设控制，不冒充调优最强基线。

总显存上限预设 roomy=2048 MiB、constrained=1280 MiB（含 arena 和 context/
driver 等观察开销，留 64 MiB 余量）。若 context 基线不允许装入必要输入，
记录不适用/拒绝，不偷偷放大预算。小 fixture 与百万行用于门禁，千万行计时。
四个独立进程轮换策略顺序，保留所有样本；以进程为统计单位，报告逐进程值。

## 并发归因分开

- 静态对照：固定初始可见 epoch，无 writer。
- Shadow：读者始终查同一初始 epoch；writer 对同一真实发布序列进行等量
  host 构建、staging 和 H2D 到临时 arena 空间，不让新数据变为可见。
  校验维护复制/构建工作量与 roomy 实际增长组相符，shadow 不证明发布正确性。
- 实际增长：每请求原子 acquire 一次 epoch，允许 writer 发布并保留旧 owner
  到输出传输完成。结果对相应 epoch 的独立 CPU oracle 逐条核验。

预设请求驱动的发布节奏和固定 batch 数；不以 sleep/空转增加性能实验的上传
持续时间。记录每个请求/维护事件时间戳、重叠请求数、可见 epoch、queue/backlog。
自然小增量若曝光不足就报告不足；如需重复事件增加统计暴露，必须作为独立
事件重复列出，不能冒充更多自然连续版本。仅对 roomy 组做 shadow/实际增长
干扰对照，以免 shadow 多保留的初始库造成预算口径混淆。

## 资源与停止

仅用 pro6000-8 上当时空闲的一张卡；原 GPU 6 当前被其他任务占用，先申请
空闲 GPU 0 的本地协调锁并复查 UUID/进程。既有 TIDE global lock 和对应单卡
lock 均保持 nonblocking，不替换、不 chmod、不删除。每 GPU 子进程最多
10 分钟，首轮 GPU 总命令最多 30 分钟；CPU 准备/全 oracle 各最多 10 分钟。
 不动其他任务，不改时钟/功率、不启端口。任何正确性、超预算或外来占用失败
 停止本次计时，保留失败记录，再决定最小修订，不能用重跑挑选漂亮结果。

## 实现细化（首个 GPU 调用前）

使用一次登记锁对 acquire/register 与 publish 排序，原子 shared ownership
保留完整请求所有权。发布时 UID 集合按当前 writer epoch / 当前在途 reader
分类，显存余额单列 writer 暂存及 shadow 固定基库的其他持有，不把它们叫成
reader-only。固定 arena 的物理预留直到进程结束才归还 CUDA；这里的逐 run
实际回收是地址区间可重新分配，不是把整卡占用降下来。

并发每组为单 reader 的 closed-loop 256 个 batch；第 16/48/80/112/144/176
个完成后的下一次调度触发六个维护作业。query queue=0 是闭环设计，不代表
开放队列无排队；维护队列独立计时。CPU oracle 比较在请求服务计时之外，
会产生调度间隙，完整请求/维护时间戳用于核实实际重叠。静态/shadow/growth
每次重新建 base；shadow 内部继续执行同一 writer 版本链，读者保持初始版本。

模块先预热再固定 arena，预留额外空间遵循 NVIDIA 的
[CUDA lazy-loading 说明](https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/lazy-loading.html)。
正确性 gate 的新 GPU 数据提前全部准备完毕；host callback 仅等 CPU 指针
发布，释放 gate 前不调用任何可能等待该 stream 的 CUDA 操作，遵循
[cudaLaunchHostFunc 限制](https://docs.nvidia.com/cuda/archive/13.1.0/cuda-runtime-api/group__CUDART__EXECUTION.html)。
人工 gate 不进入性能样本；CUDA 不保证不同 stream 必然并发，需以实际
时间区间重叠来报告曝光，而不能由 stream 数量推断 GPU 并发执行。
