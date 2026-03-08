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

## 🤖 自动化流水线使用指南 (Claude Skills)

接入成功后，即可在前台系统（如 Claude Code CLI）中开启纯“动口”的开发模式。
框架在 `claude-commands/` 目录下提供了一套严格映射 **12阶段主线研发流程** 的专属拓展指令（Skills）：

### 📝 1. 前期规划阶段（前台执行）
- **`/project:assistant`**：日常代码问答与助手。
- **`/project:requirements`**：**需求分析阶段**。强制要求前台 AI 输出标准格式的 PRD 需求文档。
- **`/project:design`**：**架构设计阶段**。根据需求，输出标准的架构设计文档和数据结构。
- **`/project:test-plan`**：**测试方案阶段**（或用 `/project:code`）。将你的需求翻译成后台流水线看得懂的机器工单，即写入 `.smartroute/task.md`。

*(注：如果你已经有写好的设计文档图纸或 UI 图，可直接在对话中将文件发给 AI，并调用 `/project:test-plan` 直接生成后台工单，**跨过前 3 个阶段**！)*

### ⚙️ 2. 后台全自动落地阶段（核心！）
- **`/project:test-loop`**：**兵工厂主线**。这是整个 V3.0 最核心的魔法！
  这将在后台唤起完整生命周期流程：`[Planner 拆解] -> [Coder 编码] -> [Test Coder 写测] -> [Runtime 测试] -> [Fixer 排错]`。后台的 5 个 AI 会自动完成无尽循环，直到全部测试通过 `[SUCCESS]`。

### 👀 3. 验收与发版阶段
- **`/project:review`**：测试跑通后，进行最终的 Code Review。
- **`/project:review-fix`**：根据 Review 意见生成新的修复工单重入循环。
- **`/project:git-push`**：发版，自动生成规范提交信息并推送到 Git。

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
