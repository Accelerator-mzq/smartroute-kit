"""
runtime_executor.py - Runtime command executor wrapper.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from runners import run_compile, run_tests


@dataclass
class RuntimeExecutor:
    project_dir: str
    compile_command: str
    test_command: str
    unit_test_command: str
    test_timeout_seconds: int = 120

    def compile(self) -> Tuple[bool, str]:
        return run_compile(self.project_dir, self.compile_command)

    def run_system_tests(self) -> Tuple[str, str]:
        return run_tests(self.project_dir, self.test_command, timeout=self.test_timeout_seconds)

    def run_unit_tests(self) -> Tuple[str, str]:
        return run_tests(self.project_dir, self.unit_test_command, timeout=self.test_timeout_seconds)

