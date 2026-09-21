---
title: "TIDE 内容过滤：BitBound 后精确候选处理的结构化实验设计"
protocol_id: tide_content_filter_v1_20260921
document_edition: structured_v1
date: 2026-09-21
status: DESIGN_ONLY
real_data_experiment: NOT_RUN_IN_THIS_DELIVERY
gpu_experiment: NOT_RUN_IN_THIS_DELIVERY
primary_task: complete_exact_tanimoto_threshold_search
primary_stage: static
primary_batch_size: 8
owned_research: ["GTS++", "Safe-TIDE", "TIDE++"]
excluded_implementation_base: "BitIVF"
reference_repository: "wangwenqingqq/GTSPP-TIDEpro"
reference_commit: "e21f13167cbe8c6abc4e9dc35a0e864ed7085a1c"
---

# TIDE 内容过滤：结构化实验设计

> **核心问题：**对于已经通过 BitBound、但最终不满足 Tanimoto 阈值的对象，内容过滤省下的完整指纹访问，能否覆盖摘要、位图、倒排、候选状态和精确验证的额外成本？
>
> **执行顺序：**先完成 100K CPU 语义与工作量诊断；只有阶段 A 放行，才投入最多一个内容后端的 1M GPU 实现。静态有系统信号后，才检查一次真实增量发布兼容性。
>
> **文档性质：**这是上一轮 `PROTOCOL.md` 与 `config.yaml` 的结构化整理，不更改已登记的方法、样本数、阈值、预算或继续门槛。尚未固定的执行细节集中列为 `PENDING`，不得由执行程序静默选择。

## 目录

1. 实验概要与证据边界
2. 研究问题与判定目标
3. 查询语义与整数条件
4. 数据、查询划分与输入冻结
5. 方法与算法合同
6. 实验矩阵与配置冻结
7. 工作量、时间与统计指标
8. 资源预算
9. 阶段 A：CPU 诊断
10. 阶段 B：条件性 GPU 验证
11. 阶段 C：条件性发布兼容检查
12. 成熟基线与新颖性边界
13. 结果状态与停止规则
14. 交付物与结果表模板
15. 任务安排与执行检查
16. 待补齐事项
17. 来源与版本记录

---

## 1. 实验概要与证据边界

### 1.1 一页概要

| 项目 | 约定 |
|---|---|
| 任务 | 高维二进制指纹的完整精确 Tanimoto 阈值查询 |
| 第一数据条件 | SureChEMBL，256 bit |
| 第二数据条件 | 官方 ChEMBL 37 FPS，2048 bit |
| 阶段 A | 100,000 条数据库记录；CPU 语义、空间与访问工作量诊断 |
| 阶段 B | 条件性扩到 1,000,000 条；单 GPU 完整查询计时 |
| 阶段 C | 仅静态有信号后；一次真实 SureChEMBL insert-only 转移 |
| 查询划分 | 128 dev / 256 A-screen / 512 B-final |
| 主阈值 | 精确有理数 `7/10`、`4/5` |
| 主 batch | 8；batch 1、64 是预登记诊断 |
| 方法 | R0 完整扫描；R1 逐字早停；R2 分段摘要；B 转置位图；P 稀疏倒排 |
| GPU 开发上限 | R0/R1/R2 对照之外，最多实现 B/P 中一个内容后端 |
| 总投入上限 | 两周；阶段 A 先封顶四天 |
| 本轮不做 | 新压实器、近似剪枝、学习模型、BitIVF 移植、H 残余探针续作、41M 自动扩展 |

### 1.2 已有证据与本轮设计分离

| 来源 | 已支持的内容 | 不支持的外推 |
|---|---|---|
| TIDE++ §2.1、§4 | 非零查询、整数阈值、完整 tuple、原生精确验证与输出合同 | 不证明新增内容过滤正确或更快 |
| TIDE++ §5.10 | 去掉既有 BitBound 会增加扫描工作并降低已测服务吞吐 | 不证明增加任何更复杂过滤都能获益 |
| TIDE++ §5.5 | 已披露 dense LES³ 对照在该 256-bit 数据上的组并集界很松 | 不证明所有 LES³ 实现或所有内容索引无效 |
| TIDEpro Gate 2 | 普通维护策略在已登记增长负载中已能满足要求 | 不证明所有负载都不需要维护研究 |
| 原实验包 `SEMANTIC_TESTS.txt` | 保存了 6 组合成 CPU 语义自检通过记录 | 不是真实数据、native CUDA、性能或新颖性证据 |
| 本文 | 重新组织实验合同、门槛、字段和交付物 | 本次整理没有新增真实数据或 GPU 实测 |

以上来源见 §17 的 [S0]—[S4]。旧稿件结果、源码能力和本轮新实验结果不得混用。

### 1.3 可继承与不可直接继承

复用用户自己的 TIDE++ 精确查询合同、stable ID、epoch/run 生命周期、独立 oracle 方法及验证基础。BitIVF 只可作为相关工作理解，不作为本轮代码底座或成果依据。

固定参考源码为 `experiments/gate1/runtime.cuh`。[S4] 上一轮审读记录指出，其中 `DB<4>/Query<4>` 是 256-bit 特化；2048-bit 必须单独实例化并重新测试。旧的 `MAXDESC=MAXQ*65` 对应原 run 描述符规模，不能直接当成新增逐置位数桶描述符的容量。

---

## 2. 研究问题与判定目标

### 2.1 三个递进问题

| 编号 | 问题 | 必要证据 |
|---|---|---|
| Q1 | 内容过滤是否能精确排除 BitBound 后的非命中对象？ | 全量 oracle 对照；审计全部被过滤对象；0 漏检、0 错误接受 |
| Q2 | 过滤是否减少完整的信息访问成本？ | 原始指纹、辅助索引、状态、目录、查询准备与输出的完整工作量核算 |
| Q3 | 工作量节省是否变成 GPU 服务收益？ | 同合同完整查询计时、实际资源与 profiler 归因 |

