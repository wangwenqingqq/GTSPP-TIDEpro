# Gate 1 复现与交接

本轮远端独立目录：`/home/data/wangxuran/GTSPP-TIDEpro_20260913_gate1`。
原始 TIDE artifact、Gate 0 目录不改动。数据不进入 Git。
必须在新的独立项目目录复现，脚本拒绝覆盖已存在的输入/oracle/结果目录。

## 数据和 CPU 阶段

需要 Python 3 + NumPy、CUDA 13.1.115、支持 `sm_120` 的 nvcc 和 OpenMP。
本轮实际 GPU 为 RTX PRO 6000 Blackwell Server Edition，驱动 590.48.01。
当前 C++ 文件已含 v3 大块分配器和 v4 pinned staging 复用；新建副本可
直接编译，不必重演失败版本或逐 run 申请 pinned buffer 的对照版本。

```bash
python3 experiments/gate1/prepare.py \
  --source-root /home/data/wangxuran/TIDE/active/tide_surechembl_gate6_20260828 \
  --output raw_data/history_mod4 --modulus 4
python3 experiments/gate1/build.py --input raw_data/history_mod4
python3 experiments/gate1/supplement.py \
  --source-root /home/data/wangxuran/TIDE/active/tide_surechembl_gate6_20260828
```

CPU oracle 是不剪枝 AND/OR 扫描，fixture / 1M / 10M 各 896 个完整向量，
ID + intersection + union 总共 2,688 份；固定四个 CPU 线程，不启动 CUDA。
编译前后 source/input/binary/oracle SHA256 记录在 `build/CPU_READY.json`
和 `build/CPU_GATE1M.json`。`refresh.py` 是本轮保留前版、重编译、重生成
并逐文件对比全部 oracle 的审计步骤；不应对已有证据目录随意重复运行。

## GPU 阶段

先手工确认候选 GPU 空闲，核对 index 和 UUID。下面只是本轮配置，不能
假设该卡一直空闲。wrapper 再次检查、取得既有 global / 对应单卡 flock。
锁冲突或外来占用时停止；不删除锁、不改权限、不停止别人的进程。

```bash
python3 experiments/gate1/run_guarded.py \
  --input raw_data/history_mod4 \
  --output raw_logs/new_campaign \
  --gpu-index 0 \
  --gpu-uuid GPU-9bd364a9-9d88-0b78-ef55-caac6f73d6b1
```

共 21 个 GPU 子进程：普通 guards/fixture，memcheck（full leak-check）、
synccheck、racecheck 各 guards/fixture，1M native-batch 门禁，8 个两档
预算顺序进程和 4 个并发进程。Q=1/8/64 及四策略由同一个 binary 执行。
每子进程 600 秒，全 campaign 1,800 秒。进程间 2 秒监控静默不计入服务或
维护时间；查询/维护内部不 sleep、不注入曝光延迟。

CUDA context/module 预热后固定一次 arena；64 MiB headroom，整卡用量在
CUDA 阶段边界和 NVML 轮询中检查。任何观测超过声明总预算立即失效。
这不是硬件显存分区，不能证明未采样瞬间的驱动内部占用；run 回收是 arena
地址重新可用，整块显存预留直到进程退出才还给 CUDA。

所有策略共同固定大 run size class（10.5M 行 capacity），padding 计入显存，
实际 uploaded bytes 不含 padding。顺序 constrained 合并不足时延期合并，
若 delta 也放不下则保留旧版本并明确拒绝。并发 roomy 若工作量无法一致
则停止，不改变 shadow 的维护工作量来偷偷绕过预算。

## 分析

仅接收有 `COLLECTION_COMPLETE.json` 的完整轮次。失败 v1/v2 独立保存，
不可将其中有利数据加入完成轮次。v3 是完整有效的逐 run pin 对照，v4
是仅改为 staging 复用的完整普通控制；两轮不混合统计。分析核对每次 arena 分配不重叠、释放余额、
唯一 owner 字节闭合、所有 CPU 完整比较、两种影子工作量以及所有样本键。
复现本次归档时，`private/gate1-evidence/` 下还需保存原始 `campaign_v1_gpu0`
和 `campaign_v2_gpu0`，用于失败尝试收据，不用于主估计。

```bash
python3 experiments/gate1/analyze.py \
  --raw private/gate1-evidence/campaign_v4_gpu0 \
  --cpu-ready private/gate1-evidence/build_v4/CPU_READY.json \
  --cpu-gate1m private/gate1-evidence/build_v4/CPU_GATE1M.json \
  --input-manifest private/gate1-evidence/input_manifest.json \
  --output results/gate1_20260913
python3 -m unittest discover -s tests
python3 scripts/audit_repo.py
```

v3 的旧 CPU receipts 在 `private/gate1-evidence/build/`，其原始测量代码
可从提交 `1ecf8c0` 读取。v3 归档为 `results/gate1_20260913_v3_per_run_pin`。
用同一分析程序和旧 receipts 可重现，不以当前 v4 的源哈希替换历史记录。

```bash
python3 experiments/gate1/compare_staging.py \
  --before results/gate1_20260913_v3_per_run_pin \
  --after results/gate1_20260913 \
  --output results/gate1_staging_ablation_20260913.json
```

此对照逐 batch 检查 sequential/static/shadow 的候选/输出不变，逐维护事件
检查 copied/merged bytes、策略与结果 run 数不变。实际增长允许 acquire
不同 epoch（writer 速度变化），因此不当作同输入前后延迟比较。

CSV gzip 设置固定 mtime/空文件名，可重新分析得到逐字节相同的归档。
报告以四个进程为统计重复单位；不能将批内 64 个查询当作 64 个独立进程。
Racecheck 只覆盖其适用的 CUDA shared-memory hazards，不是一般 host 竞态
证明；工具边界见 [NVIDIA Compute Sanitizer 文档](https://docs.nvidia.com/compute-sanitizer/ComputeSanitizer/index.html)。
完整 source、binary 和原始文件 SHA256 在结果收据中。
