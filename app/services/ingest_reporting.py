"""
Reporting helpers for ingest workflows.
"""

from __future__ import annotations

from app.config import get_model_pricing
from app.services.ingest_models import IngestOptions, ProviderSettings


def print_configuration(
    book_name: str,
    options: IngestOptions,
    settings: ProviderSettings,
    source_dir: str,
    toc_path: str | None = None,
) -> None:
    print(f"Processing book: {book_name}", flush=True)
    print(
        f"Manual TOC: {'enabled' if toc_path else 'disabled'}",
        flush=True,
    )
    print(f"Retry mode: {'enabled' if options.retry_mode else 'disabled'}", flush=True)
    print(f"OCR (VLM): {'enabled' if options.use_vlm else 'disabled'}", flush=True)
    print(f"Split pages: {'enabled' if options.split_pages else 'disabled'}", flush=True)
    print(f"Provider: {settings.provider}", flush=True)
    print(f"Model: {settings.model_id}", flush=True)
    print(f"Test mode: {'enabled' if options.test_mode else 'disabled'}", flush=True)
    print(
        f"Enrichment: {'enabled' if options.enable_enrichment else 'disabled (core mode)'}",
        flush=True,
    )
    print(
        "Semantic concept merge: %s"
        % ("enabled" if options.enable_semantic_merge else "disabled"),
        flush=True,
    )
    print(f"Source directory: {source_dir}", flush=True)
    if toc_path:
        print(f"Manual TOC path: {toc_path}", flush=True)
    if settings.notes_suffix:
        print(f"Output will be saved to: notes/{book_name}{settings.notes_suffix}.md", flush=True)
    else:
        print(f"Output will be saved to: notes/{book_name}.md", flush=True)


def print_cost_estimate(results: list) -> None:
    """Print run cost estimate based on provider usage metadata."""
    print("\n--- Cost Estimate ---", flush=True)

    if not results:
        print("  No results available for cost estimation.", flush=True)
        return

    per_model = {}
    missing_usage = 0
    priced_models = 0
    total_cost = 0.0

    for result in results:
        model = result.get("model") or "unknown"
        usage = result.get("usage") or {}
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")

        if input_tokens is None and output_tokens is None:
            missing_usage += 1
            continue

        model_totals = per_model.setdefault(
            model,
            {
                "input_tokens": 0,
                "output_tokens": 0,
                "cached_input_tokens": 0,
                "cache_creation_input_tokens": 0,
                "cost": None,
            },
        )
        model_totals["input_tokens"] += int(input_tokens or 0)
        model_totals["output_tokens"] += int(output_tokens or 0)
        model_totals["cached_input_tokens"] += int(usage.get("cached_input_tokens") or 0)
        model_totals["cache_creation_input_tokens"] += int(
            usage.get("cache_creation_input_tokens") or 0
        )

    if not per_model:
        print("  No token usage metadata available from provider.", flush=True)
        return

    for model, totals in per_model.items():
        pricing = get_model_pricing(model)
        in_tokens = totals["input_tokens"]
        out_tokens = totals["output_tokens"]
        cached_in_tokens = totals["cached_input_tokens"]
        cache_creation_in_tokens = totals["cache_creation_input_tokens"]

        if pricing:
            if (
                (cached_in_tokens > 0 or cache_creation_in_tokens > 0)
                and pricing.get("cache_read_input") is not None
                and pricing.get("cache_write_input") is not None
            ):
                total_in_tokens = in_tokens + cached_in_tokens + cache_creation_in_tokens
                in_cost = (
                    (in_tokens / 1_000_000) * pricing["input"]
                    + (cache_creation_in_tokens / 1_000_000) * pricing["cache_write_input"]
                    + (cached_in_tokens / 1_000_000) * pricing["cache_read_input"]
                )
            elif cached_in_tokens > 0 and pricing.get("cached_input") is not None:
                total_in_tokens = in_tokens
                uncached_in_tokens = in_tokens - min(cached_in_tokens, in_tokens)
                in_cost = (
                    (uncached_in_tokens / 1_000_000) * pricing["input"]
                    + (min(cached_in_tokens, in_tokens) / 1_000_000) * pricing["cached_input"]
                )
            else:
                total_in_tokens = in_tokens
                in_cost = (in_tokens / 1_000_000) * pricing["input"]
            out_cost = (out_tokens / 1_000_000) * pricing["output"]
            model_cost = in_cost + out_cost
            totals["cost"] = model_cost
            priced_models += 1
            total_cost += model_cost
            line = (
                f"  {model}: input {total_in_tokens:,}, output {out_tokens:,} "
                f"-> ${model_cost:.4f} (${in_cost:.4f} in + ${out_cost:.4f} out)"
            )
            cache_details = []
            if cache_creation_in_tokens > 0:
                cache_details.append(f"cache write: {cache_creation_in_tokens:,}")
            if cached_in_tokens > 0:
                cache_label = "cached input" if pricing.get("cached_input") is not None else "cache read"
                cache_details.append(f"{cache_label}: {cached_in_tokens:,}")
            if cache_details:
                line += f" [{'; '.join(cache_details)}]"
            print(line, flush=True)
        else:
            print(
                f"  {model}: input {in_tokens:,}, output {out_tokens:,} "
                "-> pricing unknown (add to MODEL_PRICING_USD_PER_MILLION)",
                flush=True,
            )

    if priced_models > 0:
        print(f"  Estimated total: ${total_cost:.4f}", flush=True)

    if missing_usage > 0:
        print(
            f"  Note: {missing_usage} chunk(s) had no usage metadata and are not included.",
            flush=True,
        )


