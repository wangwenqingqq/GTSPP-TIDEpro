# Gate 1：千万行、总显存、native batch 与并发归因

结论：计量和 GPU 门禁已补齐到本轮声明范围。Q=8/64 下，完全压实相对
不合并的查询收益小；逐次 pinned staging 申请造成的巨大尾延迟信号，在
普通 staging 复用后大幅回落。当前仍没有必须引入新布局或维护机制的证据。
这不是证明所有维护策略等价，也不是完成生产稳态或 41M 全规模研究。

## 实际完成的范围

2026-09-13，pro6000-8、空闲 GPU 0、RTX PRO 6000 Blackwell Server Edition，
CUDA 13.1.115、驱动 590.48.01。只使用受锁保护的一张卡，不改时钟/功率，
不停止他人任务；结束后 GPU 0 为 14 MiB / 0%。原 GTSPP 未修改。

同一固定 SureChEMBL 256-bit artifact，stable-ID 一致 1/4 抽样：
9,461,367 → 10,279,473 行。六次新增分别为 5,450 / 765,847 / 1,780 /
35,549 / 4,230 / 5,250 行。64 个非空查询来自 base/各新增 cohort，非外部
holdout；阈值 0.7/0.8。版本顺序来自真实历史，发布节奏是预设的请求驱动
压缩重放，不是按历史日期间隔运行，也不是额外制造自然版本。

共同执行层以一个融合 kernel 处理整批 query/run descriptors，Q=1/8/64；
不是 Q 次同步单查询。按 query ID 分发完整 ID/intersection/union 输出，
每 query 容量 65,536；任何溢出使整批失败，不返回截断结果。
不可变 run 的 bounds metadata 只建立一次。请求计时从 acquire/register
之前到完整 CPU 输出物化、排序及 owner 释放结束，oracle 比较另计。

有效 v3（逐次 pin）与 v4（复用 pin）各完成 21 个 GPU 子进程，其中
12 个性能进程：两档显存 × 四个顺序进程，加四个并发进程；均轮换策略顺序。
每轮 69,568 个计时 batch、983,040 个逻辑查询；两轮合计 1,966,080 个计时
查询全部完整匹配。每轮含 warmup/final checks 共 1,084,416 个已记录查询。
两轮独立分析，不将批内查询数当作统计独立进程数。

v3/v4 wrapper 总墙钟分别 337.64 / 325.05 秒，包含门禁、监控和进程间间隔，
不是 kernel 时间。v1/v2 两次中断以及所有有效 v3 数据均保留。

## 正确性与生命周期

- 40 项本地 CPU 测试通过；fixture、1M 和 10M 各 896 份独立、不剪枝 AND/OR
  完整 oracle，共 2,688 份。每次实现修订均重新生成并逐文件核对一致。
- memcheck（含 full leak-check）为 0 errors / 0 bytes leaked；synccheck
  为 0 errors；racecheck 为 0 hazards/errors/warnings。Racecheck 的适用
  范围不是一般 host 竞态证明。
- 分配前、分配后、部分/完整 H2D 后故障，以及发布前取消，均恢复原 epoch
  和 arena 余额；超预算拒绝、真实 GPU 输出溢出（专用检查将 append 容量
  降为 1 触发）、在途取消检查通过。
- 正确性专用 gate 先准备新 GPU 数据，再把旧 query 的后续 GPU 工作保持在
  已入队、未完成状态；发布新指针后旧 owner 仍存活，完整 D2H 结束后才能
  回收。它不用于性能样本，不声称 gated kernel 当时已在 SM 上执行。
- 实际增长 v4 中，49 次发布观测到 reader-only GPU 对象，最大约 420.79 MiB；
  旧 reader 的设备完成最多晚于发布约 5.66 ms。每次分配、释放、共享 UID、
  最后 reader 完成及实际地址回收都有记录，最终 arena live bytes 为 0。

## 总显存口径与真正约束

