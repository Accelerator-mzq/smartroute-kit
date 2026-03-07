

------

# SmartRoute V3 多智能体软件研发引擎

## 需求与架构设计说明书 (增强版)

### 1. 架构目标与核心原则

SmartRoute V3 的终极目标是构建一个由 AI 驱动的软件研发流水线引擎，通过多智能体协作完成软件开发的完整生命周期（SDLC）。

**三大核心原则：**

1. **彻底避开协议地狱**：放弃底层的 `Claude Code -> Proxy -> Tool Protocol Translation` 链路。
2. **大脑与躯干物理隔离**：强模型（Claude）负责战略决策与架构，驻留在 CLI 层；快模型（MiniMax）承担重体力执行与循环试错，驻留在 Python 后台。
3. **基于文件的稳定握手**：双层级之间通过标准的 Markdown / JSON 文件（如 `task.md`）进行跨进程任务交接，实现上下文的绝对纯净。

------

### 2. 系统整体架构

系统在物理层和逻辑层被严格划分为 **Layer 1 (AI 指挥层)** 和 **Layer 2 (自动化执行层)**。

Plaintext

```
                  ┌─────────────────────────────────────┐
                  │ Layer 1: Claude Code CLI (强模型)    │
                  │ 角色: PM / Architect / QA / Reviewer │
                  │ 行为: 交互、架构设计、输出任务说明书     │
                  └─────────────────┬───────────────────┘
                                    │
                         【文件握手: task.md】
                                    │
                                    ▼
        ┌────────────────────────────────────────────────────────┐
        │ Layer 2: SmartRoute Python Orchestrator (状态机引擎)      │
        │                                                        │
        │  ┌───────────┐   ┌───────────┐   ┌───────────┐         │
        │  │ Planner   │──►│ Coder     │──►│ TestCoder │         │
        │  └───────────┘   └───────────┘   └───────────┘         │
        │                        │               │               │
        │                        ▼               ▼               │
        │  ┌───────────┐   ┌───────────┐   ┌───────────┐         │
        │  │ Debug Exp │◄──│ Fixer     │◄──│ Runtime   │         │
        │  └───────────┘   └───────────┘   └───────────┘         │
        │                                                        │
        │   [Context Mgr]  [Task Graph]  [Artifacts]  [Observe]  │
        └───────────────────────────┬────────────────────────────┘
                                    │
                                    ▼
                        【物理文件: Source Code / Tests】
```

------

### 3. 新增四大核心基础设施模块

为了支撑复杂的开发任务并防止 AI 系统崩溃失控，后台 Python 引擎必须引入以下四大核心模块：

#### 3.1 Context Manager (上下文管理器)

- **痛点**：全局上下文越堆越大，导致快模型失忆、幻觉，且 API 成本高昂。
- **职责**：动态组装上下文。根据当前执行的节点，精准提供切片信息。例如，`Fixer` 只需要当前报错的 `.cpp` 文件和错误日志，不需要整个项目的 `CLAUDE.md`。
- **物理结构**：`.pipeline/context/` (存放 `project_context.md`, `task_context.md`, `runtime_logs.md`)。

#### 3.2 Task Graph Engine (任务图引擎)

- **痛点**：线性执行（A -> B -> C）无法处理存在依赖关系的复杂工程需求。
- **职责**：解析 Planner 输出的 `Execution_Plan.json`，构建有向无环图 (DAG)。支持多任务的串行依赖与潜在的并行生成。
- **数据结构示例**：`Nodes` (任务原子) + `Edges` (依赖指向)。

#### 3.3 Artifact Manager (产物管理器)

- **痛点**：AI 在多次重试中容易将原本正确的代码覆盖或删坏，导致排错方向彻底偏离。
- **职责**：执行版本控制（Time Travel）。每一次重试或生成都在独立目录保存快照。当判定当前修复路径已彻底失败时，提供安全回滚到上一正常状态的能力。
- **物理结构**：`.smartroute/artifacts/execution_xxx/` (分别存放 `code/`, `tests/`, `logs/`)。

#### 3.4 Observability System (可观测系统)

- **痛点**：黑盒调试困难，流水线卡死时无法定位是提示词问题、Token 超限还是逻辑死循环。
- **职责**：全链路追踪。统一记录模型入参、出参、Token 消耗、耗时以及节点状态流转轨迹。
- **物理结构**：`.pipeline/logs/`。

------

### 4. 全生命周期 (SDLC) 任务流转与角色分配

系统涵盖 11 个标准软件工程节点，实现了从需求到提交流水线的完全闭环：

