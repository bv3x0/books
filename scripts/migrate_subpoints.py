#!/usr/bin/env python3
"""
Migration script to convert existing book indexes from string sub_points
to structured sub_points with speaker attribution.

Usage:
    python scripts/migrate_subpoints.py                    # Dry run (preview changes)
    python scripts/migrate_subpoints.py --apply            # Apply changes
    python scripts/migrate_subpoints.py --book "book name" # Migrate single book
    python scripts/migrate_subpoints.py --estimate         # Estimate cost only

Cost: ~$0.03-0.05 per book using Claude Haiku
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from anthropic import Anthropic
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent / "app" / ".env")

INDEX_DIR = Path(__file__).parent.parent / "index"
MIGRATION_MODEL = "claude-haiku-4-5-20251001"  # Fast and cheap for this task

MIGRATION_PROMPT = """Convert these sub_points from string format to structured format with speaker attribution.

INPUT FORMAT (current):
["Einstein said 'God does not play dice' showing his religious views",
 "Greek philosophers created all basic concepts still valid in modern physics"]

OUTPUT FORMAT (new):
[{{"text": "God does not play dice", "speaker": "Einstein"}},
 {{"text": "Greek philosophers created all basic concepts still valid in modern physics", "speaker": null}}]

RULES:
1. If a sub_point contains a direct quote with clear attribution, extract:
   - "text": the exact quoted words (without surrounding prose)
   - "speaker": who said it
2. If a sub_point is NOT a quote (evidence, example, detail), set:
   - "text": the full original text
   - "speaker": null
3. For quotes by the book's author, use "speaker": "the author"
4. Preserve ALL information - don't drop content
5. When in doubt, set speaker to null (it's better to miss a quote than fabricate one)

Here are the sub_points to convert:

{sub_points}

Respond with ONLY the JSON array, no explanation."""


def load_index(book_path: Path) -> dict:
    """Load a book's index JSON."""
    with open(book_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_index(book_path: Path, data: dict) -> None:
    """Save a book's index JSON."""
    with open(book_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def estimate_tokens(sub_points: list) -> int:
    """Rough token estimate for a list of sub_points."""
    text = json.dumps(sub_points)
    # Rough estimate: 1 token per 4 characters
    return len(text) // 4


def needs_migration(sub_points: list) -> bool:
    """Check if sub_points need migration (are strings, not dicts)."""
    if not sub_points:
        return False
    # If any sub_point is a string, needs migration
    return any(isinstance(sp, str) for sp in sub_points)


def migrate_sub_points(client: Anthropic, sub_points: list) -> list:
    """Send sub_points to Claude for restructuring."""
    if not sub_points:
        return []

    # Skip if already migrated
    if not needs_migration(sub_points):
        return sub_points

    response = client.messages.create(
        model=MIGRATION_MODEL,
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": MIGRATION_PROMPT.format(
                    sub_points=json.dumps(sub_points, indent=2)
                ),
            }
        ],
    )

    result_text = response.content[0].text.strip()

    # Clean up response
    if result_text.startswith("```json"):
        result_text = result_text[7:]
    if result_text.startswith("```"):
        result_text = result_text[3:]
    if result_text.endswith("```"):
        result_text = result_text[:-3]
    result_text = result_text.strip()

    try:
        result = json.loads(result_text)

        # Validate structure
        if not isinstance(result, list):
            raise ValueError(f"Expected array, got {type(result).__name__}")
        for i, item in enumerate(result):
            if not isinstance(item, dict):
                raise ValueError(f"Item {i} is not a dict")
            if "text" not in item:
                raise ValueError(f"Item {i} missing 'text' field")
            if "speaker" not in item:
                raise ValueError(f"Item {i} missing 'speaker' field")

        return result
    except json.JSONDecodeError as e:
        print(f"    WARNING: Failed to parse response: {e}")
        print(f"    Raw response: {result_text[:200]}...")
        print(f"    Original sub_points: {json.dumps(sub_points)[:200]}...")
        # Return original on failure
        return sub_points
    except ValueError as e:
        print(f"    WARNING: Invalid response structure: {e}")
        print(f"    Raw response: {result_text[:200]}...")
        # Return original on failure
        return sub_points


