# 首轮尝试记录

- 2026-09-13：初始 `nvcc` 命令经 `/usr/local/bin/nvcc` 跳转，编译报告
  `cuda_runtime.h` 不存在；未运行 GPU。读取工具链后确认完整 CUDA 13.1.115
  在 `/usr/local/cuda-13.1/`，改用该目录下的明确编译器路径。
- 输入准备成功：初始 996,854 行；六次增量依次为 584、80,753、202、3,612、
  434、551 行；最终 1,082,990 行。实际源文件只读，抽样行完整 popcount 和
  全历史 stable-ID 唯一性检查通过。输入准备墙钟 5.224 秒，不是 GPU 发布延迟。
- CPU 阶段随后完成：CUDA 13.1.115 编译通过（34 registers、无 spill），
  fixture / 百万行各 448 个独立完整 oracle vectors；后者 CPU 扫描约 2.465 秒。
- 首次 GPU wrapper 在打开现有 `/tmp` 共享锁时遇到 PermissionError，未启动
  GPU 子进程；同时读到 GPU 1 已被其他任务占用。未删除/替换锁、未改权限。
  对已存在的锁改用不带 O_CREAT 的 `r+`，并保留 nonblocking exclusive flock。
  参数化 GPU index/UUID，所有方法仍在同一张新获准空闲卡上从头验证/计时。
- GPU 6 成功运行于 01:00–01:01（Asia/Shanghai）：overflow/空候选 guard、
  fixture、memcheck、synccheck 通过；四个新进程均完成。wrapper 含间隔/监控
  的墙钟 59.45 秒，不等于有效 kernel 时间，也不是生产吞吐测量。
- 第一次下载日志用了该 SCP 实现不接受的末尾 `/.`，传输拒绝；改用明确的
  目录名后下载成功。这不是实验失败，没有重跑/替换 GPU 样本。
- 所有 7,168 个计时请求完整正确，未观察到稳定的压实查询收益；详见结果报告。