| 场景 | 声明总上限 MiB | 固定 arena MiB | arena 有效对象峰值 MiB | 整卡观测峰值 MiB |
| --- | ---: | ---: | ---: | ---: |
| roomy 顺序 | 2,048 | 1,412 | 936.23 | 1,985.94（NVML 1,986） |
| constrained 顺序 | 1,280 | 644 | 546.55 | 1,217.94（NVML 1,218） |
| roomy 并发 | 2,048 | 1,412 | 1,356.58 | 1,985.94（NVML 1,986） |

预热后 context/driver 基线约 571.94 MiB；所有 run、query/descriptor/输出
workspace 从固定 arena 分配，预留 64 MiB 余量。整卡观察包括 context/driver，
不是旧轮次只算显式数据。NVML 轮询和 CUDA 阶段检查都没有观测到超限。
这是观测约束，不是硬件显存分区，不能证明采样间隙内的驱动内部瞬时分配。

run 回收指其 arena 地址可以重新分配；物理 arena 直到进程退出才归还 CUDA。
current-only / reader-only / shared 按唯一 run ID 计算；其它 writer 暂存与
shadow 固定基库持有单列，不重复累计两个 epoch 的逻辑大小。

分配器使用共同的大块 size class，padding 全计入预算。其来由是 v2 的
一次真实连续空间拒绝：空闲总量 584,382,208 bytes，但最大连续块
431,340,032 bytes，小于所需 431,517,440 bytes。普通固定大小大块修复后，
v3/v4 都完整通过，未增加总预算。细节见 [尝试记录](GATE1_ATTEMPTS.md)。

constrained 组真正阻止了合并：每个进程 periodic2 延期 9 次、compact 延期
18 次（含三种 Q）；四进程共 36 / 72 次。它们正常发布 delta、最终为 7 runs，
与 all-delta 的有效布局相同；size-tiered 最终为 4 runs。因此不能把 constrained
里的“compact”标签当作一个确实完全压实的查询参考。

## 查询与维护结果：普通收益和普通代价

以下为 v4 roomy 下“all-delta / compact”配对 batch 服务延迟比；先在进程内
对相同 epoch/query/threshold 做几何均值，再对四个进程计算 log-t 95% 区间
（df=3）。包含六个更新后 epoch；比值大于 1 表示不合并更慢。

| Batch Q | 阈值 0.7，比值 [95% 区间] | 阈值 0.8，比值 [95% 区间] |
| --- | --- | --- |
| 1 | 1.003 [0.964, 1.044] | 0.998 [0.952, 1.047] |
| 8 | 1.018 [1.015, 1.021] | 1.023 [1.010, 1.036] |
| 64 | 1.012 [1.010, 1.014] | 1.022 [1.017, 1.026] |

Q=1 无稳定方向；Q=8/64 有约 1.2–2.3% 的延迟差。全部策略、阈值和逐进程
值均保留在 [v4 汇总](../results/gate1_20260913/summary.json)，没有只挑显著结果。
这是小收益，不应称作大幅加速，也不能直接与 Gate 0 计时比较。

| roomy 控制 | 最终 runs | 六次维护生命周期累计 ms，12 个（进程,Q）组合范围 | 实际上传 MiB |
| --- | ---: | ---: | ---: |
| all-delta | 7 | 6.23–22.04 | 32.77 |
| periodic2 | 1 | 1,002.59–1,316.19 | 1,265.73 |
| size-tiered | 4 | 31.44–53.30 | 65.54 |
| compact | 1 | 1,951.16–3,006.28 | 2,466.37 |

每个组合含四进程之一、一个 Q 和六次更新；不是 12 个独立进程。
普通 host bucket-copy merge 占重建成本的大头，未实现优化 GPU merge，控制
参数也没有在独立开发 trace 调优。因此这不是“已击败最强维护算法”的证据。
是否值得花维护成本换小查询收益，还需要实际读写比例和长期服务约束。

## 最重要的对照：巨大 p99 尖峰不需要新布局解释

v3 每次上传申请/释放同一大小的 pinned staging；v4 仅将它改为 Writer
生命周期内一次申请并复用，kernel 源码逐字节一致。前后核对了 92,320 个
固定可见集合 batch，及全部 1,248 个维护事件：候选、输出、上传/合并字节、
控制和最终 run 数保持相同。真实增长因发布速度不同可能 acquire 不同 epoch，
不用于同输入前后延迟比较。

