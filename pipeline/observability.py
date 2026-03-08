"""
observability.py - Pipeline tracing and model interaction logging.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _estimate_tokens(text: str) -> int:
    # Lightweight fallback when provider usage is unavailable.
    if not text:
        return 0
    return max(1, len(text) // 4)


@dataclass
class ObservabilitySystem:
    project_dir: Path
    enabled: bool = True
    capture_prompts: bool = True
    capture_responses: bool = True

    def __post_init__(self):
        self.project_dir = Path(self.project_dir).resolve()
        self.log_dir = self.project_dir / ".pipeline" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.trace_file = self.log_dir / "trace.jsonl"
        self.error_file = self.log_dir / "error-history.log"
        self.role_logs = {
            "planner": self.log_dir / "planner.log",
            "coder": self.log_dir / "coder.log",
            "test_coder": self.log_dir / "test-coder.log",
            "runtime": self.log_dir / "runtime.log",
            "fixer": self.log_dir / "fixer.log",
            "debug_expert": self.log_dir / "debug-expert.log",
            # legacy aliases
            "debug": self.log_dir / "debug-expert.log",
            "worker": self.log_dir / "coder.log",
            "test": self.log_dir / "fixer.log",
        }
        for path in self.role_logs.values():
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text("", encoding="utf-8")
        if not self.trace_file.exists():
            self.trace_file.write_text("", encoding="utf-8")
        if not self.error_file.exists():
            self.error_file.write_text("", encoding="utf-8")
            
        # 统计每个角色的 token 消耗: {"coder": {"in": 0, "out": 0, "latency_ms": 0, "calls": 0}, ...}
        self.token_usage = {}

    def record_event(self, kind: str, payload: Dict):
        if not self.enabled:
            return
        row = {"ts": _ts(), "type": kind, **payload}
        with open(self.trace_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def record_runtime(self, level: str, message: str, phase: str = ""):
        if not self.enabled:
            return
        self.record_event(
            "runtime",
            {"level": level, "phase": phase, "message": message},
        )
        runtime_log = self.role_logs["runtime"]
        with open(runtime_log, "a", encoding="utf-8") as f:
            line = f"[{_ts()}] [{level}]"
            if phase:
                line += f" [{phase}]"
            f.write(f"{line} {message}\n")

    def record_error(self, component: str, message: str):
        if not self.enabled:
            return
        self.record_event("error", {"component": component, "message": message})
        with open(self.error_file, "a", encoding="utf-8") as f:
            f.write(f"[{_ts()}] [{component}] {message}\n")

    def record_model_call_event(self, event: Dict):
        """
        Event schema comes from model_caller.set_model_observer callback.
        """
        if not self.enabled:
            return

        role = event.get("role", "coder")
        role_log_file = self.role_logs.get(role, self.role_logs["runtime"])

        usage = event.get("usage") or {}
        in_tokens = usage.get("input_tokens")
        out_tokens = usage.get("output_tokens")
        if in_tokens is None:
            in_tokens = _estimate_tokens(event.get("system_prompt", "") + event.get("user_message", ""))
        if out_tokens is None:
            out_tokens = _estimate_tokens(event.get("response", ""))

        payload = {
            "role": role,
            "provider": event.get("provider_type", ""),
            "model": event.get("model", ""),
            "base_url": event.get("base_url", ""),
            "ok": not str(event.get("response", "")).startswith("[ERROR]"),
            "latency_ms": event.get("latency_ms", 0),
            "usage": {
                "input_tokens": in_tokens,
                "output_tokens": out_tokens,
                "raw": usage,
            },
        }

        if role not in self.token_usage:
            self.token_usage[role] = {"in": 0, "out": 0, "latency_ms": 0, "calls": 0}
        self.token_usage[role]["in"] += in_tokens
        self.token_usage[role]["out"] += out_tokens
        self.token_usage[role]["latency_ms"] += payload["latency_ms"]
        self.token_usage[role]["calls"] += 1

        if self.capture_prompts:
            payload["system_prompt"] = event.get("system_prompt", "")
            payload["user_message"] = event.get("user_message", "")
        if self.capture_responses:
            payload["response"] = event.get("response", "")

        self.record_event("model_call", payload)
        with open(role_log_file, "a", encoding="utf-8") as f:
            f.write(
                f"[{_ts()}] role={role} model={payload['model']} "
                f"in={in_tokens} out={out_tokens} latency_ms={payload['latency_ms']}\n"
            )
        if not payload["ok"]:
            self.record_error(role, str(event.get("response", ""))[:800])
