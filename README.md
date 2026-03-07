# SmartRoute V3.0

SmartRoute V3.0 是「Claude Code 前台 + Python Orchestrator 后台」的任务协作框架。  
V3.0 只保留 `roles` 配置，不再使用 CCM，不再使用 `models.fast/models.strong`。

## 配置步骤

### 步骤 1：初始化项目（推荐业务仓）

```bash
bash smartroute-kit/init-smartroute.sh /path/to/your/project
cd /path/to/your/project
```

### 步骤 2：编辑统一配置 `smartroute.config.json`

最少填写 5 个角色：
- `planner`
- `coder`
- `test_coder`
- `fixer`
- `debug_expert`

每个角色必须有：
- `name`
- `provider_type`
- `api_key`
- `base_url`

示例：

```json
{
  "roles": {
    "planner": {
      "name": "claude-sonnet-4-5",
      "provider_type": "anthropic",
      "api_key": "填入你的 Key",
      "base_url": "https://api.anthropic.com"
    },
    "coder": {
      "name": "MiniMax-M2.5-highspeed",
      "provider_type": "openai",
      "api_key": "填入你的 Key",
      "base_url": "https://api.minimaxi.com/v1"
    },
    "test_coder": {
      "name": "MiniMax-M2.5-highspeed",
      "provider_type": "openai",
      "api_key": "填入你的 Key",
      "base_url": "https://api.minimaxi.com/v1"
    },
    "fixer": {
      "name": "MiniMax-M2.5-highspeed",
      "provider_type": "openai",
      "api_key": "填入你的 Key",
      "base_url": "https://api.minimaxi.com/v1"
    },
    "debug_expert": {
      "name": "claude-opus-4-6",
      "provider_type": "anthropic",
      "api_key": "填入你的 Key",
      "base_url": "https://api.anthropic.com",
      "temperature": 0.2,
      "max_tokens": 8192
    }
  },
  "runtime": {
    "compile_command": "make -j4",
    "test_command": "./bin/system_tests",
    "unit_test_command": "./bin/unit_tests",
    "test_timeout_seconds": 120
  },
  "engine_settings": {
    "max_retries": 3,
    "max_loops": 30,
    "context_limit": 12000
  },
  "artifact_policy": {
    "mode": "per_execution"
  },
  "logging": {
    "enabled": true,
    "capture_prompts": true,
    "capture_responses": true
  }
}
```

> **高阶特性指引**：
> - `artifact_policy` 控制物理版本回溯能力（Time Travel），避免被次级模型破坏环境。
> - `logging` 控制 AI 的日志埋点（Observability），启用会带来 `.pipeline/logs` 的链路溯源收益。
> - `temperature` 及 `max_tokens`：针对具体不同身份模型发散率的精准控制。

### 步骤 3：同步配置

```bash
python .pipeline/setup.py --check
python .pipeline/setup.py
```

作用：
- 生成/更新 `.env`
- 更新 `CLAUDE.md`
- 创建 `.pipeline/` 与 `.smartroute/` 目录

### 步骤 4：运行阶段 5-9 流水线

创建 `.smartroute/task.md`：

```markdown
[Task Objective]
实现 xxx 功能

[Strict Rules]
- 不修改公共接口签名
- 仅允许修改目标文件

[Target Files]
- src/xxx.cpp
- include/xxx.h
```

执行：

```bash
python .pipeline/test_loop.py --project-dir . --task .smartroute/task.md
```

带 Bug 反思：

```bash
python .pipeline/test_loop.py --project-dir . --task .smartroute/task.md --bug-report "xxx问题"
```

## `documents` 路径配置

`smartroute.config.json` 的 `documents` 是统一路径入口。  
修改文档路径后，Python 流水线与命令执行时会读取最新配置。

## 源码仓与安装仓

- 源码仓（`smartroute-kit`）：开发框架本体，命令用 `pipeline/...`
- 安装仓（你的业务项目）：使用框架，命令用 `.pipeline/...`

## 12 阶段命令映射

见 [claude-commands/STAGE-MAP.md](claude-commands/STAGE-MAP.md)。
