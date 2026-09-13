# Gate 1 尝试记录

不删除中断尝试，不把 CPU 编译修订或准入失败藏进成功结果。

1. CPU compiler v1：首次编译通过，fixture/10M 的 1,792 个 oracle 生成。
   随后为百万行门禁另准备 896 个 oracle。首次 GPU 调用前，审查发现
   acquire 与 reader 登记的间隙会使归属快照不精确，添加共同短锁，按 UID
   完整分类并记录其他暂存余额。编译 v2 后重新生成全部 2,688 个 oracle，
   与 v1 完整文件 SHA256 逐项一致。v1 binary/receipt 单独保留。
2. `campaign_v1_gpu0`：使用编译 v2。普通 guards、fixture 全策略/批量检查、
   memcheck guards 均通过，memcheck 明确 0 bytes leaked / 0 errors。
   下一项 `memcheck fixture` 尚未启动即被空闲准入拒绝。本尝试没有性能数据。
   当时未保存失败 pre 快照，不能精确重构触发条件；相邻 post/后续整卡检查
   无外来 compute 进程，后续 GPU 0 恢复 14 MiB / 0%。因此仅推断为采样
   利用率尾部，不声称已证明。保留本次全部日志。
3. 下一次 wrapper 修订：每个子进程间增加 2 秒静默间隔，仍执行原来严格
   idle 准入；此间隔完全在 C++ 请求/维护计时之外。任何失败 pre 快照保存。
   racecheck 单独识别 hazard summary，memcheck 同时要求明确零泄漏摘要。
   未更改 GPU binary、输入、阈值、控制、显存上限或性能样本选择。
4. `campaign_v2_gpu0`：全部 fixture/sanitizer/百万行 native gate 通过；首个
   rotation 的 roomy/constrained 顺序测试也通过。随后 concurrent Q=1 的
   shadow compact 组因大连续块空间拒绝而整体停止。v2 的按需 256-byte
   对齐分配使旧 base 块小于增长后大块；即使 arena 总空闲量尚有余量，也
   不能保证新大 run 的连续分配成功。此轮部分性能日志保留，但不与修订后
   样本混合或挑选。失败仍未返回不完整查询或超总显存。
   根据 arena 分配/释放日志重建，失败在 shadow compact 第五次更新：
   剩余总空间 584,382,208 bytes，最大连续块 431,340,032 bytes，待合并
   分配需 431,517,440 bytes。因此是可核实的外部碎片，不是整卡容量用尽。
5. allocator v3：所有策略共同采用一个普通大块 size class：run 的数据
   达到 256 MiB 后，分配固定 10,500,000 行 × 42 bytes（向上 256-byte 对齐）；
   更大 run 明确拒绝。padding 属于实际占用并进入 UID/预算/arena 账目；
   uploaded bytes 仍按实际数据算。不增加两档总预算，不改变维护控制规则。
   增加拒绝事件的最大连续空闲块记录。重新编译、重算核对所有 oracle，
   从故障/sanitizer 门禁到所有 rotation 全部重新执行。
6. `campaign_v3_gpu0`：21 个子进程全部通过，12 个性能进程、69,568 个
   measured batch（983,040 个逻辑查询），观测总显存均未超限。此为有效
   第一轮，而非失败尝试。报告保存完整 v3 结果。
7. v4 单变量普通基线改进（v3 分析后登记）：v3 all-delta shadow Q=1
   p99 为约 2.4–3.4 ms（static 约 0.17 ms）；顺序 all-delta 总维护时间中
   约 70.7% 没有被 build/metadata/staging-copy/H2D 子计时解释。源码每次
   Run 上传都会 `cudaMallocHost/cudaFreeHost`，可能引入共享驱动开销；
   此时尚不能证明这是尾部的原因。v4 仅把同一 8 MiB pinned staging 提前
   分配给 Writer 并复用。kernel、arena、控制、输入、输出、发布节奏、预算
   全部不变。重新生成核对 oracle，完整重跑同一 21 进程协议；不与 v3
   混样本。它是普通缓冲复用的前后对照，不是新算法，也不是随机交错因果试验。
