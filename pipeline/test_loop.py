#!/usr/bin/env python3
"""
test_loop.py — 自动化测试循环主入口
SmartRoute: Claude Code + Python 编排脚本整合方案

功能:
  编译 → 测试 → Fast修复 → 超限升级Strong → Strong给方案 →
  Fast执行 → 漏测反思 → 回归测试

用法:
  python3 test_loop.py --project-dir /path/to/project
  python3 test_loop.py --project-dir . --max-retries 3 --bug-report "xxx功能崩溃"

  在 Claude Code 中通过自定义命令触发:
  /project:test-loop
"""

import argparse
import os
import sys

# 确保能导入同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from state import TestLoopState, create_initial_state, save_state
from router import (
    route_after_compile, route_after_test, route_after_reflection,
    should_abort, describe_route_decision,
    NODE_FAST_FIX, NODE_STRONG_DIAGNOSE, NODE_FAST_APPLY_FIX,
    NODE_STRONG_REFLECTION, NODE_REGRESSION, NODE_DONE, NODE_MANUAL, NODE_ABORT,
)
from nodes import (
    compile_node, test_node, fast_fix_node,
    strong_diagnose_node, fast_apply_fix_node, strong_reflection_node,
    strong_update_automation_plan_node, fast_generate_test_code_node,
)
from logger import PipelineLogger


