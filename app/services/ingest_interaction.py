"""
Interaction contracts for ingest workflows.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


@dataclass(frozen=True)
class TocValidationReview:
    filename: str
    toc_count: int
    match_rate: float
    matched_titles: list[str]
    unmatched_titles: list[str]


@dataclass(frozen=True)
class ChunkingReview:
    chunked_files: list[tuple[str, int]]
    max_tokens: int
    has_toc: bool


class LowMatchAction(str, Enum):
    PROCEED = "proceed"
    MANUAL_TOC = "manual_toc"
    RETRY = "retry"
    ABORT = "abort"


@dataclass(frozen=True)
class LowMatchDecision:
    action: LowMatchAction
    toc_path: Optional[str] = None


class IngestPrompter:
    """Abstracts operator decisions out of the ingest service layer."""

    def choose_low_match_action(self, review: TocValidationReview) -> LowMatchDecision:
        return LowMatchDecision(LowMatchAction.ABORT)

    def confirm_toc_continue(self, review: TocValidationReview, passed: bool) -> bool:
        return False

    def confirm_chunking_without_toc(self, review: ChunkingReview) -> bool:
        return False
