# 启动自动化测试循环（Python 脚本）

此命令触发方案C的核心自动化流水线。

请执行以下操作：

1. 确认当前代码已编译通过
2. 执行以下命令启动自动化测试循环：

```bash
cd $PROJECT_DIR
python3 .pipeline/test_loop.py \
  --project-dir . \
  --compile-cmd "[请替换为项目编译命令]" \
  --test-cmd "[请替换为系统测试命令]" \
  --unit-test-cmd "[请替换为单元测试命令]" \
  --max-retries 3
```

如果需要处理用户提交的 Bug 并触发漏测反思，加上 --bug-report 参数：
```bash
python3 .pipeline/test_loop.py \
  --project-dir . \
  --max-retries 3 \
  --bug-report "$ARGUMENTS"
```

3. 脚本会全自动完成：
   - 编译验证
   - 系统测试执行
   - MiniMax 修复失败的测试（最多重试 3 次）
   - 超过 3 次自动升级到 Opus 诊断
   - Opus 给出方案后自动切回 MiniMax 执行
   - 漏测反思和文档更新（如有 Bug 报告）
   - 单元测试执行

4. 脚本完成后，查看结果：
   - `.pipeline/test-loop-report.md` — 执行报告
   - `.pipeline/last-state.json` — 最终状态（可断点恢复）
   - `docs/test/system-test-cases.md` — 可能已被自动更新