**Q1 通过不代表 Q2 通过；Q2 通过只允许进入 GPU 验证，不代表 Q3 已通过。**

### 2.2 研究范围

| 纳入 | 排除 |
|---|---|
| 完整精确阈值检索 | kNN、ANN 候选预算、经验放大下界 |
| 已通过 provenance 检查的原始二进制指纹 | 折叠、量化或换指纹以改变问题 |
| 同等合理的 GPU batch、workspace 和 staging 复用 | 只优化待测方案、故意保留低效扫描基线 |
| 普通早停、摘要、位图和倒排作为机制探针 | 将既有原则预先包装成新算法 |
| 静态主实验与一次条件性更新检查 | 新 compaction、删除、替换、崩溃恢复、生产稳态声明 |

### 2.3 最终需要区分的结论

- **普通优化有效：**R1 或 R2 已足够，不需要建立更复杂的内容索引。
- **内容索引有系统信号：**B/P 在完整计费后超过普通控制，值得进一步查新和验证。
- **当前机制不划算：**过滤虽有效，但辅助访问或状态处理抵消收益。
- **证据不足：**输入、访问模型、资源或成熟基线覆盖仍有缺口。

这些状态允许分别出现；不能用一个总 `PASS` 代替分项结论。

---

## 3. 查询语义与整数条件

### 3.1 输入与输出合同

| 字段 | 合同 |
|---|---|
| 指纹宽度 `D` | 256 或 2048；同一实验组固定 |
| 数据库记录 | 唯一源 stable ID；相同位串、不同 ID 的记录全部保留 |
| 查询 `q` | 必须非零；空查询显式拒绝 |
| 零数据库指纹 | 合法；在非零查询和正阈值下不命中 |
| 阈值 | 整数 `m/n`，`0 < m <= n <= 2^31-1` |
| 判定产品类型 | `uint64`；参与加法、乘法前提升到该类型 |
| 输出 | 全部 `(stable_id:uint64, intersection:uint32, union:uint32)` |
| 输出顺序 | 按 stable ID 排序；不得重复输出同一记录 |
| 完整性 | 不按结果预算停止、不截断、不返回概率结果 |
| 主静态 self-match | 查询 ID 不属于数据库；其他 ID 的同位串仍须返回 |
| 失败条件 | 漏结果、错误结果、tuple 数值错误、重复 ID、未恢复溢出任一出现即失败 |

输出字段若继承较窄类型，必须检查其范围并记录，不能改变结果含义。[S2]

### 3.2 公共整数谓词

定义：

```text
a = popcount(q)
b = popcount(x)
c = popcount(q AND x)
u = a + b - c
```

最终命中当且仅当：

```text
n * c >= m * u
```

公共 BitBound 与最小交集：

```text
lo = ceil(m*a / n)
hi = min(D, floor(n*a / m))
c_star(a,b) = ceil(m*(a+b) / (m+n))
e(a,b) = a - c_star(a,b)
```

只枚举 `lo <= b <= hi` 的记录。在该范围内 `0 <= e < a`。整数上取整使用：

```text
ceil_div(num, den) = (num + den - 1) // den
```

不经过浮点数，不使用近似 epsilon 改变相等边界。上述条件来自 TIDE++ 的已有整数谓词；整理为 `c_star` 不是新贡献。[S2]

### 3.3 解释示例：不是实测结果

设 `a=80`，阈值 `4/5`：

| 对象置位数 `b` | 所需交集 `c_star` | 允许缺失 `e` | 精确拒绝条件 |
|---:|---:|---:|---|
| 80 | 72 | 8 | 已确定缺失至少 9 个查询特征 |
| 100 | 80 | 0 | 已确定缺失至少 1 个查询特征 |

**稀有特征不等于每个命中都必须包含的特征。**是否足以拒绝，取决于允许缺失数 `e`。

---

## 4. 数据、查询划分与输入冻结

### 4.1 数据条件

| 配置 | `surechembl256` | `chembl37_2048` |
|---|---|---|
| canonical 输入 | 现有已验证 SureChEMBL artifact | 已验收官方 ChEMBL 37 FPS |
| 宽度 | 256 bit | 2048 bit |
| 阶段 A 数据库 | 100,000 条 | 100,000 条 |
| 阶段 B 数据库 | 1,000,000 条 | 1,000,000 条 |
| 两阶段关系 | 100K 是 1M 的确定性子集 | 同左 |
| 主阈值 | `7/10`、`4/5` | 同左 |
| 动态扩展 | 条件性真实 insert-only 发布 | 本轮不作为动态 lane |

禁止将同 ID 指纹不一致的 FPS/HDF5 混用。两个条件同时改变语料和宽度，差异不能全部归因于维度。[S2]

### 4.2 数据库抽取

沿用 `config.yaml` 中的划分种子 `20260921`。[S1]

```text
输入：canonical 记录、语料命名空间、稳定 ID 编码
排序键：SHA256(protocol_seed || corpus_namespace || canonical_stable_id)
取前 1M：阶段 B 数据库
再取该顺序前 100K：阶段 A 数据库
```

哈希字段的编码、分隔和同哈希处理规则须在输入冻结时写明。不得依赖未登记的机器原生字符串或端序。

### 4.3 查询划分

| 集合 | 查询组数 | 允许用途 | 禁止用途 |
|---|---:|---|---|
| `dev` | 128 | 参数、布局、后端与开发实现选择 | 作为独立最终测试证据 |
| `A-screen` | 256 | 在冻结方法下决定阶段 A 是否放行 | 看过结果后改算法，再称同一次预登记实验 |
| `B-final` | 512 | 源码、配置、二进制冻结后的最终 GPU 测试 | 调参、挑 batch、选择 h/g、剔除不利查询 |

查询构造必须满足：

