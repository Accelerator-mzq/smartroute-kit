# SmartRoute

<p align="center">
  <strong>基于 Claude Code 的任务模型智能调度框架</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-v1.0-blue.svg" alt="v1.0">
</p>

<p align="center">
  让 Claude Code 根据任务类型自动使用不同 AI 模型：强模型做分析设计，快模型做编码测试。
</p>

---

## ✨ 核心特性

- **双模型协作**：强模型（如 Claude Opus）处理需求分析、设计、Review；快模型（如 MiniMax）处理编码、测试、修复
- **统一配置入口**：模型、API Key、项目命令、文档路径全部集中在 `smartroute.config.json`，改一处即生效
- **全自动测试循环**：Python 脚本自动编译→测试→修复→升级→漏测反思→生成测试代码→回归，无需人工干预
- **11 个 Claude Code 命令**：覆盖从需求分析到 Git 提交的完整开发流程
- **智能模型升级/降级**：快模型修复 3 次失败后自动升级到强模型诊断，诊断完自动降回快模型执行

## 📐 架构

```
smartroute.config.json (统一配置入口)
        │
        ├──→ Claude Code 交互层 (CLAUDE.md + 11个命令)
        │      半自动模型切换，AI 提示你手动切 Provider
        │
        ├──→ Python 自动化层 (.pipeline/)
        │      全自动模型切换，call_model("strong"/"fast")
        │
        └──→ CCM 路由代理层 (可选)
               think 请求走强模型，普通请求走快模型
```

## 📦 前置依赖

