"""
Ingest service: orchestrates the book summarization pipeline.
"""

from __future__ import annotations

from typing import Optional

from app.config import validate_config
from app.services.ingest_interaction import (
    ChunkingReview,
    IngestPrompter,
    LowMatchAction,
    LowMatchDecision,
    TocValidationReview,
)
from app.services.ingest_models import IngestOptions, ProviderSettings
from app.services.ingest_reporting import (
    print_configuration,
    print_cost_estimate,
    print_export_summary,
)
from app.services.ingest_runtime import (
    initialize_runtime,
    load_ingest_env,
    resolve_provider_settings,
    submit_requests,
    validate_book_name,
)
from app.services.ingest_validation_service import check_chunking_warning, validate_toc_matches


def _stage_and_validate_inputs(runtime, options: IngestOptions, prompter: IngestPrompter):
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
        options.use_manual_toc,
        prompter,
        model_id=runtime.manifest.model_id,
    ):
        print("Aborted to add TOC. Exiting.", flush=True)
        return None

    return uploaded_files


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


def _export_results(runtime, uploaded_files: dict, job_result) -> bool:
    print("\n--- Step 4: Exporting Results ---", flush=True)
    export_ok = runtime.exporter.save_results(job_result.name)
    summary = runtime.exporter.get_export_summary()
    print_export_summary(
        runtime.exporter,
        uploaded_files,
        summary,
        runtime.concept_registry,
        export_ok,
    )
    print("\n--- Step 6: Cleanup ---", flush=True)
    runtime.exporter.cleanup_uploaded_files(uploaded_files)
    print_cost_estimate(job_result.results)
    return export_ok


def run_ingest(options: IngestOptions, prompter: Optional[IngestPrompter] = None) -> bool:
    """Run the end-to-end ingest pipeline for one book."""
    load_ingest_env()
    prompter = prompter or IngestPrompter()

    try:
        book_name = validate_book_name(options.book)
        settings: ProviderSettings = resolve_provider_settings(options)
    except ValueError as e:
        print(f"Error: {e}", flush=True)
        return False

    print_configuration(book_name, options, settings)

    if not validate_config(
        provider=settings.provider,
        require_openai=settings.require_openai,
    ):
        print("Error: Configuration invalid. Please check your .env file.", flush=True)
        return False

    runtime = initialize_runtime(book_name, options, settings)
    uploaded_files = _stage_and_validate_inputs(runtime, options, prompter)
    if not uploaded_files:
        return False

    job_result = _process_requests(runtime, uploaded_files, options.retry_mode)
    if not job_result:
        return False

    return _export_results(runtime, uploaded_files, job_result)


__all__ = [
    "IngestOptions",
    "ProviderSettings",
    "run_ingest",
    "validate_book_name",
    "resolve_provider_settings",
    "validate_toc_matches",
    "check_chunking_warning",
    "TocValidationReview",
    "ChunkingReview",
    "LowMatchAction",
    "LowMatchDecision",
]
