# 测试编码（MiniMax 模型）

> **路径规则**：所有文档路径以 `smartroute.config.json` 中的 `documents` 配置为准，不要使用硬编码路径。

## 第一步：读取配置
1. 读取 `smartroute.config.json` 中 `documents` 配置，确定以下路径：
   - `detailed_design`：详细设计文档路径
   - `unit_test_code_dir`：单元测试代码输出目录

## 第二步：生成测试代码
根据详细设计文档和 src/ 中的模块逻辑编写单元测试代码：

1. 框架: 使用 Qt Test 框架（`QTest`、`QCOMPARE`、`QVERIFY`）
2. 测试代码存放在 `documents.unit_test_code_dir` 配置指定的目录
3. 代码必须包含详细的中文注释
4. 每个函数上方必须有固定格式的函数头注释，包含：
   - 函数名称
   - 功能描述
   - 测试场景说明
5. 每个被测模块对应一个测试文件（如 `src/ModuleA.cpp` → `test_ModuleA.cpp`）
6. 测试类命名: `Test` + 模块名（如 `TestModuleA`）
7. 测试方法命名: `test_` + 功能描述（如 `test_parseValidInput`）
8. 重点覆盖详细设计中标注 `[需单元测试]` 的功能接口
9. 必须包含正常路径和异常路径的测试
10. 每次修改后确保测试代码编译通过
11. **[重要配置回写]**：如果在编写测试过程中确立了执行单元测试的具体终端命令，你**必须主动更新** `.env` 文件中的 `UNIT_TEST_COMMAND` 变量，并同步更新 `CLAUDE.md` 底部项目构建信息中的 `单元测试命令`，以便自动化流程调用。
