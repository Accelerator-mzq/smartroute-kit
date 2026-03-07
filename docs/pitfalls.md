# SmartRoute V3.0-new 排障

## 1. `roles` 仍是旧版 `worker/test/debug`

症状：启动时报角色缺失或路由异常。  
处理：改为 `planner/coder/test_coder/fixer/debug_expert`。

## 2. `current_task.md` 不完整

症状：Planner 无法产出有效 `Execution_Plan.json`。  
处理：确保存在 `[Task Objective] / [Strict Rules] / [Target Files]` 三段。

## 3. Planner 输出 JSON 非法

症状：日志提示“Planner 输出非法，使用默认计划”。  
处理：检查 task 描述是否过于模糊，收紧目标文件范围。

## 4. Runtime 命令漂移

症状：手工能编译，流水线失败。  
处理：统一在 `runtime.compile_command/test_command/unit_test_command` 维护。

## 5. Fixer 超限

症状：反复修复失败进入人工介入。  
处理：查看 `.pipeline/logs/debug-expert.log` 和 `trace.jsonl`，补充规则后重新下发 task。
