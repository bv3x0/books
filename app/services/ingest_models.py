"""
Shared data models for ingest workflows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class IngestOptions:
    book: str
    use_manual_toc: bool = False
    retry_mode: bool = False
    use_vlm: bool = False
    split_pages: bool = False
    use_gemini: bool = False
    use_gpt: bool = False
    test_mode: bool = False
    enable_enrichment: bool = False
    enable_semantic_merge: bool = True


@dataclass(frozen=True)
class ProviderSettings:
    provider: str
    model_id: str
    notes_suffix: str
    cache_suffix: str
    require_openai: bool


@dataclass(frozen=True)
class IngestRuntime:
    client: Any
    google_api_key: str | None
    concept_registry: Any
    stager: Any
    manifest: Any
    monitor: Any
    exporter: Any
