# 辅助命令：阶段7 测试编码（Test Coder / Python）

说明：仅在主线 test-loop 无法覆盖特殊测试框架时使用。

执行：
1. 读取 `documents.detailed_design` 与 `[需单元测试]` 标记。
2. 输出/更新 `documents.unit_test_code_dir` 下测试代码。
3. 保持 Qt Test/GTest 规范，包含正常+异常路径。

完成后必须回到主线：`/project:test-loop`。
