# SmartRoute V3.0

## 架构分层

- 前台指挥部（Claude Code CLI / 强模型）  
  `Assistant -> PM -> Architect -> QA Lead -> Reviewer -> DevOps`
- 后台兵工厂（Python Orchestrator / 角色流水线）  
  `Planner -> Coder -> Test Coder -> Runtime -> Fixer -> Debug Expert`

> V3.0 已移除 `worker` 概念，后端按生命周期角色执行。

## 生命周期角色映射（1-12）

| 阶段 | 角色 | 物理层 |
|---|---|---|
| 1 日常提问 | Assistant | Claude Code CLI |
| 2 需求分析 | PM | Claude Code CLI |
| 3 设计文档 | Architect | Claude Code CLI |
| 4 测试任务交接 | QA Lead | Claude Code CLI |
| 5 任务拆解 | Planner | Python Orchestrator |
| 6 业务编码 | Coder | Python Orchestrator |
| 7 测试编码 | Test Coder | Python Orchestrator |
| 8 编译/测试执行 | Runtime | Python 子进程 |
| 9 自动修复 | Fixer / Debug Expert | Python Orchestrator |
| 10 代码审查 | Reviewer | Claude Code CLI |
| 11 Review 修改闭环 | Reviewer + Coder | CLI + Python |
| 12 Git 提交 | DevOps | Claude Code CLI |

## Python 流水线（步骤 5-9）

1. `Planner` 读取 `.smartroute/task.md`，生成 `.smartroute/Execution_Plan.json`
2. `Coder` 按原子步骤生成业务代码
3. `Test Coder` 生成系统测试/单元测试代码
4. `Runtime` 执行 `cmake/make/ctest` 或配置命令
5. `Fixer` 失败修复（最多 `max_retries`）
6. 超限升级 `Debug Expert`，输出诊断方案并回落给 `Coder`

## 关键目录

- `.smartroute/task.md`：CLI → Python 任务交接
- `.smartroute/Execution_Plan.json`：Planner 执行计划
- `.pipeline/context/`：Context Manager
- `.pipeline/logs/`：Observability（含 `trace.jsonl`）
- `.smartroute/artifacts/execution_xxx/`：Artifact Manager

## 配置入口

唯一入口：`smartroute.config.json`

核心段：

- `roles.planner/coder/test_coder/fixer/debug_expert`
- `engine_settings`
- `runtime`
- `artifact_policy`
- `logging`

## 运行方式

源仓（smartroute-kit）：

```bash
python pipeline/setup.py
python pipeline/test_loop.py --project-dir . --task .smartroute/task.md
```

安装到业务项目后：

```bash
python .pipeline/setup.py
python .pipeline/test_loop.py --project-dir . --task .smartroute/task.md
```

## 命令映射

- 严格 12 阶段命令映射见：
  [claude-commands/STAGE-MAP.md](claude-commands/STAGE-MAP.md)