1. 从 1M 数据库以外选择非零查询；查询 ID 不在数据库中。
2. 排除已知旧实验查询 ID 及其相同位串。
3. 按查询位串分组，每组取固定代表；相同位串不跨 dev/A-screen/B-final。
4. 使用独立 query-hash seed，并在 `INPUT_FROZEN.json` 中记录；其具体值待冻结。
5. 不按命中数筛除查询；空结果、稠密结果和罕见置位数均保留。
6. 数据库位串重复记录不删除；查询分组隔离不等于数据库去重。

旧查询清单不完整时标记 `PRIOR_EXPOSURE_UNKNOWN`，不得声称严格 fresh。此处的同语料独立查询，不是自然业务日志或外部化学域泛化证据。

### 4.4 输入冻结门槛

以下任一必需字段为空，状态为 `BLOCKED_INPUT`：

| 必需字段 | 内容 |
|---|---|
| 输入身份 | canonical 路径、SHA-256、记录数、位宽、版本 |
| 编码合同 | stable-ID 类型、指纹端序、尾部位掩码规则 |
| 划分身份 | 数据库 ID、三套 query ID/位串组、独立 query seed 与哈希 |
| 既往使用 | 旧 query inventory、已知 exposure 及未知部分 |
| 环境 | 代码提交、CPU 限制、GPU 阶段的设备与资源合同 |

---

## 5. 方法与算法合同

### 5.1 最小方法矩阵

全部方法使用同一个 BitBound 和最终整数谓词。

| 标签 | 方法 | 配置空间 | 验证目的 |
|---|---|---|---|
| **R0** | BitBound + 完整指纹扫描 | 现有布局；可选常规 word-major 布局 | 强扫描基线 |
| **R1** | 逐 64-bit 字扫描 + 剩余交集上界早停 | 自然字序 / query-word popcount 降序 | 普通早停是否已足够 |
| **R2** | 分段 popcount 上界 + 公共验证器 V | `g ∈ {4,8}` | 普通小摘要是否已足够 |
| **B** | 精确置位数桶内的转置位图前缀过滤 + V | `h ∈ {1,8}` | 位图内容访问是否划算 |
| **P** | 与 B 相同前缀的稀疏倒排计数 + V | `h ∈ {1,8}` | 相同语义下的稀疏访问对照 |

P 必做 CPU 候选、空间与工作量对照；GPU 实现有条件。上述均为普通控制或探针，不预先主张新算法。

### 5.2 公共验证器 V

R2/B/P 的幸存对象使用同一个验证器 `V`。V 从 R0/R1 的单对象精确验证方式中，在 dev 上选择并冻结。

必须满足：

- 过滤通过只是必要条件，不能直接当成最终命中。
- 为输出准确 `c/u`，真正命中对象仍需完成精确计数。
- survivor gather、验证和结果转换全部计费。
- 不让某个方法独享更强验证器或更好的内存管理。

### 5.3 R0：强完整扫描

复用原生 TIDE 查询运行时，独立验证 2048-bit 实例。允许相同的 staging/workspace 复用、真正 GPU batch 与合理合并访存。

在 dev 最多比较现有布局和一个常规 word-major 布局。不得以旧 Gate 0 不完整计时作为分母，也不得把 batch=8 实现为八次同步 API 调用来弱化基线。[S0][S4]

### 5.4 R1：无新增逐行摘要的精确早停

已读字上的状态：

```text
c_s：已读交集数
a_s：已读 query 置位数
b_s：已读 object 置位数

upper = c_s + min(a-a_s, b-b_s)
upper < c_star  → 拒绝
```

`a_s` 可由查询预计算；`b_s` 需要对已加载对象字做 popcount，其额外指令必须计入。不能免费知道对象未读部分的内容。

仅两种字序：

| 配置 | 顺序 |
|---|---|
| natural | 原始 word index |
| query-popcount | query-word popcount 降序，word index 打破并列 |

顺序构造成本计入查询；不能按对象真值选择顺序。每数据条件在 dev 选一个跨两个阈值共用的配置。

### 5.5 R2：分段计数上界

将原始位位置等长分成 `g=4` 或 `g=8` 段。每对象每段保存 `uint16` 置位数 `b_j`；查询计算 `a_j`。

```text
upper_seg = sum_j min(a_j, b_j)
upper_seg < c_star  → 拒绝
否则                → V
```

不学习新的位重排。摘要读取、查询准备、候选收集和 V 均计费。

解释例子：query 段计数 `[20,20,20,20]`，object 为 `[5,25,25,25]`，最大交集为 65；若要求 72，即可拒绝。此例不是实测结果。

### 5.6 B/P 公共规则：允许缺失的前缀

#### 数据组织

按 `(popcount, stable_id)` 建库，每个真实 `b` 值独立为桶。每个 `(run,b)` 的 `df[b,j]` 只由该 run 的数据库计算。

对 query 的所有置位特征，按以下顺序排列：

```text
df[b,j] 升序 → bit index 升序打破并列
```

频率仅影响访问顺序，不是正确性假设。不得利用测试答案选择特征。

#### 过滤规则

对固定 `query/run/b/h`：

```text
e = a - c_star
L = min(a, e+h)
t = L-e
prefix = 排序后的前 L 个 query 置位特征
c_L(x) = object 在 prefix 中的命中特征数

c_L(x) < t   → 拒绝
c_L(x) >= t  → 进入 V
```

正确性依据：前缀外只剩 `a-L` 个 query 特征。如果 `c_L+(a-L)<c_star`，后续全部命中也不够。该必要条件不是本轮新颖性声明。

#### 两个固定配置

| h | 通常执行形态 | 截断边界 |
|---:|---|---|
| 1 | 前缀至少命中一个特征，即 prefix-union | 仍以实际 `L,t` 为准 |
| 8 | 较长前缀，需要更多命中 | `L` 截到 `a` 时，不强行要求 8，使用 `t=L-e` |

当 `a=b=80, τ=4/5`：h=1 对应前 9 位至少命中 1 位；h=8 对应前 16 位至少命中 8 位。

**B 与 P 在同一个 query/run/b/h 下的候选 ID 集必须完全相同。**不同即实现错误，不是合法的召回—性能折中。

