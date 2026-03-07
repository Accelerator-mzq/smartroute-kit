# 阶段3：设计文档（Architect / CLI）

> 路径以 `smartroute.config.json.documents` 为准。

执行：
1. 读取需求文档目录 `documents.requirements_dir`。
2. 更新 `documents.overview_design` 与 `documents.detailed_design`。
3. 保证接口、模块边界、数据流可落地。
4. 在详细设计中标记 `[需单元测试]` 接口。

输出：
- 设计文档覆盖矩阵（需求->模块->接口）。
- 下一阶段建议：`/project:test-plan`。
