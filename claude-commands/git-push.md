# 阶段12：上传 Git（DevOps / CLI）

执行：
1. 检查分支、变更范围、敏感文件过滤（.env/log/artifacts）。
2. 生成规范 commit message 并提交。
3. 推送远程分支。

约束：
- 禁止 `git push -f`。
- 如冲突，先 `git pull --rebase` 并报告冲突文件。
