#!/usr/bin/env python3
"""
setup.py — SmartRoute V3 配置同步工具（纯角色化）

读取 smartroute.config.json，一键生成/更新：
  - .env（ROLE_* + 项目命令）
  - CLAUDE.md（从模板注入角色模型与构建命令）
  - 配置检查摘要
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict


def find_project_root() -> Path:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    current = Path.cwd()
    for parent in [current] + list(current.parents):
        if (parent / "smartroute.config.json").exists():
            return parent
    script_dir = Path(__file__).parent.parent
    if (script_dir / "smartroute.config.json").exists():
        return script_dir
    return current


def load_config(project_root: Path) -> dict:
    config_path = project_root / "smartroute.config.json"
    if not config_path.exists():
        print(f"❌ 找不到配置文件: {config_path}")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_roles(config: dict) -> dict:
    roles = config.get("roles", {})
    required = ("planner", "coder", "test_coder", "fixer", "debug_expert")

    def normalize(role_cfg: dict, default_provider: str) -> dict:
        return {
            "name": role_cfg.get("name", role_cfg.get("model_name", "")),
            "provider_type": role_cfg.get("provider_type", role_cfg.get("provider", default_provider)),
            "api_key": role_cfg.get("api_key", ""),
            "base_url": role_cfg.get("base_url", ""),
            "temperature": role_cfg.get("temperature", 0.1 if default_provider == "openai" else 0.2),
            "max_tokens": role_cfg.get("max_tokens", 4096 if default_provider == "openai" else 8192),
        }

    # 新版五角色
    if all(r in roles for r in required):
        return {
            "planner": normalize(roles["planner"], "anthropic"),
            "coder": normalize(roles["coder"], "openai"),
            "test_coder": normalize(roles["test_coder"], "openai"),
            "fixer": normalize(roles["fixer"], "openai"),
            "debug_expert": normalize(roles["debug_expert"], "anthropic"),
        }

    # 兼容旧版三角色
    if all(r in roles for r in ("worker", "test", "debug")):
        return {
            "planner": normalize(roles["debug"], "anthropic"),
            "coder": normalize(roles["worker"], "openai"),
            "test_coder": normalize(roles["test"], "openai"),
            "fixer": normalize(roles["test"], "openai"),
            "debug_expert": normalize(roles["debug"], "anthropic"),
        }

    missing = [r for r in required if r not in roles]
    raise ValueError(
        "roles 配置缺失: "
        + ", ".join(missing)
        + "（或提供兼容旧版 worker/test/debug）"
    )


def resolve_runtime(config: dict) -> Dict[str, Any]:
    runtime = config.get("runtime", {})
    project = config.get("project", {})
    return {
        "compile_command": runtime.get("compile_command", project.get("compile_command", "make -j4")),
        "test_command": runtime.get("test_command", project.get("test_command", "./bin/system_tests")),
        "unit_test_command": runtime.get("unit_test_command", project.get("unit_test_command", "./bin/unit_tests")),
        "test_timeout_seconds": int(
            runtime.get("test_timeout_seconds", project.get("test_timeout_seconds", 120))
        ),
    }


def resolve_engine_settings(config: dict) -> Dict[str, Any]:
    engine = config.get("engine_settings", {})
    project = config.get("project", {})
    return {
        "max_retries": int(engine.get("max_retries", project.get("max_retries", 3))),
        "max_loops": int(engine.get("max_loops", project.get("max_loops", 30))),
        "context_limit": int(engine.get("context_limit", config.get("context_limit", 12000))),
    }


def resolve_artifact_policy(config: dict) -> str:
    value = config.get("artifact_policy", {})
    if isinstance(value, str):
        return value or "per_execution"
    if isinstance(value, dict):
        return value.get("mode", "per_execution")
    return "per_execution"


def resolve_logging(config: dict) -> Dict[str, bool]:
    cfg = config.get("logging", {})
    if not isinstance(cfg, dict):
        cfg = {}
    return {
        "enabled": bool(cfg.get("enabled", True)),
        "capture_prompts": bool(cfg.get("capture_prompts", True)),
        "capture_responses": bool(cfg.get("capture_responses", True)),
    }


def _load_existing_commands(env_path: Path) -> dict:
    existing = {}
    if not env_path.exists():
        return existing
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            if key in {"COMPILE_COMMAND", "TEST_COMMAND", "UNIT_TEST_COMMAND"}:
                existing[key] = val
    return existing


def generate_env(config: dict, project_root: Path):
    roles = resolve_roles(config)
    runtime_cfg = resolve_runtime(config)
    engine_cfg = resolve_engine_settings(config)
    artifact_policy = resolve_artifact_policy(config)
    logging_cfg = resolve_logging(config)
    proxy = config.get("proxy", {})
    env_path = project_root / ".env"

    existing_cmds = _load_existing_commands(env_path)
    compile_cmd = existing_cmds.get("COMPILE_COMMAND", runtime_cfg["compile_command"])
    test_cmd = existing_cmds.get("TEST_COMMAND", runtime_cfg["test_command"])
    unit_test_cmd = existing_cmds.get("UNIT_TEST_COMMAND", runtime_cfg["unit_test_command"])

    planner = roles["planner"]
    coder = roles["coder"]
    test_coder = roles["test_coder"]
    fixer = roles["fixer"]
    debug_expert = roles["debug_expert"]

    lines = [
        "# ============================================",
        "# SmartRoute .env — 由 setup.py 自动生成（V3）",
        "# 修改 smartroute.config.json 后请重跑 setup.py",
        "# ============================================",
        "",
        "# Role: planner",
        f"ROLE_PLANNER_MODEL={planner['name']}",
        f"ROLE_PLANNER_API_KEY={planner['api_key']}",
        f"ROLE_PLANNER_BASE_URL={planner['base_url']}",
        f"ROLE_PLANNER_PROVIDER_TYPE={planner['provider_type']}",
        f"ROLE_PLANNER_TEMPERATURE={planner['temperature']}",
        f"ROLE_PLANNER_MAX_TOKENS={planner['max_tokens']}",
        "",
        "# Role: coder",
        f"ROLE_CODER_MODEL={coder['name']}",
        f"ROLE_CODER_API_KEY={coder['api_key']}",
        f"ROLE_CODER_BASE_URL={coder['base_url']}",
        f"ROLE_CODER_PROVIDER_TYPE={coder['provider_type']}",
        f"ROLE_CODER_TEMPERATURE={coder['temperature']}",
        f"ROLE_CODER_MAX_TOKENS={coder['max_tokens']}",
        "",
        "# Role: test_coder",
        f"ROLE_TEST_CODER_MODEL={test_coder['name']}",
        f"ROLE_TEST_CODER_API_KEY={test_coder['api_key']}",
        f"ROLE_TEST_CODER_BASE_URL={test_coder['base_url']}",
        f"ROLE_TEST_CODER_PROVIDER_TYPE={test_coder['provider_type']}",
        f"ROLE_TEST_CODER_TEMPERATURE={test_coder['temperature']}",
        f"ROLE_TEST_CODER_MAX_TOKENS={test_coder['max_tokens']}",
        "",
        "# Role: fixer",
        f"ROLE_FIXER_MODEL={fixer['name']}",
        f"ROLE_FIXER_API_KEY={fixer['api_key']}",
        f"ROLE_FIXER_BASE_URL={fixer['base_url']}",
        f"ROLE_FIXER_PROVIDER_TYPE={fixer['provider_type']}",
        f"ROLE_FIXER_TEMPERATURE={fixer['temperature']}",
        f"ROLE_FIXER_MAX_TOKENS={fixer['max_tokens']}",
        "",
        "# Role: debug_expert",
        f"ROLE_DEBUG_EXPERT_MODEL={debug_expert['name']}",
        f"ROLE_DEBUG_EXPERT_API_KEY={debug_expert['api_key']}",
        f"ROLE_DEBUG_EXPERT_BASE_URL={debug_expert['base_url']}",
        f"ROLE_DEBUG_EXPERT_PROVIDER_TYPE={debug_expert['provider_type']}",
        f"ROLE_DEBUG_EXPERT_TEMPERATURE={debug_expert['temperature']}",
        f"ROLE_DEBUG_EXPERT_MAX_TOKENS={debug_expert['max_tokens']}",
        "",
        "# Legacy aliases (for backward compatibility)",
        f"ROLE_WORKER_MODEL={coder['name']}",
        f"ROLE_WORKER_API_KEY={coder['api_key']}",
        f"ROLE_WORKER_BASE_URL={coder['base_url']}",
        f"ROLE_WORKER_PROVIDER_TYPE={coder['provider_type']}",
        f"ROLE_WORKER_TEMPERATURE={coder['temperature']}",
        f"ROLE_WORKER_MAX_TOKENS={coder['max_tokens']}",
        f"ROLE_TEST_MODEL={fixer['name']}",
        f"ROLE_TEST_API_KEY={fixer['api_key']}",
        f"ROLE_TEST_BASE_URL={fixer['base_url']}",
        f"ROLE_TEST_PROVIDER_TYPE={fixer['provider_type']}",
        f"ROLE_TEST_TEMPERATURE={fixer['temperature']}",
        f"ROLE_TEST_MAX_TOKENS={fixer['max_tokens']}",
        f"ROLE_DEBUG_MODEL={debug_expert['name']}",
        f"ROLE_DEBUG_API_KEY={debug_expert['api_key']}",
        f"ROLE_DEBUG_BASE_URL={debug_expert['base_url']}",
        f"ROLE_DEBUG_PROVIDER_TYPE={debug_expert['provider_type']}",
        f"ROLE_DEBUG_TEMPERATURE={debug_expert['temperature']}",
        f"ROLE_DEBUG_MAX_TOKENS={debug_expert['max_tokens']}",
        "",
        "# Project commands",
        f"COMPILE_COMMAND={compile_cmd}",
        f"TEST_COMMAND={test_cmd}",
        f"UNIT_TEST_COMMAND={unit_test_cmd}",
        f"MAX_RETRIES={engine_cfg['max_retries']}",
        f"MAX_LOOPS={engine_cfg['max_loops']}",
        f"TEST_TIMEOUT={runtime_cfg['test_timeout_seconds']}",
        f"CONTEXT_LIMIT={engine_cfg['context_limit']}",
        f"ARTIFACT_POLICY={artifact_policy}",
        f"LOGGING_ENABLED={'1' if logging_cfg['enabled'] else '0'}",
        f"LOGGING_CAPTURE_PROMPTS={'1' if logging_cfg['capture_prompts'] else '0'}",
        f"LOGGING_CAPTURE_RESPONSES={'1' if logging_cfg['capture_responses'] else '0'}",
    ]

    if proxy.get("http_proxy"):
        lines.extend([
            "",
            "# Proxy",
            f"HTTP_PROXY={proxy['http_proxy']}",
            f"HTTPS_PROXY={proxy['https_proxy']}",
        ])

    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    if existing_cmds:
        print("  ✅ .env 已生成 (已保护原有动态命令)")
    else:
        print("  ✅ .env 已生成")


def generate_claude_md(config: dict, project_root: Path):
    roles = resolve_roles(config)
    runtime_cfg = resolve_runtime(config)
    template_path = project_root / ".pipeline" / "CLAUDE.md.template"
    if not template_path.exists():
        # 在 smartroute-kit 源仓中，模板位于 pipeline/ 目录
        fallback = project_root / "pipeline" / "CLAUDE.md.template"
        if fallback.exists():
            template_path = fallback
    output_path = project_root / "CLAUDE.md"

    if not template_path.exists():
        print("  ⚠ CLAUDE.md.template 不存在，跳过 CLAUDE.md 生成")
        return

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    content = (
        template
        .replace("{{ROLE_PLANNER_MODEL}}", roles["planner"]["name"])
        .replace("{{ROLE_CODER_MODEL}}", roles["coder"]["name"])
        .replace("{{ROLE_TEST_CODER_MODEL}}", roles["test_coder"]["name"])
        .replace("{{ROLE_FIXER_MODEL}}", roles["fixer"]["name"])
        .replace("{{ROLE_DEBUG_EXPERT_MODEL}}", roles["debug_expert"]["name"])
        # backward placeholders
        .replace("{{ROLE_WORKER_MODEL}}", roles["coder"]["name"])
        .replace("{{ROLE_TEST_MODEL}}", roles["fixer"]["name"])
        .replace("{{ROLE_DEBUG_MODEL}}", roles["debug_expert"]["name"])
        .replace("{{COMPILE_COMMAND}}", runtime_cfg["compile_command"])
        .replace("{{TEST_COMMAND}}", runtime_cfg["test_command"])
        .replace("{{UNIT_TEST_COMMAND}}", runtime_cfg["unit_test_command"])
    )

    marker_start = "<!-- SMARTROUTE-CONFIG-START -->"
    marker_end = "<!-- SMARTROUTE-CONFIG-END -->"
    new_block = f"{marker_start}\n{content}\n{marker_end}"

    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            existing = f.read()
        if marker_start in existing and marker_end in existing:
            start = existing.index(marker_start)
            end = existing.index(marker_end) + len(marker_end)
            final = existing[:start] + new_block + existing[end:]
            msg = "已更新"
        else:
            final = existing.rstrip() + "\n\n" + new_block
            msg = "已追加 (首次注入)"
    else:
        final = new_block
        msg = "已生成"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final)
    print(f"  ✅ CLAUDE.md {msg}")


def show_config_summary(config: dict):
    roles = resolve_roles(config)
    runtime_cfg = resolve_runtime(config)
    engine_cfg = resolve_engine_settings(config)
    artifact_policy = resolve_artifact_policy(config)
    logging_cfg = resolve_logging(config)

    def mask(key: str) -> str:
        if len(key) <= 16:
            return "***"
        return key[:8] + "..." + key[-4:]

    print()
    print("  ┌─────────────────────────────────────────────┐")
    print("  │         SmartRoute V3 当前配置摘要           │")
    print("  ├─────────────────────────────────────────────┤")
    ordered_roles = ("planner", "coder", "test_coder", "fixer", "debug_expert")
    for idx, role in enumerate(ordered_roles):
        cfg = roles[role]
        print(f"  │ {role:<12}: {cfg['name']:<28s} │")
        print(f"  │   type: {cfg['provider_type']:<35s} │")
        print(f"  │   url : {cfg['base_url'][:35]:<35s} │")
        print(f"  │   key : {mask(cfg['api_key']):<35s} │")
        if idx != len(ordered_roles) - 1:
            print("  ├─────────────────────────────────────────────┤")
    print("  ├─────────────────────────────────────────────┤")
    print(f"  │ 编译:   {runtime_cfg['compile_command']:<35s} │")
    print(f"  │ 测试:   {runtime_cfg['test_command']:<35s} │")
    print(f"  │ 重试:   {engine_cfg['max_retries']:<35d} │")
    print(f"  │ 循环:   {engine_cfg['max_loops']:<35d} │")
    print(f"  │ 上下文: {engine_cfg['context_limit']:<35d} │")
    print(f"  │ 工件:   {artifact_policy:<35s} │")
    print(f"  │ 观测:   {str(logging_cfg['enabled']):<35s} │")
    print("  └─────────────────────────────────────────────┘")
    print()


def check_config(config: dict) -> list:
    warnings = []
    roles = resolve_roles(config)

    def is_placeholder(value: str) -> bool:
        if not value:
            return True
        markers = ["在此填入", "填入你的", "YOUR_", "your_"]
        return any(marker in value for marker in markers)

    for role_name in ("planner", "coder", "test_coder", "fixer", "debug_expert"):
        cfg = roles[role_name]
        if is_placeholder(cfg["api_key"]):
            warnings.append(f"{role_name} API Key 未填写")
        if not cfg["name"]:
            warnings.append(f"{role_name} 模型名称未填写")
        if not cfg["base_url"]:
            warnings.append(f"{role_name} base_url 未填写")

    for role_name in ("coder", "test_coder", "fixer"):
        if roles[role_name]["provider_type"] != "openai":
            warnings.append(f"{role_name} provider_type 建议为 openai")
    for role_name in ("planner", "debug_expert"):
        if roles[role_name]["provider_type"] != "anthropic":
            warnings.append(f"{role_name} provider_type 建议为 anthropic")

    runtime_cfg = resolve_runtime(config)
    if not runtime_cfg["compile_command"]:
        warnings.append("runtime.compile_command 未填写")
    if not runtime_cfg["test_command"]:
        warnings.append("runtime.test_command 未填写")

    return warnings


def main():
    project_root = find_project_root()
    config = load_config(project_root)

    if "--show-config" in sys.argv:
        show_config_summary(config)
        return

    print()
    print("  SmartRoute V3 配置同步")
    print("  ━━━━━━━━━━━━━━━━━━━━━")
    print()

    try:
        warnings = check_config(config)
    except ValueError as e:
        print(f"  ❌ 配置错误: {e}")
        sys.exit(1)

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

    print("  正在同步配置...")
    generate_env(config, project_root)
    generate_claude_md(config, project_root)

    for d in [
        "docs/requirements",
        "docs/design",
        "docs/test",
        "docs/review",
        ".pipeline",
        ".pipeline/context",
        ".pipeline/logs",
        ".smartroute",
        ".smartroute/artifacts",
    ]:
        (project_root / d).mkdir(parents=True, exist_ok=True)

    show_config_summary(config)
    print("  ✅ 配置同步完成！")
    print()
    test_loop_entry = "pipeline/test_loop.py" if (project_root / "pipeline" / "test_loop.py").exists() else ".pipeline/test_loop.py"
    print("  下一步:")
    print("    1. 在 Claude Code 中按任务生成 .smartroute/task.md")
    print(f"    2. 运行 python {test_loop_entry} --project-dir . --task .smartroute/task.md")
    print()


if __name__ == "__main__":
    main()