def print_export_summary(
    exporter,
    uploaded_files: dict,
    summary: dict,
    concept_registry,
    export_ok: bool,
) -> None:
    """Print final export, structure, and concept registry status."""
    if export_ok:
        print("\n--- Step 4b: Structure Validation ---", flush=True)
        toc_structured = None
        for file_data in uploaded_files.values():
            if file_data.get("toc_structured"):
                toc_structured = file_data["toc_structured"]
                break
        exporter.validate_structure(toc_structured)
    else:
        print("\n--- Step 4b: Structure Validation ---", flush=True)
        print("  Skipped (export failed)", flush=True)

    if concept_registry:
        print("\n--- Step 5: Saving Concept Registry ---", flush=True)
        if export_ok:
            concept_registry.save()
            stats = concept_registry.get_stats()
            print(f"  Concepts: {stats['total_concepts']}", flush=True)
            print(f"  Total claims: {stats['total_claims']}", flush=True)
        else:
            print("  Skipped (export failed before completion)", flush=True)
    else:
        print("\n--- Step 5: Concept Registry ---", flush=True)
        print("  Skipped (test mode)", flush=True)

    print("\n--- Export Summary ---", flush=True)
    print(f"  Notes: {summary.get('notes_path', 'N/A')}", flush=True)
    print(f"  Index: {summary.get('index_path', 'N/A')}", flush=True)
    if summary.get("claim_count"):
        print(f"  Claims: {summary['claim_count']}", flush=True)
        print(f"  Chapters: {summary['chapter_count']}", flush=True)
        if summary.get("concepts"):
            print(f"  Unique concepts: {len(summary['concepts'])}", flush=True)


def print_batch_summary(
    total_jobs: int,
    successful_books: list[str],
    failed_books: list[str],
) -> None:
    """Print a concise batch ingest summary."""
    print("\n=== Batch Summary ===", flush=True)
    print(f"  Total jobs: {total_jobs}", flush=True)
    print(f"  Successful: {len(successful_books)}", flush=True)
    print(f"  Failed: {len(failed_books)}", flush=True)
    if successful_books:
        print(f"  Completed books: {', '.join(successful_books)}", flush=True)
    if failed_books:
        print(f"  Failed books: {', '.join(failed_books)}", flush=True)