| 依赖 | 必需/可选 | 用途 |
|------|----------|------|
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | 必需 | Anthropic 官方 AI 编程助手，本框架的运行载体 |
| [CC Switch](https://github.com/nicekid1/Claude-Code-Switch) | 必需 | Claude Code 的多 Provider 切换工具，用于在不同模型之间手动切换 |
| [claude-code-mux (CCM)](https://github.com/xuyizhe/claude-code-mux) | 可选 | Claude Code 路由代理，实现按请求类型（think/普通）自动分流到不同模型 |
| Python 3.8+ | 必需 | 运行 `.pipeline/` 中的自动化脚本 |

> **说明**：CC Switch 负责在开发阶段间手动切换模型（如从编码切到 Review），CCM 负责在同一阶段内按请求特征自动分流（如 plan mode 走强模型）。两者互补，不冲突。

## 🚀 快速开始

### 1. 初始化项目

```bash
bash smartroute-kit/init-smartroute.sh /path/to/your/project
```

### 2. 编辑配置

打开 `smartroute.config.json`，填入你的 API Key：

```json
{
  "models": {
    "strong": {
      "name": "claude-opus-4-5",
      "provider_type": "anthropic",
      "api_key": "填入你的 Opus Key",
      "base_url": "https://api.anthropic.com"
    },
    "fast": {
      "name": "MiniMax-M2.5-highspeed",
      "provider_type": "openai",
      "api_key": "填入你的 MiniMax Key",
      "base_url": "https://api.minimaxi.com/v1"
    }
  }
}
```

> **MiniMax 特有**：由于 MiniMax 不支持 Anthropic 格式，`provider_type` 必须设为 `"openai"`。其他快模型按实际情况配置。

### 3. 同步配置

```bash
python .pipeline/setup.py
```

此操作会自动生成 `.env` 和 `CLAUDE.md`。

### 4. 配置 CCM 路由代理（可选，推荐）

如果你需要按任务类型自动分流功能：

1. 启动 CCM: `ccm start`
2. 浏览器打开 `http://127.0.0.1:13456`
3. 添加 **强模型 Provider**: Type `anthropic`，填入对应 Base URL 和 Key
4. 添加 **快模型 Provider**: 
   - **注意**: 如果快模型是 MiniMax，Type 必须选 `openai`
   - Custom Endpoint: `https://api.minimaxi.com/v1`
5. 配置 **Router**: Default 指向快模型，Think 指向强模型
6. 点击 **Save & Restart**

### 5. 配置 CC Switch 手动切换

在 CC Switch 中添加以下 Providers：

1. **强模型专用**: 填入 Opus 的配置
2. **快模型专用**: 填入 MiniMax 的配置
3. **智能路由（如启用了 CCM）**:
   - 名称: `智能路由 (Opus+MiniMax)`
   - API Key: `dummy-key` (随意填)
   - 请求地址: `http://127.0.0.1:13456`
   - 主模型 / Sonnet 默认模型 / Haiku 默认模型: 填入**快模型架构名称**（如 `MiniMax-M2.5-highspeed`）
   - 推理模型 (Thinking) / Opus 默认模型: 填入**强模型名称**（如 `claude-opus-4-6`）
   - 注意：**不要**开启代理/测试测速功能，直接写通即可。

## 📋 开发流程

```
/project:requirements  →  需求分析 (strong)
/project:design        →  设计文档 (strong)
/project:test-plan     →  测试文档 (strong)
/project:code          →  编码 (fast)
/project:test-code     →  测试编码 (fast)
/project:test-auto     →  自动化测试验证 (fast)
/project:test-loop     →  自动化测试循环 (Python 脚本)
/project:review        →  代码 Review (strong)
/project:review-fix    →  Review 修改 (fast)
/project:git-push      →  上传 Git (fast)
```

### Bug 修复流程

```bash
python .pipeline/test_loop.py --project-dir . --bug-report "xxx功能崩溃"
```

脚本自动执行：修复 → 漏测反思 → 更新测试方案 → 生成测试代码 → 编译 → 回归测试

## 📁 项目结构

```
smartroute-kit/
├── smartroute.config.json       # 统一配置入口
├── init-smartroute.sh           # 一键初始化
├── SmartRoute-配置文档.md        # 详细配置指南
├── docs/
│   └── pitfalls.md              # 踩坑记录（6 个已知坑）
├── claude-commands/             # 11 个 Claude Code 命令
│   ├── requirements.md          #   需求分析
│   ├── design.md                #   设计文档
│   ├── test-plan.md             #   测试文档
│   ├── code.md                  #   编码
│   ├── test-code.md             #   测试编码
│   ├── test-auto.md             #   自动化测试验证
│   ├── test-loop.md             #   触发测试循环
│   ├── test-fix.md              #   Bug 修复
│   ├── review.md                #   代码 Review
│   ├── review-fix.md            #   Review 修改
│   └── git-push.md              #   上传 Git
└── pipeline/                    # Python 自动化脚本
    ├── setup.py                 #   配置同步工具
    ├── CLAUDE.md.template       #   CLAUDE.md 模板
    ├── test_loop.py             #   测试循环主入口
    ├── model_caller.py          #   模型调用封装
    ├── state.py                 #   状态定义
    ├── router.py                #   路由逻辑
    ├── nodes.py                 #   执行节点
    ├── runners.py               #   本地编译/测试
    └── logger.py                #   日志记录
```

## ⚙️ 文档路径配置

所有文档路径通过 `smartroute.config.json` 的 `documents` 配置统一管理：

```json
"documents": {
  "requirements_dir": "docs/requirements",
  "detailed_design": "docs/design/detailed-design.md",
  "system_test_cases": "docs/test/system-test-cases.md",
  "unit_test_cases": "docs/test/unit-test-cases.md",
  "automation_plan": "docs/test/automation-plan.md",
  "review_dir": "docs/review",
  "system_test_code_dir": "tests/system",
  "unit_test_code_dir": "tests/src"
}
```

修改文档路径后**无需重跑** `setup.py`，Python 脚本和 Claude Code 命令会自动读取最新配置。

## 🔧 模型切换机制

| 场景 | 切换方式 | 自动化程度 |
|------|---------|-----------|
| 阶段切换（需求→编码） | CC Switch 手动切 Provider | 半自动（AI 会提示） |
| 修复超限升级 | Python 脚本 `router.py` 控制 | 全自动 |
| think 请求分流 | CCM 路由代理 | 全自动（可选） |

## 📖 详细文档

- [SmartRoute 配置文档](SmartRoute-配置文档.md) — 完整的配置指南和使用说明
- [踩坑记录](docs/pitfalls.md) — 6 个已知问题的解决方案

## 🤝 适用场景

- 使用 Claude Code 进行项目开发，希望在不同阶段使用不同模型
- 需要自动化的编译→测试→修复循环
- 希望在 Bug 修复后自动补充测试用例和测试代码
- 多项目开发，需要灵活配置不同的文档结构

## 📄 License

MIT
