"""
Ingest service: orchestrates book summarization workflows.
"""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Optional

from app.config import BOOKS_DIR, INPUT_DIR, validate_config
from app.services.ingest_interaction import (
    ChunkingReview,
    IngestPrompter,
    LowMatchAction,
    LowMatchDecision,
    TocValidationReview,
)
from app.services.ingest_models import (
    BatchIngestRequest,
    IngestJob,
    IngestOptions,
    IngestSourcePaths,
    ProcessedIngestJob,
    ProviderSettings,
)
from app.services.ingest_reporting import (
    print_batch_summary,
    print_configuration,
    print_cost_estimate,
    print_export_summary,
)
from app.services.ingest_runtime import (
    initialize_concept_registry,
    initialize_exporter,
    initialize_runtime,
    load_ingest_env,
    resolve_provider_settings,
    submit_requests,
    validate_book_name,
)
from app.services.ingest_validation_service import check_chunking_warning, validate_toc_matches


DEFAULT_SINGLE_BOOK_TOC_PATH = os.path.join(BOOKS_DIR, "toc.txt")
DEFAULT_BATCH_TOC_FILENAME = "toc.txt"


def _stage_and_validate_inputs(runtime, prompter: IngestPrompter):
    print("\n--- Step 1: Staging Files ---", flush=True)
    uploaded_files = runtime.stager.upload_files()
    if not uploaded_files:
        print("No files uploaded or found. Exiting.", flush=True)
        return None

    print("\n--- Step 1b: TOC Validation ---", flush=True)
    if not validate_toc_matches(uploaded_files, prompter):
        print("TOC validation failed or aborted. Exiting.", flush=True)
        return None

    print("\n--- Step 1c: Chunking Check ---", flush=True)
    if not check_chunking_warning(
        uploaded_files,
        bool(runtime.stager.toc_path),
        prompter,
        model_id=runtime.manifest.model_id,
    ):
        print("Aborted to add TOC. Exiting.", flush=True)
        return None

    return uploaded_files


def _print_batch_job_header(phase: str, idx: int, total: int, book: str) -> None:
    print(
        f"\n{'=' * 60}\nBatch {phase} {idx}/{total}: {book}\n{'=' * 60}",
        flush=True,
    )


def _process_requests(runtime, uploaded_files: dict, retry_mode: bool):
    plan_requests = [] if retry_mode else runtime.manifest.get_chunk_plan_requests(uploaded_files)
    if plan_requests:
        print("\n--- Step 2a: Planning Extra-Long Books ---", flush=True)
        for plan_request in plan_requests:
            filename = plan_request["filename"]
            print(f"Planning chunk boundaries for: {filename}", flush=True)
            result = runtime.monitor.run_ephemeral_request(
                plan_request["request"],
                label=f"chunk plan for {filename}",
            )
            if result.get("status") != "SUCCESS":
                print("  Planning failed; falling back to local chunking.", flush=True)
                continue
            chunk_plan = runtime.manifest.parse_chunk_plan_response(
                result.get("response", ""),
                plan_request["file_data"],
            )
            if chunk_plan:
                plan_request["file_data"]["chunk_plan"] = chunk_plan
                print(
                    f"  Planned {len(chunk_plan['chunks'])} chunk(s) from full-book pass.",
                    flush=True,
                )
            else:
                print("  Plan unusable; falling back to local chunking.", flush=True)

    print("\n--- Step 2: Creating Manifest ---", flush=True)
    requests = runtime.manifest.create_batch_job(uploaded_files, mode="quick")
    print(f"Prepared {len(requests)} requests for batch processing.", flush=True)

    print("\n--- Step 3: Processing Requests ---", flush=True)
    job_result = submit_requests(runtime, requests, retry_mode)
    if not job_result:
        print("Processing failed. Exiting.", flush=True)
        return None

    if job_result.state not in {"SUCCEEDED", "PARTIAL"}:
        print(
            f"Processing did not succeed. State: {job_result.state}. Skipping export.",
            flush=True,
        )
        print_cost_estimate(job_result.results)
        return None

    return job_result


def _export_results(exporter, concept_registry, uploaded_files: dict, job_result) -> bool:
    print("\n--- Step 4: Exporting Results ---", flush=True)
    export_ok = exporter.save_results(job_result.name)
    summary = exporter.get_export_summary()
    print_export_summary(
        exporter,
        uploaded_files,
        summary,
        concept_registry,
        export_ok,
    )
    print("\n--- Step 6: Cleanup ---", flush=True)
    exporter.cleanup_uploaded_files(uploaded_files)
    print_cost_estimate(job_result.results)
    return export_ok


