#!/usr/bin/env python3
"""
Safely delete a book and all its associated data.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.book_management_service import delete_book


def render_delete_result(result) -> int:
    print(f"{'=' * 70}")
    print(f"{'DRY RUN - ' if result.dry_run else ''}DELETE BOOK: {result.book_name}")
    print(f"{'=' * 70}\n")

    if not result.found:
        print(f"❌ Book '{result.book_name}' not found")
        print(f"   Expected: {result.notes_file}")
        return 1

    if result.notes_exists:
        print(
            f"📄 Would delete: {result.notes_file}"
            if result.dry_run
            else f"🗑️  Deleting: {result.notes_file}"
        )
        if not result.dry_run:
            print("   ✅ Deleted")
    else:
        print(f"⚠️  Notes file not found: {result.notes_file}")

    if result.index_exists:
        print(
            f"\n📊 Would delete: {result.index_file}"
            if result.dry_run
            else f"\n🗑️  Deleting: {result.index_file}"
        )
        if not result.dry_run:
            print("   ✅ Deleted")
    else:
        print(f"\n⚠️  Index file not found: {result.index_file}")

    print(
        "\n🔢 Would remove quotes and claims from vector database..."
        if result.dry_run
        else "\n🗑️  Removing quotes and claims from vector database..."
    )
    if not result.dry_run:
        if result.vector_error:
            print(f"   ⚠️  Error removing from vector store: {result.vector_error}")
        else:
            print(f"   ✅ Removed {result.removed_quotes} quotes")
            print(f"   ✅ Removed {result.removed_claims} claims")

    print(
        "\n📚 Would clean concept registry..."
        if result.dry_run
        else "\n🗑️  Cleaning concept registry..."
    )
    if not result.dry_run:
        if result.concepts_error:
            print(f"   ⚠️  Error cleaning concepts: {result.concepts_error}")
        else:
            print(f"   ✅ Removed references from {result.removed_concepts} concepts")

    print(f"\n{'=' * 70}")
    if result.dry_run:
        print("DRY RUN COMPLETE - No changes made")
        print("Run without --dry-run to actually delete")
    else:
        print("✅ DELETION COMPLETE")
    print(f"{'=' * 70}\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Safely delete a book and its associated notes, index, vectors, and concept references."
    )
    parser.add_argument("book_name", help="Book slug/name used for notes and index output")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview deletions without changing files or databases.",
    )
    args = parser.parse_args()
    return render_delete_result(delete_book(args.book_name, args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
