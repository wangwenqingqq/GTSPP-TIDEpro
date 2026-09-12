# GTSPP & TIDEpro

**状态：研究重启起始包，2026-09-12。不是原 GTSPP/TIDE CUDA 系统的迁移版，也不是已经成立的新算法。**

建议远端名：`wangwenqingqq/GTSPP-TIDEpro`，先保持 **private**。本次没有创建远端仓库，没有修改已有 GTSPP，没有连接研究服务器或运行 GPU 实验。

## 当前可运行内容

Python 标准库 CPU 语义参考：整数 Tanimoto 阈值验证、按置位位数筛选的不可变 runs、查询持有固定 epoch、失败发布不改变可见版本、压实前后结果一致、输出溢出显式报错。另有祖先区间陈旧导致漏检的数学反例。

这些都是用于回归的参考机制，不作为新颖性或性能结论。CPU 示例里的二进制记录是合成数据，不是端到端化学应用。参考实现不支持删除、崩溃恢复、持久化、网络服务或 CUDA。

```bash
# 在目录根执行；Python 3.10+，无第三方依赖
python3 -B -m unittest discover -s tests -v
python3 -B -m examples.exact_release_demo
```

本次实际在 Python 3.13.5 上通过 **24 项 CPU 测试**。测试报告见 [CPU_TEST_RESULTS](docs/CPU_TEST_RESULTS.txt)，示例输出见 [CPU_DEMO_OUTPUT](docs/CPU_DEMO_OUTPUT.txt)。该结果不能代替原 CUDA 实现的 oracle / sanitizer 验证。

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

`scripts/create_private_repo.sh` 默认仅打印步骤；只有显式传入 `--execute` 才会调用已登录的 GitHub CLI 创建私有仓库并推送。它验证账户、仓库根和白名单文件，不会覆盖已有 origin 或远端仓库。本次只做了本地语法/干运行检查，**没有测试远端写入**。

```bash
bash scripts/create_private_repo.sh             # 只说明操作，不联网、不推送
# 确认 git 身份与 gh 登录后，在本机明确执行：
bash scripts/create_private_repo.sh --execute
```

首次准备完原始代码迁移及共同作者许可后，再决定是否公开和采用何种许可证。本包没有替你为既有研究代码重新授权。