| **阶段**         | **虚拟角色 (Role)** | **运行层** | **驱动模型** | **核心职责与产出**                                           |
| ---------------- | ------------------- | ---------- | ------------ | ------------------------------------------------------------ |
| **1. 日常提问**  | Assistant           | CLI        | 强模型       | 常规解答，不改动代码。                                       |
| **2. 需求分析**  | PM                  | CLI        | 强模型       | 理解人类需求，定义产品边界。                                 |
| **3. 设计文档**  | Architect           | CLI        | 强模型       | 更新 `CLAUDE.md`，输出系统设计。                             |
| **4. 测试文档**  | QA Lead             | CLI        | 强模型       | 制定测试用例大纲，打包输出跨层级交接文件 `.smartroute/task.md`。 |
| **5. 任务拆解**  | Planner             | Python     | 强模型       | 读取 `task.md`，构建 DAG 任务图，输出 `Execution_Plan.json`。 |
| **6. 编码**      | Coder               | Python     | 快模型       | 执行任务图节点，生成纯净业务源码。                           |
| **7. 测试编码**  | Test Coder          | Python     | 快模型       | 根据源码与测试大纲，生成对应 GTest / QtTest 用例代码。       |
| **8. 运行测试**  | Runtime (执行器)    | Python     | -            | 调用物理环境 (`cmake/make/ctest`)，抓取退出码与错误日志。    |
| **9. 自动修复**  | Fixer               | Python     | 快模型       | 阅读日志修改语法错误（设最大重试 3 次）。超限则触发 Debug Expert (强模型) 会诊。 |
| **10. 代码审查** | Reviewer            | CLI        | 强模型       | 引擎 Exit 0 后，CLI 醒来检视新代码。若不合格，生成 `review_task.md` 打回步骤 5。 |
| **11. 上传 Git** | DevOps              | CLI        | 强模型       | 验收通过，生成 Commit Message 并提交。                       |

------

### 5. Python Orchestrator 状态机流转 (State Machine)

后台引擎的核心是一个严密的状态流转环，具备强大的阻断与容错机制：

```
INIT` ➔ `PLANNING` ➔ `CODING` ➔ `TESTING` ➔ `FIXING` ↺ (Loop <= 3) ➔ `DEBUGGING` (若 Fixer 溃败) ➔ `DONE
```

**Debug Loop Guard (兜底护栏)：**

- 当 `Fixer` 连续修改同一错误超过 3 次，流转至 `Debug Expert`。
- 若 `Debug Expert` 给出的重构方案再次被 `Runtime` 验证失败，引擎判定为“环境异常或方向性错误”，中断状态机，向 CLI 层抛出异常并等待人类介入。

------

### 6. 项目物理目录结构

为了保证这套庞大引擎的整洁，项目根目录需遵循以下骨架规范：

Plaintext

```
SmartRoute-Project/
├── .pipeline/                  # 后台兵工厂的核心逻辑与运行时
│   ├── engine/                 # 状态机与多智能体实现
│   │   ├── state_machine.py    # 主流程调度器
│   │   ├── task_graph.py       # DAG 任务图解析
│   │   └── roles/              # planner.py, coder.py, fixer.py 等角色逻辑
│   ├── runtime/                # 物理环境执行器
│   │   └── executor.py         # 封装 cmake/make 的 subprocess 执行
│   ├── context/                # 动态上下文碎片
│   ├── artifacts/              # AI 生成代码的版本快照
│   └── logs/                   # 全链路追踪日志
├── .smartroute/                # 跨层级握手与配置管理
│   ├── config.json             # 全局配置文件
│   └── task.md                 # 当前流转的任务握手书
├── src/                        # 物理业务源码 (C++/Qt)
└── tests/                      # 物理测试源码
```

------

### 7. 配置文件规范 (`smartroute.config.json`)

配置系统不仅包含 API 密钥，还统管了引擎的运行时参数、日志策略与产物管理策略：

JSON

```
{
  "engine_settings": {
    "max_compile_retries": 3,
    "max_review_loops": 2
  },
  "context_limit": {
    "max_error_log_lines": 50,
    "max_file_tokens": 4000
  },
  "artifact_policy": {
    "enable_time_travel": true,
    "keep_last_n_executions": 5
  },
  "roles": {
    "planner": {
      "provider": "anthropic",
      "model_name": "claude-3-7-sonnet-20250219",
      "api_key": "YOUR_ANTHROPIC_KEY",
      "base_url": "https://api.anthropic.com/v1"
    },
    "coder": {
      "provider": "openai",
      "model_name": "MiniMax-M2.5-highspeed",
      "api_key": "YOUR_MINIMAX_KEY",
      "base_url": "https://api.minimaxi.com/v1/text/chatcompletion_v2"
    },
    "fixer": { ... },
    "debug_expert": { ... }
  }
}
```

------

