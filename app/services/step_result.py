"""
Shared step outcome types for service-layer orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class StepStatus(str, Enum):
    SUCCESS = "success"
    WARNING = "warning"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class StepResult:
    status: StepStatus
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.status is not StepStatus.FAILED

    @property
    def is_warning(self) -> bool:
        return self.status is StepStatus.WARNING

    @property
    def is_skipped(self) -> bool:
        return self.status is StepStatus.SKIPPED

    @classmethod
    def success(cls, message: str = "") -> "StepResult":
        return cls(StepStatus.SUCCESS, message)

    @classmethod
    def warning(cls, message: str = "") -> "StepResult":
        return cls(StepStatus.WARNING, message)

    @classmethod
    def skipped(cls, message: str = "") -> "StepResult":
        return cls(StepStatus.SKIPPED, message)

    @classmethod
    def failed(cls, message: str = "") -> "StepResult":
        return cls(StepStatus.FAILED, message)
