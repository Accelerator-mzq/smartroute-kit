# 阶段4（别名）：任务交接（QA Lead / CLI）

说明：此命令与 `/project:test-plan` 同属阶段4，保留别名以兼容旧习惯。

执行目标：
1. 不直接大段编码。
2. 产出 `.smartroute/task.md`（Objective/Rules/Target Files）。
3. 触发 `/project:test-loop` 进入阶段5-9。

参考模板：
```markdown
[Task Objective]
实现xxx

[Strict Rules]
- 不改公共接口签名

[Target Files]
- src/xxx.cpp
- include/xxx.h
```
