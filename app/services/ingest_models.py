"""
Shared data models for ingest workflows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class IngestOptions:
    book: str = ""
    use_manual_toc: bool = False
    retry_mode: bool = False
    use_vlm: bool = False
    split_pages: bool = False
    use_gemini: bool = False
    use_gpt: bool = False
    use_codex: bool = False
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
class IngestSourcePaths:
    source_dir: str
    toc_path: str | None = None


@dataclass(frozen=True)
class IngestJob:
    book: str
    options: IngestOptions
    source_paths: IngestSourcePaths


@dataclass(frozen=True)
class BatchIngestRequest:
    jobs: list[IngestJob]


@dataclass(frozen=True)
class IngestRuntime:
    client: Any
    google_api_key: str | None
    stager: Any
    manifest: Any
    monitor: Any


@dataclass(frozen=True)
class ProcessedIngestJob:
    job: IngestJob
    settings: ProviderSettings | None = None
    runtime: IngestRuntime | None = None
    uploaded_files: dict = field(default_factory=dict)
    job_result: Any = None
    status: str = "pending"
    error: str | None = None


@dataclass(frozen=True)
class BatchIngestSummary:
    total_jobs: int
    successful_books: list[str] = field(default_factory=list)
    failed_books: list[str] = field(default_factory=list)
