# GTSPP & TIDEpro

## Content-filter branch checkpoint — 2026-09-21

The registered CPU reference dev grid passed all 4,608 complete-result checks
on SureChEMBL256 and official ChEMBL37 FPS2048. This is **not A_GO**: complete
access accounting, dev selection, A-screen and native GPU tests remain pending.
See the [checkpoint report](results/content_filter_20260921/DECISION.md) and
[reproduction instructions](experiments/content_filter/README.md). This branch
does not alter the historical Gate 0–2 evidence below. Repository visibility
was verified public on 2026-09-21; older private labels are historical.

## Historical Gate 0–2 record

**状态：2026-09-15 Gate 2 已完成固定到达与开发集有限调参实验；普通增长策略达标，但一次静态基线超限，不能宣称 Gate 全部通过。没有新算法必要性的证据。**

远端为 `wangwenqingqq/GTSPP-TIDEpro`（private）。原 `GTSPP` 未修改。
Gate 0 使用空闲 GPU 6，Gate 1 使用空闲 GPU 0。两轮 Gate 1 有效 campaign
共 1,966,080 个计时查询完整匹配；失败尝试、前版对照和全部样本均保留。
Gate 2 使用空闲 GPU 6：80 个正式测试进程、9,481,600 次查询完整匹配；
开发/测试 ID 不相交，参数先冻结再测试，原始日志保留，结束后输入哈希复核通过。
实验变更位于 `work/gate0-maintenance-20260913`，PR 不自动合并。

## 当前结果与下一步

- [Gate 2 完整报告](results/gate2_20260915/REPORT.md) · [机器可读汇总](results/gate2_20260915/summary.json)
- [Gate 2 冻结合同](docs/GATE2_CONTRACT.md) · [复现与审计](docs/GATE2_REPRODUCE.md)
- [Gate 1 结果与结论边界](docs/GATE1_RESULTS_20260913.md)
- [Gate 1 合同](docs/GATE1_CONTRACT_20260913.md) · [复现](docs/GATE1_REPRODUCE.md) · [尝试记录](docs/GATE1_ATTEMPTS.md)
- [Gate 1 汇总](results/gate1_20260913/summary.json) · [pinned staging 单变量对照](results/gate1_staging_ablation_20260913.json)
- [Gate 0 结果与计时勘误](docs/GATE0_RESULTS_20260913.md)
- [冻结实验合同及资源修订](docs/GATE0_RUN_CARD_20260913.md)
- [复现步骤](docs/GATE0_REPRODUCE.md) · [尝试记录](docs/GATE0_ATTEMPTS.md)
- [机器可读汇总](results/gate0_20260913/summary.json)

Gate 2 为 10M、Q=8、τ=.8、约 14,815 queries/s、固定 8 秒及六次历史增量。
两档预算中 all-delta、periodic6、tier4 均为 4/4 增长测试达标，响应 p99 约
0.99–1.00 ms。2048 MiB 每次 compact 为 7.25–17.93 ms；四个进程共 13 次
读路径回收的 GPU 后完成段达 15.37–24.39 ms，而 kernel 仅 0.22–0.92 ms。
这支持普通 CPU 回收/完成路径造成排队的解释，尚无回收线程单变量因果验证。
32 组 shadow/growth 的逐 epoch 维护工作量全部相同。1280 MiB 的 compact
实际是六次延期、零次合并，不能称为压实同样快。该预算静态 final 一次 p99
2.42 ms 超过冻结门槛 1.99 ms，完整保留，不通过补跑消除异常。
本轮到此结束，不扩 41M、不新增机制；有限历史/单负载点不等于生产 SLO 或稳态证明。

Gate 1 为 9,461,367 → 10,279,473 行，Q=1/8/64，1,280/2,048 MiB 总预算，
四个共同普通控制；memcheck/full leak-check、synccheck、racecheck 及
GPU pending-reader/失败回滚通过。Q=8/64 完全压实带来的查询延迟差约
1.2–2.3%，却有较高维护成本。all-delta shadow 的 Q=1 p99 比值，在仅复用
pinned staging 后从 17.57 回落到 1.09（后者区间含 1）。不能拿原来的大尖峰
证明新布局必要性。仍未覆盖 41M/2048-bit/开放队列稳态及独立开发 trace 调参。

