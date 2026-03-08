# SmartRoute V3.0 配置文档

## 配置步骤

### 步骤 1：初始化项目

```bash
bash smartroute-kit/init-smartroute.sh /path/to/your/project
cd /path/to/your/project
```

如果你当前就在 `smartroute-kit` 仓库中测试，也可直接：

```bash
bash init-smartroute.sh .
```

### 步骤 2：编辑统一配置 `smartroute.config.json`

V3.0 只保留 `roles`，不再使用 `models.fast/models.strong`。

```json
{
  "roles": {
    "planner": {
      "name": "claude-sonnet-4-5",
      "provider_type": "anthropic",
      "api_key": "填入你的 Planner Key",
      "base_url": "https://api.anthropic.com",
      "temperature": 0.2,
      "max_tokens": 8192
    },
    "coder": {
      "name": "MiniMax-M2.5-highspeed",
      "provider_type": "openai",
      "api_key": "填入你的 Coder Key",
      "base_url": "https://api.minimaxi.com/v1",
      "temperature": 0.1,
      "max_tokens": 4096
    },
    "test_coder": {
      "name": "MiniMax-M2.5-highspeed",
      "provider_type": "openai",
      "api_key": "填入你的 Test Coder Key",
      "base_url": "https://api.minimaxi.com/v1",
      "temperature": 0.1,
      "max_tokens": 4096
    },
    "fixer": {
      "name": "MiniMax-M2.5-highspeed",
      "provider_type": "openai",
      "api_key": "填入你的 Fixer Key",
      "base_url": "https://api.minimaxi.com/v1",
      "temperature": 0.1,
      "max_tokens": 4096
    },
    "debug_expert": {
      "name": "claude-opus-4-6",
      "provider_type": "anthropic",
      "api_key": "填入你的 Debug Expert Key",
      "base_url": "https://api.anthropic.com",
      "temperature": 0.2,
      "max_tokens": 8192
    }
  },
  "runtime": {
    "compile_command": "mingw32-make",
    "test_command": "./bin/system_tests.exe",
    "unit_test_command": "./bin/unit_tests.exe",
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

#### 📌 高级配置项补充说明：
1. **`temperature` & `max_tokens`**: 每个角色都支持精准控制响应的随机性和长度。执行重体力活的 `coder`/`fixer` 推荐 `0.1`，负责顶层设计的角色推荐 `0.2`。
2. **`artifact_policy`**: 产物快照策略（默认 `per_execution`）。启用后，AI 每一次失败尝试生成的代码都会被快照归档到 `.smartroute/artifacts`，这是时间旅行（Time Travel / 回滚）核心基石。
3. **`logging`**: 可观测系统。打开 `capture_prompts` 可以实现 Token 全链路追踪并写入 `.pipeline/logs`，方便复盘 AI 写出坏代码的上下文环境。
4. **`context_limit`**: 防止上下文撑爆报错，控制丢给 AI 的报错日志/物理文件的上限（硬截断）。


`documents` 配置块用于统一管理文档路径，例如：

```json
{
  "documents": {
    "requirements_dir": "docs/requirements",
    "overview_design": "docs/design/overview-design.md",
    "detailed_design": "docs/design/detailed-design.md",
    "system_test_cases": "docs/test/system-test-cases.md",
    "unit_test_cases": "docs/test/unit-test-cases.md",
    "automation_plan": "docs/test/automation-plan.md",
    "review_dir": "docs/review",
    "system_test_code_dir": "tests/system",
    "unit_test_code_dir": "tests/src"
  }
}
```

路径统一入口说明：
- Python 流水线执行时会读取 `documents` 最新配置。
- Claude Code 命令中的路径约定也以 `documents` 为准。

### 步骤 3：同步配置

```bash
python .pipeline/setup.py --check
python .pipeline/setup.py
```

该命令会生成/更新 `.env` 和 `CLAUDE.md`。

### 步骤 4：执行任务流水线

先创建 `.smartroute/task.md`：

```markdown
[Task Objective]
实现 xxx 功能

[Strict Rules]
- 不修改公共接口签名
- 仅允许修改目标文件

[Target Files]
- src/xxx.cpp
```

再执行：

```bash
python .pipeline/test_loop.py --project-dir . --task .smartroute/task.md
```

```bash
python .pipeline/test_loop.py --project-dir . --task .smartroute/task.md --bug-report "复现步骤..."
python .pipeline/test_loop.py --project-dir . --resume .pipeline/last-state.json
```

---

### 🌟 附录：Claude Code 专属 Skills 指令映射

如果你是在前台使用 Claude Code CLI 进行驱动，本项目在 `claude-commands/` 目录下提供了一套严格映射 12 阶段主线研发的专属技能（Skills）。
你可以直接在对话框输入这些 `/` 开头的命令，以“动口不动手”的方式完成开发闭环：

| 阶段 | 角色 | 触发指令 | 预期产出 |
|---|---|---|---|
| 1. 需求分析 | PM | `/requirements` | 生成需求文档 |
| 2. 架构设计 | Architect | `/design` | 生成详细设计文档 |
| 3. 测试方案 | QA Lead | `/test-plan` 或 `/code` | 生成任务执行单 `.smartroute/task.md` |
| **4. 自动研发闭环** | **全自动后台引擎** | **`/test-loop`** | **[核心] 执行 编码->测试->修包 的无尽循环** |
| 5. 代码审查 | Reviewer | `/review` | Review 报告与修复意见 |
| 6. 代码提交 | DevOps | `/git-push` | 汇总 Commits 并 Push |

**最佳实践**：日常开发中，如果你已经有了设计文档或 UI 截图，可直接调用 `/test-plan` 生成工单，然后运行 `/test-loop` 挂机等待测试通过即可。
