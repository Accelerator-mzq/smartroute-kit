"""
nodes.py — 执行节点实现
SmartRoute: 基于 Claude Code 的任务模型智能调度方案

每个节点: 接收 State → 调用模型或本地命令 → 返回更新后的 State
模型调用通过 call_model("planner/coder/test_coder/fixer/debug_expert")
自动从 smartroute.config.json 读取配置
"""

import json
import os
import re

from state import TestLoopState
from model_caller import call_model
from runners import run_compile, run_tests, read_file_safe, write_file_safe
from task_graph import TaskGraphEngine


def _set_current_role(state: TestLoopState, role: str):
    state["current_role"] = role
    # backward-compatible field
    state["current_model"] = role


def _normalize_allowed_paths(project_dir: str, allowed_files) -> set:
    if not allowed_files:
        return set()
    abs_project = os.path.abspath(project_dir)
    normalized = set()
    for f in allowed_files:
        if os.path.isabs(f):
            p = os.path.abspath(f)
        else:
            p = os.path.abspath(os.path.join(project_dir, f))
        if p.startswith(abs_project):
            normalized.add(p)
    return normalized


def _parse_and_write_code_files(response: str, project_dir: str, allowed_files=None) -> int:
    """
    解析模型输出中的 File + 代码块并写入文件。
    仅允许写入 project_dir 内文件；如果设置 allowed_files，则仅允许写入清单内文件。
    """
    pattern = r"File:\s*(.+?)\s*\n\s*```(?:[A-Za-z0-9_+.-]+)?\s*\n(.*?)```"
    matches = re.findall(pattern, response, re.DOTALL)
    abs_project = os.path.abspath(project_dir)
    allowed_abs = _normalize_allowed_paths(project_dir, allowed_files)

    files_written = 0
    for filepath_raw, code_content in matches:
        filepath_raw = filepath_raw.strip()
        if os.path.isabs(filepath_raw):
            abs_path = os.path.abspath(filepath_raw)
        else:
            abs_path = os.path.abspath(os.path.join(project_dir, filepath_raw))

        if not abs_path.startswith(abs_project):
            print(f"  ⚠️ 跳过项目外文件: {filepath_raw}")
            continue

        if allowed_abs and not any(abs_path == p or abs_path.startswith(p + os.sep) for p in allowed_abs):
            print(f"  ⚠️ 跳过非目标文件: {filepath_raw}")
            continue

        write_file_safe(abs_path, code_content.strip() + "\n")
        print(f"  📝 写入: {os.path.relpath(abs_path, abs_project)}")
        files_written += 1

    return files_written


def _build_task_file_context(state: TestLoopState, max_chars: int = 8000) -> str:
    target_files = state.get("task_target_files", [])
    if not target_files:
        return ""

    chunks = []
    for rel_path in target_files[:20]:
        abs_path = rel_path
        if not os.path.isabs(abs_path):
            abs_path = os.path.join(state["project_dir"], rel_path)
        content = read_file_safe(abs_path, max_chars=2500)
        chunks.append(f"--- File: {rel_path} ---\n{content}")
        if sum(len(c) for c in chunks) > max_chars:
            break
    return "\n\n".join(chunks)


def _extract_json_from_response(text: str) -> str:
    if not text:
        return ""
    cleaned = text.strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned
    code_block = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
    if code_block:
        return code_block.group(1).strip()
    generic_block = re.search(r"```[\w-]*\s*(\{[\s\S]*?\})\s*```", text)
    if generic_block:
        return generic_block.group(1).strip()
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and last > first:
        return text[first:last + 1]
    return ""


def compile_node(state: TestLoopState) -> TestLoopState:
    """执行本地编译"""
    print(f"⚙️  [编译] 执行: {state['compile_command']}")
    success, log = run_compile(state["project_dir"], state["compile_command"])
    state["compile_success"] = success
    state["compile_error_log"] = "" if success else log
    if success:
        print("  ✅ 编译成功")
        state["retry_count"] = 0
    else:
        state["retry_count"] += 1
        print(f"  ❌ 编译失败 (第 {state['retry_count']}/{state['max_retries']} 次)")
    return state