### 5.7 B：未压缩逐特征转置位图

| 要素 | 固定规则 |
|---|---|
| 内容 | 每 `(run,b,j)` 保存该桶各对象是否包含特征 j |
| 处理块 | 64 行一个 `uint64` tile |
| 桶尾 | 最后不足 64 行使用 valid mask |
| `t=1` | OR 前缀位图 |
| `t>1` | 普通 bit-sliced 二进制计数，`ceil(log2(L+1))` 个平面，再比较 `count>=t` |
| 状态 | 以 tile 为单位；不默认分配每 query N 个整数计数器 |
| 验证 | 幸存者读取原始指纹调用 V |
| 存储 | 原始行数据与转置列数据、频率、目录、padding 全计费 |

必须计入 query 特征排序、逐 b 描述符、candidate mask 转换以及寄存器溢出产生的 local traffic。不得将逐 bit/逐桶 host 同步排除在计时外。

B 不等于文献中的 hashed Bitmap Filter 原样实现；这里没有哈希压缩。[S0]

### 5.8 P：未压缩稀疏倒排

每 `(run,b,j)` 保存有该特征的桶内 sorted `uint32` row-ID 列表。公共 stable-ID 数组用于最终映射，倒排表不重复保存全局 64-bit ID。

CPU 诊断可使用合并/RLE 得到前缀命中计数。GPU 若获准开发，必须在计时前冻结采用 atomic counters 还是排序/RLE，并计入清零、scatter、排序、去重、容量处理及全部 workspace。

**第一版不新增压缩格式。**未压缩 P 超预算，只否定该具体表示；不能外推为压缩倒排、GENIE 或所有稀疏索引都不可行。

---

## 6. 实验矩阵与配置冻结

### 6.1 阶段矩阵

| 阶段 | 数据库 | 查询 | 方法 | 主要输出 | 是否计 GPU 性能 |
|---|---:|---|---|---|---|
| A0 | 合成小宇宙及定向边界 | 穷举/固定 fixture | R0/R1/R2/B/P | 语义与容量检查 | 否 |
| A1-dev | 每数据条件 100K | 128 dev | 全部登记配置 | 参数与访问模型选择 | 否 |
| A1-screen | 每数据条件 100K | 256 A-screen | 冻结配置 | 独立正确性、工作量、资源 | 否 |
| B0-dev | 获准条件 1M | 原 128 dev | 普通控制 + 最多一个 B/P | GPU 配置与二进制冻结 | 仅开发 |
| B-final | 获准条件 1M | 封存 512 B-final | 已冻结方法 | 完整查询与 profiler 归因 | 是；profiler 另计 |
| C | 一次合法真实发布 | 固定回归与可见性查询 | 静态获胜路径、all-delta | 新索引发布兼容性 | 单独报告 |

### 6.2 选择规则

| 项目 | 允许范围 |
|---|---|
| 参数来源 | 仅 dev；每方法、每数据条件一个配置 |
| 阈值共享 | 同一配置同时用于 `7/10`、`4/5` |
| A 比较基线 | dev 冻结的最强 R0/R1 |
| B 比较基线 | dev 冻结的最快合法 R0/R1/R2 |
| B/P 开发数量 | 最多一个 GPU 后端 |
| GPU 线程块 | B0-dev 可比较 128、256 |
| 1M 的有限开发 | 按原协议在 dev 上选择登记的字序、段数、h 与线程块；不读取 B-final |
| A-screen | 只作放行；看过后新增方法视为新协议 |
| B-final | 冻结后一次性解封，不以结果修复选择 |

v1 没有明确两个阈值的配置目标聚合、访问代理冲突裁决及并列规则，执行前须完成 §16 的书面补充。不得由脚本默认取最有利规则。

---

## 7. 工作量、时间与统计指标

### 7.1 逐查询公共计数

| 符号 | 定义 |
|---|---|
| `N` | 全库对象数 |
| `C` | BitBound 后对象数 |
| `H` | 独立 oracle 的最终命中数；这里 H 是计数，不是旧线性模型 |
| `C-H` | BitBound 后的非命中候选数 |
| `S` | 内容过滤后进入 V 的对象数 |
| `S-H` | 仍需验证的非命中候选数 |
| `FN/FP` | 漏结果/错误结果计数 |

规则：`C-H=0` 时，非命中过滤率记 `NA`，不填 100%；`C=0` 时仍计入完整接口与输出成本。

R1 主要报告 `raw_words_loaded` 与早停位置分布。它不生成独立二级候选列表，相关 S 字段可为 `NA`，不得人为制造与 B 不一致的精算口径。

### 7.2 三层访存指标

| 指标 | 定义 | 限定 |
|---|---|---|
| 逻辑请求字节 | 按明确访问过程记录所有读写次数 | 不是 DRAM 实测 |
| 布局事务代理 | 每处理步骤触达的对齐 32-byte sectors | 不模拟跨步骤缓存，不是硬件事务 |
| 实测 DRAM/L2 | 单独 profiler 采集的原始指标 | 只有 GPU 阶段能填写 |

所有方法均需计入：

```text
query_prepare / feature_order
+ raw_fingerprint_reads
+ summary / bitmap / posting_reads
+ directory / descriptor_accesses
+ candidate_state_reads_and_writes
+ candidate_conversion / gather
+ verifier_reads
+ complete_output
```

位图纯输入的量级是：

```text
8 * sum_b ceil(N_b / 64) * L_b
```

不能拿它直接与 `8*(D/64)*C` 比较后宣布加速；还要加幸存者验证、索引目录、状态 spill、候选转换和查询准备。

### 7.3 计算与控制工作量

独立记录 AND/popcount、整数比较、bit-sliced 加法、posting elements、计数器更新、候选转换、早停位置和输出量。

CPU 运行时间只作诊断。CPU 时间、理论/代理字节与 GPU 时间分表报告。

### 7.4 完整服务时间

主 timer 边界：

```text
开始：接收 host query batch、acquire epoch、查询准备之前
结束：完整 tuple D2H + 同步 + stable-ID 排序 + request owner release 之后
```

