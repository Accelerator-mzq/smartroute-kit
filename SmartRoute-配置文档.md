# SmartRoute — 基于 Claude Code 的任务模型智能调度方案

## 方案简介

SmartRoute 让你在 Claude Code 中根据任务类型使用不同的 AI 模型：强模型（如 Opus）做分析和设计，快模型（如 MiniMax）做编码和测试，关键流程由 Python 脚本实现全自动的模型升级/降级。

### 核心特点

- **统一配置入口**：所有模型名称、API Key、项目命令、文档路径只需在 `smartroute.config.json` 中修改一次
- **三层架构**：Claude Code 交互层 + Python 自动化层 + 路由代理层
- **MiniMax 兼容方案**：使用 OpenAI 格式对接 MiniMax，避免 CCM 兼容性问题

---

## 模块划分

```
SmartRoute 架构图
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    smartroute.config.json
                    (统一配置入口)
                           │
                    python .pipeline/setup.py
                    (一键同步所有配置)
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         .env 文件     CLAUDE.md     CCM Web UI
        (Python用)    (Claude Code用)  (路由代理用)
              │            │            │
              ▼            ▼            ▼
      ┌──────────┐  ┌──────────┐  ┌──────────┐
      │ Python   │  │ Claude   │  │ CCM      │
      │ 自动化层 │  │ Code     │  │ 路由代理 │
      │          │  │ 交互层   │  │ 辅助层   │
      └──────────┘  └──────────┘  └──────────┘
```

### 模块 1：统一配置 (`smartroute.config.json`)

**作用**：所有模型、Key、命令、文档路径的唯一修改入口

修改此文件后运行 `python .pipeline/setup.py`，自动同步到 `.env` 和 `CLAUDE.md`。不再需要分别编辑多个文件。

### 模块 2：Claude Code 交互层 (`CLAUDE.md` + 自定义命令)

**作用**：在 Claude Code 中使用的项目规则和快捷命令

| 命令 | 模型 | 用途 |
|------|------|------|
| `/project:requirements` | strong | 需求分析 |
| `/project:design` | strong | 设计文档 |
| `/project:test-plan` | strong | 测试文档 |
| `/project:code` | fast | 编码 |
| `/project:test-code` | fast | 测试编码（单元测试代码生成） |
| `/project:test-auto` | fast | 自动化测试方案逐条验证 |
| `/project:test-loop` | 自动化 | 触发 Python 测试循环 |
| `/project:test-fix <Bug>` | fast→strong | 问题定位修复 |
| `/project:review` | strong | 代码 Review |
| `/project:review-fix` | fast | Review 修改 |
| `/project:git-push` | fast | 上传 Git |

**模型切换方式**：CLAUDE.md 中的规则让 AI 在需要升级时主动提示（`⚠️ [建议切换模型]`），你通过 CC Switch 手动切换 Provider。这层是半自动的。

### 模块 3：Python 自动化层 (`.pipeline/`)

**作用**：测试阶段的全自动模型切换

| 文件 | 功能 |
|------|------|
| `setup.py` | 读取统一配置，生成 .env 和 CLAUDE.md |
| `test_loop.py` | 主入口：编译→测试→修复→升级→反思→生成测试代码→回归 全自动循环 |
| `model_caller.py` | 封装强/快模型 API 调用，自动从 config 读取配置 |
| `router.py` | 路由逻辑：retry_count 控制升级/降级 |
| `nodes.py` | 执行节点：编译/测试/修复/诊断/漏测反思/自动化方案更新/测试代码生成 |
| `runners.py` | 本地编译和测试执行（含 MinGW 乱码处理） |
| `logger.py` | 日志记录：终端输出 + 文件记录 |

**模型切换方式**：Python 代码精确控制，`call_model("strong")` / `call_model("fast")`。这层是全自动的。

### 模块 4：CCM 路由代理层（可选）

**作用**：在 Claude Code 内部，根据请求特征（think/背景任务）自动分流

通过 CC Switch 的"智能路由"Provider 使用。plan mode 请求自动走强模型，普通请求走快模型。

**注意**：CCM 无法实现"修 3 次没修好就升级"这种业务逻辑，这部分由 Python 脚本层负责。

---

## 配置步骤

### 步骤 1：初始化项目

```bash
bash smartroute-kit/init-smartroute.sh /path/to/your/project
```

### 步骤 2：编辑统一配置

打开 `smartroute.config.json`，修改以下内容：

```json
{
  "models": {
    "strong": {
      "name": "claude-opus-4-5",
      "provider_type": "anthropic",
      "api_key": "填入你的 Opus Key",
      "base_url": "https://code.newcli.com/claude/ultra"
    },
    "fast": {
      "name": "MiniMax-M2.5-highspeed",
      "provider_type": "openai",
      "api_key": "填入你的 MiniMax Key",
      "base_url": "https://api.minimaxi.com/v1"
    }
  },
  "project": {
    "compile_command": "mingw32-make",
    "test_command": "./bin/system_tests.exe",
    "unit_test_command": "./bin/unit_tests.exe",
    "max_retries": 3
  }
}
```

> **注意（MiniMax 特有）**：由于 MiniMax 不支持 Anthropic 格式，当快模型使用 MiniMax 时，`provider_type` 必须设为 `"openai"`，`base_url` 必须是 `https://api.minimaxi.com/v1`。如果你使用其他快模型（如 GPT-4o-mini），请按该模型的实际要求配置。详见 `docs/pitfalls.md` 坑 1。

配置中还有一个 `documents` 配置块，用于统一管理所有文档路径：

```json
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
```

