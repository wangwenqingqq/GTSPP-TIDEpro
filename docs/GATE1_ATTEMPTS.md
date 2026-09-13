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