def _resolve_manifest_relative_path(base_dir: Path, raw_path: str) -> str:
    path = Path(os.path.expanduser(raw_path))
    if not path.is_absolute():
        path = base_dir / path
    return str(path.resolve())


def _resolve_batch_toc_path(
    entry: dict,
    source_dir: str,
    options: IngestOptions,
    manifest_dir: Path,
) -> str | None:
    if "toc_path" in entry:
        raw_toc_path = entry.get("toc_path")
        if not raw_toc_path:
            return None
        return _resolve_manifest_relative_path(manifest_dir, raw_toc_path)

    if options.use_manual_toc:
        inferred = os.path.join(source_dir, DEFAULT_BATCH_TOC_FILENAME)
        if os.path.exists(inferred):
            return inferred

    return None


def build_single_book_job(options: IngestOptions) -> IngestJob:
    """Build the backward-compatible single-book ingest job."""
    return IngestJob(
        book=options.book,
        options=options,
        source_paths=IngestSourcePaths(
            source_dir=INPUT_DIR,
            toc_path=DEFAULT_SINGLE_BOOK_TOC_PATH if options.use_manual_toc else None,
        ),
    )


def load_batch_request(manifest_path: str, options: IngestOptions) -> BatchIngestRequest:
    """Load a batch manifest and convert it to validated ingest jobs."""
    manifest_file = Path(os.path.expanduser(manifest_path)).resolve()
    if not manifest_file.exists():
        raise ValueError(f"Batch manifest not found: {manifest_file}")

    with open(manifest_file, "r", encoding="utf-8") as f:
        payload = json.load(f)

    if not isinstance(payload, list) or not payload:
        raise ValueError("Batch manifest must be a non-empty JSON list.")

    jobs = []
    seen_books = set()

    for idx, entry in enumerate(payload, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"Batch manifest entry {idx} must be an object.")

        raw_book = entry.get("book", "")
        if not raw_book:
            raise ValueError(f"Batch manifest entry {idx} is missing 'book'.")
        book = validate_book_name(raw_book)
        if book in seen_books:
            raise ValueError(
                f"Duplicate batch book '{book}'. "
                "Each book key must be unique so notes/index/cache outputs do not collide."
            )
        seen_books.add(book)

        raw_source_dir = entry.get("source_dir")
        if not raw_source_dir:
            raise ValueError(f"Batch manifest entry '{book}' is missing 'source_dir'.")

        source_dir = _resolve_manifest_relative_path(manifest_file.parent, raw_source_dir)
        toc_path = _resolve_batch_toc_path(entry, source_dir, options, manifest_file.parent)

        raw_collections = entry.get("collections", [])
        if not isinstance(raw_collections, list) or any(
            not isinstance(item, str) or not item.strip() for item in raw_collections
        ):
            raise ValueError(
                f"Batch manifest entry '{book}' has invalid 'collections'; "
                "expected a list of non-empty strings."
            )
        collections = tuple(dict.fromkeys(item.strip() for item in raw_collections))

        jobs.append(
            IngestJob(
                book=book,
                options=replace(options, book=book),
                source_paths=IngestSourcePaths(source_dir=source_dir, toc_path=toc_path),
                collections=collections,
            )
        )

    return BatchIngestRequest(jobs=jobs)


def prepare_ingest_job(job: IngestJob, prompter: IngestPrompter) -> ProcessedIngestJob:
    """Stage and validate one ingest job before batch execution begins."""
    try:
        book_name = validate_book_name(job.book)
        settings: ProviderSettings = resolve_provider_settings(job.options)
    except ValueError as e:
        print(f"Error: {e}", flush=True)
        return ProcessedIngestJob(job=job, status="failed", error=str(e))

    print_configuration(
        book_name,
        job.options,
        settings,
        source_dir=job.source_paths.source_dir,
        toc_path=job.source_paths.toc_path,
    )

    if not validate_config(
        provider=settings.provider,
        require_openai=settings.require_openai,
        input_dir=job.source_paths.source_dir,
    ):
        error = "Configuration invalid."
        print("Error: Configuration invalid. Please check your .env file.", flush=True)
        return ProcessedIngestJob(
            job=job,
            settings=settings,
            status="failed",
            error=error,
        )

    runtime = initialize_runtime(book_name, job.options, settings, job.source_paths)
    uploaded_files = _stage_and_validate_inputs(runtime, prompter)
    if not uploaded_files:
        return ProcessedIngestJob(
            job=job,
            settings=settings,
            runtime=runtime,
            status="failed",
            error="Staging or validation failed.",
        )

    return ProcessedIngestJob(
        job=job,
        settings=settings,
        runtime=runtime,
        uploaded_files=uploaded_files,
        status="prepared",
    )


