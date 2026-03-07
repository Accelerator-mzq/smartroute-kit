# 辅助命令：阶段9 问题定位与修复（Fixer / Debug Expert）

说明：仅用于紧急手动会诊；主线仍推荐 `/project:test-loop` 自动闭环。

执行：
1. 复现并定位问题，先由 Fixer 尝试修复。
2. 连续失败超阈值，升级 Debug Expert 产出诊断方案。
3. 回落 Coder 落地方案并重跑验证。

输出：
- 修复记录与根因结论
- 必要时更新 `.smartroute/task.md` 再回主线
