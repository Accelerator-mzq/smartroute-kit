"""
state.py — 自动化测试循环的状态定义
SmartRoute: Claude Code + Python 编排脚本整合方案
"""

from typing import TypedDict, Optional, List
import json
import os


class TestLoopState(TypedDict):
    """自动化测试循环状态"""

    # ── 项目配置 ──
    project_dir: str                # 项目根目录
    compile_command: str            # 编译命令 (如 "make -j4" 或 "mingw32-make")
    test_command: str               # 测试执行命令 (如 "./bin/system_tests")
    unit_test_command: str          # 单元测试命令
    test_timeout_seconds: int       # 测试命令超时阈值

    # ── 文档路径 ──
    system_test_cases_path: str     # 系统测试例文档路径
    unit_test_cases_path: str       # 单元测试例文档路径
    automation_plan_path: str       # 自动化测试方案路径
    design_doc_path: str            # 详细设计文档路径
    system_test_code_dir: str       # 系统测试代码目录 (tests/system/)
    unit_test_code_dir: str         # 单元测试代码目录 (tests/src/)

    # ── 编译状态 ──
    compile_error_log: str          # 编译错误日志
    compile_success: bool           # 编译是否成功

    # ── 测试状态 ──
    test_results: str               # 测试结果 ("PASS" / "FAIL" / "FAIL_TIMEOUT")
    test_error_log: str             # 测试错误日志
    current_test_item: str          # 当前正在执行的测试项

    # ── 代码上下文 ──
    current_code: str               # 当前相关代码内容
    modified_files: List[str]       # 本轮修改的文件列表

    # ── V3 任务握手上下文 ──
    task_file: str                  # 任务说明文件路径
    task_objective: str             # 任务目标
    task_rules: str                 # 强约束规则
    task_target_files: List[str]    # 目标文件列表
    execution_plan_path: str        # 任务图执行计划文件路径
    execution_plan: dict            # 任务拆解后的执行计划内容

    # ── 升级控制 ──
    retry_count: int                # 当前重试次数
    max_retries: int                # 最大重试次数 (替代15分钟超时)
    current_role: str               # 当前角色 (planner/coder/test_coder/fixer/debug_expert/runtime)
    current_model: str              # 兼容字段，等同 current_role
    escalation_history: List[str]   # 升级历史记录

    # ── Debug 诊断 ──
    debug_diagnosis_plan: str       # debug_expert 角色给出的诊断方案
    debug_diagnosis_used: bool      # 是否已使用 debug_expert 方案

    # ── 漏测反思 ──
    user_bug_report: Optional[str]  # 用户提交的 Bug 描述
    reflection_done: bool           # 漏测反思是否已完成
    reflection_result: str          # 反思结论
    automation_plan_updated: bool   # 自动化测试方案是否已更新
    system_test_code_generated: bool  # 是否已生成系统测试代码
    unit_test_code_generated: bool    # 是否已生成单元测试代码

    # ── 流程控制 ──
    current_phase: str              # 当前阶段
    loop_count: int                 # 总循环次数 (防止无限循环)
    max_loop_count: int             # 最大总循环次数
    final_status: str               # 最终状态 ("success" / "manual_intervention" / "aborted")
    context_dir: str                # 上下文目录
    task_context_path: str          # 任务上下文文件
    runtime_logs_path: str          # 运行日志上下文文件
    artifact_execution_id: str      # 工件执行 ID
    artifact_execution_dir: str     # 工件执行目录
    log_dir: str                    # 观测日志目录


def load_documents_config(project_dir: str) -> dict:
    """
    从 smartroute.config.json 读取 documents 配置。
    如果配置文件不存在或缺少某项，使用默认值。
    """
    defaults = {
        "requirements_dir": "docs/requirements",
        "overview_design": "docs/design/overview-design.md",
        "detailed_design": "docs/design/detailed-design.md",
        "system_test_cases": "docs/test/system-test-cases.md",
        "unit_test_cases": "docs/test/unit-test-cases.md",
        "automation_plan": "docs/test/automation-plan.md",
        "review_dir": "docs/review",
        "system_test_code_dir": "tests/system",
        "unit_test_code_dir": "tests/src",
    }
    config_path = os.path.join(project_dir, "smartroute.config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            docs = config.get("documents", {})
            # 用配置中的值覆盖默认值（跳过说明字段）
            for key in defaults:
                if key in docs:
                    defaults[key] = docs[key]
        except Exception as e:
            print(f"⚠️ 读取 documents 配置失败，使用默认路径: {e}")
    return defaults


def create_initial_state(
    project_dir: str,
    compile_command: str = "make -j4",
    test_command: str = "./bin/system_tests",
    unit_test_command: str = "./bin/unit_tests",
    test_timeout_seconds: int = 120,
    max_retries: int = 3,
    max_loop_count: int = 30,
    user_bug_report: Optional[str] = None,
    task_file: str = "",
    task_objective: str = "",
    task_rules: str = "",
    task_target_files: Optional[List[str]] = None,
    execution_plan_path: str = "",
    execution_plan: Optional[dict] = None,
    context_dir: str = "",
    task_context_path: str = "",
    runtime_logs_path: str = "",
    artifact_execution_id: str = "",
    artifact_execution_dir: str = "",
    log_dir: str = "",
) -> TestLoopState:
    """创建初始状态，文档路径从 smartroute.config.json 读取"""
    docs = load_documents_config(project_dir)
    abs_dir = os.path.abspath(project_dir)

    return TestLoopState(
        project_dir=abs_dir,
        compile_command=compile_command,
        test_command=test_command,
        unit_test_command=unit_test_command,
        test_timeout_seconds=test_timeout_seconds,
        system_test_cases_path=os.path.join(abs_dir, docs["system_test_cases"]),
        unit_test_cases_path=os.path.join(abs_dir, docs["unit_test_cases"]),
        automation_plan_path=os.path.join(abs_dir, docs["automation_plan"]),
        design_doc_path=os.path.join(abs_dir, docs["detailed_design"]),
        system_test_code_dir=os.path.join(abs_dir, docs["system_test_code_dir"]),
        unit_test_code_dir=os.path.join(abs_dir, docs["unit_test_code_dir"]),
        compile_error_log="",
        compile_success=False,
        test_results="",
        test_error_log="",
        current_test_item="",
        current_code="",
        modified_files=[],
        task_file=task_file,
        task_objective=task_objective,
        task_rules=task_rules,
        task_target_files=task_target_files or [],
        execution_plan_path=execution_plan_path,
        execution_plan=execution_plan or {},
        retry_count=0,
        max_retries=max_retries,
        current_role="planner",
        current_model="planner",
        escalation_history=[],
        debug_diagnosis_plan="",
        debug_diagnosis_used=False,
        user_bug_report=user_bug_report,
        reflection_done=False,
        reflection_result="",
        automation_plan_updated=False,
        system_test_code_generated=False,
        unit_test_code_generated=False,
        current_phase="init",
        loop_count=0,
        max_loop_count=max_loop_count,
        final_status="",
        context_dir=context_dir,
        task_context_path=task_context_path,
        runtime_logs_path=runtime_logs_path,
        artifact_execution_id=artifact_execution_id,
        artifact_execution_dir=artifact_execution_dir,
        log_dir=log_dir,
    )


def save_state(state: TestLoopState, filepath: str):
    """保存状态到文件 (用于断点恢复)"""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(dict(state), f, ensure_ascii=False, indent=2)


def load_state(filepath: str) -> TestLoopState:
    """从文件恢复状态"""
    with open(filepath, "r", encoding="utf-8") as f:
        return TestLoopState(**json.load(f))