def process_prepared_job(prepared_job: ProcessedIngestJob) -> ProcessedIngestJob:
    """Run provider processing for a job that already passed staging and validation."""
    if not prepared_job.runtime or not prepared_job.settings:
        return replace(
            prepared_job,
            status="failed",
            error="Prepared job is missing runtime context.",
        )

    job_result = _process_requests(
        prepared_job.runtime,
        prepared_job.uploaded_files,
        prepared_job.job.options.retry_mode,
    )
    if not job_result:
        return replace(
            prepared_job,
            status="failed",
            error="Processing failed.",
        )

    return replace(
        prepared_job,
        job_result=job_result,
        status="processed",
    )


def run_ingest_job(job: IngestJob, prompter: IngestPrompter) -> ProcessedIngestJob:
    """Stage, validate, and process one ingest job without canonical writes."""
    prepared_job = prepare_ingest_job(job, prompter)
    if prepared_job.status != "prepared":
        return prepared_job
    return process_prepared_job(prepared_job)


def _write_processed_job(
    processed_job: ProcessedIngestJob,
    concept_registry,
    enable_semantic_merge: bool,
) -> bool:
    """Write one processed job through the serialized export phase."""
    exporter = initialize_exporter(
        processed_job.job.book,
        processed_job.job.options,
        processed_job.settings,
        processed_job.job.source_paths,
        concept_registry,
        enable_semantic_merge,
        processed_job.job.collections,
    )
    return _export_results(
        exporter,
        concept_registry,
        processed_job.uploaded_files,
        processed_job.job_result,
    )


def run_batch_ingest(
    batch_request: BatchIngestRequest | list[IngestJob],
    prompter: Optional[IngestPrompter] = None,
) -> bool:
    """Run a batch with upfront staging/validation and serialized canonical writes."""
    load_ingest_env()
    prompter = prompter or IngestPrompter()
    if isinstance(batch_request, list):
        batch_request = BatchIngestRequest(jobs=batch_request)

    total_jobs = len(batch_request.jobs)
    if total_jobs == 0:
        print("No ingest jobs were provided.", flush=True)
        return False

    preflight_jobs = []
    processed_jobs = []
    for idx, job in enumerate(batch_request.jobs, start=1):
        if total_jobs > 1:
            _print_batch_job_header("preflight", idx, total_jobs, job.book)
        preflight_jobs.append(prepare_ingest_job(job, prompter))

    ready_total = sum(1 for job in preflight_jobs if job.status == "prepared")
    execution_idx = 0
    for prepared_job in preflight_jobs:
        if prepared_job.status != "prepared":
            processed_jobs.append(prepared_job)
            continue

        execution_idx += 1
        if total_jobs > 1:
            _print_batch_job_header(
                "execution",
                execution_idx,
                ready_total,
                prepared_job.job.book,
            )
        processed_jobs.append(process_prepared_job(prepared_job))

    successful_books = []
    failed_books = [
        processed.job.book for processed in processed_jobs if processed.job_result is None
    ]
    writable_jobs = [processed for processed in processed_jobs if processed.job_result is not None]

    concept_registry = None
    enable_semantic_merge = False
    if writable_jobs:
        print("\n--- Shared Write Setup ---", flush=True)
        concept_registry, enable_semantic_merge = initialize_concept_registry(
            writable_jobs[0].job.options
        )

    for processed in writable_jobs:
        if _write_processed_job(processed, concept_registry, enable_semantic_merge):
            successful_books.append(processed.job.book)
        else:
            failed_books.append(processed.job.book)

    if total_jobs > 1:
        print_batch_summary(total_jobs, successful_books, failed_books)
    return len(failed_books) == 0


def run_ingest(options: IngestOptions, prompter: Optional[IngestPrompter] = None) -> bool:
    """Backward-compatible wrapper for one-book ingest."""
    return run_batch_ingest([build_single_book_job(options)], prompter=prompter)


__all__ = [
    "BatchIngestRequest",
    "IngestJob",
    "IngestOptions",
    "IngestSourcePaths",
    "ProcessedIngestJob",
    "ProviderSettings",
    "build_single_book_job",
    "check_chunking_warning",
    "load_batch_request",
    "LowMatchAction",
    "LowMatchDecision",
    "ChunkingReview",
    "TocValidationReview",
    "prepare_ingest_job",
    "process_prepared_job",
    "resolve_provider_settings",
    "run_batch_ingest",
    "run_ingest",
    "run_ingest_job",
    "validate_book_name",
    "validate_toc_matches",
]