必须包含：

```text
query_prepare + bounds + feature_order + descriptor_build
+ H2D + filter + state/compaction + gather/verify
+ output + D2H + sync + host_materialize
```

oracle 比较和验证哈希放在计时后，不能将答案提供给查询执行。另报设备流水线时间与 kernel 分解，不替代主服务时间。

闭环 `QPS=Q/batch_service_time` 只表示当前执行条件的查询吞吐，不是开放队列 SLO。

---

## 8. 资源预算

设 `F=N*D/8`，原协议对 1M 静态实验登记：

```text
resident_index_cap_bytes = 2*F + 16*N + 64*1048576
query_workspace_reserved_cap = 256 MiB
whole_card_observed_cap = 4 GiB
CPU diagnostic max RSS = 8 GiB
CPU diagnostic threads <= 8
```

| 核算项 | 必须包含 |
|---|---|
| resident index | 原始指纹、stable ID、置位数、全部辅助摘要/列/倒排、频率、目录、metadata、padding、allocator reserved |
| query workspace | 候选状态、计数/排序/转换、descriptor、结果缓冲等实际 reserved |
| whole card | context/driver、模块、arena 预留、原始库副本、索引与全部设备 workspace |
| host | 主体数据、索引、查询准备、完整结果和诊断/oracle scratch 分别记录 |

**共同上限不等于相同实际用量。**必须报告 payload、used、reserved 和查询性能，不宣称严格 matched bytes。

若现有环境的 context 已使 4 GiB 合同不可运行，先修订版本并保留原因，不能在测试中提高上限。资源不支持的基线记 `RESOURCE_UNSUPPORTED`，不得记为无限慢或从结果中删除。

100K 阶段的索引预算如何映射 1M 上限，需按 §16 在执行前明确；不得在观察 A-screen 后选择更宽松规则。

---

## 9. 阶段 A：CPU 语义与机制诊断

### 9.1 A0：正确性预检

| 检查 | 必须覆盖 |
|---|---|
| 小宇宙 | D=8，255 个非零 query、256 个 object、阈值 `1/2,7/10,4/5,1/1` |
| 整数边界 | 恰等于阈值、少一个交集位、整数提升及参数拒绝 |
| 数据边界 | 全 0 数据、全 1、重复位串不同 ID、空结果 |
| 位图边界 | 尾部不足 64 行、无效尾位、空桶 |
| 候选一致性 | B/P 同规则产生相同候选，stable ID 不重复、不遗漏 |
| 容量边界 | 目录、descriptor、计数器、索引地址与输出容量 |

D=8 的组合数为 `255*256*4=261,120`。原实验包提供的命令是：

```bash
python3 reference_semantics.py --self-test
```

该脚本在原实验包中，不是本文新增的原生实现。其历史自检记录不能替代新增 C++/CUDA 路径的独立检查。[S0]

### 9.2 A1：真实数据 oracle 与工作量

1. 输入冻结后，在 100K 数据库计算 128 dev + 256 A-screen 的完整结果。
2. 独立 oracle 只使用原始位串的 AND、OR 和 popcount，不读被测 stored counts、BitBound 目录或候选列表。
3. 在小样本用第二实现交叉核对 oracle。
4. dev 上运行全部登记配置，冻结方法和对照后再评 A-screen。
5. 审计所有被过滤对象，不只检查返回对象、不抽样检查漏检。
6. 保留全部参数行、失败查询、容量拒绝和输出分布。

### 9.3 A2：放行条件

以下为预登记的投入门槛，不是理论保证：

| 条件 | 门槛 |
|---|---|
| 正确性 | 完整结果一致，0 错误剪枝、0 错误接受 |
| 资源 | 登记预算可行；完整空间账本 |
| 相对 R0/R1 | 某内容路径在同一数据条件两个主阈值上，完整访问代理均减少至少 20% |
| 因果解释 | raw 访问下降，没有遗漏前端、状态或利用 oracle 顺序 |
| B/P 的额外必要性 | 相对冻结 R2，至少一个阈值的代理再低 10%，另一个不增加超过 5% |

若只有 R2 通过，说明普通摘要有用，不支持“必须建立内容倒排索引”。

代理无法刻画缓存/计数成本时记 `INCONCLUSIVE_PROXY`。允许另行预登记最多半天 GPU dev 微测澄清成本；微测不作为完整系统加速。

**`A_GO` 只允许进入 native 验证；`A_NO_GO` 只停止这轮具体探针。**

---

## 10. 阶段 B：条件性最小 GPU 系统实验

### 10.1 B0：开发与执行冻结

| 项目 | 规则 |
|---|---|
| 数据库 | 嵌套的预定 1M |
| 可用查询 | 只使用原 dev 进行开发 |
| 方法 | R0/R1/冻结 R2 + 最多一个 A 放行的 B/P |
| 参数 | 登记的布局/字序/段数/h、线程块 128/256，有限 grid 全记录 |
| 主工作点 | batch=8；batch=1/64 不能取代主结果 |
| 复用 | 真 batch、预分配 workspace、pinned staging |
| 冻结文件 | source/build/binary/input/config 哈希写入 `FROZEN.json` 后解封 B-final |
| 安全 | 指定同一物理卡/UUID；不终止他人进程、不改时钟功耗、不盲跑旧 launcher |

### 10.2 完整输出与溢出回退

公共快路径预留每 query **65,536 tuples**，所有方法使用相同政策。

```text
正常：atomic append → 完整输出
溢出：同一个 request 内进入 count/allocate/fill
      或 workspace 有界的分块 count/fill
```

必须计入失败的第一次执行、额外 kernel、分配、复制和重试。不得从 CPU oracle 预知测试输出量后免费分配。

若公共回退未实现而出现溢出，该组为 `BLOCKED_OUTPUT`，不发布性能结论；修订后重新冻结，保留原失败，不仅补跑有利查询。

