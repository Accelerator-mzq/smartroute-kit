"""
state_machine.py - SmartRoute pipeline state machine definition.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PipelinePhase(str, Enum):
    INIT = "INIT"
    PLANNING = "PLANNING"
    CODING = "CODING"
    TESTING = "TESTING"
    FIXING = "FIXING"
    DEBUGGING = "DEBUGGING"
    DONE = "DONE"
    ABORTED = "ABORTED"


@dataclass
class PipelineStateMachine:
    phase: PipelinePhase = PipelinePhase.INIT

    def transition(self, next_phase: PipelinePhase):
        self.phase = next_phase

    def to_string(self) -> str:
        return self.phase.value