def run_test_loop(state: TestLoopState, log: PipelineLogger) -> TestLoopState:
    """
    主循环: 编译 → 测试 → 修复/升级 → 反思 → 回归

    这是整个自动化流水线的核心引擎。
    """

    # ── 阶段 1: 编译 ──
    log.phase("阶段 1: 编译验证")
    state["current_phase"] = "compilation"
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
                f"编译失败, retry={state['retry_count']}/{state['max_retries']}, model={state['current_model']}")

            if next_node == NODE_FAST_FIX:
                log.node_start("Fast 编译修复", "minimax")
                state = fast_fix_node(state)
                log.node_end("Fast 编译修复", True)

            elif next_node == NODE_STRONG_DIAGNOSE:
                log.escalation(f"编译修复超过 {state['max_retries']} 次")
                log.node_start("Strong 编译诊断", "opus")
                state = strong_diagnose_node(state)
                log.node_end("Strong 编译诊断", True)
                # Strong 给方案后，让 Fast 执行
                log.node_start("Fast 执行Strong方案", "minimax")
                state = fast_apply_fix_node(state)
                log.node_end("Fast 执行Strong方案", True)

            elif next_node == NODE_MANUAL:
                state["final_status"] = "manual_intervention"
                log.error("编译问题无法自动解决，需要人工介入")
                return state

            # 重新编译
            state = compile_node(state)

    log.success("编译通过")

    # ── 阶段 2: 系统测试 ──
    log.phase("阶段 2: 系统自动化测试")
    state["current_phase"] = "system_testing"
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

        if next_node == NODE_FAST_FIX:
            log.node_start("Fast Bug修复", "minimax")
            state = fast_fix_node(state)
            log.node_end("Fast Bug修复", True)

        elif next_node == NODE_STRONG_DIAGNOSE:
            log.escalation(f"测试Bug修复超过 {state['max_retries']} 次")
            log.node_start("Strong 深度诊断", "opus")
            state = strong_diagnose_node(state)
            log.node_end("Strong 深度诊断", True)
            continue  # 回到循环顶部，router 会引导到 MINIMAX_APPLY_FIX

        elif next_node == NODE_FAST_APPLY_FIX:
            log.node_start("Fast 执行Strong方案", "minimax")
            state = fast_apply_fix_node(state)
            log.node_end("Fast 执行Strong方案", True)

        elif next_node == NODE_STRONG_REFLECTION:
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
        state["current_phase"] = "reflection"
        log.node_start("Strong 漏测反思", "opus")
        state = strong_reflection_node(state)
        log.node_end("Strong 漏测反思", state["reflection_done"],
                     state.get("reflection_result", ""))

        # 反思完成后，更新自动化测试方案
        if state["reflection_done"]:
            # ── 阶段 3.1: 更新自动化测试方案 ──
            log.phase("阶段 3.1: 更新自动化测试方案")
            state["current_phase"] = "update_automation_plan"
            log.node_start("Strong 自动化方案更新", "opus")
            state = strong_update_automation_plan_node(state)
            log.node_end("Strong 自动化方案更新", state.get("automation_plan_updated", False))

            # ── 阶段 3.2: 根据方案生成测试代码（系统+单元） ──
            if state.get("automation_plan_updated"):
                log.phase("阶段 3.2: 生成系统测试代码")
                state["current_phase"] = "generate_system_test_code"
                log.node_start("Fast 系统测试代码生成", "minimax")
                state = fast_generate_test_code_node(state, test_type="system")
                log.node_end("Fast 系统测试代码生成", state.get("system_test_code_generated", False))

                log.phase("阶段 3.2: 生成单元测试代码")
                state["current_phase"] = "generate_unit_test_code"
                log.node_start("Fast 单元测试代码生成", "minimax")
                state = fast_generate_test_code_node(state, test_type="unit")
                log.node_end("Fast 单元测试代码生成", state.get("unit_test_code_generated", False))

                # 生成代码后重新编译
                any_code_generated = state.get("system_test_code_generated") or state.get("unit_test_code_generated")
                if any_code_generated:
                    log.info("重新编译（包含新测试代码）...")
                    state = compile_node(state)
                    if not state["compile_success"]:
                        log.error("新测试代码编译失败，可能需要人工检查")

            # ── 阶段 3.3: 回归测试（系统测试 + 单元测试） ──
            log.phase("阶段 3.3: 回归测试（反思后）")
            state["current_phase"] = "regression_after_reflection"
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
        state["current_phase"] = "unit_testing"
        state["retry_count"] = 0
        state = test_node(state, test_type="unit")

        if state["test_results"] != "PASS":
            log.error(f"单元测试失败: {state['test_error_log'][:200]}")
            # 简单重试一轮 Fast 修复
            for i in range(state["max_retries"]):
                state = fast_fix_node(state)
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
  python3 test_loop.py --project-dir . --compile-cmd "cmake --build build"
        """
    )
    parser.add_argument("--project-dir", required=True, help="项目根目录")
    parser.add_argument("--compile-cmd", default="make -j4", help="编译命令")
    parser.add_argument("--test-cmd", default="./bin/system_tests", help="系统测试命令")
    parser.add_argument("--unit-test-cmd", default="./bin/unit_tests", help="单元测试命令")
    parser.add_argument("--max-retries", type=int, default=3, help="最大重试次数 (替代15分钟)")
    parser.add_argument("--max-loops", type=int, default=30, help="最大总循环次数 (安全阀)")
    parser.add_argument("--bug-report", default=None, help="用户Bug描述 (触发漏测反思)")
    parser.add_argument("--resume", default=None, help="从状态文件恢复执行")

    args = parser.parse_args()

    # ── 初始化 ──
    log = PipelineLogger(log_dir=os.path.join(args.project_dir, ".pipeline"))

    log.phase("SmartRoute 自动化测试循环启动")
    log.info(f"项目目录: {args.project_dir}")
    log.info(f"编译命令: {args.compile_cmd}")
    log.info(f"测试命令: {args.test_cmd}")
    log.info(f"最大重试: {args.max_retries}")
    if args.bug_report:
        log.info(f"Bug报告: {args.bug_report}")

    # 检查环境变量
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.error("未设置 ANTHROPIC_API_KEY 环境变量 (Strong)")
        sys.exit(1)
    if not os.environ.get("MINIMAX_API_KEY"):
        log.error("未设置 MINIMAX_API_KEY 环境变量 (Fast)")
        sys.exit(1)

    # 创建或恢复状态
    if args.resume:
        from state import load_state
        state = load_state(args.resume)
        log.info(f"从断点恢复: {args.resume}")
    else:
        state = create_initial_state(
            project_dir=args.project_dir,
            compile_command=args.compile_cmd,
            test_command=args.test_cmd,
            unit_test_command=args.unit_test_cmd,
            max_retries=args.max_retries,
            max_loop_count=args.max_loops,
            user_bug_report=args.bug_report,
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
        # 保存最终状态
        state_file = os.path.join(args.project_dir, ".pipeline", "last-state.json")
        save_state(state, state_file)
        log.info(f"状态已保存: {state_file}")

    # ── 生成报告 ──
    report = log.generate_report(state)
    report_path = os.path.join(args.project_dir, ".pipeline", "test-loop-report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

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
