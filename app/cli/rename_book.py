#!/usr/bin/env python3
"""
Safely rename a book and update all references.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.book_management_service import rename_book


def render_rename_result(result) -> int:
    print(f"{'=' * 70}")
    print(f"{'DRY RUN - ' if result.dry_run else ''}RENAME BOOK")
    print(f"{'=' * 70}")
    print(f"From: {result.old_name}")
    print(f"To:   {result.new_name}")
    print(f"{'=' * 70}\n")

    if not result.source_found:
        print(f"❌ Book '{result.old_name}' not found")
        return 1

    if result.destination_exists:
        print(f"❌ Book '{result.new_name}' already exists!")
        print("   Delete it first or choose a different name.")
        return 1

    if result.notes_exists:
        print(
            f"📄 Would rename: {result.old_notes} → {result.new_notes}"
            if result.dry_run
            else f"📝 Renaming: {result.old_notes}"
        )
        if not result.dry_run:
            print(f"   ✅ Renamed to {result.new_notes}")

    if result.index_exists:
        print(
            f"\n📊 Would update and rename: {result.old_index} → {result.new_index}"
            if result.dry_run
            else "\n📊 Updating JSON index..."
        )
        if not result.dry_run:
            print(f"   ✅ Saved as {result.new_index}")

    print(
        "\n🔢 Would update vector database..."
        if result.dry_run
        else "\n🔢 Updating vector database..."
    )
    if not result.dry_run:
        if result.vector_error:
            print(f"   ⚠️  Error updating vector database: {result.vector_error}")
        else:
            print(f"   ✅ Updated {result.updated_claims} claims")

    print(
        "\n📚 Would update concept registry..."
        if result.dry_run
        else "\n📚 Updating concept registry..."
    )
    if not result.dry_run:
        if result.concepts_error:
            print(f"   ⚠️  Error updating concepts: {result.concepts_error}")
        else:
            print(f"   ✅ Updated {result.updated_concepts} concepts")

    print(f"\n{'=' * 70}")
    if result.dry_run:
        print("DRY RUN COMPLETE - No changes made")
        print("Run without --dry-run to actually rename")
    else:
        print("✅ RENAME COMPLETE")
    print(f"{'=' * 70}\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Safely rename a book and update linked notes, index, vectors, and concept references."
    )
    parser.add_argument("old_name", help="Existing book slug/name")
    parser.add_argument("new_name", help="New book slug/name")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the rename without changing files or databases.",
    )
    args = parser.parse_args()
    return render_rename_result(rename_book(args.old_name, args.new_name, args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
