"""
router.py — 路由决策逻辑（按生命周期角色）
"""

from state import TestLoopState

# ── 路由目标节点常量 ──
NODE_COMPILE = "compile"
NODE_FIXER = "fixer"
NODE_DEBUG_EXPERT_DIAGNOSE = "debug_expert_diagnose"
NODE_CODER_APPLY_DEBUG_FIX = "coder_apply_debug_fix"
NODE_UNIT_TEST = "unit_test"
NODE_DEBUG_REFLECTION = "debug_reflection"
NODE_REGRESSION = "regression_test"
NODE_DONE = "done"
NODE_MANUAL = "manual_intervention"
NODE_ABORT = "abort"


def route_after_compile(state: TestLoopState) -> str:
    """
    编译结果路由

    编译成功 -> 进入测试
    编译失败 + 重试未超限 -> fixer 继续修复
    编译失败 + 重试超限 + 当前角色非 debug_expert -> 升级 debug_expert 诊断
    编译失败 + debug_expert 方案仍失败 -> 人工介入
    """
    if state["compile_success"]:
        return "test"

    current_role = state.get("current_role", state.get("current_model", ""))
    if state["retry_count"] < state["max_retries"]:
        if current_role == "debug_expert":
            return NODE_CODER_APPLY_DEBUG_FIX
        return NODE_FIXER

    if current_role != "debug_expert" and not state.get("debug_diagnosis_used"):
        return NODE_DEBUG_EXPERT_DIAGNOSE
    return NODE_MANUAL


def route_after_test(state: TestLoopState) -> str:
    """
    测试结果路由
    """
    test_result = state.get("test_results", "")
    current_role = state.get("current_role", state.get("current_model", ""))

    if test_result == "PASS":
        if state.get("user_bug_report") and not state.get("reflection_done"):
            return NODE_DEBUG_REFLECTION
        return NODE_DONE

    if state["retry_count"] < state["max_retries"]:
        if current_role == "debug_expert" and state.get("debug_diagnosis_plan"):
            return NODE_CODER_APPLY_DEBUG_FIX
        return NODE_FIXER

    if current_role != "debug_expert" and not state.get("debug_diagnosis_used"):
        return NODE_DEBUG_EXPERT_DIAGNOSE

    if state.get("debug_diagnosis_used") and state["retry_count"] >= state["max_retries"]:
        return NODE_MANUAL

    return NODE_MANUAL


def route_after_reflection(state: TestLoopState) -> str:
    return NODE_REGRESSION


def route_after_unit_test(state: TestLoopState) -> str:
    if state.get("test_results") == "PASS":
        return NODE_DONE
    if state["retry_count"] < state["max_retries"]:
        return NODE_FIXER
    return NODE_MANUAL


def should_abort(state: TestLoopState) -> bool:
    return state["loop_count"] >= state["max_loop_count"]


def describe_route_decision(from_node: str, to_node: str, state: TestLoopState) -> str:
    retry = state["retry_count"]
    max_r = state["max_retries"]
    descriptions = {
        NODE_FIXER: f"🔄 fixer 角色第 {retry + 1}/{max_r} 次修复尝试",
        NODE_DEBUG_EXPERT_DIAGNOSE: f"⚠️ fixer 角色已尝试 {retry} 次失败，升级到 debug_expert",
        NODE_CODER_APPLY_DEBUG_FIX: "🛠️ coder 角色根据 debug_expert 方案执行修改",
        NODE_DEBUG_REFLECTION: "🧠 触发 debug_expert 漏测反思机制",
        NODE_REGRESSION: "🔁 执行全量回归测试",
        NODE_DONE: "✅ 流程完成",
        NODE_MANUAL: "🚨 需要人工介入",
        NODE_ABORT: "⛔ 循环次数超限，强制中止",
    }
    return descriptions.get(to_node, f"→ {to_node}")

