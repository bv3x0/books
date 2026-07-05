#!/usr/bin/env python3
"""
CLI entry point for book processing quality and cost evaluation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.evaluation_service import BookEvaluator


def load_fidelity_report(book_name: str) -> dict | None:
    report_path = PROJECT_ROOT / "app" / "logs" / f"{book_name}_fidelity.json"
    if not report_path.exists():
        return None
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
    report["path"] = str(report_path)
    return report


def render_notes_report(metrics: dict) -> None:
    print("NOTES QUALITY ASSESSMENT")
    print("-" * 70)
    print(f"File size:        {metrics['file_size_kb']:.1f} KB")
    print(f"Total words:      {metrics['total_words']:,}")
    print(f"Total chapters:   {metrics['headings']['h3']}")
    print(f"Avg words/ch:     {metrics['avg_words_per_chapter']:.0f}")
    print("\nStructure:")
    print(f"  H1 (title):     {metrics['headings']['h1']}")
    print(f"  H2 (sections):  {metrics['headings']['h2']}")
    print(f"  H3 (chapters):  {metrics['headings']['h3']}")
    print(
        f"\nQuality Score:    {metrics['quality_indicators']['completeness_score'] * 100:.0f}%"
    )
    print(f"  ✓ Metadata:     {metrics['quality_indicators']['has_metadata_section']}")
    print(f"  ✓ Thesis:       {metrics['quality_indicators']['has_thesis']}")
    print(f"  ✓ Topics:       {metrics['quality_indicators']['has_topics']}")
    print(f"  ✓ Categories:   {metrics['quality_indicators']['has_categories']}")
    print(f"\nReadability:      {metrics['readability']['readability_rating']}")
    print()


def render_index_report(metrics: dict) -> None:
    print("INDEX QUALITY ASSESSMENT")
    print("-" * 70)
    print(f"File size:        {metrics['file_size_kb']:.1f} KB")
    print(f"Pipeline version: {metrics['pipeline_version']}")
    print("\nStructure:")
    print(f"  Chapters:       {metrics['chapters']}")
    print(f"  Total claims:   {metrics['claims']['total']}")
    print(f"  Avg claims/ch:  {metrics['claims']['avg_per_chapter']:.1f}")
    print("\nConcepts:")
    print(f"  Total mentions: {metrics['concepts']['total_mentions']}")
    print(f"  Unique:         {metrics['concepts']['unique_count']}")
    print(f"  Avg per claim:  {metrics['concepts']['avg_per_claim']:.1f}")
    print("\nTop concepts:")
    for concept, count in metrics["concepts"]["most_common"][:3]:
        print(f"    • {concept}: {count}")
    print("\nEntities:")
    print(f"  Total mentions: {metrics['entities']['total_mentions']}")
    print(f"  Unique:         {metrics['entities']['unique_count']}")
    print(f"\nQuality Score:    {metrics['quality_score'] * 100:.0f}%")
    print()


def render_embeddings_report(metrics: dict) -> None:
    print("EMBEDDINGS QUALITY ASSESSMENT")
    print("-" * 70)
    print(f"Database size:    {metrics['db_size_kb']:.1f} KB")
    print("\nClaims:")
    print(f"  Count:          {metrics['claims']['count']}")
    print(f"  Dimensions:     {metrics['claims']['dimensions']}")
    print(f"\nConcepts (total): {metrics['concepts_total']}")
    if "sample_embedding" in metrics:
        print("\nSample Embedding Quality:")
        print(f"  Non-zero ratio: {metrics['sample_embedding']['non_zero_ratio']:.1%}")
        print(
            f"  Value range:    [{metrics['sample_embedding']['min']:.3f}, {metrics['sample_embedding']['max']:.3f}]"
        )
    print(f"\nQuality Score:    {metrics['quality_score'] * 100:.0f}%")
    for check, passed in metrics["quality_checks"].items():
        print(f"  ✓ {check.replace('_', ' ').title()}: {passed}")
    print()


def render_cost_report(metrics: dict) -> None:
    print("COST ANALYSIS")
    print("-" * 70)
    print("Claude API:")
    print(f"  Input tokens:   {metrics['tokens']['claude_input']:,}")
    print(f"  Output tokens:  {metrics['tokens']['claude_output']:,}")
    print(f"  Cost:           ${metrics['costs']['claude']:.4f}")
    print("\nOpenAI API (embeddings):")
    print(f"  Est. tokens:    {metrics['tokens']['openai_embedding']:,}")
    print(f"  Cost:           ${metrics['costs']['openai']:.4f}")
    print(f"\n{'─' * 70}")
    print(f"TOTAL COST:       ${metrics['costs']['total']:.4f}")
    print()


def render_overall_report(metrics: dict) -> None:
    print("OVERALL ASSESSMENT")
    print("-" * 70)
    print(f"Overall Score:    {metrics['score'] * 100:.0f}%")
    print(f"Rating:           {metrics['rating']}")
    print()


def render_fidelity_report(report: dict | None) -> None:
    print("FIDELITY REPORT")
    print("-" * 70)
    if not report:
        print("  No fidelity report found.\n")
        return

    summary = report.get("summary") or {}
    print(f"Report:          {report.get('path')}")
    print(f"Hard failures:   {report.get('hard_failures', 0)}")
    if summary:
        print("\nFindings:")
        for finding_type, count in summary.items():
            print(f"  {finding_type}: {count}")
    else:
        print("\nFindings:        none")

    offenders = [
        chunk for chunk in report.get("chunks", []) if chunk.get("findings")
    ][:5]
    if offenders:
        print("\nChunks with findings:")
        for chunk in offenders:
            filename = chunk.get("filename") or f"chunk {chunk.get('index')}"
            print(f"  {filename}: {len(chunk.get('findings') or [])}")
    print()


def render_concept_health(metrics: dict) -> None:
    print("CONCEPT REGISTRY HEALTH")
    print("-" * 70)
    if not metrics:
        print("  No concept registry data available.\n")
        return

    print(f"Total concepts:       {metrics['total_concepts']:,}")
    print(
        f"Singletons (1 book):  {metrics['singleton_count']:,} ({metrics['singleton_rate']:.1%})"
    )
    print(
        f"Multi-book concepts:  {metrics['multi_book_count']:,} ({1 - metrics['singleton_rate']:.1%})"
    )
    print("\nBooks-per-concept distribution:")
    for n_books in sorted(metrics["distribution"].keys())[:15]:
        count = metrics["distribution"][n_books]
        bar = "#" * min(count // 20, 50)
        print(f"  {n_books:>3} book(s): {count:>5}  {bar}")

    total = metrics["total_concepts"]
    print("\nField population:")
    print(f"  aliases:      {metrics['has_aliases']:>5} / {total} ({metrics['has_aliases']/total:.0%})")
    print(f"  related:      {metrics['has_related']:>5} / {total} ({metrics['has_related']/total:.0%})")
    print(f"  broader:      {metrics['has_broader']:>5} / {total} ({metrics['has_broader']/total:.0%})")
    print(
        f"  description:  {metrics['has_description']:>5} / {total} ({metrics['has_description']/total:.0%})"
    )

    print("\nTop concepts by book count:")
    for item in metrics["top_by_books"]:
        print(
            f"  {item['concept_id']:40s}  {item['book_count']:>2} books, {item['claim_count']:>4} claims"
        )

    if metrics.get("embedded_count") is not None:
        print(
            f"\nEmbeddings: {metrics['embedded_count']:,} / {metrics['total_concepts']:,} concepts have embeddings"
        )
        if metrics["embedded_count"] < metrics["total_concepts"]:
            missing = metrics["total_concepts"] - metrics["embedded_count"]
            print(f"  ({missing} missing — run analyze_concepts.py for cluster analysis)")
    print()


def render_report(book_name: str, evaluator: BookEvaluator, results: dict, include_concepts: bool) -> None:
    print(f"\n{'=' * 70}")
    print(f"EVALUATION REPORT: {book_name}")
    print(f"{'=' * 70}\n")

    if evaluator.notes_path.exists():
        render_notes_report(results["notes"])
    else:
        print(f"Notes file not found: {evaluator.notes_path}\n")

    if evaluator.index_path.exists():
        render_index_report(results["index"])
    else:
        print(f"Index file not found: {evaluator.index_path}\n")

    if evaluator.vectors_db.exists():
        render_embeddings_report(results["embeddings"])
    else:
        print(f"Vector database not found: {evaluator.vectors_db}\n")

    render_cost_report(results["cost"])
    render_overall_report(results["overall"])
    render_fidelity_report(results.get("fidelity"))

    if include_concepts:
        render_concept_health(results.get("concept_health", {}))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate book processing quality and costs")
    parser.add_argument("book_name", help="Name of the book to evaluate")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument(
        "--concepts",
        action="store_true",
        help="Include global concept registry health metrics",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    evaluator = BookEvaluator(args.book_name)
    results = evaluator.evaluate_all()
    results["fidelity"] = load_fidelity_report(args.book_name)

    if args.concepts:
        results["concept_health"] = evaluator.evaluate_concept_health()

    if args.json:
        print(json.dumps(results, indent=2))
        return 0

    render_report(args.book_name, evaluator, results, include_concepts=args.concepts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
