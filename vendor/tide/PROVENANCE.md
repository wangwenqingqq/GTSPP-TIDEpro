# 冻结查询 runtime 来源

从用户授权的 pro6000-8 TIDE 工作区读取，不从论文伪代码重建。
原 artifact 为 `tide_surechembl_gate6_20260828/experiments/
tide_20260904_fusion_fair_control_gate0/src/fair_dispatch.cu`，
SHA256 `8c0add9b2204fe75b93786bce6293cc9dea7ce9db146b00b7c2bb9730f5d867d`。
该目录无 Git 元数据，因此这是固定 artifact 身份，不冒充权威 Git 提交。

`frozen_query_runtime.cuh` 是上述源的前 579 行，加 namespace 闭括号。
设备查询函数和 `QueryRuntime` 不变；移除了旧主程序，避免运行旧 campaign。
原始文件仅保存在忽略的 `private/source-evidence/` 供字节检查。
该 runtime 只在其固定接口范围内复用；本轮重新运行正确性门禁。

不为既有研究代码重新选择许可证；本仓库保持私有。不是完整 GTSPP 迁移，
也不恢复任何旧 direct-insert/近似剪枝主张。
