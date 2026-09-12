# 原代码与远端交接

## 本次做了什么

新增 CPU 参考和回归、评估文件、实验卡。本地已运行测试；没有克隆/迁移原 GTSPP CUDA 项目，没有获取旧实验 CSV/二进制，没有修改原有仓库，也没有连接服务器。本包不含 GPU 编译器配置和可发表的新实验结果。

原公开项目入口为 https://github.com/wangwenqingqq/GTSPP 。正式迁移必须确定真实权威提交，不要从 PDF 伪代码或对话片段拼出“原实现”。

## 最小迁入材料

固定提交的 C++/CUDA 源码和构建说明；每个保留实验的输入/查询/trace 哈希、run card、完整 oracle、原始记录；实际执行的 GPU/驱动/CUDA 信息；第三方依赖版本与许可证。请通过明确的代码归档或已授权连接移交，不要提交 token、SSH 密钥、Cookie。

可保留旧代码为 legacy 子模块或独立分支，但在复核以前必须标记旧 direct-insert / calibrated-recall 主张未恢复。正式运行始终把“本次版本已验证”和“历史记录报告已验证”分开。

## 远端仓库

建议名称 `GTSPP-TIDEpro`，显示标题 `GTSPP & TIDEpro`。这个名称是建议的规范化路径，不是论文新颖性主张。默认 private，不触及既有 GTSPP。

当前会话 GitHub 连接未安装，尚无写入权限。`scripts/create_private_repo.sh` 可在用户自己的、已安装 GitHub CLI 且登录正确账户的环境使用。脚本只推送白名单中校验通过的本次起始文件，拒绝现有 origin、已有历史或其他已跟踪文件；不会克隆旧项目、设置访问凭据或修改全局 git 身份。

先检查提交者身份和授权：

```bash
git config --get user.name
git config --get user.email
gh auth status
```

若无身份信息，由你使用自己的真实信息配置，脚本不会代填。远端创建与推送由 [GitHub CLI 官方 gh repo create](https://cli.github.com/manual/gh_repo_create) 的 `--private --source --remote --push` 完成。

执行中网络/授权失败可能留下本地初次提交或已创建远端；脚本不做删除回滚。检查现状后人工恢复，不要删已有研究成果。

## 后续 GPU 接口必须额外覆盖的测试

实际 CUDA 发布完成事件先于可见 epoch；每请求保存 owner 直到输出传输完成；老版本回收不能越过 GPU in-flight reader；完整结果缓冲不能静默截断；分配/传输失败不发布；索引插入真实新对象后每步 oracle；GPU sanitizer；真实长序列和峰值内存。CPU 锁实现通过不代表这些 GPU 条件已经通过。
