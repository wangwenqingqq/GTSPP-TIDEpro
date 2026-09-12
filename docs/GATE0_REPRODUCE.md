# Gate 0 复现与交接

## 环境与范围

本轮实际用 Python 3.10（本地测试）、NumPy 1.26.4（远端输入准备）、
CUDA 13.1.115、驱动 590.48.01、sm_120 编译目标；机器为 pro6000-8。
GPU 6 的 UUID/每次进程状态记录于 evidence receipt 对应的原始记录。
所有 GPU 测试按同一冻结 kernel、同一输入/输出合同执行。

历史源没有 Git 元数据，使用 artifact SHA256，不冒充原仓库提交。
新 harness 的注册提交为 `f3da658`，资源修订为 `8a075fe`。
GPU 实际执行的源码与 binary SHA 见
[evidence_receipt.json](../results/gate0_20260913/evidence_receipt.json)。

## CPU 测试与起始包校验

```bash
python3 -B -m unittest discover -s tests -v
python3 -B scripts/verify_package.py --revision e45abb9823af3aeed80a811c7e4ce7467fa44c2d
```

前者本轮 31 项通过。没有 NumPy 时只跳过输入准备的 5 项，不自动安装依赖。
后者从本地 Git 初始提交验证原始 18 个 hash，不改当前工作区。
`MANIFEST.sha256`/`RELEASE_FILES.txt` 是起始包的历史白名单，不是新实验文件清单。
已有仓库不再执行建库脚本的 `--execute`。

## 重跑 GPU（必须选新的实验目录）

把本仓库代码放在服务器上的新目录，数据/原日志保留原位。以下变量需要填为
实际路径；`TIDE_PILOT_DATA` 必须不存在，不能指向历史源内部。

```bash
export TIDE_SOURCE_ROOT=/home/data/wangxuran/TIDE/active/tide_surechembl_gate6_20260828
export TIDE_PILOT_DATA=/path/to/new/project/raw_data/history_mod38
export TIDE_PILOT_LOGS=/path/to/new/project/raw_logs/new_attempt

python3 experiments/gate0/prepare_history.py \
  --source-root "$TIDE_SOURCE_ROOT" --output "$TIDE_PILOT_DATA"
python3 experiments/gate0/build_and_oracle.py \
  --input "$TIDE_PILOT_DATA" --nvcc /usr/local/cuda-13.1/bin/nvcc
```

CPU 阶段编译并为 fixture/百万行输入生成全部 896 个完整 oracle vectors，
将代码/输入/oracle/binary 的 hash 写入 `build/CPU_READY.json`。不调用 GPU。
若已有 oracle/receipt，会拒绝覆盖；失败产物留存，换新的独立实验目录再试。

只在卡确实空闲且本次资源分配仍适用时执行：

```bash
python3 experiments/gate0/run_guarded.py \
  --input "$TIDE_PILOT_DATA" --output "$TIDE_PILOT_LOGS" \
  --gpu-index 6 --gpu-uuid GPU-865ae1f0-780e-d04c-5ec3-4deccea65f82
```

wrapper 校验输入/代码/binary/oracle，持有现有全局锁和单卡锁，核验无外来
compute process，再依次执行 overflow guard、fixture、memcheck、synccheck、
四个轮换策略顺序的新进程。每个进程最多 15 分钟，总 wrapper 最多 30 分钟；
发现外来占用只停止自身 process group，绝不杀其他进程。锁忙/权限错误/
卡不空闲时会停止，不能删除旧锁强行运行。换卡必须先记录分配修订。

维护是顺序发布，所有结果都完整物化到主机；不包含分子指纹生成/元数据回连。
性能样本没有原始分子、权重、凭据或聊天记录。原始运行日志保留在忽略目录，
只发布本任务所需的数值记录和来源收据。

## 分析已有证据

```bash
python3 experiments/gate0/analyze.py \
  --raw "$TIDE_PILOT_LOGS" \
  --input-manifest "$TIDE_PILOT_DATA/MANIFEST.json" \
  --cpu-ready build/CPU_READY.json \
  --output /path/to/new/analysis-directory
```

分析首先检查所有请求键、完整结果匹配、候选行数一致、warmup、sanitizer 和
进程退出状态，随后才生成汇总。输出目录必须不存在。完整原始日志及 CPU
receipt 属于本次实验证据，复现不能只依据汇总表倒推数据。

## 本轮保留的位置

- 远端独立根：`/home/data/wangxuran/GTSPP-TIDEpro_20260913_gate0/`
- 输入：`raw_data/history_mod38/`；完整 oracle 位于其 `oracle/` 和 `fixture/oracle/`
- 原始成功运行：`raw_logs/pilot_v2_gpu6/`；初始失败目录 `raw_logs/pilot_v1/` 保留
- 本地下载副本：本仓库忽略的 `private/remote-evidence/`
- 可审阅、可发布数值证据：`results/gate0_20260913/`

脚本不会自动开下一轮、不改原 GTSPP、不合并 PR。本轮所有 GPU 子进程已经结束。