本轮默认 survivor 调用原始指纹验证器 V。继续读完所有位图来直接产出 exact c 是另一条执行路径，不能事后无声明替换。

### 10.3 重复与统计

| 项目 | 规定 |
|---|---|
| 进程 | 每数据条件 3 个 fresh-process 配对周期 |
| 方法顺序 | 拉丁轮换；阈值顺序反向或轮换 |
| 预热 | dev 5 遍 |
| 正式查询 | 512 B-final，固定排序与 batch 划分 |
| 重复 | 计时 10 遍 |
| 基础聚合 | 每进程对相同 query/batch 的重复先取 median，再形成配对比 |
| 主表 | 各进程 service median/p95、配对 ratio 的 min/median/max |
| 不确定性 | 进程数仍为 3；query bootstrap 不替代进程/硬件层不确定性 |
| p99 | 仅诊断，不作为生产尾延迟保证 |

同一请求重复十次不是十条独立查询。不利 query、进程、阈值和配置不得删除。

计数构建与计时构建必须返回同样的结果、候选和选择路径；instrumentation 开销不混入无计数构建的正式性能。

### 10.4 正确性与 profiler

GPU fixture 执行 memcheck/full leak-check、synccheck；涉及相关共享状态时增加 racecheck。它们不是一般并发正确性的完整证明。

全部正式查询及计时重复都物化完整 tuple，并在计时后与独立 1M oracle 对照。不能用错误结果充当快样本。

Profiler 请求只在 dev 中按 `C/H/a` 的典型和边界条件预先选择，保留原始指标名称/单位：DRAM、L2、warp 活跃、local spill、指令数和各 kernel 占比。NCU replay 耗时不进入服务延迟。

### 10.5 B 阶段继续门槛

在某数据条件的两个主阈值、batch=8 上，相比 dev 冻结的最快合法普通控制 R0/R1/R2：

| 条件 | 门槛 |
|---|---|
| 正确性 | 全部 tuple 一致 |
| 资源 | 所有实际资源门槛通过 |
| 完整服务中位比值 | `method/control <= 0.85` |
| 配对方向 | 3 个独立进程配对全部更快 |
| 完整服务 p95 比值 | `method/control <= 1.05` |
| 归因 | 收益可由访问/状态/执行测量解释，不拿逻辑代理当硬件时间 |

满足则记 `SYSTEM_SIGNAL`，仅代表相对已测控制有系统收益线索。R2 足够时记 `ORDINARY_SUMMARY_SUFFICIENT`；只一个阈值有效记 `NARROW_SIGNAL`，不达本轮双阈值门槛。

两个数据条件各自判定，不能合成一个掩盖不利结果的统一加速比。

---

## 11. 阶段 C：条件性发布兼容检查

**仅静态阶段有系统信号后执行。**只用一次既有、provenance 合格的真实 SureChEMBL insert-only 转移，维护策略固定 all-delta。

完整计时链：

```text
prepared raw delta
→ 建立新增摘要 / bitmap / postings
→ validation 与 upload
→ 与 raw run 一起发布同一 epoch
→ 首个完整精确查询结束
```

辅助索引构建必须包含在计时内，不能隐藏到 setup。保留 base 不变、旧 reader ownership、失败回滚和完整输出验证。

每个新 run 使用自己的 df 与目录；频率顺序影响效率，不改变精确必要条件。不得为更新索引顺序而偷偷重建全库。

不人为构造 64 次自然发布，不引入新 compaction。ChEMBL 36→37 的已知移除/替换不能丢弃后伪装成 insert-only。[S2]

本检查只支持接入现有发布路径，不支持删除、长期队列、持久化或崩溃恢复结论。

---

## 12. 成熟基线与新颖性边界

### 12.1 普通对照通过之后仍缺什么

进入论文或全规模前，至少取得一个强精确静态内容索引的同合同结果，优先 ChemDex/Multibit-tree 类，并补充可合法运行的 chemfp/FPSim2 性能上下文。

原稿明确保留 ChemDex 同合同结果缺口；缺失不是对本方法有利的证据。[S2]

| 对照情况 | 报告方式 |
|---|---|
| 同数据、同结果合同、实际运行 | 报参数、资源、完整服务计时及正确性 |
| CPU 对 GPU | 明确资源不同；不能把弱单线程时间当作 GPU 机制新颖性 |
| 无源码/许可/完整 ID 接口 | `NOT_COVERED`，保留原因 |
| 资源超限 | `RESOURCE_UNSUPPORTED`，不记为无限慢 |
| 仅语义适配、尚无 native 性能 | 只报告已覆盖层次 |

### 12.2 不能独立作为新贡献的内容

原 BitBound、普通前缀必要条件、逐字早停、分段置位计数、转置位图、倒排计数、普通压实与 epoch publication，都不作为本轮 novelty claim。[S0][S2]

B 是精确逐特征转置位图，不是文献 hashed Bitmap Filter 的原样实现；P 与 GPU 倒排检索/既有前缀过滤也需要逐项比较。本文仅保留原协议的查新边界，未在本次整理中开展新的在线查新。

---

## 13. 结果状态与停止规则

### 13.1 状态流

```text
DESIGN_ONLY
    │ 输入、参数、oracle 与资源合同齐全
    ▼
A0 correctness / boundary checks
    ├─ 输入或实现缺口 ───────────────► BLOCKED
    ├─ 正确性失败 ─────────────────► CORRECTNESS_FAIL
    ▼
A1 dev freeze → A-screen
    ├─ 无工作量优势 ───────────────► A_NO_GO
    ├─ 代理不足 ───────────────────► INCONCLUSIVE_PROXY
    │                                最多半天预登记 dev 微测
    ▼
A_GO
    ▼
B0 1M native dev freeze → B-final
    ├─ 普通摘要已足够 ──────────────► ORDINARY_SUMMARY_SUFFICIENT
    ├─ 单阈值窗口 ─────────────────► NARROW_SIGNAL
    ├─ 完整服务不获益 ──────────────► SYSTEM_NO_GO
    ▼
SYSTEM_SIGNAL
    ▼
成熟基线核查 + 条件性一次发布兼容检查
```

