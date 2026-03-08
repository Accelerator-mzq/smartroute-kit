---
description: ﻿# SmartRoute 12阶段命令映射（严格版）
---

﻿# SmartRoute 12阶段命令映射（严格版）

本表定义主线阶段与命令映射。主线阶段必须按 1→12 执行。

| 阶段 | 研发任务 | 角色 | 物理层 | 主命令 | 产出 |
|---|---|---|---|---|---|
| 1 | 日常提问 | Assistant | CLI | `/assistant` | 技术答复 |
| 2 | 需求分析 | PM | CLI | `/requirements` | 需求文档 |
| 3 | 设计文档 | Architect | CLI | `/design` | 架构/详细设计 |
| 4 | 测试方案与交接 | QA Lead | CLI | `/test-plan`（或`/code`） | 系统测试用例 + 自动化方案 + `task.md` |
| 5 | 任务拆解 | Planner | Python | `/test-loop` 内部执行 | `Execution_Plan.json` |
| 6 | 业务编码 | Coder | Python | `/test-loop` 内部执行 | 业务代码 |
| 7 | 测试编码 | Test Coder | Python | `/test-loop` 内部执行 | 测试代码 |
| 8 | 自动化验证 | Runtime | Python子进程 | `/test-loop` 内部执行 | 编译/测试结果 |
| 9 | 自动修复 | Fixer / Debug Expert | Python | `/test-loop` 内部执行 | 修复与诊断 |
| 10 | 代码审查 | Reviewer | CLI | `/review` | Review报告 |
| 11 | Review修改闭环 | Reviewer + Coder | CLI+Python | `/review-fix` | 新版task.md + 回归结果 |
| 12 | 上传Git | DevOps | CLI | `/git-push` | Commit + Push |

## 辅助命令（非主线）

- `/test-code`：仅手动补测代码（对应阶段7）
- `/test-auto`：仅手动跑自动化测试（对应阶段8）
- `/test-fix`：仅手动定位修复（对应阶段9）

主线要求：阶段 5-9 统一由 `/test-loop` 驱动，不允许 CLI 手工拆开执行替代主线。
