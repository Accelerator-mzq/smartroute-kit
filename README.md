# SmartRoute V3.0 自动化编程与协作框架

SmartRoute V3.0 是新一代**「前台对话指挥 + 后台多智能体（Multi-Agent）流水线执行」**的工程协作框架。
通过统一的 JSON 配置与一套 Python Orchestrator 引擎，将繁琐的“修改代码、本地编译、跑单元测试、修语法 Bug”整个闭环交由背后的 AI 角色自动完成。开发者只需专注于需求对话与高层架构设计。

---

## 🌟 核心特性与架构

- **角色解耦 (Roles)**：不再依赖单一模型。细分 Planner, Coder, Test Coder, Fixer, Debug Expert 等身份，允许为不同难度阶段灵活指派最合适的模型（如 Claude 4.5 负责规划与架构，高吞吐低延迟的 MiniMax 负责底层代码敲击）。
- **统一化配置管理**：抛弃繁杂的 `.env` 变量拼凑，单凭一个 `smartroute.config.json` 文件即可管理所有 AI Keys、编译运行命令和引擎状态机策略。
- **沙盒与版本管理 (Artifact Policy)**：每次编译失败都能进行安全的代码物理回溯防破坏，并支持生成观测日志供后续溯源。

---

## 🚀 业务仓接入与初始化

将 SmartRoute V3.0 注入到你的任意代码仓中非常简单：

### 步骤 1：植入并初始化流水线
```bash
# 将框架套件植入到你的目标项目下
bash smartroute-kit/init-smartroute.sh /path/to/your/project
cd /path/to/your/project
```

### 步骤 2：编辑统一配置文件
在目标项目根目录下编辑生成的 `smartroute.config.json` 文件，并至少配齐 5 种处理层角色的 API 密钥，以及该项目的真实编译和测试指令。

> **示例核心配置片段**：
> ```json
> {
>   "roles": {
>     "planner": { ... },
>     "coder": { "name": "MiniMax-M2.5-highspeed", "api_key": "你的Key" },
>     "test_coder": { ... },
>     "fixer": { ... },
>     "debug_expert": { ... }
>   },
>   "runtime": {
>     "compile_command": "cmake --build build -j 8",
>     "test_command": "powershell -File .\\Run-Test.ps1",
>     "unit_test_command": "python run_tests.py"
>   }
> }
> ```

### 步骤 3：同步生效并生成守护结构
```bash
# 执行同步验证，会生成/更新 .env 等必要环境变量和目录
python .pipeline/setup.py
```
这将在业务仓中生成 `.pipeline/`（运作脚本）与 `.smartroute/`（AI 工作区与编排上下文）等隐藏目录。

---

## 🤖 自动化流水线使用指南

接入成功后，即可在前台系统（如 Claude Code CLI）开启纯“动口”的开发模式：

### 开发模式 1：指令/自然对话触发（推荐）
在对话框中讨论完代码方案后，直接输入快捷指令：
> **`/project:test-loop`**

或者用自然语言要求 AI 接管：
> **“方案敲定，请写入 `.smartroute/task.md` 工单并启动后台 `test_loop.py` 循环。”**

这将在后台唤起完整生命周期流程：`[Planner 解析] -> [Coder 编码] -> [Test Coder 写测] -> [Runtime 编译&集成] -> [Fixer 排错]`，直到项目终端健康反馈 `[SUCCESS]`。

### 开发模式 2：手动单次调用
你也可以通过在控制台主动注入任务目标来开启后台引擎：

1. 编辑工作单 `.smartroute/task.md`：
   ```markdown
   [Task Objective]
   新增某某模块网络解析功能
   [Strict Rules]
   - 禁止修改已有公共接口
   [Target Files]
   - src/network.cpp
   - include/network.h
   ```
2. 执行引擎启动脚本：
   ```bash
   python .pipeline/test_loop.py --project-dir . --task .smartroute/task.md
   ```

*(如需指定之前测试暴露的错误让 AI 重点修复，可追加参数：`--bug-report "某个严重错误日志" `)*

---

## 📂 `documents` 路径配置
项目的文档路径统一由 `smartroute.config.json` 内部的 `documents` 节点映射。这方便不同的项目套件定制各自的架构设计、用例库和 PR 审核归档位置。

---
## 💡 进阶提示

1. **引擎日志 (Observability)**：若在配置内开启 `logging.enabled`，底层会将每次编排与大模型产生的 Prompt/响应 全部存档于 `.pipeline/logs` 中，方便人类 Debug AI 脑回路。
2. **源码仓与业务仓区分**：
   - 本项目（`smartroute-kit`）为**源码仓**，测试自身脚本用 `pipeline/...`
   - 当部署到**业务仓**后，为防冲突脚本将前置隐藏点，使用 `.pipeline/...`
