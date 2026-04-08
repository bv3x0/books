"""
Terminal prompting for ingest workflows.
"""

from __future__ import annotations

import os

from app.services.ingest_interaction import (
    ChunkingReview,
    IngestPrompter,
    LowMatchAction,
    LowMatchDecision,
    TocValidationReview,
)


class TerminalIngestPrompter(IngestPrompter):
    """Interactive terminal prompts for ingest decisions."""

    def choose_low_match_action(self, review: TocValidationReview) -> LowMatchDecision:
        print(
            f"\n⚠️  WARNING: Low match rate ({review.match_rate:.0%}). This may cause:",
            flush=True,
        )
        print("   - Poor chapter boundary detection", flush=True)
        print("   - Duplicate content in output", flush=True)
        print("   - Wasted API costs", flush=True)
        print("\n" + "=" * 60, flush=True)
        print("Options:", flush=True)
        print("  [1] Proceed anyway (may cause issues)", flush=True)
        print("  [2] Provide manual TOC file", flush=True)
        print("  [3] Abort", flush=True)

        try:
            choice = input("\nChoice [1/2/3]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.", flush=True)
            return LowMatchDecision(LowMatchAction.ABORT)

        if choice == "1":
            return LowMatchDecision(LowMatchAction.PROCEED)
        if choice == "2":
            try:
                toc_path = input("Enter path to TOC file: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nAborted.", flush=True)
                return LowMatchDecision(LowMatchAction.ABORT)

            if not toc_path:
                print("No path provided.", flush=True)
                return LowMatchDecision(LowMatchAction.RETRY)
            toc_path = os.path.expanduser(toc_path)
            if not os.path.isabs(toc_path):
                toc_path = os.path.join(os.getcwd(), toc_path)
            if not os.path.exists(toc_path):
                print(f"File not found: {toc_path}", flush=True)
                return LowMatchDecision(LowMatchAction.RETRY)
            return LowMatchDecision(LowMatchAction.MANUAL_TOC, toc_path=toc_path)

        print("Aborted.", flush=True)
        return LowMatchDecision(LowMatchAction.ABORT)

    def confirm_toc_continue(self, review: TocValidationReview, passed: bool) -> bool:
        if passed:
            print("\n" + "=" * 60, flush=True)
            prompt = "TOC validation passed. Proceed? [Y/n]: "
        else:
            print("\n⚠️  NOTICE: Some chapters may not be detected properly.", flush=True)
            print("\n" + "=" * 60, flush=True)
            prompt = "Proceed with processing? [Y/n]: "

        try:
            response = input(prompt).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.", flush=True)
            return False
        return response != "n"

    def confirm_chunking_without_toc(self, review: ChunkingReview) -> bool:
        print("\n" + "=" * 60, flush=True)
        print("⚠️  CHUNKING WARNING", flush=True)
        print("=" * 60, flush=True)
        print("\nThe following files exceed the token limit and will be chunked:", flush=True)
        for filename, tokens in review.chunked_files:
            print(
                f"  • {filename}: {tokens:,} tokens (limit: {review.max_tokens:,})",
                flush=True,
            )

        if review.has_toc:
            print("\n✓ Manual TOC is loaded - this helps prevent duplicate headings.", flush=True)
            return True

        print("\n⚠️  No manual TOC provided.", flush=True)
        print("\nWithout a TOC, chunked books may have issues:", flush=True)
        print("  - Duplicate chapter headings across chunks", flush=True)
        print("  - Inconsistent section naming", flush=True)
        print("  - Structure validation warnings", flush=True)
        print("\nOptions:", flush=True)
        print("  [1] Proceed anyway", flush=True)
        print("  [2] Abort to add a TOC (create books/toc.txt, then rerun with --toc)", flush=True)

        try:
            choice = input("\nChoice [1/2]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.", flush=True)
            return False

        if choice == "1":
            return True

        print("\nAborted. To add a TOC:", flush=True)
        print("  1. Create books/toc.txt with chapter names (one per line)", flush=True)
        print('  2. Rerun with: python3 -m app.main "book-name" --toc', flush=True)
        return False


class AutoYesIngestPrompter(IngestPrompter):
    """Auto-accept normal ingest prompts for attended but frictionless runs."""

    def choose_low_match_action(self, review: TocValidationReview) -> LowMatchDecision:
        print(
            f"\n⚠️  WARNING: Low match rate ({review.match_rate:.0%}) for {review.filename}. "
            "--yes is proceeding automatically.",
            flush=True,
        )
        return LowMatchDecision(LowMatchAction.PROCEED)

    def confirm_toc_continue(self, review: TocValidationReview, passed: bool) -> bool:
        status = "passed" if passed else "warning"
        print(
            f"\nTOC validation {status} for {review.filename}. --yes is proceeding automatically.",
            flush=True,
        )
        return True

    def confirm_chunking_without_toc(self, review: ChunkingReview) -> bool:
        if review.has_toc:
            print("\nChunking check passed with TOC. --yes is proceeding automatically.", flush=True)
            return True

        print(
            "\n⚠️  CHUNKING WARNING: no TOC provided. --yes is proceeding automatically.",
            flush=True,
        )
        return True


class NonInteractiveIngestPrompter(IngestPrompter):
    """Fail fast instead of prompting when human judgment would be required."""

    def choose_low_match_action(self, review: TocValidationReview) -> LowMatchDecision:
        print(
            f"\n⚠️  WARNING: Low match rate ({review.match_rate:.0%}) for {review.filename}. "
            "--non-interactive is aborting instead of prompting.",
            flush=True,
        )
        return LowMatchDecision(LowMatchAction.ABORT)

    def confirm_toc_continue(self, review: TocValidationReview, passed: bool) -> bool:
        status = "passed" if passed else "warning"
        print(
            f"\nTOC validation {status} for {review.filename}. "
            "--non-interactive is proceeding without prompt.",
            flush=True,
        )
        return True

    def confirm_chunking_without_toc(self, review: ChunkingReview) -> bool:
        if review.has_toc:
            print(
                "\nChunking check passed with TOC. --non-interactive is proceeding without prompt.",
                flush=True,
            )
            return True

        print(
            "\n⚠️  CHUNKING WARNING: no TOC provided. "
            "--non-interactive is aborting instead of prompting.",
            flush=True,
        )
        return False
