#!/usr/bin/env python3
"""
Integrity checks for cross-book claim/concept retrieval data.

Fails (exit 1) when structural issues are detected that can silently degrade
recall/precision across books.

Checks:
1) index/*.json claim IDs/counts match vectors.db by book
2) duplicate book slugs (e.g. spaced vs hyphen variants)
3) required vectors.db metadata columns exist
4) concept IDs used in index claims exist in _concepts.json
5) concept registry book refs point to existing indexed books

Usage:
    python3 scripts/check_integrity.py
    python3 scripts/check_integrity.py --allow-vector-drift
"""

import argparse
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
INDEX_DIR = PROJECT_ROOT / "index"
VECTORS_DB = INDEX_DIR / "vectors.db"
CONCEPTS_JSON = INDEX_DIR / "_concepts.json"


def load_index_books() -> dict[str, dict]:
    books = {}
    for path in sorted(INDEX_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        with open(path, encoding="utf-8") as f:
            books[path.stem] = json.load(f)
    return books


def canonical_slug(text: str) -> str:
    return re.sub(r"[-_\s]+", "", text.lower().strip())


def parse_json_field(raw, default):
    if raw in (None, ""):
        return default
    if isinstance(raw, (list, dict)):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return default


def main():
    parser = argparse.ArgumentParser(
        description="Validate index/vectors/concepts integrity."
    )
    parser.add_argument(
        "--allow-vector-drift",
        action="store_true",
        help=(
            "Downgrade vector parity failures to warnings. "
            "Useful when core ingest intentionally skips embeddings."
        ),
    )
    args = parser.parse_args()

    errors = []
    warnings = []

    if not VECTORS_DB.exists():
        print(f"ERROR: Missing vectors DB: {VECTORS_DB}")
        sys.exit(1)
    if not CONCEPTS_JSON.exists():
        print(f"ERROR: Missing concept registry: {CONCEPTS_JSON}")
        sys.exit(1)

    index_books = load_index_books()
    with open(CONCEPTS_JSON, encoding="utf-8") as f:
        concepts_payload = json.load(f)
    registry = concepts_payload.get("concepts", {})

    # 1) duplicate slug variants
    by_canonical = defaultdict(list)
    for book in index_books.keys():
        by_canonical[canonical_slug(book)].append(book)
    dup_groups = [sorted(v) for v in by_canonical.values() if len(v) > 1]
    if dup_groups:
        for group in dup_groups:
            errors.append(f"Duplicate slug variants present: {', '.join(group)}")

    # 2) index concept coverage + book refs
    index_concepts = set()
    empty_claims = []
    for book, payload in index_books.items():
        for claim in payload.get("claims", []):
            claim_id = claim.get("id", "")
            text = (claim.get("text") or "").strip()
            if not text:
                empty_claims.append((book, claim_id))
            for concept_id in claim.get("concepts", []):
                if concept_id:
                    index_concepts.add(concept_id)
    missing_from_registry = sorted(c for c in index_concepts if c not in registry)
    if missing_from_registry:
        sample = ", ".join(missing_from_registry[:20])
        suffix = "" if len(missing_from_registry) <= 20 else f" (+{len(missing_from_registry)-20} more)"
        errors.append(f"Concept IDs used in index but missing from registry: {sample}{suffix}")
    if empty_claims:
        sample = ", ".join(f"{b}:{cid}" for b, cid in empty_claims[:10])
        suffix = "" if len(empty_claims) <= 10 else f" (+{len(empty_claims)-10} more)"
        errors.append(f"Claims with empty text detected: {sample}{suffix}")

    known_books = set(index_books.keys())
    orphan_book_refs = []
    for cid, cdata in registry.items():
        refs = list((cdata.get("book_claims") or {}).keys())
        for ref in refs:
            if ref not in known_books:
                orphan_book_refs.append((cid, ref))
    if orphan_book_refs:
        sample = ", ".join(f"{cid}->{ref}" for cid, ref in orphan_book_refs[:20])
        suffix = "" if len(orphan_book_refs) <= 20 else f" (+{len(orphan_book_refs)-20} more)"
        warnings.append(f"Concept registry references unknown books: {sample}{suffix}")

    # 3) vectors DB parity + metadata columns
    conn = sqlite3.connect(VECTORS_DB)
    conn.row_factory = sqlite3.Row
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(claims)").fetchall()}
        required_cols = {
            "id",
            "book_name",
            "chapter_index",
            "claim_index",
            "embedding",
            "concepts_json",
            "entities_json",
            "sub_points_json",
            "embedding_text",
        }
        missing_cols = sorted(required_cols - cols)
        if missing_cols:
            errors.append(f"claims table missing required columns: {', '.join(missing_cols)}")

        db_books = {
            row["book_name"]: row["count"]
            for row in conn.execute(
                "SELECT book_name, COUNT(*) AS count FROM claims GROUP BY book_name"
            ).fetchall()
        }
        extra_db_books = sorted(set(db_books.keys()) - known_books)
        if extra_db_books:
            message = (
                f"vectors.db contains books missing from index/: {', '.join(extra_db_books)}"
            )
            if args.allow_vector_drift:
                warnings.append(message)
            else:
                errors.append(message)

        mismatch_books = []
        for book, payload in index_books.items():
            index_ids = {c.get("id") for c in payload.get("claims", []) if c.get("id")}
            db_ids = {
                row["id"]
                for row in conn.execute(
                    "SELECT id FROM claims WHERE book_name = ?",
                    (book,),
                ).fetchall()
            }
            if index_ids != db_ids:
                mismatch_books.append(
                    (
                        book,
                        len(index_ids),
                        len(db_ids),
                        len(index_ids - db_ids),
                        len(db_ids - index_ids),
                    )
                )
        if mismatch_books:
            sample = ", ".join(
                f"{b}(index={i},db={d},missing={m},extra={e})"
                for b, i, d, m, e in mismatch_books[:20]
            )
            suffix = "" if len(mismatch_books) <= 20 else f" (+{len(mismatch_books)-20} more)"
            message = f"Index/vector ID parity failures: {sample}{suffix}"
            if args.allow_vector_drift:
                warnings.append(message)
            else:
                errors.append(message)

        # Spot-check metadata coverage in DB rows.
        meta_null_count = conn.execute(
            """
            SELECT COUNT(*) FROM claims
            WHERE concepts_json IS NULL OR concepts_json = ''
               OR entities_json IS NULL OR entities_json = ''
               OR sub_points_json IS NULL OR sub_points_json = ''
            """
        ).fetchone()[0]
        if meta_null_count > 0:
            warnings.append(f"{meta_null_count} claim rows missing JSON metadata fields")

        # Validate DB concept IDs against registry.
        unknown_db_concepts = set()
        for row in conn.execute("SELECT concepts_json FROM claims"):
            concepts = parse_json_field(row["concepts_json"], [])
            if isinstance(concepts, list):
                for cid in concepts:
                    if cid and cid not in registry:
                        unknown_db_concepts.add(cid)
        if unknown_db_concepts:
            sample = ", ".join(sorted(unknown_db_concepts)[:20])
            suffix = (
                ""
                if len(unknown_db_concepts) <= 20
                else f" (+{len(unknown_db_concepts)-20} more)"
            )
            errors.append(f"DB concepts missing from registry: {sample}{suffix}")
    finally:
        conn.close()

    print("=== Integrity Check ===")
    print(f"Indexed books: {len(index_books)}")
    print(f"Registry concepts: {len(registry)}")

    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"- {w}")

    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"- {e}")
        print("\nFAIL: integrity check failed.")
        sys.exit(1)

    print("\nPASS: integrity check passed.")


if __name__ == "__main__":
    main()
