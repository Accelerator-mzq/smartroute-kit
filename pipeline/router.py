"""
router.py — 路由决策逻辑
SmartRoute: Claude Code + Python 编排脚本整合方案

根据状态中的 retry_count、test_results 等字段，决定下一步流转到哪个节点。
这是整个方案的"大脑"——精确控制 MiniMax/Opus 的升级降级。
"""

from state import TestLoopState

# ── 路由目标节点常量 ──
NODE_COMPILE = "compile"
NODE_FAST_FIX = "fast_fix"
NODE_STRONG_DIAGNOSE = "strong_diagnose"
NODE_FAST_APPLY_FIX = "fast_apply_strong_fix"
NODE_UNIT_TEST = "unit_test"
NODE_STRONG_REFLECTION = "strong_reflection"
NODE_REGRESSION = "regression_test"
NODE_DONE = "done"
NODE_MANUAL = "manual_intervention"
NODE_ABORT = "abort"


def route_after_compile(state: TestLoopState) -> str:
    """
    编译结果路由

    编译成功 → 进入测试
    编译失败 + 重试未超限 → MiniMax 继续修复
    编译失败 + 重试超限 + 当前是 fast → 升级 Opus
    编译失败 + 重试超限 + 当前是 strong → 人工介入
    """
    if state["compile_success"]:
        return "test"

    if state["retry_count"] < state["max_retries"]:
        if state["current_model"] == "fast":
            return NODE_FAST_FIX
        else:
            return NODE_FAST_APPLY_FIX

    # 重试超限
    if state["current_model"] == "fast":
        return NODE_STRONG_DIAGNOSE
    else:
        return NODE_MANUAL


def route_after_test(state: TestLoopState) -> str:
    """
    测试结果路由（核心路由函数）

    测试通过 + 有 Bug 报告且未反思 → 漏测反思
    测试通过 → 进入单元测试或完成
    测试失败 + 重试未超限 → MiniMax 修复
    测试失败 + 重试超限 + 当前 fast → 升级 Opus
    测试失败 + Opus 已诊断但 MiniMax 执行后仍失败 → 标记手工测试
    """
    test_result = state.get("test_results", "")

    if test_result == "PASS":
        # 测试通过
        if state.get("user_bug_report") and not state.get("reflection_done"):
            # 有用户 Bug 报告，需要做漏测反思
            return NODE_STRONG_REFLECTION
        return NODE_DONE

    # 测试失败
    if state["retry_count"] < state["max_retries"]:
        if state["current_model"] == "strong" and state.get("strong_diagnosis_plan"):
            # Opus 已给方案，让 MiniMax 去落实
            return NODE_FAST_APPLY_FIX
        return NODE_FAST_FIX

    # 重试超限
    if state["current_model"] == "fast" and not state.get("strong_diagnosis_used"):
        # MiniMax 超限，第一次升级到 Opus
        return NODE_STRONG_DIAGNOSE

    if state.get("strong_diagnosis_used") and state["retry_count"] >= state["max_retries"]:
        # Opus 方案也执行失败了
        if test_result == "FAIL_TIMEOUT":
            return NODE_MANUAL  # 超时类问题，需要人工介入
        return NODE_MANUAL

    return NODE_MANUAL


def route_after_reflection(state: TestLoopState) -> str:
    """漏测反思完成后 → 全量回归测试"""
    return NODE_REGRESSION


def route_after_unit_test(state: TestLoopState) -> str:
    """单元测试结果路由"""
    if state.get("test_results") == "PASS":
        return NODE_DONE
    if state["retry_count"] < state["max_retries"]:
        return NODE_FAST_FIX
    return NODE_MANUAL


def should_abort(state: TestLoopState) -> bool:
    """检查是否应该中止整个循环（防止无限循环）"""
    return state["loop_count"] >= state["max_loop_count"]


def describe_route_decision(from_node: str, to_node: str, state: TestLoopState) -> str:
    """生成人类可读的路由决策说明"""
    model = state["current_model"]
    retry = state["retry_count"]
    max_r = state["max_retries"]

    descriptions = {
        NODE_FAST_FIX: f"🔄 MiniMax 第 {retry + 1}/{max_r} 次修复尝试",
        NODE_STRONG_DIAGNOSE: f"⚠️ MiniMax 已尝试 {retry} 次失败，升级到 Opus 诊断",
        NODE_FAST_APPLY_FIX: "🛠️ MiniMax 根据 Opus 方案执行修改",
        NODE_STRONG_REFLECTION: "🧠 触发 Opus 漏测反思机制",
        NODE_REGRESSION: "🔁 执行全量回归测试",
        NODE_DONE: "✅ 流程完成",
        NODE_MANUAL: "🚨 需要人工介入",
        NODE_ABORT: "⛔ 循环次数超限，强制中止",
    }
    return descriptions.get(to_node, f"→ {to_node}")
