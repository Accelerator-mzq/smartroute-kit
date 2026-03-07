# SmartRoute V3.0 配置文档

## 1. 角色划分

### 前台指挥部（CLI，强模型）

- Assistant（问答）
- PM（需求分析）
- Architect（设计文档）
- QA Lead（测试任务交接）
- Reviewer（代码审查）
- DevOps（提交与发布）

### 后台兵工厂（Python Orchestrator）

- Planner（任务拆解）
- Coder（业务编码）
- Test Coder（测试编码）
- Runtime（本地编译/测试执行）
- Fixer（失败修复）
- Debug Expert（超限会诊）

## 2. 配置结构

```json
{
  "roles": {
    "planner": {},
    "coder": {},
    "test_coder": {},
    "fixer": {},
    "debug_expert": {}
  },
  "engine_settings": {},
  "runtime": {},
  "artifact_policy": {},
  "logging": {},
  "documents": {}
}
```

## 3. roles 说明

- `planner`：建议强模型（anthropic）
- `coder`：建议快模型（openai）
- `test_coder`：建议快模型（openai）
- `fixer`：建议快模型（openai）
- `debug_expert`：建议强模型（anthropic）

## 4. 任务交接

文件：`.smartroute/task.md`

```markdown
[Task Objective]
...

[Strict Rules]
...

[Target Files]
- src/xxx.cpp
```

Planner 会据此生成 `.smartroute/Execution_Plan.json`。

## 5. 执行命令

源仓：

```bash
python pipeline/setup.py
python pipeline/test_loop.py --project-dir . --task .smartroute/task.md
```

安装版：

```bash
python .pipeline/setup.py
python .pipeline/test_loop.py --project-dir . --task .smartroute/task.md
```