### 13.2 典型结果解释

| 结果 | 合法结论 | 不合法结论 |
|---|---|---|
| R1 拿走主要收益 | 普通早停已足够 | 必须建新内容索引 |
| R2 优于 B/P | 普通摘要更划算 | 给 R2 改名就是新算法 |
| B/P 少候选但更慢 | 辅助处理抵消收益 | 候选减少百分比等于加速百分比 |
| 只有 2048-bit 有效 | 条件性窗口 | 完全由维度决定，或 256-bit 实验可删除 |
| B/P 稳定胜普通控制 | 可继续与成熟精确索引比较 | 已经达到 SOTA 或完成新颖性证明 |
| 所有探针失败 | 停止本轮具体机制 | 所有精确内容索引都不可行 |

### 13.3 必须立即停止或登记新版本的情况

输入身份不一致、query 泄漏、oracle 不一致、假阴性、错误 tuple、未恢复溢出、越界/泄漏、超预算、测试后改参数，均不得继续产生正式性能结论。

失败、取消和资源拒绝写入 `attempts.jsonl`。修复公共实现时保留旧记录，并在查看新测试结果前重新冻结版本，不能覆盖不利证据。

---

## 14. 交付物与结果表模板

### 14.1 必需文件

以下是待实现实验的交付目录要求，不表示这些结果已在本次生成：

```text
experiment_root/
├── INPUT_FROZEN.json
├── FROZEN.json
├── prior_art.csv
├── per_query.csv
├── memory.csv
├── process_timing.csv
├── attempts.jsonl
├── oracle/
├── profiler/
└── DECISION.md
```

| 文件 | 最少内容 |
|---|---|
| INPUT_FROZEN | source/input/split/ID/端序、旧 exposure、各哈希 |
| FROZEN | dev 选择、资源合同、源码/构建/二进制哈希、测试解封条件 |
| prior_art | 普通探针与成熟基线的覆盖层次、许可、接口与未覆盖原因 |
| per_query | 逐 query/阈值/方法的全部正确性与工作量 |
| memory | host/device payload、used、reserved、context、workspace |
| process_timing | 进程配对、顺序、service 时间、重复与聚合 |
| attempts | 失败、取消、修复、版本与退出码 |
| oracle | 完整基准 tuples 或可独立复算的冻结归档 |
| profiler | 原始报告、请求选择、工具版本与指标单位 |
| DECISION | 正确性、资源、机制、系统、新颖性覆盖分别判定 |

### 14.2 `per_query.csv` 字段

沿用原协议的最少字段：

```text
lane,base_sha,query_sha,query_id,split,D,N,m,n,batch,
method,config_sha,a,C,H,S,
false_negative_count,false_positive_count,
raw_words_loaded,summary_bytes_read,bitmap_bytes_read,posting_bytes_read,
state_bytes_read,state_bytes_written,descriptor_bytes,
logical_total_bytes,sector_proxy_bytes,bitwise_ops,integer_ops,
output_count,overflow_retries
```

日志中另外保留 tuple 数值不一致、重复 ID、源版本和溢出状态，确保满足语义合同；字段不存在或不适用填 `NA`，不能填 0 冒充已测。

### 14.3 A 阶段主结果表

| 数据条件 | 阈值 | 方法/配置 | C | H | S/早停字数 | 原始读取 | 索引读取 | 状态读写 | 总访问代理 | 实际空间 | 全结果正确 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| PENDING | — | — | — | — | — | — | — | — | — | — | NOT_RUN |

### 14.4 B 阶段主结果表

| 数据条件 | 阈值 | Batch | 方法 | Service median | Service p95 | 3 配对比值 min/med/max | Workspace reserved | DRAM/L2 诊断 | Oracle |
|---|---|---:|---|---:|---:|---|---:|---|---|
| PENDING | — | — | — | — | — | — | — | NOT_PROFILED | NOT_RUN |

### 14.5 最终决策模板

```markdown
# 实验决策

Protocol ID: tide_content_filter_v1_20260921
Run ID: PENDING
Source / binary / input / split / config hashes: PENDING

## 范围

数据条件、数据库规模、查询集合、阈值、batch、设备、资源预算：PENDING
旧 query exposure 完整性：PENDING
参数是否先冻结：PENDING

## 分项判定

| 维度 | 状态 | 证据位置 | 限定 |
|---|---|---|---|
| correctness | NOT_RUN | — | 全部 tuple，不仅 hit count |
| resource | NOT_RUN | — | actual reserved，不仅 payload |
| mechanism | NOT_RUN | — | 完整访问与状态成本 |
| native_system | NOT_STARTED | — | 完整 service，不是 CPU/profiler 时间 |
| novelty_coverage | NOT_ESTABLISHED | — | 普通机制与成熟强基线 |

## 阶段结果

A: NOT_RUN
B: NOT_STARTED
C: NOT_STARTED

## 不利结果与未覆盖事项

PENDING

## 决策及可重新开启的条件

PENDING
```

---

## 15. 任务安排与执行检查

### 15.1 时间与产物

| 时段 | 工作 | 退出条件/交付物 |
|---|---|---|
| 日 1–2 | 数据与新查询冻结、合成自检、普通方法参考 | INPUT_FROZEN、边界测试、待补齐事项关闭 |
| 日 3–4 | 100K oracle、访问模型、dev 选择、A-screen | 完整 A 表与 A_GO/A_NO_GO/INCONCLUSIVE/BLOCKED |
| 仅必要时 | 最多半天预登记 GPU dev 微测 | 澄清访问代理，不直接宣布系统加速 |
| A 放行后日 5–9 | 最多一个内容后端、1M 原生完整计时 | B 结果、空间、正确性和 profiler 分解 |
| 日 10–14 | 成熟基线核查、统计；静态有信号才做一次发布 | 分项 DECISION 与全部未覆盖项 |

