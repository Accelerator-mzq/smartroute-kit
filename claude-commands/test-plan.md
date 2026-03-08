---
description: ﻿# 阶段4：测试任务交接（QA Lead / CLI）
---

﻿# 阶段4：测试任务交接（QA Lead / CLI）

> 目标：生成系统测试用例、自动化测试方案，并输出本轮交接书 `.smartroute/task.md` 作为 Python 兵工厂入口。

执行：
1. **[TDD 标准测试前移]**：读取 `documents.requirements_dir` (需求) 和 `documents.detailed_design` (设计)。
2. 根据需求点与设计的对应关系，强制生成完整的**《系统测试用例文档》**（保存至 `documents.system_test_cases`）。
3. 接着，基于生成的系统测试用例，生成对应的**《自动化测试方案》**（保存至 `documents.automation_plan`）。
4. 在上述规范确立后，明确本轮最小可交付编码范围，生成给兵工厂的 `.smartroute/task.md`，必须包含：

```markdown
[Task Objective]
...

[Strict Rules]
- 必须严格遵守并覆盖新生成的自动化测试方案中要求的单元测试断言。

[Target Files]
- src/...
```

5. 若任务过大，拆分为多轮 task，不得一次覆盖全仓。

输出：
- `documents.system_test_cases`
- `documents.automation_plan`
- `.smartroute/task.md`
- 触发主线命令：`/test-loop`
