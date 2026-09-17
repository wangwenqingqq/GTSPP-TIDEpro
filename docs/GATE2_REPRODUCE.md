# Gate 2 复现

先读 [冻结合同](GATE2_CONTRACT.md)。本轮独立远端根目录为
`/home/data/wangxuran/GTSPP-TIDEpro_20260915_gate2`，不改 Gate 1 或原始 TIDE。
需要 Python/NumPy、OpenMP、CUDA 13.1.115 和 `sm_120`；本轮沿用 Gate 1
源码，Gate 2 仅新增 host 固定时钟协议及普通控制参数。旧 entry point 通过
include 重命名，只用于复用原 guards；旧 kernel/runtime 文件没有编辑。

在新项目副本中执行，输出目录/binary/oracle 必须不存在：

```bash
python3 experiments/gate2/prepare.py \
  --source-root /home/data/wangxuran/TIDE/active/tide_surechembl_gate6_20260828 \
  --test /home/data/wangxuran/GTSPP-TIDEpro_20260913_gate1/raw_data/history_mod4 \
  --output raw_data/dev
python3 experiments/gate2/cpu_stage.py --dev raw_data/dev \
  --test /home/data/wangxuran/GTSPP-TIDEpro_20260913_gate1/raw_data/history_mod4
python3 -m unittest discover -s tests -p test_gate2.py
```

测试集必须是 Gate 1 的完整 prepared 数据与 oracle，包括 fixture。
开发集验证与它的 source SHA256 一致，逐 ID 确认两个不同余数，因而 ID 不相交。
输入、oracle、编译命令、binary、合同与测量脚本身份写入 `build/CPU_READY.json`。
CPU 阶段不启动 GPU。

先检查 GPU 空闲，核对 index/UUID，再调用 wrapper。以下只是本轮卡号，不能
假定复现时仍空闲；不可删除锁、修改锁权限、停止别人的任务。

```bash
python3 experiments/gate2/campaign.py --output raw_logs/new_campaign \
  --gpu-index 6 --gpu-uuid GPU-865ae1f0-780e-d04c-5ec3-4deccea65f82
```

门禁为 inherited guards、新增长/shadow 小样本（普通和 memcheck/full leak-check）。
之后每预算 512-batch 校准、静态 8 秒基线、五种有限开发配置。`FROZEN.json`
记录每预算的间隔、p99 门槛、两家族选择和开发证据 SHA256，先于任何测试进程。
最后执行 80 个固定 8 秒的主测试 case。所有步骤中断即留证据，未完成 campaign
不进入主分析，不按好坏挑选单个 case 重跑。

每个请求分别保存内部 service、完整返回 service、排队、响应、窗口完成标志；
六次维护保存固定到达与实际发布时间、回收时钟、字节/merge ledger。窗口后校验
全部 ID/intersection/union 和哈希，错误时整个 case 失败。原始日志不进入 Git。

```bash
python3 experiments/gate2/analyze.py \
  --raw private/gate2-evidence/campaign_v1_gpu6 \
  --cpu-ready private/gate2-evidence/build/CPU_READY.json \
  --dev-manifest private/gate2-evidence/dev_manifest.json \
  --test-manifest private/gate2-evidence/test_manifest.json \
  --output results/gate2_20260915
```

分析要求 `COLLECTION_COMPLETE.json`，重新计算全部 case 并核对冻结前后时间顺序、
选择规则、固定到达、窗口分母、逐 epoch 覆盖、arena 无重叠/无泄漏、完整 oracle
标志、CUDA/NVML 显存上限。shadow/growth 工作量按每次维护比较，不只比较总字节。
四进程 min–max 不是置信区间，不宣称盲测或业务 SLO 达标。

本地 Python 3.10 与远端 Python 的浮点 `sum` 实现产生末位差异。仅对
`mean_service_ms` 的独立复算使用 abs/rel `1e-12` 容差并保留远端原值；p99、
队列、覆盖、冻结门槛及所有其他字段仍要求完全相同。此兼容修订不改测量脚本、
冻结选择或原始日志；没有重跑 GPU。
