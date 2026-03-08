---
description: ﻿# 阶段4：测试任务交接（QA Lead / CLI）
---

﻿# 阶段4：测试任务交接（QA Lead / CLI）

> 目标：生成交接书 `.smartroute/task.md`，作为 Python 兵工厂入口。

执行：
1. 读取 `documents.detailed_design`、系统/单元测试文档路径。
2. 明确本轮最小可交付范围。
3. 生成 `.smartroute/task.md`，必须包含：

```markdown
[Task Objective]
...

[Strict Rules]
...

[Target Files]
- src/...
```

4. 若任务过大，拆分为多轮 task，不得一次覆盖全仓。

输出：
- `.smartroute/task.md`
- 触发主线命令：`/project:test-loop`
