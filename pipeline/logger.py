"""
logger.py — 流水线日志记录器
SmartRoute: Claude Code + Python 编排脚本整合方案

记录每个节点的执行情况、模型切换、路由决策等，
输出到终端和日志文件，方便追踪和调试。
"""

import os
import sys
from datetime import datetime
from typing import Optional


class PipelineLogger:
    """流水线日志记录器"""

    # ANSI 颜色
    COLORS = {
        "red": "\033[0;31m",
        "green": "\033[0;32m",
        "yellow": "\033[1;33m",
        "blue": "\033[0;34m",
        "cyan": "\033[0;36m",
        "magenta": "\033[0;35m",
        "bold": "\033[1m",
        "reset": "\033[0m",
    }

    def __init__(self, log_dir: str = ".pipeline"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.log_file = os.path.join(
            log_dir, f"test-loop-{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        self.events = []

    def _color(self, text: str, color: str) -> str:
        if sys.stdout.isatty():
            return f"{self.COLORS.get(color, '')}{text}{self.COLORS['reset']}"
        return text

    def _write(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] [{level}] {message}"

        # 终端输出
        print(log_line)

        # 写入文件 (不含颜色)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")

        self.events.append({"time": timestamp, "level": level, "message": message})

    def phase(self, phase_name: str):
        """记录阶段切换"""
        separator = "━" * 60
        self._write("")
        self._write(separator)
        print(self._color(f"  📋 {phase_name}", "bold"))
        self._write(f"  📋 {phase_name}")
        self._write(separator)

    def model_switch(self, from_model: str, to_model: str, reason: str):
        """记录模型切换"""
        msg = f"🔀 模型切换: {from_model} → {to_model} | 原因: {reason}"
        print(self._color(msg, "yellow"))
        self._write(msg, "MODEL_SWITCH")

    def route_decision(self, from_node: str, to_node: str, reason: str):
        """记录路由决策"""
        msg = f"🔀 路由: {from_node} → {to_node} | {reason}"
        print(self._color(msg, "cyan"))
        self._write(msg, "ROUTE")

    def node_start(self, node_name: str, model: str):
        """记录节点开始执行"""
        msg = f"▶ [{model.upper()}] 开始执行: {node_name}"
        print(self._color(msg, "blue"))
        self._write(msg, "NODE_START")

    def node_end(self, node_name: str, success: bool, detail: str = ""):
        """记录节点执行结束"""
        status = "✅ 成功" if success else "❌ 失败"
        msg = f"◀ {status}: {node_name}"
        if detail:
            msg += f" | {detail}"
        color = "green" if success else "red"
        print(self._color(msg, color))
        self._write(msg, "NODE_END")

    def retry(self, count: int, max_count: int, context: str = ""):
        """记录重试"""
        msg = f"🔄 重试 {count}/{max_count}"
        if context:
            msg += f" | {context}"
        print(self._color(msg, "yellow"))
        self._write(msg, "RETRY")

    def escalation(self, reason: str):
        """记录升级事件"""
        msg = f"⚠️ 升级触发: {reason}"
        print(self._color(msg, "magenta"))
        self._write(msg, "ESCALATION")

    def info(self, message: str):
        self._write(message, "INFO")

    def error(self, message: str):
        print(self._color(f"❌ {message}", "red"))
        self._write(message, "ERROR")

    def success(self, message: str):
        print(self._color(f"✅ {message}", "green"))
        self._write(message, "SUCCESS")

    def generate_report(self, state: dict) -> str:
        """生成最终报告 Markdown"""
        report = f"""# 自动化测试循环报告

生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 执行概要

| 项目 | 值 |
|------|-----|
| 最终状态 | {state.get('final_status', '未知')} |
| 总循环次数 | {state.get('loop_count', 0)} |
| 当前模型 | {state.get('current_model', '未知')} |
| 漏测反思 | {'已完成' if state.get('reflection_done') else '未执行'} |

## 升级历史

"""
        for item in state.get("escalation_history", []):
            report += f"- {item}\n"

        if not state.get("escalation_history"):
            report += "无升级事件\n"

        report += f"""
## 执行日志

详细日志文件: `{self.log_file}`

## 事件统计

| 事件类型 | 次数 |
|---------|------|
| 模型切换 | {sum(1 for e in self.events if e['level'] == 'MODEL_SWITCH')} |
| 路由决策 | {sum(1 for e in self.events if e['level'] == 'ROUTE')} |
| 重试 | {sum(1 for e in self.events if e['level'] == 'RETRY')} |
| 升级 | {sum(1 for e in self.events if e['level'] == 'ESCALATION')} |
| 错误 | {sum(1 for e in self.events if e['level'] == 'ERROR')} |
"""
        return report
