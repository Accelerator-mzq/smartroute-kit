---
description: ﻿# 阶段10：代码 Review（Reviewer / CLI）
---

﻿# 阶段10：代码 Review（Reviewer / CLI）

> 路径以 `smartroute.config.json.documents` 为准。

执行：
1. 对照需求、设计、测试文档做一致性审查。
2. 重点检查：功能缺失、边界风险、安全问题、测试不足。
3. 按严重度输出问题清单。

输出：
- `documents.review_dir/review-report-{日期}.md`
- 若存在问题，进入阶段11：`/project:review-fix`