重要勘误：Gate 0 service 未计入每请求 O(N) bounds-metadata CPU 扫描；
旧数字不是完整请求端到端延迟，不与 Gate 1 计算加速比。

## 起始包的历史边界

以下起始包说明对应 2026-09-12 的初始提交
`e45abb9823af3aeed80a811c7e4ce7467fa44c2d`；原有决策/先行工作文件保留，
其中“未执行 GPU/未创建远端”描述的是当时状态。新工作只抽取了固定 artifact
中的查询 runtime，并非迁移或验证整个 GTSPP/TIDE CUDA 系统。

## 起始 CPU 语义参考

Python 标准库 CPU 语义参考：整数 Tanimoto 阈值验证、按置位位数筛选的不可变 runs、查询持有固定 epoch、失败发布不改变可见版本、压实前后结果一致、输出溢出显式报错。另有祖先区间陈旧导致漏检的数学反例。

这些都是用于回归的参考机制，不作为新颖性或性能结论。CPU 示例里的二进制记录是合成数据，不是端到端化学应用。参考实现不支持删除、崩溃恢复、持久化、网络服务或 CUDA。

```bash
# 在目录根执行；Python 3.10+，无第三方依赖
python3 -B -m unittest discover -s tests -v
python3 -B -m examples.exact_release_demo
```

起始包在 Python 3.13.5 上报告 **24 项 CPU 测试**。历史报告见 [CPU_TEST_RESULTS](docs/CPU_TEST_RESULTS.txt)，示例见 [CPU_DEMO_OUTPUT](docs/CPU_DEMO_OUTPUT.txt)。Gate 0 扩为 31 项，Gate 1 时 **40 项通过**；Gate 2 新增的 **10 项针对性测试通过**。实数据准备测试使用 NumPy；缺少 NumPy 时会明确跳过对应 9 项。CPU 参考不代替 CUDA 验证。

## 研究文件

- [独立评估与重启决策](docs/DECISION_20260912.md)
- [审稿问题与修复矩阵](docs/REVIEW_MATRIX.md)
- [下一轮实验设计](docs/EXPERIMENT_PLAN.md)
- [已知先行工作与边界](docs/PRIOR_ART.md)
- [原代码迁移与私有仓库交接](docs/HANDOFF.md)

## 推荐主线

保留原 GTS++ 的实现资产，但不恢复尚未复核的直接插入和旧加速比主张。优先研究 TIDE 的持续更新精确检索；不把普通分片、快照、单次融合发射重新命名为新贡献。Top-p 输出层检索作为独立探索，不与本系统强行合写。

下一步先验证：在合理的固定显存预算和真实连续发布下，现有优化执行与普通维护策略是否仍留下具有结构性原因的成本差距。先证明问题和交互，再决定是否需要新布局或维护机制；不预设一定能发论文。

## 安全发布

本包不包含上传的 PDF/DOCX、原始审稿意见、长对话、远程配置、凭据、模型权重或化学数据。`.gitignore` 不是安全扫描器，不能替代人工检查。

`scripts/create_private_repo.sh` 是一次性起始包建库脚本，本轮已成功使用。
不要对已有仓库再次运行 `--execute`。它的白名单/哈希属于原起始包，不是
当前开发树。可以不改动工作区地重新校验原包：

```bash
python3 -B scripts/verify_package.py --revision e45abb9823af3aeed80a811c7e4ce7467fa44c2d
```

```bash
bash scripts/create_private_repo.sh             # 只说明操作，不联网、不推送
# 不再次创建仓库或覆盖 origin
```

首次准备完原始代码迁移及共同作者许可后，再决定是否公开和采用何种许可证。本包没有替你为既有研究代码重新授权。