all-delta 固定 base 的 shadow/static p99 比值如下；每轮仍以四进程为单位。

| Batch Q | v3 逐次 pin [95% 区间] | v4 复用 pin [95% 区间] |
| --- | --- | --- |
| 1 | 17.575 [13.651, 22.627] | 1.087 [0.925, 1.279] |
| 8 | 2.887 [2.512, 3.317] | 1.000 [0.996, 1.004] |
| 64 | 1.182 [1.169, 1.195] | 0.994 [0.974, 1.014] |

Q=1 的绝对 shadow p99 从 2.412–3.415 ms 回落到 0.176–0.226 ms；static
约为 0.17–0.18 ms。服务延迟几何比从 1.170 降至 1.024，后者区间
[1.008, 1.040]，所以也不能说剩余干扰严格为零。

结果支持优先用普通 pinned-buffer 生命周期开销解释之前的大尾部信号，
不能拿那组尖峰证明需要新结构。两轮前后顺序固定、没有随机交错，且维护
加速会自然改变曝光；这里不是严格分离所有 CPU/driver 因素的因果证明。
完整数据见 [单变量对照](../results/gate1_staging_ablation_20260913.json) 和
[保留的 v3 汇总](../results/gate1_20260913_v3_per_run_pin/summary.json)。

## 并发结果不能越过的边界

每组是单 reader、closed-loop 256 个 batch，六个维护作业可排队；query
queue=0 是设计结果，不是开放队列无排队的证据。CPU oracle 比较在服务计时
之外，会产生调度间隙；maintenance queue/backlog 独立记录。mode 顺序固定，
共享主机调度与时间漂移仍可能影响结果。

尤其不能把 compact 较小的 shadow 干扰解释成更适合在线服务：Q=1/8 时，
四进程的实测增长窗口都只看见 epoch 0，六次大维护大多在 reader 结束后
才完成；Q=64 也只看见部分 epoch。最终 epoch 6 在 writer join 后独立完整
验证，但这不构成六次更新全程有负载的稳态测试。

相反 all-delta 的 Q=8/64 增长窗口覆盖全部七个 epoch；Q=64 每轮也只有
7–8 个 batch 与维护墙钟重叠，其余五个小增量各通常仅一次曝光。重叠是
请求/维护时间区间的相交，不是证明 GPU kernel 与 H2D 在硬件上同时运行。
所有逐事件曝光、队列与可见 epoch 保留，不人为 sleep 延长维护制造干扰。

仍未完成：41M 全库、2048-bit、独立开发 trace 调参、外部查询集、开放队列/
长期稳态、优化 GPU merge、删除/崩溃恢复，以及从原始分子重新核验全部指纹。
本轮补齐的是声明的实验能力和普通控制，不是整份研究计划已经结束。

## 旧计时勘误与证据

Gate 0 的 `OwnedHostDB::view()` 每请求 O(N) CPU 扫描位于旧 service 计时外。
旧数据不改写，明确不能叫完整请求延迟，也不与新数字计算跨轮加速比。
见 [Gate 0 勘误](GATE0_RESULTS_20260913.md)。

- [合同与修订](GATE1_CONTRACT_20260913.md) · [全部尝试](GATE1_ATTEMPTS.md) · [复现步骤](GATE1_REPRODUCE.md)
- [v4 全部顺序 batch](../results/gate1_20260913/sequential_requests.csv.gz) · [全部并发 batch](../results/gate1_20260913/concurrent_requests.csv.gz) · [维护时间线](../results/gate1_20260913/maintenance.csv)
- [输入 SHA](../results/gate1_20260913/input_manifest.json) · [原始文件/源/binary 收据](../results/gate1_20260913/evidence_receipt.json) · [中断尝试收据](../results/gate1_20260913/attempts_receipt.json)

两轮每份 arena 账目均核对分配不重叠及最终释放；重新分析产生逐字节相同
的压缩 CSV/JSON 归档。仓库不包含原始化学数据、CUDA binary 或凭据。
