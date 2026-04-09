"""
Validation helpers for ingest workflows.
"""

from __future__ import annotations

from app.services.ingest_interaction import (
    ChunkingReview,
    IngestPrompter,
    LowMatchAction,
    TocValidationReview,
)


def validate_toc_matches(uploaded_files: dict, prompter: IngestPrompter) -> bool:
    """Validate TOC extraction for EPUB files before processing."""
    from app.core.epub_processor import get_flat_toc, parse_manual_toc, test_toc_matches

    epub_files = {
        k: v for k, v in uploaded_files.items() if v.get("format") == "markdown"
    }
    if not epub_files:
        print("No EPUB files found. Skipping validation.", flush=True)
        return True

    for filename, file_data in epub_files.items():
        toc = file_data.get("toc", [])
        text = file_data.get("text", "")
        if not text:
            continue

        print(f"\nValidating TOC for: {filename}", flush=True)

        while True:
            if not toc:
                print("No TOC extracted from EPUB.", flush=True)
                match_rate = 0.0
                matched = []
                unmatched = []
            else:
                print(f"TOC entries: {len(toc)}", flush=True)
                results = test_toc_matches(text, toc)
                matched = results["matched"]
                unmatched = results["unmatched"]
                match_rate = results["match_rate"]

                print(f"\nMatch rate: {len(matched)}/{len(toc)} ({match_rate:.0%})", flush=True)
                if matched:
                    print(f"\n✓ Matched entries ({len(matched)}):", flush=True)
                    for title, _context in matched[:5]:
                        print(f"  • {title}", flush=True)
                    if len(matched) > 5:
                        print(f"  ... and {len(matched) - 5} more", flush=True)

                if unmatched:
                    print(f"\n✗ Unmatched entries ({len(unmatched)}):", flush=True)
                    for title in unmatched[:10]:
                        print(f"  • {title}", flush=True)
                    if len(unmatched) > 10:
                        print(f"  ... and {len(unmatched) - 10} more", flush=True)

            review = TocValidationReview(
                filename=filename,
                toc_count=len(toc),
                match_rate=match_rate,
                matched_titles=[title for title, _context in matched],
                unmatched_titles=unmatched,
            )

            if match_rate < 0.5:
                decision = prompter.choose_low_match_action(review)
                if decision.action is LowMatchAction.PROCEED:
                    return True
                if decision.action is LowMatchAction.MANUAL_TOC and decision.toc_path:
                    try:
                        structured_toc = parse_manual_toc(decision.toc_path)
                        flat_toc = get_flat_toc(structured_toc)
                        parts_count = sum(
                            1 for level, _title in structured_toc if level == "part"
                        )
                        chapters_count = sum(
                            1 for level, _title in structured_toc if level == "chapter"
                        )
                        print(
                            f"\nLoaded manual TOC: {parts_count} parts, {chapters_count} chapters",
                            flush=True,
                        )
                        file_data["toc"] = flat_toc
                        file_data["toc_structured"] = structured_toc
                        toc = flat_toc
                        print("Re-testing matches...\n", flush=True)
                    except Exception as e:
                        print(f"Error parsing TOC file: {e}", flush=True)
                        continue
                elif decision.action is LowMatchAction.RETRY:
                    continue
                else:
                    print("Aborted.", flush=True)
                    return False
            elif match_rate < 0.8:
                return prompter.confirm_toc_continue(review, passed=False)
            elif match_rate >= 1.0:
                print(
                    "\nTOC validation reached 100% match. Proceeding automatically.",
                    flush=True,
                )
                return True
            else:
                return prompter.confirm_toc_continue(review, passed=True)

    return True


def check_chunking_warning(
    uploaded_files: dict,
    use_manual_toc: bool,
    prompter: IngestPrompter,
    model_id: str | None = None,
) -> bool:
    """Warn if the book will be chunked without a TOC."""
    from app.config import get_single_request_token_limit

    max_tokens_single_request = get_single_request_token_limit(model_id)

    chunked_files = []
    for filename, file_data in uploaded_files.items():
        tokens = file_data.get("estimated_tokens", 0)
        if tokens > max_tokens_single_request:
            chunked_files.append((filename, tokens))

    if not chunked_files:
        return True

    has_toc = use_manual_toc or any(
        file_data.get("toc_structured") for file_data in uploaded_files.values()
    )

    return prompter.confirm_chunking_without_toc(
        ChunkingReview(
            chunked_files=chunked_files,
            max_tokens=max_tokens_single_request,
            has_toc=has_toc,
        )
    )
