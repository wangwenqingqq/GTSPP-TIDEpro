# 一手来源与新颖性边界

访问日期：2026-09-12。这是针对本轮判断的查新记录，不是穷尽性 novelty 证明。网页可能继续更新，正式实验应固定发布版、commit 和输入哈希。

| 来源 | 已覆盖的内容 | 不可直接推出 |
|---|---|---|
| [HNSW 原论文](https://arxiv.org/abs/1603.09320) | 一般度量空间的近似图检索 | hnswlib 的每个发布接口都直接支持任意距离；或它提供本题的完整精确阈值语义 |
| [chemfp 5.1 shardsearch](https://chemfp.com/docs/chemfp_shardsearch_command.html) | 多文件相似检索、结果合并、季度 base 与每周累计更新示例 | 与 TIDE 同 GPU、同 epoch 所有权、同端到端接口的性能已对齐 |
| [FPSim2](https://github.com/chembl/FPSim2) | 化学指纹检索及 CPU/GPU 实现 | 单文件生命周期是所有合理动态实现必须付出的成本 |
| [GPU LSM](https://arxiv.org/abs/1707.05354) | GPU 上的动态有序层次、插删和查询权衡 | 专用 Tanimoto 查询的最优物理维护策略已证明 |
| [A GPU Multiversion B-Tree，作者代码](https://github.com/owensgroup/MVGpuBTree) | GPU 快照、并发查询/修改、版本回收 | 普通 shared_ptr 发布可单独当新贡献 |
| [ArceKV](https://doi.org/10.14778/3796195.3796208) / [技术报告](https://arxiv.org/abs/2508.03565) | 动态工作负载下的 LSM 结构与 compaction 决策 | 本轮提出“自适应合并”四个字就已有创新；也不能未对照便说覆盖专用剪枝/版本/显存交互 |
| [基于向量索引的输出层检索](https://arxiv.org/abs/2608.27460) | HNSW 替代完整输出投影的近似路径 | 严格保持全词表 Top-p 分布的问题已被解决 |
| [FlashInfer 排序消除采样](https://flashinfer.ai/2025/03/10/sampling.html) | 给定输出概率/分数的过滤采样与融合执行 | 已经省掉计算全部词表 logits 所需的投影 |
| [OS*](https://aclanthology.org/W12-6106/) | 优化与采样的统一自适应框架 | 任意球界/拒绝采样组合就是新的现代 LLM 算法 |
| [SureChEMBL bulk data](https://chembl.gitbook.io/surechembl/downloads/bulk-data) | 真实分子/专利数据的批量发布与数据字段 | 生产用户需要毫秒级发布 SLA；指纹相似等于活性或法律结论 |

研究贡献应比较问题、保证、机制、执行条件、成本边界五个方面。新系统不必每个组件都是首次；但普通组合已经达到同样目标时，需要新的机制、可推广的系统发现或非平凡集成证据，而不是只换名或筛选最有利数据。
