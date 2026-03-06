#!/usr/bin/env python3
"""
setup.py — SmartRoute 配置同步工具

读取 smartroute.config.json，一键生成/更新所有配置文件：
  - .env（Python 脚本用）
  - CLAUDE.md（Claude Code 项目指令）
  - 验证所有配置是否一致

用法:
  python .pipeline/setup.py                # 从项目根目录运行
  python .pipeline/setup.py --check        # 仅检查，不修改
  python .pipeline/setup.py --show-config  # 显示当前配置摘要
"""

import json
import os
import sys
import shutil
from pathlib import Path


def find_project_root():
    """向上查找包含 smartroute.config.json 的目录"""
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        if (parent / "smartroute.config.json").exists():
            return parent
    # 如果在 .pipeline 目录下运行
    script_dir = Path(__file__).parent.parent
    if (script_dir / "smartroute.config.json").exists():
        return script_dir
    return current


def load_config(project_root: Path) -> dict:
    config_path = project_root / "smartroute.config.json"
    if not config_path.exists():
        print(f"❌ 找不到配置文件: {config_path}")
        print("   请确认 smartroute.config.json 在项目根目录")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_env(config: dict, project_root: Path):
    """生成 .env 文件"""
    strong = config["models"]["strong"]
    fast = config["models"]["fast"]
    project = config["project"]
    proxy = config.get("proxy", {})

    lines = [
        "# ============================================",
        "# SmartRoute .env — 由 setup.py 自动生成",
        "# 请勿手动编辑，修改 smartroute.config.json 后重新运行 setup.py",
        "# ============================================",
        "",
        "# 强模型 (Opus)",
        f"STRONG_MODEL_NAME={strong['name']}",
        f"STRONG_API_KEY={strong['api_key']}",
        f"STRONG_BASE_URL={strong['base_url']}",
        f"STRONG_PROVIDER_TYPE={strong['provider_type']}",
        f"STRONG_TEMPERATURE={strong['temperature']}",
        f"STRONG_MAX_TOKENS={strong['max_tokens']}",
        "",
        "# 快模型 (MiniMax)",
        f"FAST_MODEL_NAME={fast['name']}",
        f"FAST_API_KEY={fast['api_key']}",
        f"FAST_BASE_URL={fast['base_url']}",
        f"FAST_PROVIDER_TYPE={fast['provider_type']}",
        f"FAST_TEMPERATURE={fast['temperature']}",
        f"FAST_MAX_TOKENS={fast['max_tokens']}",
        "",
        "# 兼容旧变量名",
        f"ANTHROPIC_API_KEY={strong['api_key']}",
        f"MINIMAX_API_KEY={fast['api_key']}",
        "",
        "# 项目配置",
        f"COMPILE_COMMAND={project['compile_command']}",
        f"TEST_COMMAND={project['test_command']}",
        f"UNIT_TEST_COMMAND={project['unit_test_command']}",
        f"MAX_RETRIES={project['max_retries']}",
        f"MAX_LOOPS={project['max_loops']}",
        f"TEST_TIMEOUT={project['test_timeout_seconds']}",
    ]

    if proxy.get("http_proxy"):
        lines.extend([
            "",
            "# 网络代理",
            f"HTTP_PROXY={proxy['http_proxy']}",
            f"HTTPS_PROXY={proxy['https_proxy']}",
        ])

    env_path = project_root / ".env"
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  ✅ .env 已生成")


def generate_claude_md(config: dict, project_root: Path):
    """生成 CLAUDE.md"""
    strong_name = config["models"]["strong"]["name"]
    fast_name = config["models"]["fast"]["name"]
    project = config["project"]

    template_path = project_root / ".pipeline" / "CLAUDE.md.template"
    output_path = project_root / "CLAUDE.md"

    if template_path.exists():
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace("{{STRONG_MODEL}}", strong_name)
        content = content.replace("{{FAST_MODEL}}", fast_name)
        content = content.replace("{{COMPILE_COMMAND}}", project["compile_command"])
        content = content.replace("{{TEST_COMMAND}}", project["test_command"])
        content = content.replace("{{UNIT_TEST_COMMAND}}", project["unit_test_command"])
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  ✅ CLAUDE.md 已生成")
    else:
        print(f"  ⚠ CLAUDE.md.template 不存在，跳过 CLAUDE.md 生成")


def show_config_summary(config: dict):
    """显示配置摘要"""
    strong = config["models"]["strong"]
    fast = config["models"]["fast"]
    project = config["project"]

    key_mask = lambda k: k[:8] + "..." + k[-4:] if len(k) > 16 else "***"

    print()
    print("  ┌─────────────────────────────────────────────┐")
    print("  │         SmartRoute 当前配置摘要              │")
    print("  ├─────────────────────────────────────────────┤")
    print(f"  │ 强模型: {strong['name']:<35s} │")
    print(f"  │   类型: {strong['provider_type']:<35s} │")
    print(f"  │   地址: {strong['base_url'][:35]:<35s} │")
    print(f"  │   Key:  {key_mask(strong['api_key']):<35s} │")
    print("  ├─────────────────────────────────────────────┤")
    print(f"  │ 快模型: {fast['name']:<35s} │")
    print(f"  │   类型: {fast['provider_type']:<35s} │")
    print(f"  │   地址: {fast['base_url'][:35]:<35s} │")
    print(f"  │   Key:  {key_mask(fast['api_key']):<35s} │")
    print("  ├─────────────────────────────────────────────┤")
    print(f"  │ 编译:   {project['compile_command']:<35s} │")
    print(f"  │ 测试:   {project['test_command']:<35s} │")
    print(f"  │ 重试:   {project['max_retries']:<35d} │")
    print("  └─────────────────────────────────────────────┘")
    print()


def check_config(config: dict) -> list:
    """检查配置问题"""
    warnings = []
    strong = config["models"]["strong"]
    fast = config["models"]["fast"]

    if "在此填入" in strong["api_key"]:
        warnings.append("强模型 API Key 未填写")
    if "在此填入" in fast["api_key"]:
        warnings.append("快模型 API Key 未填写")
    if fast["provider_type"] != "openai":
        warnings.append(
            f"快模型 provider_type 为 '{fast['provider_type']}'，"
            "MiniMax 建议使用 'openai' 类型以避免 CCM 兼容问题"
        )
    return warnings


def main():
    project_root = find_project_root()
    config = load_config(project_root)

    if "--show-config" in sys.argv:
        show_config_summary(config)
        return

    print()
    print("  SmartRoute 配置同步")
    print("  ━━━━━━━━━━━━━━━━━━")
    print()

    # 检查
    warnings = check_config(config)
    if warnings:
        print("  ⚠ 配置警告:")
        for w in warnings:
            print(f"    - {w}")
        print()

    if "--check" in sys.argv:
        if warnings:
            print("  请修改 smartroute.config.json 后重新运行")
        else:
            print("  ✅ 配置检查通过")
        show_config_summary(config)
        return

    # 生成文件
    print("  正在同步配置...")
    generate_env(config, project_root)
    generate_claude_md(config, project_root)

    # 确保目录存在
    for d in ["docs/requirements", "docs/design", "docs/test", "docs/review", ".pipeline"]:
        (project_root / d).mkdir(parents=True, exist_ok=True)

    show_config_summary(config)
    print("  ✅ 配置同步完成！")
    print()
    print("  下一步:")
    print("    1. CCM Web UI (http://127.0.0.1:13456) 中同步 Provider 配置")
    print("    2. 新开终端，启动 Claude Code 验证")
    print()


if __name__ == "__main__":
    main()