def test_node(state: TestLoopState, test_type: str = "system") -> TestLoopState:
    """执行测试"""
    cmd = state["test_command"] if test_type == "system" else state["unit_test_command"]
    print(f"🚀 [测试] 执行 {test_type} 测试: {cmd}")
    timeout = int(state.get("test_timeout_seconds", 120))
    result, log = run_tests(state["project_dir"], cmd, timeout=timeout)
    state["test_results"] = result
    state["test_error_log"] = log if result != "PASS" else ""
    if result == "PASS":
        print(f"  ✅ {test_type} 测试全部通过")
        state["retry_count"] = 0
    else:
        state["retry_count"] += 1
        print(f"  ❌ {test_type} 测试失败 (第 {state['retry_count']}/{state['max_retries']} 次)")
    return state


def planner_generate_execution_plan_node(state: TestLoopState) -> TestLoopState:
    """Planner: 读取 task.md，输出 Execution_Plan.json"""
    print("🧭 [Planner] 生成原子化执行计划...")
    _set_current_role(state, "planner")
    state["planner_failed"] = False

    objective = state.get("task_objective", "").strip() or "未提供任务目标"
    rules = state.get("task_rules", "").strip() or "遵循现有项目编码规范"
    target_files = state.get("task_target_files", [])
    files_text = "\n".join(f"- {f}" for f in target_files) if target_files else "- （未指定）"

    system_prompt = """你是 SmartRoute Planner（规划师）。
请基于任务目标拆解出可执行原子步骤，输出严格 JSON，不要输出解释文字。
JSON 格式:
{
  "nodes":[
    {"id":"1","task":"...","role":"coder"},
    {"id":"2","task":"...","role":"test_coder"},
    {"id":"3","task":"...","role":"runtime"},
    {"id":"4","task":"...","role":"fixer"},
    {"id":"5","task":"...","role":"debug_expert"}
  ],
  "edges":[
    {"from":"1","to":"2"},
    {"from":"2","to":"3"},
    {"from":"3","to":"4"},
    {"from":"4","to":"5"}
  ]
}

约束:
1. role 仅允许: coder/test_coder/runtime/fixer/debug_expert
2. 节点是原子步骤，不要写成宏观描述
3. 必须包含 runtime 节点和 fixer 节点"""

    user_message = f"""[Task Objective]
{objective}

[Strict Rules]
{rules}

[Target Files]
{files_text}

请输出 Execution Plan JSON。"""

    response = call_model("planner", system_prompt, user_message, max_tokens=4096)
    if response.startswith("[ERROR]"):
        print(f"  ⚠️ Planner 调用失败: {response[:160]}")
        state["planner_failed"] = True
        state["planner_error"] = response[:500]
    else:
        json_text = _extract_json_from_response(response)
        try:
            plan = json.loads(json_text)
            plan_path = state.get("execution_plan_path") or os.path.join(
                state["project_dir"], ".smartroute", "Execution_Plan.json"
            )
            os.makedirs(os.path.dirname(plan_path), exist_ok=True)
            with open(plan_path, "w", encoding="utf-8") as f:
                json.dump(
                    {"nodes": plan.get("nodes", []), "edges": plan.get("edges", [])},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            checked = TaskGraphEngine.from_json_file(plan_path)
            state["execution_plan"] = checked.to_dict()
        except Exception as e:
            print(f"  ⚠️ Planner 输出非法，已中止本轮流水线: {e}")
            state["planner_failed"] = True
            state["planner_error"] = f"invalid_execution_plan_json: {e}"
            state["execution_plan"] = {}

    if (not state.get("planner_failed")) and state.get("execution_plan_path") and state.get("execution_plan"):
        with open(state["execution_plan_path"], "w", encoding="utf-8") as f:
            json.dump(state["execution_plan"], f, ensure_ascii=False, indent=2)
        print(f"  📝 已输出计划: {state['execution_plan_path']}")

    return state


def coder_generate_from_plan_node(state: TestLoopState) -> TestLoopState:
    """Coder: 严格按 Execution_Plan 生成/更新业务代码"""
    print("🧩 [Coder] 根据 Execution Plan 生成代码...")
    _set_current_role(state, "coder")

    objective = state.get("task_objective", "").strip() or "未提供任务目标"
    rules = state.get("task_rules", "").strip() or "遵循现有项目编码规范"
    target_files = state.get("task_target_files", [])
    files_text = "\n".join(f"- {f}" for f in target_files) if target_files else "- （未指定，按任务目标自定）"
    existing_context = _build_task_file_context(state)
    execution_plan = state.get("execution_plan", {})

    system_prompt = """你是 SmartRoute Coder（主程序员）。
请严格按照 Execution_Plan 的原子步骤输出代码修改，格式必须为：
File: relative/path/to/file.ext
```lang
完整文件内容
```

要求：
1. 只输出需要创建或修改的文件
2. 默认只改目标文件清单中的文件
3. 不要输出解释文字"""

    user_message = f"""[Task Objective]
{objective}

[Strict Rules]
{rules}

[Execution Plan]
{json.dumps(execution_plan, ensure_ascii=False, indent=2) if execution_plan else "（无）"}

[Target Files]
{files_text}

[Existing File Context]
{existing_context if existing_context else "（目标文件当前不存在或未读取）"}

请输出可直接落盘的文件内容。"""

    response = call_model("coder", system_prompt, user_message, max_tokens=8192)
    state["current_code"] = response

    if response.startswith("[ERROR]"):
        print(f"  ❌ Coder 生成失败: {response[:200]}")
        return state

    files_written = _parse_and_write_code_files(
        response,
        state["project_dir"],
        allowed_files=target_files or None,
    )
    if files_written > 0:
        state["modified_files"] = list(set(state["modified_files"] + target_files))
        print(f"  ✨ Coder 已生成/更新 {files_written} 个文件")
    else:
        print("  ⚠️ 未解析到有效代码块，请检查任务描述或模型输出格式")
    return state


def test_coder_generate_from_plan_node(state: TestLoopState) -> TestLoopState:
    """Test Coder: 按执行计划生成系统测试/单元测试代码骨架"""
    print("🧪 [Test Coder] 根据 Execution Plan 生成测试代码...")
    _set_current_role(state, "test_coder")

    execution_plan = state.get("execution_plan", {})
    target_files = state.get("task_target_files", [])
    code_context = _build_task_file_context(state, max_chars=6000)

    system_prompt = """你是 SmartRoute Test Coder。
请根据 Execution Plan 和目标业务代码，生成测试代码，输出格式必须为:
File: tests/.../xxx.cpp
```cpp
完整文件内容
```

约束:
1. 输出路径只能在 tests/system 或 tests/src 下
2. 优先为本轮目标业务文件生成对应测试
3. 测试必须包含正常路径与异常路径
4. 不要输出解释文本"""

    user_message = f"""[Execution Plan]
{json.dumps(execution_plan, ensure_ascii=False, indent=2) if execution_plan else "（无）"}

[Target Files]
{target_files if target_files else "（无）"}

[Current Code Context]
{code_context if code_context else "（无）"}

请输出测试代码。"""

    response = call_model("test_coder", system_prompt, user_message, max_tokens=8192)
    if response.startswith("[ERROR]"):
        print(f"  ⚠️ Test Coder 生成失败: {response[:200]}")
        state["system_test_code_generated"] = False
        state["unit_test_code_generated"] = False
        return state

    files_written = _parse_and_write_test_files(response, state["project_dir"], state["system_test_code_dir"])
    generated = files_written > 0
    state["system_test_code_generated"] = generated
    state["unit_test_code_generated"] = generated
    if generated:
        print(f"  ✨ Test Coder 已生成/更新 {files_written} 个测试文件")
    else:
        print("  ⚠️ 未解析到有效测试代码文件")
    return state


def fixer_node(state: TestLoopState) -> TestLoopState:
    """Fixer 角色修复代码"""
    print(f"🔧 [Fixer] 第 {state['retry_count']}/{state['max_retries']} 次修复尝试...")
    _set_current_role(state, "fixer")

    error_context = (
        f"【编译错误日志】:\n{state['compile_error_log']}"
        if state.get("compile_error_log")
        else f"【测试错误日志】:\n{state.get('test_error_log', '')}"
    )
    design_doc = read_file_safe(state["design_doc_path"], max_chars=5000)
    task_rules = state.get("task_rules", "")
    target_files = state.get("task_target_files", [])
    target_file_context = _build_task_file_context(state, max_chars=6000)

    system_prompt = """你是一个高效的开发工程师，负责根据错误日志修复代码。
修复规则：
1. 每次修改都必须保证编译能通过
2. 只修改必要的部分，不要大范围重构
3. 输出修改后的完整文件内容，用 Markdown 代码块包裹
4. 在代码块前注明文件路径 (如: File: src/xxx.cpp)"""

    user_message = f"""{error_context}

【设计文档参考】:
{design_doc[:3000]}

【任务硬约束】:
{task_rules if task_rules else "（无）"}

【目标文件】:
{target_files if target_files else "（未限制）"}

【目标文件当前内容】:
{target_file_context if target_file_context else "（无）"}

请分析问题并给出修复代码:"""

    response = call_model("fixer", system_prompt, user_message)
    state["current_code"] = response
    if not response.startswith("[ERROR]"):
        files_written = _parse_and_write_code_files(
            response,
            state["project_dir"],
            allowed_files=target_files or None,
        )
        if files_written == 0:
            print("  ⚠️ 修复响应未解析到可落盘代码")
    return state


def debug_expert_diagnose_node(state: TestLoopState) -> TestLoopState:
    """Debug Expert 角色深度诊断"""
    print("🧠 [Debug Expert] fixer 角色修复超限，debug_expert 介入深度诊断...")
    _set_current_role(state, "debug_expert")
    state["escalation_history"].append(
        f"[{state['current_phase']}] retry={state['retry_count']} → 升级到 debug_expert"
    )

    design_doc = read_file_safe(state["design_doc_path"], max_chars=8000)
    error_log = state.get("compile_error_log") or state.get("test_error_log", "")

    system_prompt = """你是一位顶级系统架构师。初级工程师多次修复失败，请你：
1. 深度诊断: 结合设计文档和错误日志，指出问题深层根因
2. 修改方案: 给出具体、明确的修改指导

注意: 不需要输出完整代码。只输出诊断报告和修改方案，
后续由初级工程师执行。

输出格式:
## 诊断结论
## 修改方案
## 注意事项"""

    user_message = f"""【详细设计】:\n{design_doc}
【当前代码】:\n{state.get('current_code', '')[:5000]}
【持续失败的错误日志】:\n{error_log}
【已尝试次数】: {state['retry_count']}

请给出诊断和修改方案:"""

    task_appendix = ""
    if state.get("task_objective"):
        task_appendix = (
            f"\n【任务目标】:\n{state.get('task_objective', '')}\n"
            f"【任务约束】:\n{state.get('task_rules', '')}\n"
            f"【目标文件】:\n{state.get('task_target_files', [])}\n"
        )
    response = call_model("debug_expert", system_prompt, user_message + task_appendix)
    state["debug_diagnosis_plan"] = response
    state["debug_diagnosis_used"] = True
    state["retry_count"] = 0
    print(f"  💡 诊断完成 (方案长度: {len(response)} 字符)")
    return state


def coder_apply_debug_fix_node(state: TestLoopState) -> TestLoopState:
    """Coder 角色执行 debug_expert 方案"""
    print("🛠️  [Coder] 根据 debug_expert 方案执行修改...")
    _set_current_role(state, "coder")

    system_prompt = """你是一个开发工程师。首席架构师已给出诊断与修改方案。
严格按照方案执行修改，输出修改后的完整代码，确保可编译。"""

    user_message = f"""【诊断方案】:\n{state['debug_diagnosis_plan']}
【当前代码】:\n{state.get('current_code', '')[:5000]}

请严格落实方案:"""

    response = call_model("coder", system_prompt, user_message)
    state["current_code"] = response
    state["debug_diagnosis_plan"] = ""
    if not response.startswith("[ERROR]"):
        files_written = _parse_and_write_code_files(
            response,
            state["project_dir"],
            allowed_files=state.get("task_target_files") or None,
        )
        if files_written == 0:
            print("  ⚠️ 执行方案后未解析到可落盘代码")
    return state


def debug_expert_reflection_node(state: TestLoopState) -> TestLoopState:
    """debug_expert 角色漏测反思 — 同时更新系统测试用例和单元测试用例"""
    print("🧠 [Debug Expert] 执行漏测反思机制...")
    _set_current_role(state, "debug_expert")

    system_test_doc = read_file_safe(state["system_test_cases_path"])
    unit_test_doc = read_file_safe(state["unit_test_cases_path"])
    bug_report = state.get("user_bug_report", "未提供")
    fixed_code = state.get("current_code", "")[:5000]

    system_prompt = """你是首席 QA 架构师。团队刚修复了一个 Bug，你需要从系统测试和单元测试两个维度审查并更新测试文档。

任务逻辑:
1. 分析该 Bug 场景是否已存在于系统测试用例或单元测试用例中
2. 不存在 → 补充新测试用例（编号、测试项、前置条件、步骤、预期结果、优先级）
3. 已存在 → 分析漏测原因，增强该测试项

必须分别输出两份文档，使用以下分隔格式：

===SYSTEM_TEST_CASES===
（更新后的完整系统测试用例文档，Markdown 格式）

===UNIT_TEST_CASES===
（更新后的完整单元测试用例文档，Markdown 格式）"""

    user_message = f"""【Bug 描述】:\n{bug_report}
【修复后代码】:\n{fixed_code}
【当前系统测试用例文档】:\n{system_test_doc}
【当前单元测试用例文档】:\n{unit_test_doc if not unit_test_doc.startswith('[文件不存在') else '（尚无单元测试用例文档，请从零创建）'}

请分别输出更新后的系统测试用例和单元测试用例文档:"""

    response = call_model("debug_expert", system_prompt, user_message, max_tokens=8192)

    if not response.startswith("[ERROR]"):
        # 解析两份文档
        sys_doc, unit_doc = _parse_reflection_output(response)
        if sys_doc:
            write_file_safe(state["system_test_cases_path"], sys_doc)
            print("  ✨ 系统测试用例文档已更新")
        if unit_doc:
            write_file_safe(state["unit_test_cases_path"], unit_doc)
            print("  ✨ 单元测试用例文档已更新")
        state["reflection_done"] = True
        state["reflection_result"] = "系统测试和单元测试文档均已更新"
    else:
        state["reflection_result"] = f"反思失败: {response[:200]}"
        print(f"  ❌ {response[:200]}")
    return state


def _parse_reflection_output(response: str):
    """
    从反思输出中解析系统测试和单元测试两份文档。
    使用 ===SYSTEM_TEST_CASES=== 和 ===UNIT_TEST_CASES=== 分隔。
    """
    sys_doc = ""
    unit_doc = ""

    if "===SYSTEM_TEST_CASES===" in response and "===UNIT_TEST_CASES===" in response:
        parts = response.split("===UNIT_TEST_CASES===")
        sys_part = parts[0].split("===SYSTEM_TEST_CASES===")[-1].strip()
        unit_part = parts[-1].strip()
        sys_doc = sys_part
        unit_doc = unit_part
    else:
        # 降级处理：如果模型没有按格式输出，整体当作系统测试文档
        sys_doc = response
        print("  ⚠️ 模型未按分隔格式输出，仅更新系统测试文档")

    return sys_doc, unit_doc


def debug_expert_update_automation_plan_node(state: TestLoopState) -> TestLoopState:
    """debug_expert 角色根据更新后的系统+单元测试用例，生成/更新自动化测试方案"""
    print("🧠 [Debug Expert] 更新自动化测试方案...")
    _set_current_role(state, "debug_expert")

    system_test_cases = read_file_safe(state["system_test_cases_path"])
    unit_test_cases = read_file_safe(state["unit_test_cases_path"])
    current_plan = read_file_safe(state["automation_plan_path"])
    bug_report = state.get("user_bug_report", "未提供")

    system_prompt = """你是首席测试架构师。团队刚修复了一个 Bug 并更新了测试用例文档。
你需要确保自动化测试方案与最新的系统测试用例和单元测试用例保持同步。

任务逻辑:
1. 对比系统测试用例和单元测试用例文档与当前自动化方案，找出新增或修改的测试项
2. 为每个新增/修改的测试项生成对应的自动化测试方案，包括：
   - 测试类型标注（系统测试 / 单元测试）
   - 测试脚本模板（函数名、测试步骤伪代码）
   - 断言策略（预期结果的验证方式）
   - 前置条件准备（测试数据、环境配置）
   - 是否可自动化的判断（如不可自动化，标注原因并标记为手工测试）
3. 保留原有方案中未变化的部分
4. 方案文档中必须明确区分「系统测试自动化方案」和「单元测试自动化方案」两个章节

直接输出更新后的完整自动化测试方案文档（Markdown 格式）。"""

    user_message = f"""【本次修复的 Bug 描述】:
{bug_report}

【最新系统测试用例文档】:
{system_test_cases}

【最新单元测试用例文档】:
{unit_test_cases if not unit_test_cases.startswith('[文件不存在') else '（尚无单元测试用例文档）'}

【当前自动化测试方案文档】:
{current_plan if current_plan else "（尚无自动化测试方案，请从零创建）"}

请输出更新后的完整自动化测试方案文档:"""

    response = call_model("debug_expert", system_prompt, user_message, max_tokens=8192)

    if not response.startswith("[ERROR]"):
        write_file_safe(state["automation_plan_path"], response)
        state["automation_plan_updated"] = True
        print("  ✨ 自动化测试方案已更新（含系统测试+单元测试）")
    else:
        state["automation_plan_updated"] = False
        print(f"  ❌ 自动化方案更新失败: {response[:200]}")
    return state


def test_coder_generate_test_code_node(state: TestLoopState, test_type: str = "unit") -> TestLoopState:
    """
    test_coder 角色根据自动化测试方案生成/更新测试代码。
    test_type: "system" 生成系统测试代码, "unit" 生成单元测试代码(Qt Test)
    """
    type_label = "系统测试" if test_type == "system" else "单元测试"
    print(f"🔧 [Test Coder] 根据自动化方案生成{type_label}代码...")
    _set_current_role(state, "test_coder")

    import glob

    # 根据类型选择目录
    if test_type == "system":
        code_dir = state["system_test_code_dir"]
    else:
        code_dir = state["unit_test_code_dir"]
    os.makedirs(code_dir, exist_ok=True)

    # 读取自动化测试方案
    automation_plan = read_file_safe(state["automation_plan_path"])
    design_doc = read_file_safe(state["design_doc_path"], max_chars=5000)

    # 扫描现有测试代码
    existing_tests = ""
    test_files = glob.glob(os.path.join(code_dir, "*.cpp")) + \
                 glob.glob(os.path.join(code_dir, "*.h"))
    for tf in test_files[:10]:
        content = read_file_safe(tf, max_chars=2000)
        existing_tests += f"\n--- {os.path.basename(tf)} ---\n{content}\n"

    if not existing_tests:
        existing_tests = f"（尚无{type_label}代码，请从零创建）"

    bug_report = state.get("user_bug_report", "未提供")

    # 根据类型选择 prompt
    if test_type == "system":
        code_dir_rel = "tests/system"
        system_prompt = f"""你是一个高效的测试开发工程师，负责根据自动化测试方案编写系统测试代码。

编码规范：
1. 代码必须包含详细的中文注释
2. 每个函数上方必须有固定格式的函数头注释（函数名称、功能描述、测试场景说明）
3. 系统测试侧重端到端的功能验证和集成场景
4. 测试文件存放在 {code_dir_rel}/ 目录
5. 必须包含正常路径和异常路径的测试

输出格式：
对于每个需要创建或修改的测试文件，使用以下格式：
File: {code_dir_rel}/test_xxx.cpp
```cpp
// 完整文件内容
```

只输出自动化方案中标注为「系统测试」的部分对应的代码。
只输出新增或有变更的文件。"""
    else:
        code_dir_rel = "tests/src"
        system_prompt = f"""你是一个高效的测试开发工程师，负责根据自动化测试方案编写 Qt Test 单元测试代码。

编码规范：
1. 框架: Qt Test（使用 QTest、QCOMPARE、QVERIFY 等宏）
2. 代码必须包含详细的中文注释
3. 每个函数上方必须有固定格式的函数头注释（函数名称、功能描述、测试场景说明）
4. 每个被测模块对应一个测试文件（如 src/ModuleA.cpp → {code_dir_rel}/test_ModuleA.cpp）
5. 测试类命名: Test + 模块名（如 TestModuleA）
6. 测试方法命名: test_ + 功能描述（如 test_parseValidInput）
7. 必须包含正常路径和异常路径的测试

输出格式：
对于每个需要创建或修改的测试文件，使用以下格式：
File: {code_dir_rel}/test_XxxXxx.cpp
```cpp
// 完整文件内容
```

只输出自动化方案中标注为「单元测试」的部分对应的代码。
只输出新增或有变更的文件。"""

    user_message = f"""【本次修复的 Bug 描述】:
{bug_report}

【自动化测试方案】:
{automation_plan}

【详细设计参考】:
{design_doc[:3000]}

【现有{type_label}代码】:
{existing_tests}

请根据自动化测试方案，生成或更新对应的{type_label}代码:"""

    response = call_model("test_coder", system_prompt, user_message, max_tokens=8192)

    state_key = f"{test_type}_test_code_generated"
    if not response.startswith("[ERROR]"):
        files_written = _parse_and_write_test_files(response, state["project_dir"], code_dir)
        if files_written > 0:
            state[state_key] = True
            print(f"  ✨ 已生成/更新 {files_written} 个{type_label}文件")
        else:
            state[state_key] = False
            print(f"  ⚠️ 模型输出中未解析到有效的{type_label}文件")
    else:
        state[state_key] = False
        print(f"  ❌ {type_label}代码生成失败: {response[:200]}")
    return state


def _parse_and_write_test_files(response: str, project_dir: str, test_code_dir: str) -> int:
    """
    从模型响应中解析 File: xxx 和代码块，写入对应文件。
    返回成功写入的文件数量。
    """
    import re

    pattern = r'File:\s*(.+?)\s*\n\s*```(?:cpp|c\+\+|h)?\s*\n(.*?)```'
    matches = re.findall(pattern, response, re.DOTALL)

    files_written = 0
    for filepath_raw, code_content in matches:
        filepath_raw = filepath_raw.strip()
        if os.path.isabs(filepath_raw):
            filepath = filepath_raw
        else:
            filepath = os.path.join(project_dir, filepath_raw)

        # 安全检查：只允许写入 tests/ 目录
        abs_path = os.path.abspath(filepath)
        abs_tests_root = os.path.abspath(os.path.join(project_dir, "tests"))
        if not abs_path.startswith(abs_tests_root):
            print(f"  ⚠️ 跳过非测试目录文件: {filepath_raw}")
            continue

        write_file_safe(abs_path, code_content.strip() + "\n")
        print(f"  📝 写入: {filepath_raw}")
        files_written += 1

    return files_written


# --- Backward compatibility aliases ---
test_fix_node = fixer_node
debug_diagnose_node = debug_expert_diagnose_node
worker_apply_fix_node = coder_apply_debug_fix_node
debug_reflection_node = debug_expert_reflection_node
debug_update_automation_plan_node = debug_expert_update_automation_plan_node
test_generate_test_code_node = test_coder_generate_test_code_node