第一阶段失败后不自动扩规模、不自动换图/IVF、不自动增加学习模型、不自动重开 H。

### 15.2 执行前检查单

- [ ] 输入身份、ID 与端序明确；两种数据库是预定嵌套子集。
- [ ] 新查询已冻结，旧 exposure 未知部分已披露，B-final 已封存。
- [ ] 独立 oracle 不使用待测索引或 stored count。
- [ ] R0/R1/R2/B/P 语义正确，B/P 候选完全一致。
- [ ] 访问代理、配置聚合/并列规则和预算已在结果前冻结。
- [ ] 原始指纹、辅助索引、状态与输出均计入空间/工作量。
- [ ] GPU UUID、空闲/独占条件和停止权限确认，不盲跑旧脚本。
- [ ] 公共输出溢出可恢复；失败记录与测试后改版规则可追踪。
- [ ] A/B 的继续标准分别使用代理与完整服务，不混用。
- [ ] 结果只写已验证范围，不把 NO_GO 删除，也不把 PASS 写成 novelty。

---

## 16. 待补齐事项：不得静默设默认值

本文不替执行者补造未提供的环境或方法细节。下面各项须在相应阶段前登记；若会改变已冻结实验合同，应保留修订版本，而不是覆盖 v1。

| 项目 | 当前状态 | 必须在何时确定 |
|---|---|---|
| 两个 canonical 文件路径/哈希/记录数 | PENDING | A0 前 |
| stable-ID/端序/哈希字段编码 | PENDING | INPUT_FROZEN 前 |
| 独立 query-hash seed | v1 要求独立，具体值未固定 | 划分前 |
| 旧 query inventory 与未知 exposure | PENDING | 查询冻结前 |
| 两阈值配置目标的聚合与并列规则 | v1 未细化 | dev 选择前 |
| A 主访问代理：逻辑字节与 sector 代理如何使用 | 两者都要求报告，冲突裁决未细化 | A-screen 前 |
| 100K 的索引预算映射 | v1 明确登记的是 1M 公式 | A 预算审查前 |
| 2048-bit 原生入口与每 b 描述符容量 | 需要实现审计 | GPU 冻结前 |
| P 的 GPU 状态实现 | 仅获准后选择；未固定 | P 开发与计时前 |
| 输出回退采用 count/fill 还是 chunked count/fill | 原协议允许两者，具体实现未固定 | B-final 前 |
| p95 跨三个进程的正式 gate 聚合 | v1 要求报告逐进程值，精细 gate 聚合未定义 | B-final 前 |
| GPU UUID、工具链与 profiler 原指标 | PENDING | B0 前 |
| 成熟强基线的源码/许可/适配合同 | PENDING | 论文或全规模前 |
| 一次真实增量的具体 base/delta 身份 | PENDING | C 前 |

未解决项应报告 `BLOCKED` 或明确未覆盖，不能在最终数据出来后挑有利解释。

---

## 17. 来源与版本记录

### [S0] 上一轮完整实验包

- `tide_content_filter_protocol/PROTOCOL.md`
- `tide_content_filter_protocol/config.yaml`
- `tide_content_filter_protocol/DECISION_TEMPLATE.md`
- `tide_content_filter_protocol/SEMANTIC_TESTS.txt`
- `tide_content_filter_protocol/reference_semantics.py`

本结构化版读取的原 `PROTOCOL.md` SHA-256：

```text
9b467bcd43149b9f7568c332adaa57ec3443ecc20e5419e44690fc721b86e10e
```

整理时未改写原协议与原实验包，也未重新运行其中的语义测试。历史 6 组自检通过来自原包保留记录，不是本次新增成绩。

### [S1] 已登记配置

原 `config.yaml` 中的 protocol ID、划分 seed、样本数、阈值、方法 grid、资源预算、A/B 门槛及安全要求，是本结构化版的参数来源。

### [S2] 用户上传的化学版 TIDE++ 稿件

文件：`TIDE++__Release_Ready_Exact_GPU_Tanimoto_Search_over_Growing_Chemical_Fingerprint_Collections__1_(2).pdf`

使用位置：§2.1 整数精确合同；§4 原生实现与完整输出；§5.5 LES³ 的已披露条件；§5.10 BitBound 消融；§7 基线与数据/更新范围限制。

### [S3] 固定 Gate 2 报告

```text
repository: wangwenqingqq/GTSPP-TIDEpro
commit: e21f13167cbe8c6abc4e9dc35a0e864ed7085a1c
path: results/gate2_20260915/REPORT.md
https://github.com/wangwenqingqq/GTSPP-TIDEpro/blob/e21f13167cbe8c6abc4e9dc35a0e864ed7085a1c/results/gate2_20260915/REPORT.md
```

本次仅继承上一轮协议已经采用的固定报告，不把它当成本轮新性能结果。

### [S4] 固定 native runtime 参考

```text
repository: wangwenqingqq/GTSPP-TIDEpro
commit: e21f13167cbe8c6abc4e9dc35a0e864ed7085a1c
path: experiments/gate1/runtime.cuh
https://github.com/wangwenqingqq/GTSPP-TIDEpro/blob/e21f13167cbe8c6abc4e9dc35a0e864ed7085a1c/experiments/gate1/runtime.cuh
```

### [S5] 原协议保留的先例核查入口

以下是继承的查新入口，不表示本次重新检索或完成同机对照：

```text
Bitmap Filter: https://arxiv.org/abs/1711.07295
GENIE: https://arxiv.org/abs/1603.08390
chemfp shardsearch: https://chemfp.com/docs/chemfp_shardsearch_command.html
```

- Swamidass & Baldi，2007，*Bounds and algorithms for fast exact searches of chemical fingerprints in linear and sublinear time*。
- Aung & Ng，2010，*An indexing scheme for fast and accurate chemical fingerprint database searching*。

**交付完成标准：**给出一份能够区分“语义正确”“信息成本降低”“完整服务获益”和“新颖性已覆盖程度”的决策记录，而不是只给出一个候选减少率或局部 kernel 加速比。
