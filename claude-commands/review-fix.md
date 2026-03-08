---
description: ﻿# 阶段11：Review 修改闭环（Reviewer + Coder / CLI+Python）
---

﻿# 阶段11：Review 修改闭环（Reviewer + Coder / CLI+Python）

执行：
1. 读取最新 Review 报告，按严重度逐项处理。
2. 每修复一项更新状态（已修复/暂不修复+原因）。
3. 若涉及较大改动，更新 `.smartroute/task.md`。
4. 回调主线验证：`/test-loop`。

输出：
- 更新后的 review 报告
- `.pipeline/review-fix-summary.md`
- 验证结果摘要
