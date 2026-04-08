#!/usr/bin/env python3
"""
CLI entry point for semantic search and concept exploration.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.query_service import (
    compare_books,
    compute_book_overlap,
    get_book_concepts,
    run_self_test,
    search_claims,
    search_concepts,
)


def render_claim_results(query: str, total_claims: int, results, book_filter: str | None) -> None:
    print(f"\n{'=' * 60}")
    print(f'CLAIM SEARCH: "{query}"')
    if book_filter:
        print(f"Filtered to: {book_filter}")
    print(f"{'=' * 60}\n")
    print(f"Searching {total_claims} claims...\n")

    if not results:
        print("No results found.")
        return

    for i, result in enumerate(results, 1):
        print(f"[{i}] Score: {result.score:.4f}")
        print(f"    Book: {result.book_title} ({result.author})")
        print(f"    Chapter: {result.chapter}")
        print(f"    Claim ID: {result.claim_id}")
        preview = result.claim_text[:200]
        if len(result.claim_text) > 200:
            preview += "..."
        print(f"    Text: {preview}")
        if result.concepts:
            suffix = "..." if len(result.concepts) > 5 else ""
            print(f"    Concepts: {', '.join(result.concepts[:5])}{suffix}")
        print()


def render_concept_results(query: str, total_concepts: int, results) -> None:
    print(f"\n{'=' * 60}")
    print(f'CONCEPT SEARCH: "{query}"')
    print(f"{'=' * 60}\n")
    print(f"Searching {total_concepts} concepts...\n")

    if not results:
        print("No results found.")
        return

    for i, result in enumerate(results, 1):
        print(f"[{i}] Score: {result.score:.4f}")
        print(f"    Concept: {result.label} ({result.concept_id})")
        print(f"    Claim count: {result.claim_count}")
        suffix = "..." if len(result.books) > 5 else ""
        print(f"    Books: {', '.join(result.books[:5])}{suffix}")
        if result.aliases:
            print(f"    Aliases: {', '.join(result.aliases[:3])}")
        print()


def render_book_overlap(top_k: int) -> None:
    overlaps = compute_book_overlap(top_k=top_k)
    print(f"\n{'=' * 60}")
    print("BOOK SIMILARITY BY SHARED CONCEPTS")
    print(f"{'=' * 60}\n")

    book_count = len(get_book_concepts())
    if book_count < 2:
        print("Need at least 2 books for overlap analysis.")
        return

    print(f"Found {len(overlaps)} book pairs with shared concepts.\n")
    print(f"Top {top_k} most related book pairs:\n")

    for i, overlap in enumerate(overlaps, 1):
        print(
            f"[{i}] {overlap.shared_count} shared concepts (Jaccard: {overlap.jaccard:.2f})"
        )
        print(f"    {overlap.title1}")
        print(f"    {overlap.title2}")
        suffix = "..." if len(overlap.shared_concepts) > 5 else ""
        print(f"    Shared: {', '.join(overlap.shared_concepts[:5])}{suffix}")
        print()


def render_book_comparison(book1: str, book2: str) -> int:
    comparison, missing = compare_books(book1, book2)
    if not comparison:
        print(f"Book not found: {missing}")
        print(f"Available books: {', '.join(sorted(get_book_concepts().keys()))}")
        return 1

    print(f"\n{'=' * 60}")
    print(f"COMPARING: {book1} vs {book2}")
    print(f"{'=' * 60}\n")
    print(f"Book 1: {comparison.title1} ({comparison.concepts1_count} concepts)")
    print(f"Book 2: {comparison.title2} ({comparison.concepts2_count} concepts)")
    print()

    print(f"SHARED CONCEPTS ({len(comparison.shared)}):")
    print("-" * 40)
    for concept in comparison.shared:
        print(f"  • {concept}")
    print()

    print(f"ONLY IN '{comparison.title1}' ({len(comparison.only1)}):")
    print("-" * 40)
    for concept in comparison.only1[:20]:
        print(f"  • {concept}")
    if len(comparison.only1) > 20:
        print(f"  ... and {len(comparison.only1) - 20} more")
    print()

    print(f"ONLY IN '{comparison.title2}' ({len(comparison.only2)}):")
    print("-" * 40)
    for concept in comparison.only2[:20]:
        print(f"  • {concept}")
    if len(comparison.only2) > 20:
        print(f"  ... and {len(comparison.only2) - 20} more")
    return 0


def render_self_test() -> int:
    try:
        result = run_self_test()
    except Exception as e:
        print(f"Query self-test failed: {e}")
        return 1

    print(f"\n{'=' * 60}")
    print("QUERY SYSTEM TEST SUITE")
    print(f"{'=' * 60}\n")
    print(f"Claims in vectors DB: {result.claim_count}")
    print(f"Concepts in vectors DB: {result.concept_count}")
    print(f"Embedding dimensions: {result.embedding_dimensions}")
    if result.sample_books:
        print(f"Sample books: {', '.join(result.sample_books)}")
    print("\nALL TESTS PASSED")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Query semantic search across book summaries")
    parser.add_argument("query", nargs="?", help="Search query text")
    parser.add_argument("--book", "-b", help="Filter results to a specific book")
    parser.add_argument(
        "--concepts",
        "-c",
        action="store_true",
        help="Search concepts instead of claims",
    )
    parser.add_argument(
        "--overlap",
        "-o",
        action="store_true",
        help="Show book similarity by shared concepts",
    )
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("BOOK1", "BOOK2"),
        help="Compare concepts between two books",
    )
    parser.add_argument(
        "--top",
        "-k",
        type=int,
        default=10,
        help="Number of results to return (default: 10)",
    )
    parser.add_argument("--test", "-t", action="store_true", help="Run test suite")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.test:
        return render_self_test()

    if args.overlap:
        render_book_overlap(top_k=args.top)
        return 0

    if args.compare:
        return render_book_comparison(args.compare[0], args.compare[1])

    if not args.query:
        parser.print_help()
        return 1

    if args.concepts:
        total, results = search_concepts(args.query, top_k=args.top)
        render_concept_results(args.query, total, results)
    else:
        total, results = search_claims(args.query, top_k=args.top, book_filter=args.book)
        render_claim_results(args.query, total, results, args.book)

    return 0


if __name__ == "__main__":
    sys.exit(main())
