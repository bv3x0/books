#!/usr/bin/env python3
"""
Concept clustering analysis and merge tool.

Analyzes concept embeddings from vectors.db to find near-duplicates,
report quality metrics, and optionally merge similar concepts.

Usage:
    python3 scripts/analyze_concepts.py                    # Analyze and report
    python3 scripts/analyze_concepts.py --threshold 0.85   # Custom similarity threshold
    python3 scripts/analyze_concepts.py merge --dry-run    # Preview proposed merges
    python3 scripts/analyze_concepts.py merge --apply      # Execute merges
"""

import argparse
import json
import sqlite3
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import CONCEPTS_PATH, INDEX_DIR, VECTORS_DB_PATH


def load_concept_embeddings(db_path: str) -> tuple[list[str], np.ndarray]:
    """
    Load all concept embeddings from vectors.db.

    Returns:
        (concept_ids, embedding_matrix) where embedding_matrix is (N, dims)
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.execute(
        "SELECT id, embedding FROM concepts WHERE embedding IS NOT NULL"
    )

    ids = []
    vectors = []
    for concept_id, embedding_blob in cursor:
        num_floats = len(embedding_blob) // 4
        vec = struct.unpack(f"{num_floats}f", embedding_blob)
        ids.append(concept_id)
        vectors.append(vec)

    conn.close()

    if not ids:
        return [], np.array([])

    return ids, np.array(vectors, dtype=np.float32)


def compute_similarity_matrix(embeddings: np.ndarray) -> np.ndarray:
    """
    Compute pairwise cosine similarity using numpy.

    For 7k concepts this takes ~1 second instead of hours in pure Python.
    """
    # Normalize rows to unit length
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)  # avoid division by zero
    normalized = embeddings / norms

    # Cosine similarity = dot product of normalized vectors
    return normalized @ normalized.T


def find_merge_pairs(
    concept_ids: list[str],
    sim_matrix: np.ndarray,
    threshold: float,
    registry: dict,
) -> list[dict]:
    """
    Find merge candidates as directed pairs (source -> target).

    For each concept above threshold with another, proposes merging the
    less-used concept into the more-used one. Each source concept maps to
    its single best target (no transitive chaining).

    Returns list of {source, target, similarity} dicts.
    """
    n = len(concept_ids)

    def concept_weight(cid: str) -> tuple[int, int]:
        """(n_books, n_claims) — higher = more canonical."""
        cdata = registry.get(cid, {})
        bc = cdata.get("book_claims", {})
        n_books = len(bc) if bc else len(cdata.get("books", []))
        n_claims = sum(bc.values()) if bc else cdata.get("claim_count", 0)
        return (n_books, n_claims)

    # For each concept, find its best match above threshold
    # that has higher weight (more books/claims)
    best_target = {}  # source_id -> (target_id, similarity)

    for i in range(n):
        weight_i = concept_weight(concept_ids[i])
        best_sim = 0
        best_j = None

        for j in range(n):
            if i == j:
                continue
            sim = float(sim_matrix[i, j])
            if sim < threshold:
                continue

            weight_j = concept_weight(concept_ids[j])

            # Merge i into j if j has more weight, or equal weight but earlier alphabetically
            if weight_j > weight_i or (weight_j == weight_i and concept_ids[j] < concept_ids[i]):
                if sim > best_sim:
                    best_sim = sim
                    best_j = j

        if best_j is not None:
            best_target[concept_ids[i]] = (concept_ids[best_j], best_sim)

    # Convert to list of pairs
    pairs = []
    for source, (target, sim) in sorted(best_target.items()):
        pairs.append({
            "source": source,
            "target": target,
            "similarity": round(float(sim), 4),
        })

    return pairs


def find_related_pairs(
    concept_ids: list[str],
    sim_matrix: np.ndarray,
    low: float,
    high: float,
) -> list[dict]:
    """Find concept pairs in the 'related but not duplicate' similarity range."""
    n = len(concept_ids)
    pairs = []

    # Only check upper triangle
    for i in range(n):
        for j in range(i + 1, n):
            sim = float(sim_matrix[i, j])
            if low <= sim < high:
                pairs.append({
                    "a": concept_ids[i],
                    "b": concept_ids[j],
                    "similarity": round(sim, 4),
                })

    pairs.sort(key=lambda x: x["similarity"], reverse=True)
    return pairs


def load_concept_registry(path: str) -> dict:
    """Load concept registry from JSON."""
    with open(path) as f:
        data = json.load(f)
    return data.get("concepts", {})


def concept_info(cid: str, registry: dict) -> str:
    """Format concept info for display."""
    cdata = registry.get(cid, {})
    bc = cdata.get("book_claims", {})
    n_books = len(bc) if bc else len(cdata.get("books", []))
    n_claims = sum(bc.values()) if bc else cdata.get("claim_count", 0)
    return f"{cid:40s}  {n_books:>2} books, {n_claims:>3} claims"


def analyze(args):
    """Run analysis and produce report of merge candidates."""
    threshold = args.threshold

    print(f"\n{'=' * 70}")
    print("CONCEPT CLUSTERING ANALYSIS")
    print(f"{'=' * 70}\n")

    # Load data
    if not os.path.exists(VECTORS_DB_PATH):
        print(f"Error: Vector database not found at {VECTORS_DB_PATH}")
        sys.exit(1)
    if not os.path.exists(CONCEPTS_PATH):
        print(f"Error: Concept registry not found at {CONCEPTS_PATH}")
        sys.exit(1)

    print("Loading data...")
    concept_ids, embeddings = load_concept_embeddings(VECTORS_DB_PATH)
    print(f"  {len(concept_ids)} concept embeddings from vectors.db")

    registry = load_concept_registry(CONCEPTS_PATH)
    print(f"  {len(registry)} concepts from _concepts.json")

    missing = set(registry.keys()) - set(concept_ids)
    if missing:
        print(f"  {len(missing)} concepts have no embeddings (skipped in similarity analysis)")

    # --- Registry overview ---
    print(f"\n{'─' * 70}")
    print("REGISTRY OVERVIEW")
    print(f"{'─' * 70}")

    total_concepts = len(registry)
    books_counts = []
    for cdata in registry.values():
        bc = cdata.get("book_claims", {})
        books_counts.append(len(bc) if bc else len(cdata.get("books", [])))

    singletons = sum(1 for b in books_counts if b <= 1)
    singleton_rate = singletons / total_concepts if total_concepts else 0

    print(f"Total concepts:      {total_concepts:,}")
    print(f"Singletons (1 book): {singletons:,} ({singleton_rate:.1%})")
    print(f"Multi-book:          {total_concepts - singletons:,} ({1 - singleton_rate:.1%})")

    dist = Counter(books_counts)
    print(f"\nBooks-per-concept distribution:")
    for n_books in sorted(dist.keys())[:10]:
        count = dist[n_books]
        bar = "#" * min(count // 50, 60)
        print(f"  {n_books:>3} book(s): {count:>5}  {bar}")
    if max(dist.keys()) > 10:
        remaining = sum(v for k, v in dist.items() if k > 10)
        print(f"  >10 books: {remaining:>5}")

    # --- Similarity computation ---
    print(f"\n{'─' * 70}")
    print(f"SIMILARITY ANALYSIS (threshold={threshold})")
    print(f"{'─' * 70}")

    if len(concept_ids) == 0:
        print("No embeddings to analyze.")
        return

    print(f"Computing {len(concept_ids):,} x {len(concept_ids):,} similarity matrix...")
    sim_matrix = compute_similarity_matrix(embeddings)
    print("  Done.")

    # --- Merge candidates (pairs, not clusters) ---
    print(f"\nFinding merge candidates...")
    merge_pairs = find_merge_pairs(concept_ids, sim_matrix, threshold, registry)
    print(f"Found {len(merge_pairs)} merge candidates\n")

    # Group by target for display
    by_target = defaultdict(list)
    for pair in merge_pairs:
        by_target[pair["target"]].append(pair)

    # Sort groups by size descending
    groups = sorted(by_target.items(), key=lambda x: len(x[1]), reverse=True)

    for i, (target, pairs) in enumerate(groups[:40]):
        print(f"  Target: {concept_info(target, registry)}")
        for p in sorted(pairs, key=lambda x: x["similarity"], reverse=True):
            print(f"    <- {p['source']:40s}  (sim={p['similarity']:.3f})")
        print()

    if len(groups) > 40:
        print(f"  ... and {len(groups) - 40} more groups (see JSON output)\n")

    # --- Related pairs ---
    print(f"{'─' * 70}")
    print(f"RELATED PAIRS (similarity {threshold - 0.10:.2f} - {threshold:.2f})")
    print(f"{'─' * 70}")

    related = find_related_pairs(concept_ids, sim_matrix, threshold - 0.10, threshold)
    print(f"Found {len(related)} related pairs")
    for p in related[:20]:
        print(f"  {p['a']:35s} <-> {p['b']:35s}  ({p['similarity']:.3f})")
    if len(related) > 20:
        print(f"  ... and {len(related) - 20} more")

    # --- Summary ---
    print(f"\n{'─' * 70}")
    print("SUMMARY")
    print(f"{'─' * 70}")
    print(f"Total concepts:        {total_concepts:,}")
    print(f"Singleton rate:        {singleton_rate:.1%}")
    print(f"Merge candidates:      {len(merge_pairs)}")
    print(f"After merge estimate:  {total_concepts - len(merge_pairs):,}")
    print(f"Related pairs:         {len(related)}")

    # --- Save JSON ---
    output = {
        "analysis": {
            "total_concepts": total_concepts,
            "concepts_with_embeddings": len(concept_ids),
            "singleton_count": singletons,
            "singleton_rate": round(singleton_rate, 4),
            "threshold": threshold,
            "merge_candidate_count": len(merge_pairs),
        },
        "merge_pairs": merge_pairs,
        "related_pairs": related,
    }

    output_path = os.path.join(project_root, "concept_analysis.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved analysis to {output_path}")


def merge(args):
    """Merge near-duplicate concepts based on analysis output."""
    analysis_path = os.path.join(project_root, "concept_analysis.json")

    if not os.path.exists(analysis_path):
        print("Error: No concept_analysis.json found. Run analysis first:")
        print("  python3 scripts/analyze_concepts.py")
        sys.exit(1)

    with open(analysis_path) as f:
        analysis = json.load(f)

    merge_pairs = analysis.get("merge_pairs", [])
    related_pairs = analysis.get("related_pairs", [])

    if not merge_pairs:
        print("No merge candidates found in analysis.")
        return

    dry_run = not args.apply

    print(f"\n{'=' * 70}")
    print(f"CONCEPT MERGE {'(DRY RUN)' if dry_run else '(APPLYING)'}")
    print(f"{'=' * 70}\n")
    print(f"Merge candidates: {len(merge_pairs)}")

    if dry_run:
        print("\nDry run — showing what would change:\n")

    # Load concept registry
    with open(CONCEPTS_PATH) as f:
        registry_data = json.load(f)
    concepts = registry_data.get("concepts", {})

    # Execute merges
    merge_count = 0
    redirect_map = {}  # old_id -> canonical_id

    for pair in merge_pairs:
        source = pair["source"]
        target = pair["target"]
        sim = pair["similarity"]

        # Resolve target through existing redirects (in case target was itself merged)
        while target in redirect_map:
            target = redirect_map[target]

        if source not in concepts or target not in concepts:
            continue

        redirect_map[source] = target

        if dry_run:
            print(f"  {source:40s} -> {target:30s}  (sim={sim:.3f})")
        else:
            source_data = concepts[source]
            target_data = concepts[target]

            # Merge aliases
            aliases = set(target_data.get("aliases", []))
            aliases.add(source)
            for a in source_data.get("aliases", []):
                aliases.add(a)
            target_data["aliases"] = sorted(aliases)

            # Merge book_claims
            for book, count in source_data.get("book_claims", {}).items():
                target_claims = target_data.get("book_claims", {})
                target_claims[book] = target_claims.get(book, 0) + count
                target_data["book_claims"] = target_claims

            # Update computed fields
            target_data["books"] = list(target_data.get("book_claims", {}).keys())
            target_data["claim_count"] = sum(target_data.get("book_claims", {}).values())

            del concepts[source]

        merge_count += 1

    print(f"\n{'─' * 70}")
    print(f"Merges: {merge_count}")

    # Populate related fields
    related_count = 0
    for pair in related_pairs:
        a = pair["a"]
        b = pair["b"]
        # Resolve through redirects
        while a in redirect_map:
            a = redirect_map[a]
        while b in redirect_map:
            b = redirect_map[b]
        if a == b or a not in concepts or b not in concepts:
            continue

        if not dry_run:
            a_rel = set(concepts[a].get("related", []))
            b_rel = set(concepts[b].get("related", []))
            a_rel.add(b)
            b_rel.add(a)
            concepts[a]["related"] = sorted(a_rel)
            concepts[b]["related"] = sorted(b_rel)
        related_count += 1

    print(f"Related links: {related_count}")

    if dry_run:
        print(f"\nTo apply, run:")
        print(f"  python3 scripts/analyze_concepts.py merge --apply")
        return

    # Save updated registry
    registry_data["concepts"] = concepts
    registry_data["stats"] = {
        "total_concepts": len(concepts),
        "total_claims": sum(
            c.get("claim_count", sum(c.get("book_claims", {}).values()))
            for c in concepts.values()
        ),
        "books_indexed": len(
            set(
                b
                for c in concepts.values()
                for b in c.get("books", list(c.get("book_claims", {}).keys()))
            )
        ),
    }

    with open(CONCEPTS_PATH, "w") as f:
        json.dump(registry_data, f, indent=2)
    print(f"\nSaved registry to {CONCEPTS_PATH}")

    # Update index JSON files
    if redirect_map:
        print(f"Updating index files...")
        index_dir = Path(INDEX_DIR)
        updated_files = 0

        for json_file in sorted(index_dir.glob("*.json")):
            if json_file.name.startswith("_"):
                continue

            with open(json_file) as f:
                index_data = json.load(f)

            changed = False
            for claim in index_data.get("claims", []):
                new_concepts = []
                for concept in claim.get("concepts", []):
                    redirected = redirect_map.get(concept, concept)
                    new_concepts.append(redirected)
                if new_concepts != claim.get("concepts", []):
                    claim["concepts"] = new_concepts
                    changed = True

            if changed:
                with open(json_file, "w") as f:
                    json.dump(index_data, f, indent=2)
                updated_files += 1

        print(f"Updated {updated_files} index files")

    # Clean up orphaned concepts from vectors.db
    if redirect_map and os.path.exists(VECTORS_DB_PATH):
        print(f"Cleaning up vectors.db...")
        conn = sqlite3.connect(VECTORS_DB_PATH)
        deleted_ids = list(redirect_map.keys())
        # Delete in batches to avoid overly long SQL
        removed = 0
        for i in range(0, len(deleted_ids), 500):
            batch = deleted_ids[i : i + 500]
            placeholders = ",".join("?" * len(batch))
            cursor = conn.execute(
                f"DELETE FROM concepts WHERE id IN ({placeholders})", batch
            )
            removed += cursor.rowcount
        conn.commit()
        conn.close()
        print(f"Removed {removed} orphaned concept embeddings from vectors.db")

    print(f"\nMerge complete.")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze and merge near-duplicate concepts"
    )
    subparsers = parser.add_subparsers(dest="command")

    # Default: analyze
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.80,
        help="Cosine similarity threshold (default: 0.80)",
    )

    # Merge subcommand
    merge_parser = subparsers.add_parser("merge", help="Merge near-duplicate concepts")
    merge_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview changes without applying (default)",
    )
    merge_parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the merges",
    )

    args = parser.parse_args()

    if args.command == "merge":
        merge(args)
    else:
        analyze(args)


if __name__ == "__main__":
    main()
