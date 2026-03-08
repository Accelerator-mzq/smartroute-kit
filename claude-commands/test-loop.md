---
description: ﻿# 阶段5-9：兵工厂自动执行（Python Orchestrator）
---

﻿# 阶段5-9：兵工厂自动执行（Python Orchestrator）

此命令是主线入口，严格覆盖阶段5-9：
- 5 Planner
- 6 Coder
- 7 Test Coder
- 8 Runtime
- 9 Fixer / Debug Expert

执行：
```bash
cd $PROJECT_DIR
python3 .pipeline/test_loop.py \
  --project-dir . \
  --task .smartroute/task.md \
  --max-retries 3
```

若需漏测反思：
```bash
python3 .pipeline/test_loop.py \
  --project-dir . \
  --task .smartroute/task.md \
  --max-retries 3 \
  --bug-report "$ARGUMENTS"
```

执行后检查：
- `.smartroute/Execution_Plan.json`
- `.pipeline/test-loop-report.md`
- `.pipeline/logs/trace.jsonl`
- `.smartroute/artifacts/execution_xxx/`

约束：阶段5-9不应被CLI手工拆散替代。