> **路径统一入口**：所有命令文件和 Python 脚本都从此处读取文档路径。修改路径后，Python 脚本自动生效（无需重跑 setup.py），Claude Code 命令执行时也会自动读取最新配置。

### 步骤 3：同步配置

```bash
python .pipeline/setup.py
```

此命令自动生成 `.env` 和 `CLAUDE.md`。以后修改模型配置，只改 `smartroute.config.json` 然后重跑这条命令即可。

> **注意**：修改 `documents` 中的文档路径时，**不需要**重跑 `setup.py`。Python 脚本和 Claude Code 命令都会在执行时自动读取最新配置。

### 步骤 4：配置 CCM 路由代理（可选）

如果你使用 CC Switch 的智能路由功能：

```bash
ccm start
# 浏览器打开 http://127.0.0.1:13456
```

在 Web UI 中：

**添加强模型 Provider**：
- Type: `anthropic`
- API Base: 你的 Opus base_url
- API Key: 你的 Opus Key

**添加快模型 Provider**（关键：用 OpenAI 类型）：
- Type: `openai`
- Name: `MiniMax-OpenAI-Mode`
- API Key: 你的 MiniMax Key
- Custom Endpoint: `https://api.minimaxi.com/v1`

**配置 Router**：
- Default → 快模型
- Think → 强模型

点击 **Save & Restart**。

### 步骤 5：配置 CC Switch Provider

在 CC Switch 中新建"智能路由"Provider：

| 字段 | 值 |
|------|-----|
| 名称 | 🔀 SmartRoute |
| Base URL | `http://127.0.0.1:13456` |
| Auth Token | `dummy-key-not-used` |
| Model | 你的快模型名称 |
| 代理配置 | **不需要填** |

### 步骤 6：验证

```bash
python .pipeline/setup.py --check
```

---

## 日常使用流程

### 项目启动 → CC Switch 切到强模型 Provider

```
> /project:requirements 我想开发一个xxx系统...
> /project:design
> /project:test-plan
```

### 编码 → CC Switch 切到快模型 Provider

```
> /project:code
```

### 自动化测试 → 直接运行 Python 脚本

```bash
python .pipeline/test_loop.py --project-dir . --max-retries 3
# 或处理用户 Bug（触发漏测反思）：
python .pipeline/test_loop.py --project-dir . --bug-report "xxx功能崩溃"
```

使用 `--bug-report` 时，脚本会自动执行完整的反思闭环：

1. **漏测反思**：强模型同时更新系统测试用例和单元测试用例文档
2. **更新自动化方案**：强模型生成含系统测试+单元测试两个章节的自动化方案
3. **生成测试代码**：快模型分别生成系统测试代码和单元测试代码（路径由 `documents` 配置决定）
4. **编译验证**：确保新测试代码编译通过
5. **回归测试**：分别运行系统测试和单元测试，验证新增测试可用

### Review → CC Switch 切到强模型

```
> /project:review
```

### 修改 + 提交 → CC Switch 切到快模型

```
> /project:review-fix
> /project:git-push
```

---

## 修改配置的正确方式

**只改一个文件**：`smartroute.config.json`

### 修改模型/Key/命令

```bash
# 1. 编辑配置
notepad smartroute.config.json    # Windows

# 2. 同步到所有组件
python .pipeline/setup.py

# 3. CCM Web UI 中同步 Provider（如果用了 CCM）
# 4. CC Switch 中如有对应 Provider 也需要更新
```

### 修改文档路径

```bash
# 1. 编辑 smartroute.config.json 中的 documents 配置
notepad smartroute.config.json    # Windows

# 2. 不需要运行任何命令，Python 脚本和 Claude Code 命令自动读取最新配置
```

无需再分别编辑 `.env`、`CLAUDE.md`、`config.toml` 等文件。

---

## 已知问题与解决方案

详见 `docs/pitfalls.md`，包含：

1. CCM 中 MiniMax 必须配置为 OpenAI 类型
2. 不要手动编写 CCM config.toml
3. CCM 日志需要环境变量开启
4. CC Switch 本地代理和 CCM 不能同时开启
5. CC Switch 切换后需新开终端
6. Clash Rule 模式下的代理配置

---

## 文件清单

```
smartroute-kit/
├── SmartRoute-配置文档.md          # 本文档
├── init-smartroute.sh              # 一键初始化
├── smartroute.config.json          # 统一配置入口
├── docs/                            # 路径可通过 documents 配置修改
│   ├── pitfalls.md                 # 踩坑记录
│   └── test/                       # 测试文档（由脚本自动维护）
│       ├── system-test-cases.md    # 系统测试用例
│       ├── unit-test-cases.md      # 单元测试用例
│       └── automation-plan.md      # 自动化测试方案
├── tests/                          # 测试代码（路径可通过 documents 配置修改）
│   ├── system/                     # 系统测试代码
│   └── src/                        # 单元测试代码（Qt Test）
├── claude-commands/                # 11个自定义命令
│   ├── requirements.md
│   ├── design.md
│   ├── test-plan.md
│   ├── code.md
│   ├── test-code.md
│   ├── test-auto.md
│   ├── test-loop.md
│   ├── test-fix.md
│   ├── review.md
│   ├── review-fix.md
│   └── git-push.md
└── pipeline/                       # Python 自动化脚本
    ├── setup.py                    # 配置同步工具
    ├── CLAUDE.md.template          # CLAUDE.md 模板
    ├── test_loop.py                # 测试循环主入口
    ├── model_caller.py             # 模型调用（读统一配置）
    ├── state.py                    # 状态定义
    ├── router.py                   # 路由逻辑
    ├── nodes.py                    # 执行节点
    ├── runners.py                  # 本地编译/测试
    └── logger.py                   # 日志记录
```
