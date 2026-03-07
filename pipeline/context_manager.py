"""
context_manager.py - Manage SmartRoute runtime context files.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class ContextManager:
    """
    Maintain runtime context under `.pipeline/context/`.

    Files:
      - project_context.md
      - task_context.md
      - runtime_logs.md
    """

    project_dir: Path
    context_limit: int = 12000

    def __post_init__(self):
        self.project_dir = Path(self.project_dir).resolve()
        self.context_dir = self.project_dir / ".pipeline" / "context"
        self.context_dir.mkdir(parents=True, exist_ok=True)
        self.project_context_path = self.context_dir / "project_context.md"
        self.task_context_path = self.context_dir / "task_context.md"
        self.runtime_logs_path = self.context_dir / "runtime_logs.md"
        self._ensure_files()

    def _ensure_files(self):
        if not self.project_context_path.exists():
            self.project_context_path.write_text(
                "# Project Context\n\n初始化时间: " + _now() + "\n",
                encoding="utf-8",
            )
        if not self.task_context_path.exists():
            self.task_context_path.write_text(
                "# Task Context\n\n初始化时间: " + _now() + "\n",
                encoding="utf-8",
            )
        if not self.runtime_logs_path.exists():
            self.runtime_logs_path.write_text(
                "# Runtime Logs\n\n",
                encoding="utf-8",
            )

    def update_project_context(self, summary: str, append: bool = False):
        """Write or append project context summary."""
        if append:
            previous = self.project_context_path.read_text(encoding="utf-8")
            content = previous.rstrip() + "\n\n" + summary.strip() + "\n"
        else:
            content = f"# Project Context\n\n更新时间: {_now()}\n\n{summary.strip()}\n"
        self.project_context_path.write_text(content, encoding="utf-8")

    def update_task_context(
        self,
        objective: str,
        rules: str,
        target_files: Iterable[str],
        task_file: str = "",
    ):
        target_files_list = [f for f in target_files if f]
        files_block = "\n".join(f"- {f}" for f in target_files_list) or "- (未指定)"
        source_line = f"\n来源: `{task_file}`\n" if task_file else "\n"
        content = (
            "# Task Context\n\n"
            f"更新时间: {_now()}{source_line}\n"
            "## Objective\n"
            f"{objective.strip() or '(空)'}\n\n"
            "## Strict Rules\n"
            f"{rules.strip() or '(空)'}\n\n"
            "## Target Files\n"
            f"{files_block}\n"
        )
        self.task_context_path.write_text(content, encoding="utf-8")

    def get_project_context(self) -> str:
        return self._read_with_limit(self.project_context_path)

    def get_task_context(self) -> str:
        return self._read_with_limit(self.task_context_path)

    def append_runtime_log(self, message: str, level: str = "INFO", phase: str = ""):
        phase_text = f" [{phase}]" if phase else ""
        line = f"- {_now()} [{level.upper()}]{phase_text} {message.strip()}\n"
        with open(self.runtime_logs_path, "a", encoding="utf-8") as f:
            f.write(line)

    def _read_with_limit(self, path: Path) -> str:
        text = path.read_text(encoding="utf-8")
        if len(text) <= self.context_limit:
            return text
        keep = max(2000, self.context_limit)
        return text[-keep:]

    def summarize_target_files(self, project_dir: str, target_files: List[str], per_file_limit: int = 1800) -> str:
        """
        Build concise file snippets used by coder/test nodes.
        """
        abs_project = Path(project_dir).resolve()
        chunks: List[str] = []
        for rel in target_files[:20]:
            abs_path = Path(rel)
            if not abs_path.is_absolute():
                abs_path = abs_project / rel
            abs_path = abs_path.resolve()
            if not str(abs_path).startswith(str(abs_project)):
                continue
            if not abs_path.exists() or not abs_path.is_file():
                chunks.append(f"--- File: {rel} ---\n(文件不存在)\n")
                continue
            try:
                content = abs_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = abs_path.read_text(encoding="utf-8", errors="replace")
            if len(content) > per_file_limit:
                content = content[:per_file_limit] + "\n... [截断]"
            chunks.append(f"--- File: {rel} ---\n{content}\n")
        return "\n".join(chunks)


def discover_project_context(project_dir: str) -> str:
    """
    Collect lightweight context from common docs.
    """
    root = Path(project_dir).resolve()
    candidates = [
        "README.md",
        "docs/design/overview-design.md",
        "docs/design/detailed-design.md",
        "docs/requirements/requirements.md",
    ]
    blocks: List[str] = []
    for rel in candidates:
        p = root / rel
        if not p.exists():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = p.read_text(encoding="utf-8", errors="replace")
        sample = text[:2000]
        blocks.append(f"## {rel}\n\n{sample}\n")
    if not blocks:
        return "未发现可用项目文档。"
    return "\n".join(blocks)

