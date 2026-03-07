"""
artifact_manager.py - Manage execution artifacts snapshots.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


def _safe_rel(project_root: Path, target: Path) -> Path:
    try:
        rel = target.resolve().relative_to(project_root.resolve())
        return rel
    except ValueError:
        # Fallback to filename only when path is outside project root.
        return Path(target.name)


@dataclass
class ArtifactManager:
    project_dir: Path
    policy: str = "per_execution"

    def __post_init__(self):
        self.project_dir = Path(self.project_dir).resolve()
        self.root = self.project_dir / ".smartroute" / "artifacts"
        self.root.mkdir(parents=True, exist_ok=True)
        self.execution_id = ""
        self.execution_dir: Optional[Path] = None

    def start_execution(self) -> str:
        """
        Allocate `execution_XXX` directory.
        """
        existing = sorted(p.name for p in self.root.glob("execution_*") if p.is_dir())
        next_no = 1
        if existing:
            try:
                next_no = int(existing[-1].split("_")[-1]) + 1
            except ValueError:
                next_no = len(existing) + 1
        self.execution_id = f"execution_{next_no:03d}"
        self.execution_dir = self.root / self.execution_id
        for sub in ("code", "tests", "logs", "plans", "state"):
            (self.execution_dir / sub).mkdir(parents=True, exist_ok=True)
        return self.execution_id

    def ensure_started(self):
        if self.execution_dir is None:
            self.start_execution()

    def save_plan(self, plan: dict, filename: str = "Execution_Plan.json") -> Path:
        self.ensure_started()
        out = self.execution_dir / "plans" / filename
        with open(out, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)
        return out

    def save_text(self, text: str, category: str, filename: str) -> Path:
        self.ensure_started()
        out = self.execution_dir / category / filename
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        return out

    def save_state(self, state: dict, filename: str = "last-state.json") -> Path:
        self.ensure_started()
        out = self.execution_dir / "state" / filename
        with open(out, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        return out

    def copy_into(self, source: Path, category: str, output_name: Optional[str] = None) -> Optional[Path]:
        self.ensure_started()
        src = Path(source)
        if not src.exists():
            return None
        if output_name:
            dest = self.execution_dir / category / output_name
        else:
            rel = _safe_rel(self.project_dir, src)
            dest = self.execution_dir / category / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return dest

    def snapshot_modified_files(self, files: Iterable[str]) -> int:
        """
        Copy modified files into `code/` or `tests/`.
        """
        self.ensure_started()
        copied = 0
        for file_path in files:
            p = Path(file_path)
            if not p.is_absolute():
                p = self.project_dir / p
            p = p.resolve()
            if not p.exists() or not p.is_file():
                continue
            rel = _safe_rel(self.project_dir, p)
            category = "tests" if rel.parts and rel.parts[0] == "tests" else "code"
            dest = self.execution_dir / category / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest)
            copied += 1
        return copied

