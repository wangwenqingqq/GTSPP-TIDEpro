# GTSPP & TIDEpro

**状态：2026-09-13 已创建私有仓库，并完成首轮百万行、六次累积发布的 GPU 维护控制。不是已经成立的新算法。**

远端为 `wangwenqingqq/GTSPP-TIDEpro`（private）。原 `GTSPP` 未修改。
本轮使用 pro6000-8 的空闲 GPU 6；完整结果、源文件哈希、CPU/GPU 门禁及
全部 7,168 个计时样本已归档。实验变更位于 `work/gate0-maintenance-20260913`。

## 当前结果与下一步

- [Gate 0 结果与边界](docs/GATE0_RESULTS_20260913.md)
- [冻结实验合同及资源修订](docs/GATE0_RUN_CARD_20260913.md)
- [复现步骤](docs/GATE0_REPRODUCE.md) · [尝试记录](docs/GATE0_ATTEMPTS.md)
- [机器可读汇总](results/gate0_20260913/summary.json)

六次真实到达的一致 ID 抽样，996,854 → 1,082,990 行；同 kernel 比较
不合并、周期合并、大小分层合并、完全压实。完整 CPU 结果逐条一致，
memcheck/synccheck 均 0 errors。这个 Q=1、非并发、小规模试验中，
完全压实没有稳定查询收益；不能据此证明更大规模/预算受限/并发条件等价。
先不引入新维护机制，下一轮补强执行层及显存/回收计量，再扩规模和并发。

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

起始包在 Python 3.13.5 上报告 **24 项 CPU 测试**。历史报告见 [CPU_TEST_RESULTS](docs/CPU_TEST_RESULTS.txt)，示例见 [CPU_DEMO_OUTPUT](docs/CPU_DEMO_OUTPUT.txt)。本轮在 Python 3.10 中重跑并增加 7 项测试，**31 项通过**。新增输入准备测试使用 NumPy；缺少 NumPy 时会明确跳过这 5 项。CPU 参考不代替 CUDA 验证。

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
