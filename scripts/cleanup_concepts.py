#!/usr/bin/env python3
"""
Clean up orphaned concepts in the registry.

This script removes concepts that have no book references (claim_count > 0 but empty books list).
This can happen when a book is deleted but claim counts weren't properly decremented.

Usage:
    python3 scripts/cleanup_concepts.py           # Run cleanup
    python3 scripts/cleanup_concepts.py --dry-run # Preview what would be removed
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import CONCEPTS_PATH
from app.core.concept_registry import ConceptRegistry


def main():
    parser = argparse.ArgumentParser(
        description="Clean orphaned concepts from the global concept registry.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview orphaned concepts without modifying the registry.",
    )
    args = parser.parse_args()
    dry_run = args.dry_run

    print(f"{'='*70}")
    print(f"{'DRY RUN - ' if dry_run else ''}CONCEPT REGISTRY CLEANUP")
    print(f"{'='*70}\n")

    registry = ConceptRegistry(CONCEPTS_PATH)

    # Find orphaned concepts (those with no books)
    orphaned = []
    for cid, concept in registry.concepts.items():
        if not concept.book_claims:
            orphaned.append((cid, concept.label, concept.claim_count))

    if not orphaned:
        print("✅ No orphaned concepts found. Registry is clean!")
        return

    print(f"Found {len(orphaned)} orphaned concepts (have claim_count but no books):\n")

    # Show top 20 by claim count
    orphaned.sort(key=lambda x: x[2], reverse=True)
    for cid, label, count in orphaned[:20]:
        print(f"  {label}: {count} claims")

    if len(orphaned) > 20:
        print(f"  ... and {len(orphaned) - 20} more")

    print()

    if dry_run:
        print(f"Would remove {len(orphaned)} orphaned concepts.")
        print("Run without --dry-run to actually remove them.")
    else:
        removed = registry.cleanup_orphaned_concepts()
        registry.save()
        print(f"✅ Removed {removed} orphaned concepts and saved registry.")

    # Show stats
    print(f"\n{'='*70}")
    stats = registry.get_stats()
    print(f"Registry stats after cleanup:")
    print(f"  Total concepts: {stats['total_concepts']}")
    print(f"  Total claims: {stats['total_claims']}")
    print(f"  Books indexed: {stats['books_indexed']}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
