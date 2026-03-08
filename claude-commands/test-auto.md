---
description: ﻿# 辅助命令：阶段8 自动化测试执行（Runtime / Python）
---

﻿# 辅助命令：阶段8 自动化测试执行（Runtime / Python）

说明：仅用于手工补跑自动化验证，主线仍推荐 `/test-loop`。

执行：
1. 读取 `runtime.compile_command/test_command/unit_test_command`。
2. 执行编译、系统测试、单元测试。
3. 输出运行报告与失败日志。

报告输出：`.pipeline/test-auto-report.md`
