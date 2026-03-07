# 阶段2：需求分析（PM / CLI）

> 路径以 `smartroute.config.json.documents` 为准。

输入：`$ARGUMENTS`

执行：
1. 读取 `documents.requirements_dir`。
2. 梳理需求点（编号、描述、优先级、验收标准）。
3. 标记边界条件、风险与待确认问题。
4. 形成可设计、可测试的需求文档。

输出：
- 保存至 `documents.requirements_dir`。
- 文档末尾附“进入阶段3设计命令”：`/project:design`。
