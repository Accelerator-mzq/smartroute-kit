#!/bin/bash
# ============================================================================
#  init-smartroute.sh — SmartRoute 一键初始化
#  用法: bash init-smartroute.sh [项目根目录]
# ============================================================================

set -euo pipefail
PROJECT_DIR="${1:-.}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║  SmartRoute v3.0 — 任务模型智能调度方案 初始化   ║${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""

cd "$PROJECT_DIR"
echo -e "${CYAN}项目目录: $(pwd)${NC}"

# 创建目录
echo -e "\n${BOLD}[1/5] 创建目录结构${NC}"
mkdir -p docs/{requirements,design,test,review} .claude/commands .pipeline/{context,logs} .smartroute/artifacts

# 复制统一配置文件
echo -e "${BOLD}[2/5] 安装配置文件${NC}"
if [ ! -f smartroute.config.json ]; then
    cp "$SCRIPT_DIR/smartroute.config.json" ./smartroute.config.json
    echo -e "  ${GREEN}✓ smartroute.config.json (统一配置入口)${NC}"
else
    echo "  ⚠ smartroute.config.json 已存在，跳过"
fi

# 复制 Python 脚本
echo -e "${BOLD}[3/5] 安装 Python 脚本${NC}"
for f in "$SCRIPT_DIR"/pipeline/*.py "$SCRIPT_DIR"/pipeline/*.template; do
    [ -f "$f" ] && cp "$f" ".pipeline/$(basename "$f")"
done
chmod +x .pipeline/test_loop.py .pipeline/setup.py 2>/dev/null || true
echo -e "  ${GREEN}✓ Python 脚本已安装到 .pipeline/${NC}"

# 复制自定义命令
echo -e "${BOLD}[4/5] 安装自定义命令${NC}"
for f in "$SCRIPT_DIR"/claude-commands/*.md; do
    [ -f "$f" ] && cp "$f" ".claude/commands/$(basename "$f")"
    echo -e "  ✓ /project:$(basename "$f" .md)"
done

# 复制文档
echo -e "${BOLD}[5/5] 安装文档${NC}"
mkdir -p docs
[ -f "$SCRIPT_DIR/docs/pitfalls.md" ] && cp "$SCRIPT_DIR/docs/pitfalls.md" docs/pitfalls.md

# 生成文档模板
[ ! -f docs/test/system-test-cases.md ] && cat > docs/test/system-test-cases.md << 'EOF'
# 系统测试例

## 更新记录
| 日期 | 更新人 | 更新内容 |

## 测试例列表
| 编号 | 测试项 | 前置条件 | 测试步骤 | 预期结果 | 优先级 | 可自动化 | 备注 |
|------|--------|---------|---------|---------|--------|---------|------|
EOF

# .gitignore
touch .gitignore
for entry in \
    ".env" \
    ".pipeline/logs/*.log" \
    ".pipeline/logs/trace.jsonl" \
    ".pipeline/last-state.json" \
    ".pipeline/test-loop-report.md" \
    ".smartroute/artifacts/"; do
    grep -q "$entry" .gitignore 2>/dev/null || echo "$entry" >> .gitignore
done

echo ""
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}  初始化完成！接下来：${NC}"
echo ""
echo -e "  1. 编辑 ${CYAN}smartroute.config.json${NC} — 填入 API Key 和项目命令"
echo -e "  2. 运行 ${CYAN}python .pipeline/setup.py${NC} — 同步生成 .env 和 CLAUDE.md"
echo -e "  3. 创建 ${CYAN}.smartroute/current_task.md${NC} — 写入 Task Objective/Strict Rules/Target Files"
echo -e "  4. 运行 ${CYAN}python .pipeline/test_loop.py --project-dir . --task .smartroute/current_task.md${NC}"
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
