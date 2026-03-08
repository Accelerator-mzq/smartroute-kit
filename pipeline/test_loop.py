#!/usr/bin/env python3
"""
test_loop.py — 自动化测试循环主入口
SmartRoute: Claude Code + Python 编排脚本整合方案

功能:
  V3 任务模式: 读取 task.md → planner/coder/test_coder → runtime → fixer/debug_expert

用法:
  python3 test_loop.py --project-dir /path/to/project
  python3 test_loop.py --project-dir . --max-retries 3 --bug-report "xxx功能崩溃"
  python3 test_loop.py --project-dir . --task .smartroute/task.md

  在 Claude Code 中通过自定义命令触发:
  /test-loop
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Tuple

# 确保能导入同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from state import TestLoopState, create_initial_state, save_state
from router import (
    route_after_compile, route_after_test, route_after_reflection,
    should_abort, describe_route_decision,
    NODE_FIXER, NODE_DEBUG_EXPERT_DIAGNOSE, NODE_CODER_APPLY_DEBUG_FIX,
    NODE_DEBUG_REFLECTION, NODE_REGRESSION, NODE_DONE, NODE_MANUAL, NODE_ABORT,
)
from nodes import (
    planner_generate_execution_plan_node,
    coder_generate_from_plan_node,
    test_coder_generate_from_plan_node,
    compile_node, test_node, fixer_node,
    debug_expert_diagnose_node, coder_apply_debug_fix_node, debug_expert_reflection_node,
    debug_expert_update_automation_plan_node, test_coder_generate_test_code_node,
)
from logger import PipelineLogger
from model_caller import ModelCaller, set_model_observer
from context_manager import ContextManager, discover_project_context
from task_graph import TaskGraphEngine
from artifact_manager import ArtifactManager
from observability import ObservabilitySystem
from state_machine import PipelineStateMachine, PipelinePhase


def load_project_runtime_config(project_dir: str) -> dict:
    """读取项目运行参数（支持 V3 增强配置 + 旧配置兼容）。"""
    defaults = {
        "compile_command": "make -j4",
        "test_command": "./bin/system_tests",
        "unit_test_command": "./bin/unit_tests",
        "max_retries": 3,
        "max_loops": 30,
        "test_timeout_seconds": 120,
        "context_limit": 12000,
        "artifact_policy": "per_execution",
        "logging": {
            "enabled": True,
            "capture_prompts": True,
            "capture_responses": True,
        },
    }
    config_path = os.path.join(project_dir, "smartroute.config.json")
    if not os.path.exists(config_path):
        return defaults

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        runtime = data.get("runtime", {})
        project = data.get("project", {})
        engine = data.get("engine_settings", {})
        logging_cfg = data.get("logging", {})
        artifact_policy = data.get("artifact_policy", {})

        defaults["compile_command"] = runtime.get(
            "compile_command",
            project.get("compile_command", defaults["compile_command"])
        )
        defaults["test_command"] = runtime.get(
            "test_command",
            project.get("test_command", defaults["test_command"])
        )
        defaults["unit_test_command"] = runtime.get(
            "unit_test_command",
            project.get("unit_test_command", defaults["unit_test_command"])
        )
        defaults["test_timeout_seconds"] = int(
            runtime.get(
                "test_timeout_seconds",
                project.get("test_timeout_seconds", defaults["test_timeout_seconds"]),
            )
        )
        defaults["max_retries"] = int(
            engine.get("max_retries", project.get("max_retries", defaults["max_retries"]))
        )
        defaults["max_loops"] = int(
            engine.get("max_loops", project.get("max_loops", defaults["max_loops"]))
        )
        defaults["context_limit"] = int(
            engine.get("context_limit", data.get("context_limit", defaults["context_limit"]))
        )
        if isinstance(artifact_policy, dict):
            defaults["artifact_policy"] = artifact_policy.get("mode", defaults["artifact_policy"])
        elif isinstance(artifact_policy, str) and artifact_policy:
            defaults["artifact_policy"] = artifact_policy
        if isinstance(logging_cfg, dict):
            defaults["logging"] = {
                "enabled": bool(logging_cfg.get("enabled", defaults["logging"]["enabled"])),
                "capture_prompts": bool(
                    logging_cfg.get("capture_prompts", defaults["logging"]["capture_prompts"])
                ),
                "capture_responses": bool(
                    logging_cfg.get("capture_responses", defaults["logging"]["capture_responses"])
                ),
            }
    except Exception:
        # 配置读取失败时回退默认值，避免因配置损坏阻塞主流程
        return defaults
    return defaults


def parse_task_file(task_path: str) -> dict:
    """
    解析 V3 握手任务文件。
    约定结构:
      [Task Objective]
      ...
      [Strict Rules]
      ...
      [Target Files]
      ...
    """
    if not os.path.exists(task_path):
        raise FileNotFoundError(f"任务文件不存在: {task_path}")

    with open(task_path, "r", encoding="utf-8") as f:
        content = f.read()

    sections = {
        "Task Objective": "",
        "Strict Rules": "",
        "Target Files": "",
    }

    current = None
    for raw_line in content.splitlines():
        line = raw_line.strip().lstrip("\ufeff")
        # 兼容 Markdown 标题格式，如 "## [Task Objective]"
        line_clean = line.lstrip("#").strip()
        if line_clean.startswith("[") and line_clean.endswith("]"):
            key = line_clean[1:-1].strip()
            current = key if key in sections else None
            continue
        if current:
            sections[current] += raw_line + "\n"

    target_files = []
    for line in sections["Target Files"].splitlines():
        stripped = line.strip().lstrip("-").strip()
        if stripped:
            target_files.append(stripped)

    return {
        "task_objective": sections["Task Objective"].strip(),
        "task_rules": sections["Strict Rules"].strip(),
        "task_target_files": target_files,
    }


def build_or_load_task_graph(project_dir: str, task_context: dict) -> Tuple[TaskGraphEngine, str]:
    """
    Load `.smartroute/Execution_Plan.json` when present, otherwise create a default DAG.
    """
    plan_path = os.path.join(project_dir, ".smartroute", "Execution_Plan.json")
    if os.path.exists(plan_path):
        graph = TaskGraphEngine.from_json_file(plan_path)
        return graph, plan_path

    graph = TaskGraphEngine.create_default(
        task_objective=task_context.get("task_objective", ""),
        target_files=task_context.get("task_target_files", []),
    )
    graph.save(plan_path)
    return graph, plan_path


def run_test_loop(state: TestLoopState, log: PipelineLogger) -> TestLoopState:
    """
    主循环: 编译 → 测试 → 修复/升级 → 反思 → 回归

    这是整个自动化流水线的核心引擎。
    """
    machine = PipelineStateMachine()

    def set_phase(phase_name: str, machine_phase: PipelinePhase):
        machine.transition(machine_phase)
        state["current_phase"] = phase_name
        log.info(f"状态机阶段: {machine.to_string()}")

    set_phase("init", PipelinePhase.INIT)

    # ── 阶段 0: Planner 任务拆解 ──
    if state.get("task_file"):
        log.phase("阶段 0: Planner 任务拆解")
        set_phase("planning", PipelinePhase.PLANNING)
        log.node_start("Planner 生成执行计划", "planner")
        state = planner_generate_execution_plan_node(state)
        plan_ok = bool(state.get("execution_plan"))
        log.node_end("Planner 生成执行计划", plan_ok)

        log.phase("阶段 0.1: Coder 业务编码")
        set_phase("coding", PipelinePhase.CODING)
        log.node_start("Coder 代码生成", "coder")
        state = coder_generate_from_plan_node(state)
        coding_ok = not state.get("current_code", "").startswith("[ERROR]")
        log.node_end("Coder 代码生成", coding_ok, f"目标文件: {len(state.get('task_target_files', []))}")

        log.phase("阶段 0.2: Test Coder 测试编码")
        set_phase("test_coding", PipelinePhase.CODING)
        log.node_start("Test Coder 测试代码生成", "test_coder")
        state = test_coder_generate_from_plan_node(state)
        tests_ok = bool(state.get("system_test_code_generated") or state.get("unit_test_code_generated"))
        log.node_end("Test Coder 测试代码生成", tests_ok)

    # ── 阶段 1: 编译 ──
    log.phase("阶段 1: 编译验证")
    set_phase("compilation", PipelinePhase.TESTING)
    state = compile_node(state)

    if not state["compile_success"]:
        # 进入编译修复循环
        while not state["compile_success"]:
            state["loop_count"] += 1
            if should_abort(state):
                state["final_status"] = "aborted"
                log.error(f"总循环次数超过 {state['max_loop_count']}，强制中止")
                return state

            next_node = route_after_compile(state)
            log.route_decision("compile", next_node,
                f"编译失败, retry={state['retry_count']}/{state['max_retries']}, role={state.get('current_role', state.get('current_model'))}")

            if next_node == NODE_FIXER:
                log.node_start("Fixer 编译修复", "fixer")
                state = fixer_node(state)
                log.node_end("Fixer 编译修复", True)

            elif next_node == NODE_DEBUG_EXPERT_DIAGNOSE:
                log.escalation(f"编译修复超过 {state['max_retries']} 次")
                log.node_start("Debug Expert 编译诊断", "debug_expert")
                state = debug_expert_diagnose_node(state)
                log.node_end("Debug Expert 编译诊断", True)
                # debug_expert 给方案后，让 coder 执行
                log.node_start("Coder 执行诊断方案", "coder")
                state = coder_apply_debug_fix_node(state)
                log.node_end("Coder 执行诊断方案", True)

            elif next_node == NODE_MANUAL:
                state["final_status"] = "manual_intervention"
                log.error("编译问题无法自动解决，需要人工介入")
                return state

            # 重新编译
            state = compile_node(state)

    log.success("编译通过")

    # ── 阶段 2: 系统测试 ──
    log.phase("阶段 2: 系统自动化测试")
    set_phase("system_testing", PipelinePhase.TESTING)
    state["retry_count"] = 0
    state = test_node(state, test_type="system")

    while state["test_results"] != "PASS":
        state["loop_count"] += 1
        if should_abort(state):
            state["final_status"] = "aborted"
            log.error(f"总循环次数超过 {state['max_loop_count']}，强制中止")
            return state

        next_node = route_after_test(state)
        log.route_decision("system_test", next_node,
            f"测试结果={state['test_results']}, retry={state['retry_count']}/{state['max_retries']}")

        if next_node == NODE_FIXER:
            log.node_start("Fixer Bug修复", "fixer")
            state = fixer_node(state)
            log.node_end("Fixer Bug修复", True)

        elif next_node == NODE_DEBUG_EXPERT_DIAGNOSE:
            log.escalation(f"测试Bug修复超过 {state['max_retries']} 次")
            log.node_start("Debug Expert 深度诊断", "debug_expert")
            state = debug_expert_diagnose_node(state)
            log.node_end("Debug Expert 深度诊断", True)
            continue  # 回到循环顶部，router 会引导到 coder_apply_fix

        elif next_node == NODE_CODER_APPLY_DEBUG_FIX:
            log.node_start("Coder 执行诊断方案", "coder")
            state = coder_apply_debug_fix_node(state)
            log.node_end("Coder 执行诊断方案", True)

        elif next_node == NODE_DEBUG_REFLECTION:
            # Bug修复成功，但需要做漏测反思
            break

        elif next_node == NODE_MANUAL:
            state["final_status"] = "manual_intervention"
            log.error("测试问题无法自动解决，需要人工介入")
            return state

        elif next_node == NODE_DONE:
            break

        # 重新编译 + 重新测试
        log.info("重新编译...")
        state = compile_node(state)
        if not state["compile_success"]:
            log.error("修复后编译失败，继续修复循环")
            continue
        log.info("重新执行系统测试...")
        state = test_node(state, test_type="system")

    # ── 阶段 3: 漏测反思 (如果有 Bug 报告) ──
    if state.get("user_bug_report") and not state.get("reflection_done"):
        log.phase("阶段 3: 漏测反思")
        set_phase("reflection", PipelinePhase.DEBUGGING)
        log.node_start("Debug Expert 漏测反思", "debug_expert")
        state = debug_expert_reflection_node(state)
        log.node_end("Debug Expert 漏测反思", state["reflection_done"],
                     state.get("reflection_result", ""))

        # 反思完成后，更新自动化测试方案
        if state["reflection_done"]:
            # ── 阶段 3.1: 更新自动化测试方案 ──
            log.phase("阶段 3.1: 更新自动化测试方案")
            set_phase("update_automation_plan", PipelinePhase.PLANNING)
            log.node_start("Debug Expert 自动化方案更新", "debug_expert")
            state = debug_expert_update_automation_plan_node(state)
            log.node_end("Debug Expert 自动化方案更新", state.get("automation_plan_updated", False))

            # ── 阶段 3.2: 根据方案生成测试代码（系统+单元） ──
            if state.get("automation_plan_updated"):
                log.phase("阶段 3.2: 生成系统测试代码")
                set_phase("generate_system_test_code", PipelinePhase.CODING)
                log.node_start("Test Coder 系统测试代码生成", "test_coder")
                state = test_coder_generate_test_code_node(state, test_type="system")
                log.node_end("Test Coder 系统测试代码生成", state.get("system_test_code_generated", False))

                log.phase("阶段 3.2: 生成单元测试代码")
                set_phase("generate_unit_test_code", PipelinePhase.CODING)
                log.node_start("Test Coder 单元测试代码生成", "test_coder")
                state = test_coder_generate_test_code_node(state, test_type="unit")
                log.node_end("Test Coder 单元测试代码生成", state.get("unit_test_code_generated", False))

                # 生成代码后重新编译
                any_code_generated = state.get("system_test_code_generated") or state.get("unit_test_code_generated")
                if any_code_generated:
                    log.info("重新编译（包含新测试代码）...")
                    state = compile_node(state)
                    if not state["compile_success"]:
                        log.error("新测试代码编译失败，可能需要人工检查")

            # ── 阶段 3.3: 回归测试（系统测试 + 单元测试） ──
            log.phase("阶段 3.3: 回归测试（反思后）")
            set_phase("regression_after_reflection", PipelinePhase.TESTING)
            state["retry_count"] = 0

            # 系统测试
            log.info("执行系统测试...")
            state = test_node(state, test_type="system")
            if state["test_results"] != "PASS":
                log.error("系统回归测试发现问题，可能需要进一步处理")

            # 单元测试（即使系统测试失败也运行，以获得完整的测试反馈）
            if state.get("unit_test_command"):
                log.info("执行单元测试...")
                sys_test_result = state["test_results"]  # 保存系统测试结果
                state = test_node(state, test_type="unit")
                if state["test_results"] != "PASS":
                    log.error("单元回归测试发现问题，可能需要进一步处理")
                # 如果系统测试也失败了，标记为更严重
                if sys_test_result != "PASS":
                    state["test_results"] = sys_test_result  # 恢复系统测试失败状态
    else:
        log.info("无用户 Bug 报告，跳过漏测反思")

    # ── 阶段 4: 单元测试 ──
    if state.get("unit_test_command") and state["test_results"] == "PASS":
        log.phase("阶段 4: 单元测试")
        set_phase("unit_testing", PipelinePhase.TESTING)
        state["retry_count"] = 0
        state = test_node(state, test_type="unit")

        if state["test_results"] != "PASS":
            log.error(f"单元测试失败: {state['test_error_log'][:200]}")
            # 简单重试一轮 fixer 角色修复
            for i in range(state["max_retries"]):
                state = fixer_node(state)
                state = compile_node(state)
                if state["compile_success"]:
                    state = test_node(state, test_type="unit")
                    if state["test_results"] == "PASS":
                        break
            if state["test_results"] != "PASS":
                log.error("单元测试修复失败，标记需人工介入")

    # ── 完成 ──
    if not state.get("final_status"):
        state["final_status"] = "success" if state["test_results"] == "PASS" else "partial"
    if state["final_status"] == "aborted":
        machine.transition(PipelinePhase.ABORTED)
    else:
        machine.transition(PipelinePhase.DONE)
    log.info(f"状态机阶段: {machine.to_string()}")

    return state


def main():
    parser = argparse.ArgumentParser(
        description="SmartRoute自动化测试循环 — Claude Code + Python编排",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 test_loop.py --project-dir .
  python3 test_loop.py --project-dir . --max-retries 3
  python3 test_loop.py --project-dir . --bug-report "下载暂停时崩溃"
    python3 test_loop.py --project-dir . --task .smartroute/task.md
  python3 test_loop.py --project-dir . --compile-cmd "cmake --build build"
        """
    )
    parser.add_argument("--project-dir", required=True, help="项目根目录")
    parser.add_argument("--compile-cmd", default=None, help="编译命令")
    parser.add_argument("--test-cmd", default=None, help="系统测试命令")
    parser.add_argument("--unit-test-cmd", default=None, help="单元测试命令")
    parser.add_argument("--max-retries", type=int, default=None, help="最大重试次数 (替代15分钟)")
    parser.add_argument("--max-loops", type=int, default=None, help="最大总循环次数 (安全阀)")
    parser.add_argument("--bug-report", default=None, help="用户Bug描述 (触发漏测反思)")
    parser.add_argument("--task", default=None, help="V3 任务说明书路径（如 .smartroute/task.md）")
    parser.add_argument("--resume", default=None, help="从状态文件恢复执行")

    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)
    runtime_cfg = load_project_runtime_config(project_dir)
    compile_cmd = args.compile_cmd or runtime_cfg["compile_command"]
    test_cmd = args.test_cmd or runtime_cfg["test_command"]
    unit_test_cmd = args.unit_test_cmd or runtime_cfg["unit_test_command"]
    max_retries = args.max_retries if args.max_retries is not None else runtime_cfg["max_retries"]
    max_loops = args.max_loops if args.max_loops is not None else runtime_cfg["max_loops"]
    test_timeout = int(runtime_cfg.get("test_timeout_seconds", 120))

    for d in [
        ".pipeline",
        ".pipeline/context",
        ".pipeline/logs",
        ".smartroute",
        ".smartroute/artifacts",
    ]:
        Path(project_dir, d).mkdir(parents=True, exist_ok=True)

    context_manager = ContextManager(project_dir=Path(project_dir), context_limit=runtime_cfg["context_limit"])
    project_context_summary = discover_project_context(project_dir)
    context_manager.update_project_context(project_context_summary)

    logging_cfg = runtime_cfg.get("logging", {})
    observability = ObservabilitySystem(
        project_dir=Path(project_dir),
        enabled=bool(logging_cfg.get("enabled", True)),
        capture_prompts=bool(logging_cfg.get("capture_prompts", True)),
        capture_responses=bool(logging_cfg.get("capture_responses", True)),
    )

    artifact_manager = ArtifactManager(
        project_dir=Path(project_dir),
        policy=runtime_cfg.get("artifact_policy", "per_execution"),
    )
    execution_id = artifact_manager.start_execution()

    # ── 初始化 ──
    log = PipelineLogger(
        log_dir=os.path.join(project_dir, ".pipeline", "logs"),
        runtime_log_hook=context_manager.append_runtime_log,
        observability=observability,
    )

    # [新特性] Windows 下自动弹出独立监控控制台
    if sys.platform == "win32":
        import subprocess
        try:
            ps_cmd = f'Write-Host "\n>>> SmartRoute 后台实时监控中心 [任务ID: {execution_id}] <<<" -ForegroundColor Cyan; Write-Host "==========================================================" -ForegroundColor Cyan; Get-Content -Path "{log.log_file}" -Encoding UTF8 -Wait -Tail 30'
            subprocess.Popen(
                ["powershell", "-NoExit", "-NoProfile", "-Command", ps_cmd],
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        except Exception as e:
            log.info(f"无法启动实时监控窗口: {e}")

    log.phase("SmartRoute 自动化测试循环启动")
    log.info(f"项目目录: {project_dir}")
    log.info(f"执行批次: {execution_id}")
    log.info(f"编译命令: {compile_cmd}")
    log.info(f"测试命令: {test_cmd}")
    log.info(f"最大重试: {max_retries}")
    log.info(f"上下文限制: {runtime_cfg['context_limit']}")
    if args.bug_report:
        log.info(f"Bug报告: {args.bug_report}")
    if args.task:
        log.info(f"任务文件: {args.task}")

    caller = ModelCaller()
    if not caller.has_valid_credentials():
        log.error("模型凭据无效：请检查 smartroute.config.json（roles）或环境变量")
        sys.exit(1)

    set_model_observer(observability.record_model_call_event)

    task_graph = None
    task_graph_path = ""

    # 创建或恢复状态
    if args.resume:
        from state import load_state
        state = load_state(args.resume)
        log.info(f"从断点恢复: {args.resume}")
        state["artifact_execution_id"] = artifact_manager.execution_id
        state["artifact_execution_dir"] = str(artifact_manager.execution_dir)
        state["context_dir"] = str(context_manager.context_dir)
        state["task_context_path"] = str(context_manager.task_context_path)
        state["runtime_logs_path"] = str(context_manager.runtime_logs_path)
        state["log_dir"] = str(observability.log_dir)
        if not state.get("execution_plan_path"):
            default_plan = os.path.join(project_dir, ".smartroute", "Execution_Plan.json")
            state["execution_plan_path"] = default_plan if os.path.exists(default_plan) else ""
    else:
        task_context = {
            "task_file": "",
            "task_objective": "",
            "task_rules": "",
            "task_target_files": [],
        }
        if args.task:
            try:
                parsed = parse_task_file(args.task)
                task_context = {
                    "task_file": os.path.abspath(args.task),
                    "task_objective": parsed["task_objective"],
                    "task_rules": parsed["task_rules"],
                    "task_target_files": parsed["task_target_files"],
                }
                context_manager.update_task_context(
                    objective=task_context["task_objective"],
                    rules=task_context["task_rules"],
                    target_files=task_context["task_target_files"],
                    task_file=task_context["task_file"],
                )
            except Exception as e:
                log.error(f"任务文件解析失败: {e}")
                sys.exit(1)

        task_graph, task_graph_path = build_or_load_task_graph(project_dir, task_context)
        ordered = task_graph.topological_order()
        graph_overview = " -> ".join(f"{n.id}:{n.role}" for n in ordered)
        log.info(f"任务图顺序: {graph_overview}")
        artifact_manager.save_plan(task_graph.to_dict())

        state = create_initial_state(
            project_dir=project_dir,
            compile_command=compile_cmd,
            test_command=test_cmd,
            unit_test_command=unit_test_cmd,
            test_timeout_seconds=test_timeout,
            max_retries=max_retries,
            max_loop_count=max_loops,
            user_bug_report=args.bug_report,
            task_file=task_context["task_file"],
            task_objective=task_context["task_objective"],
            task_rules=task_context["task_rules"],
            task_target_files=task_context["task_target_files"],
            execution_plan_path=task_graph_path,
            context_dir=str(context_manager.context_dir),
            task_context_path=str(context_manager.task_context_path),
            runtime_logs_path=str(context_manager.runtime_logs_path),
            artifact_execution_id=artifact_manager.execution_id,
            artifact_execution_dir=str(artifact_manager.execution_dir),
            log_dir=str(observability.log_dir),
        )

    # ── 执行主循环 ──
    try:
        state = run_test_loop(state, log)
    except KeyboardInterrupt:
        log.error("用户中断 (Ctrl+C)")
        state["final_status"] = "interrupted"
    except Exception as e:
        log.error(f"未预期的异常: {e}")
        state["final_status"] = "error"
        import traceback
        traceback.print_exc()
    finally:
        set_model_observer(None)
        # 保存最终状态
        state_file = os.path.join(project_dir, ".pipeline", "last-state.json")
        save_state(state, state_file)
        log.info(f"状态已保存: {state_file}")
        artifact_manager.save_state(dict(state))
        artifact_manager.copy_into(Path(state_file), category="state", output_name="last-state.json")

    # ── 生成报告 ──
    report = log.generate_report(state)
    report_path = os.path.join(project_dir, ".pipeline", "test-loop-report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    artifact_manager.copy_into(Path(report_path), category="logs", output_name="test-loop-report.md")
    artifact_manager.copy_into(Path(log.log_file), category="logs", output_name=Path(log.log_file).name)
    artifact_manager.copy_into(context_manager.task_context_path, category="state", output_name="task_context.md")
    artifact_manager.copy_into(context_manager.runtime_logs_path, category="logs", output_name="runtime_context.log")
    if task_graph_path:
        artifact_manager.copy_into(Path(task_graph_path), category="plans", output_name="Execution_Plan.json")
    copied = artifact_manager.snapshot_modified_files(state.get("modified_files", []))
    log.info(f"工件快照文件数: {copied}")

    # ── 最终输出 ──
    log.phase("执行完毕")
    if state["final_status"] == "success":
        log.success("所有测试通过！")
    elif state["final_status"] == "manual_intervention":
        log.error("存在需要人工介入的问题，请查看报告")
    elif state["final_status"] == "aborted":
        log.error("循环次数超限，已强制中止")
    else:
        log.info(f"最终状态: {state['final_status']}")

    log.info(f"测试报告: {report_path}")
    log.info(f"详细日志: {log.log_file}")

    return 0 if state["final_status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