def migrate_book(client: Anthropic, book_path: Path, dry_run: bool = True) -> dict:
    """
    Migrate a single book's sub_points to structured format.

    Returns dict with migration stats.
    """
    book_name = book_path.stem
    print(f"\n{'=' * 60}")
    print(f"Processing: {book_name}")

    data = load_index(book_path)
    claims = data.get("claims", [])

    stats = {
        "book": book_name,
        "total_claims": len(claims),
        "claims_migrated": 0,
        "sub_points_migrated": 0,
        "api_calls": 0,
        "estimated_tokens": 0,
    }

    # Collect all sub_points that need migration
    migration_needed = []
    for i, claim in enumerate(claims):
        sub_points = claim.get("sub_points", [])
        if needs_migration(sub_points):
            migration_needed.append((i, sub_points))
            stats["estimated_tokens"] += estimate_tokens(sub_points)

    if not migration_needed:
        print(f"  Already migrated or no sub_points")
        return stats

    print(f"  Claims needing migration: {len(migration_needed)}/{len(claims)}")
    print(f"  Estimated tokens: ~{stats['estimated_tokens']:,}")

    if dry_run:
        print(f"  DRY RUN - no changes made")
        stats["claims_migrated"] = len(migration_needed)
        return stats

    # Migrate each claim's sub_points
    for claim_idx, sub_points in migration_needed:
        print(f"  Migrating claim {claim_idx + 1}...", end=" ", flush=True)

        new_sub_points = migrate_sub_points(client, sub_points)
        claims[claim_idx]["sub_points"] = new_sub_points

        stats["api_calls"] += 1
        stats["claims_migrated"] += 1
        stats["sub_points_migrated"] += len(sub_points)

        # Count quotes found
        quotes_found = sum(
            1 for sp in new_sub_points if isinstance(sp, dict) and sp.get("speaker")
        )
        print(f"done ({quotes_found} quotes extracted)")

    # Update version
    data["version"] = "2.2"

    # Save
    save_index(book_path, data)
    print(f"  Saved updated index")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Migrate sub_points to structured format"
    )
    parser.add_argument(
        "--apply", action="store_true", help="Apply changes (default is dry run)"
    )
    parser.add_argument("--book", type=str, help="Migrate single book by name")
    parser.add_argument("--estimate", action="store_true", help="Only estimate cost")
    args = parser.parse_args()

    dry_run = not args.apply

    if dry_run and not args.estimate:
        print("DRY RUN MODE - use --apply to make changes")

    # Find all index files
    index_files = sorted(INDEX_DIR.glob("*.json"))
    index_files = [
        f for f in index_files if not f.name.startswith("_")
    ]  # Skip _concepts.json

    if args.book:
        # Filter to single book
        matching = [f for f in index_files if args.book.lower() in f.stem.lower()]
        if not matching:
            print(f"No book found matching: {args.book}")
            sys.exit(1)
        index_files = matching

    print(f"Found {len(index_files)} book(s) to process")

    # Initialize client
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client = Anthropic(api_key=api_key)

    # Process each book
    all_stats = []
    total_tokens = 0

    for book_path in index_files:
        stats = migrate_book(client, book_path, dry_run=dry_run or args.estimate)
        all_stats.append(stats)
        total_tokens += stats["estimated_tokens"]

    # Summary
    print(f"\n{'=' * 60}")
    print("MIGRATION SUMMARY")
    print(f"{'=' * 60}")

    total_migrated = sum(s["claims_migrated"] for s in all_stats)
    total_api_calls = sum(s["api_calls"] for s in all_stats)

    print(f"Books processed: {len(all_stats)}")
    print(f"Claims migrated: {total_migrated}")
    print(f"API calls made: {total_api_calls}")
    print(f"Estimated tokens: ~{total_tokens:,}")

    # Cost estimate (Haiku: $0.25/1M input, $1.25/1M output)
    # Assume output is ~same size as input for this task
    estimated_cost = (total_tokens * 0.25 / 1_000_000) + (
        total_tokens * 1.25 / 1_000_000
    )
    print(f"Estimated cost: ~${estimated_cost:.2f}")

    if dry_run and not args.estimate:
        print(f"\nRun with --apply to perform migration")


if __name__ == "__main__":
    main()
