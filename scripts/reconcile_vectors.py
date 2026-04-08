#!/usr/bin/env python3
"""
Reconcile index JSON claims with vectors.db without rerunning summarization.

Use this to repair legacy ID drift and metadata loss at low cost:
- Reuses existing claim/quote embeddings from vectors.db
- Rewrites rows to current index claim IDs + metadata
- Updates concept registry counts per repaired book

Default mode is audit-only (no writes).

Usage:
    python3 scripts/reconcile_vectors.py
    python3 scripts/reconcile_vectors.py --book introduction-to-christianity
    python3 scripts/reconcile_vectors.py --apply
    python3 scripts/reconcile_vectors.py --apply --book reality-of-being
"""

import argparse
import json
import os
import sqlite3
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

from dotenv import load_dotenv

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables from app/.env
load_dotenv(PROJECT_ROOT / "app" / ".env")

from app.config import (
    CONCEPTS_PATH,
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    INDEX_DIR,
    VECTORS_DB_PATH,
)
from app.core.concept_registry import Concept, ConceptRegistry
from app.core.embedder import Embedder
from app.core.vector_store import VectorStore


def normalize_text(text: str) -> str:
    """Canonicalize text for fuzzy-equivalent matching."""
    return " ".join((text or "").lower().split())


def deserialize_vector(blob: bytes) -> list[float]:
    """Deserialize SQLite BLOB embedding to float vector."""
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))


def load_index_books(book_filters: list[str] | None = None) -> dict[str, dict]:
    """Load index JSON books, optionally filtered by substring matches."""
    data = {}
    for path in sorted(Path(INDEX_DIR).glob("*.json")):
        if path.name.startswith("_"):
            continue
        book = path.stem
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
        data[book] = payload

    if not book_filters:
        return data

    selected = {}
    filters = [f.lower() for f in book_filters]
    for book, payload in data.items():
        title = (payload.get("book", {}) or {}).get("title", "")
        key = f"{book} {title}".lower()
        if any(f in key for f in filters):
            selected[book] = payload
    return selected


def build_index_claim_records(index_payload: dict) -> list[dict]:
    """
    Build index claim records with chapter/position coordinates.

    Coordinates are derived from `chapters[].claim_ids` for deterministic ordering.
    """
    chapter_lookup = {}
    for chapter_idx, chapter in enumerate(index_payload.get("chapters", [])):
        for claim_pos, claim_id in enumerate(chapter.get("claim_ids", [])):
            chapter_lookup[claim_id] = (chapter_idx, claim_pos)

    records = []
    for claim in index_payload.get("claims", []):
        claim_id = claim.get("id")
        chapter_idx, claim_pos = chapter_lookup.get(claim_id, (0, 0))
        records.append(
            {
                "id": claim_id,
                "text": claim.get("text", ""),
                "chapter": claim.get("chapter", ""),
                "part": claim.get("part", ""),
                "concepts": claim.get("concepts", []),
                "entities": claim.get("entities", {}),
                "sub_points": claim.get("sub_points", []),
                "chapter_index": chapter_idx,
                "claim_index": claim_pos,
            }
        )

    records.sort(key=lambda c: (c["chapter_index"], c["claim_index"]))
    return records


def load_db_claims(conn: sqlite3.Connection, book: str) -> list[dict]:
    """Load claim rows from vectors DB for one book."""
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM claims WHERE book_name = ?", (book,)).fetchall()
    claims = [dict(row) for row in rows]
    claims.sort(key=lambda c: (c.get("chapter_index", 0), c.get("claim_index", 0), c["id"]))
    return claims


def load_db_quotes(conn: sqlite3.Connection, book: str) -> list[dict]:
    """Load quote rows from vectors DB for one book."""
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM quotes WHERE book_name = ?", (book,)).fetchall()
    return [dict(row) for row in rows]


def match_claims(index_claims: list[dict], db_claims: list[dict]) -> tuple[list[tuple[dict, dict]], list[dict], list[dict]]:
    """
    Match index claims to DB rows so embeddings can be reused safely.

    Matching strategy:
    1) exact ID
    2) exact normalized text
    3) chapter queue by order
    4) global order fallback if remaining sizes match
    """
    mapping: list[tuple[dict, dict]] = []
    remaining_index = {c["id"]: c for c in index_claims if c.get("id")}
    remaining_db = {c["id"]: c for c in db_claims}

    def assign(index_claim_id: str, db_claim_id: str):
        index_claim = remaining_index.pop(index_claim_id, None)
        db_claim = remaining_db.pop(db_claim_id, None)
        if index_claim and db_claim:
            mapping.append((index_claim, db_claim))

    # 1) exact ID matches
    for claim in index_claims:
        cid = claim.get("id")
        if cid and cid in remaining_db and cid in remaining_index:
            assign(cid, cid)

    # 2) exact normalized text
    db_by_text = defaultdict(list)
    for db_claim in remaining_db.values():
        db_by_text[normalize_text(db_claim.get("text", ""))].append(db_claim)

    for index_claim in list(remaining_index.values()):
        tkey = normalize_text(index_claim.get("text", ""))
        candidates = db_by_text.get(tkey, [])
        if not candidates:
            continue

        # Prefer chapter-aligned candidate if unique.
        chapter_candidates = [
            c for c in candidates if c.get("chapter_index") == index_claim.get("chapter_index")
        ]
        pick = None
        if len(chapter_candidates) == 1:
            pick = chapter_candidates[0]
        elif len(candidates) == 1:
            pick = candidates[0]

        if pick and pick["id"] in remaining_db and index_claim["id"] in remaining_index:
            assign(index_claim["id"], pick["id"])

    # 3) chapter queues by claim order
    chapter_queues = defaultdict(list)
    for db_claim in remaining_db.values():
        chapter_queues[db_claim.get("chapter_index", 0)].append(db_claim)
    for queue in chapter_queues.values():
        queue.sort(key=lambda c: (c.get("claim_index", 0), c["id"]))

    for index_claim in sorted(
        remaining_index.values(), key=lambda c: (c.get("chapter_index", 0), c.get("claim_index", 0))
    ):
        chapter_idx = index_claim.get("chapter_index", 0)
        queue = chapter_queues.get(chapter_idx, [])
        while queue and queue[0]["id"] not in remaining_db:
            queue.pop(0)
        if queue:
            assign(index_claim["id"], queue[0]["id"])

    # 4) global order fallback
    if len(remaining_index) == len(remaining_db) and remaining_index:
        ordered_index = sorted(
            remaining_index.values(), key=lambda c: (c.get("chapter_index", 0), c.get("claim_index", 0), c["id"])
        )
        ordered_db = sorted(
            remaining_db.values(), key=lambda c: (c.get("chapter_index", 0), c.get("claim_index", 0), c["id"])
        )
        for idx_claim, db_claim in zip(ordered_index, ordered_db):
            assign(idx_claim["id"], db_claim["id"])

    unmatched_index = sorted(
        remaining_index.values(), key=lambda c: (c.get("chapter_index", 0), c.get("claim_index", 0))
    )
    unmatched_db = sorted(
        remaining_db.values(), key=lambda c: (c.get("chapter_index", 0), c.get("claim_index", 0))
    )

    mapping.sort(key=lambda pair: (pair[0].get("chapter_index", 0), pair[0].get("claim_index", 0)))
    return mapping, unmatched_index, unmatched_db


def ensure_entities_shape(value) -> dict:
    """Normalize entities payload to canonical dict shape."""
    base = {"people": [], "places": [], "events": [], "works": []}
    if isinstance(value, dict):
        for key in base:
            raw = value.get(key, [])
            base[key] = raw if isinstance(raw, list) else []
        return base
    return base


def truncate_text(text: str, limit: int = 240) -> str:
    """Trim support text for embedding context."""
    cleaned = (text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def format_sub_point(sub_point) -> str:
    """Normalize sub-point object/string to embedding support text."""
    if isinstance(sub_point, dict):
        text = truncate_text(sub_point.get("text", ""))
        speaker = (sub_point.get("speaker") or "").strip()
        if text and speaker:
            return f'"{text}" —{speaker}'
        return text
    if isinstance(sub_point, str):
        return truncate_text(sub_point)
    return truncate_text(str(sub_point))


def build_claim_embedding_text(book_title: str, claim: dict) -> str:
    """Build claim-level context for embeddings."""
    lines = [f"Book: {book_title}"]
    part = (claim.get("part") or "").strip()
    chapter = (claim.get("chapter") or "").strip()
    if part:
        lines.append(f"Part: {part}")
    if chapter:
        lines.append(f"Chapter: {chapter}")
    lines.append(f"Claim: {(claim.get('text') or '').strip()}")

    support = []
    for sub_point in claim.get("sub_points", []) or []:
        formatted = format_sub_point(sub_point)
        if formatted:
            support.append(formatted)
        if len(support) >= 2:
            break
    if support:
        lines.append("Support: " + " | ".join(support))
    return "\n".join(lines)


def build_quote_embedding_text(book_title: str, claim: dict, quote_text: str, speaker: str) -> str:
    """Build quote-level context for embeddings."""
    lines = [f'Quote: "{quote_text.strip()}"', f"Speaker: {speaker.strip()}", f"Book: {book_title}"]
    chapter = (claim.get("chapter") or "").strip()
    if chapter:
        lines.append(f"Chapter: {chapter}")
    lines.append(f"Related claim: {truncate_text(claim.get('text', ''), 200)}")
    return "\n".join(lines)


def build_repaired_claims(book: str, mapping: list[tuple[dict, dict]]) -> list[dict]:
    """Build claim rows ready for VectorStore.add_claims_batch."""
    repaired = []
    for index_claim, db_claim in mapping:
        blob = db_claim.get("embedding")
        if not blob:
            continue
        repaired.append(
            {
                "id": index_claim["id"],
                "book_name": book,
                "chapter_index": index_claim.get("chapter_index", 0),
                "claim_index": index_claim.get("claim_index", 0),
                "chapter_title": index_claim.get("chapter", ""),
                "part": index_claim.get("part", ""),
                "text": index_claim.get("text", ""),
                "embedding_text": db_claim.get("embedding_text") or index_claim.get("text", ""),
                "concepts": index_claim.get("concepts", []),
                "entities": ensure_entities_shape(index_claim.get("entities", {})),
                "sub_points": index_claim.get("sub_points", []),
                "embedding": deserialize_vector(blob),
            }
        )
    return repaired


def build_repaired_quotes(
    book: str,
    mapping: list[tuple[dict, dict]],
    old_quotes: list[dict],
) -> tuple[list[dict], int]:
    """Re-map quote embeddings where text/speaker still matches."""
    quotes_by_old_claim = defaultdict(list)
    for q in old_quotes:
        quotes_by_old_claim[q.get("claim_id")].append(q)

    rebuilt = []
    matched = 0

    for index_claim, db_claim in mapping:
        old_claim_id = db_claim["id"]
        old_candidates = quotes_by_old_claim.get(old_claim_id, [])
        used_old_quote_ids = set()

        for sp_idx, sub_point in enumerate(index_claim.get("sub_points", [])):
            if not isinstance(sub_point, dict):
                continue
            speaker = (sub_point.get("speaker") or "").strip()
            text = (sub_point.get("text") or "").strip()
            if not speaker or not text:
                continue

            new_quote_id = f"{index_claim['id']}_q{sp_idx}"
            target_text = normalize_text(text)

            chosen = None
            for candidate in old_candidates:
                if candidate["id"] in used_old_quote_ids:
                    continue
                if (candidate.get("speaker") or "").strip() != speaker:
                    continue
                if normalize_text(candidate.get("text", "")) == target_text:
                    chosen = candidate
                    break

            if not chosen or not chosen.get("embedding"):
                continue

            used_old_quote_ids.add(chosen["id"])
            matched += 1
            rebuilt.append(
                {
                    "id": new_quote_id,
                    "claim_id": index_claim["id"],
                    "book_name": book,
                    "text": text,
                    "speaker": speaker,
                    "embedding": deserialize_vector(chosen["embedding"]),
                }
            )

    return rebuilt, matched


def update_concept_registry_for_book(
    registry: ConceptRegistry,
    book: str,
    index_payload: dict,
) -> int:
    """Replace concept book counts for one book from index claims."""
    title = (index_payload.get("book", {}) or {}).get("title", "").strip()
    if title and title != book:
        registry.remove_book_references(title)
    registry.remove_book_references(book)

    concept_counts = Counter()
    for claim in index_payload.get("claims", []):
        for concept in claim.get("concepts", []):
            if concept:
                concept_counts[concept] += 1

    for concept_id, count in concept_counts.items():
        if concept_id not in registry.concepts:
            registry.concepts[concept_id] = Concept(
                id=concept_id,
                label=ConceptRegistry._to_title_case(concept_id),
                description="",
            )
        registry.set_book_claims(concept_id, book, count)
    return len(concept_counts)


def cleanup_unknown_registry_book_refs(
    registry: ConceptRegistry,
    known_books: set[str],
) -> tuple[int, int]:
    """
    Remove concept book refs that no longer map to indexed books.

    Returns:
        (removed_refs, deleted_concepts)
    """
    removed_refs = 0
    for concept in registry.concepts.values():
        for book_ref in list(concept.book_claims.keys()):
            if book_ref not in known_books:
                del concept.book_claims[book_ref]
                removed_refs += 1

    deleted_concepts = registry.cleanup_orphaned_concepts()
    return removed_refs, deleted_concepts


def audit_book(book: str, index_payload: dict, db_claims: list[dict]) -> dict:
    """Compute audit and matchability metrics for one book."""
    index_claims = build_index_claim_records(index_payload)
    idx_ids = {c["id"] for c in index_claims}
    db_ids = {c["id"] for c in db_claims}

    mapping, unmatched_index, unmatched_db = match_claims(index_claims, db_claims)
    short_db = sum(1 for c in db_claims if len((c.get("text") or "").split()) <= 5)

    return {
        "book": book,
        "index_count": len(index_claims),
        "db_count": len(db_claims),
        "overlap": len(idx_ids & db_ids),
        "missing_ids": len(idx_ids - db_ids),
        "extra_ids": len(db_ids - idx_ids),
        "matched_by_reconcile": len(mapping),
        "unmatched_index": len(unmatched_index),
        "unmatched_db": len(unmatched_db),
        "short_db": short_db,
        "repairable": len(index_claims) > 0 and len(unmatched_index) == 0 and len(unmatched_db) == 0,
    }


def print_audit(audit_rows: list[dict]):
    """Pretty-print audit summary."""
    print("\n=== Vector/Index Audit ===")
    total_books = len(audit_rows)
    mismatch = [r for r in audit_rows if r["index_count"] != r["db_count"] or r["missing_ids"] or r["extra_ids"]]
    repairable = [r for r in audit_rows if r["repairable"] and r["index_count"] > 0]
    needs_rerun = [
        r
        for r in audit_rows
        if (not r["repairable"]) or r["db_count"] == 0 or r["index_count"] == 0 or r["index_count"] != r["db_count"]
    ]

    print(f"Books audited: {total_books}")
    print(f"Books with ID/count mismatch: {len(mismatch)}")
    print(f"Books auto-repairable (no re-embed): {len(repairable)}")
    print(f"Books likely needing rerun/re-embed: {len(needs_rerun)}")

    if mismatch:
        print("\nTop mismatch books:")
        ranked = sorted(
            mismatch,
            key=lambda r: (r["missing_ids"] + r["extra_ids"], abs(r["index_count"] - r["db_count"])),
            reverse=True,
        )
        for r in ranked[:20]:
            print(
                f"- {r['book']}: index={r['index_count']} db={r['db_count']} "
                f"overlap={r['overlap']} missing={r['missing_ids']} extra={r['extra_ids']} "
                f"reconcile_unmatched={r['unmatched_index']}/{r['unmatched_db']}"
            )

    low_context = [r for r in audit_rows if r["db_count"] and (r["short_db"] / r["db_count"]) > 0.08]
    if low_context:
        print("\nPotential low-context legacy embeddings (>8% <=5 words):")
        for r in sorted(low_context, key=lambda x: x["short_db"] / x["db_count"], reverse=True)[:12]:
            ratio = r["short_db"] / r["db_count"] * 100
            print(f"- {r['book']}: {r['short_db']}/{r['db_count']} ({ratio:.1f}%)")


def main():
    parser = argparse.ArgumentParser(description="Reconcile vectors.db with index JSON")
    parser.add_argument("--apply", action="store_true", help="Apply repairs (default is audit only)")
    parser.add_argument(
        "--apply-all",
        action="store_true",
        help="Apply full repair (equivalent to --apply --embed-missing)",
    )
    parser.add_argument("--book", action="append", help="Book slug/title filter (repeatable)")
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Allow partial book repair when some claims cannot be matched (not recommended)",
    )
    parser.add_argument(
        "--embed-missing",
        action="store_true",
        help="Generate fresh embeddings for unmatched index claims (OpenAI embeddings only)",
    )
    args = parser.parse_args()
    apply_requested = args.apply or args.apply_all
    embed_missing = args.embed_missing or args.apply_all

    index_books = load_index_books(args.book)
    if not index_books:
        print("No books found matching the given filters.")
        sys.exit(1)

    conn = sqlite3.connect(VECTORS_DB_PATH)
    try:
        audit_rows = []
        per_book_data = {}
        for book, payload in sorted(index_books.items()):
            db_claims = load_db_claims(conn, book)
            audit = audit_book(book, payload, db_claims)
            audit_rows.append(audit)
            per_book_data[book] = {"index": payload, "db_claims": db_claims}

        print_audit(audit_rows)

        if not apply_requested:
            print("\nAudit only. Re-run with --apply (reuse-only) or --apply-all (full repair).")
            return

        print("\n=== Applying Repairs ===")
        if embed_missing:
            print("Mode: full repair (including embedding unmatched claims)")
        else:
            print("Mode: reuse-only repair (no new embeddings)")
            print("Tip: use --apply-all for full repair in one command.")
        vector_store = VectorStore(VECTORS_DB_PATH)
        concept_registry = ConceptRegistry(CONCEPTS_PATH)
        known_books_all = set(load_index_books().keys())
        embedder = None
        if embed_missing:
            api_key = os.getenv("OPENAI_API_KEY")
            embedder = Embedder(
                api_key=api_key,
                model=EMBEDDING_MODEL,
                dimensions=EMBEDDING_DIMENSIONS,
            )

        repaired_books = 0
        skipped_books = []
        total_claims_written = 0
        total_quotes_written = 0
        total_missing_embedded = 0

        for book, payload in sorted(index_books.items()):
            index_claims = build_index_claim_records(payload)
            db_claims = per_book_data[book]["db_claims"]
            mapping, unmatched_index, unmatched_db = match_claims(index_claims, db_claims)

            if (unmatched_index or unmatched_db) and not args.allow_partial and not embed_missing:
                skipped_books.append(
                    (
                        book,
                        f"unmatched index/db claims {len(unmatched_index)}/{len(unmatched_db)}",
                    )
                )
                continue

            repaired_claims = build_repaired_claims(book, mapping)
            book_title = (payload.get("book", {}) or {}).get("title", book)

            if unmatched_index and embed_missing:
                claim_texts = [build_claim_embedding_text(book_title, claim) for claim in unmatched_index]
                claim_embeddings = embedder.embed_batch(claim_texts, batch_size=100)
                for claim, embedding_text, embedding in zip(unmatched_index, claim_texts, claim_embeddings):
                    repaired_claims.append(
                        {
                            "id": claim["id"],
                            "book_name": book,
                            "chapter_index": claim.get("chapter_index", 0),
                            "claim_index": claim.get("claim_index", 0),
                            "chapter_title": claim.get("chapter", ""),
                            "part": claim.get("part", ""),
                            "text": claim.get("text", ""),
                            "embedding_text": embedding_text,
                            "concepts": claim.get("concepts", []),
                            "entities": ensure_entities_shape(claim.get("entities", {})),
                            "sub_points": claim.get("sub_points", []),
                            "embedding": embedding,
                        }
                    )
                total_missing_embedded += len(unmatched_index)

            if not repaired_claims:
                skipped_books.append((book, "no reusable embeddings found"))
                continue

            old_quotes = load_db_quotes(conn, book)
            repaired_quotes, matched_quotes = build_repaired_quotes(book, mapping, old_quotes)

            if unmatched_index and embed_missing:
                new_quote_payloads = []
                new_quote_texts = []
                for claim in unmatched_index:
                    for sp_idx, sub_point in enumerate(claim.get("sub_points", []) or []):
                        if not isinstance(sub_point, dict):
                            continue
                        speaker = (sub_point.get("speaker") or "").strip()
                        quote_text = (sub_point.get("text") or "").strip()
                        if not speaker or not quote_text:
                            continue
                        new_quote_payloads.append(
                            {
                                "id": f"{claim['id']}_q{sp_idx}",
                                "claim_id": claim["id"],
                                "book_name": book,
                                "text": quote_text,
                                "speaker": speaker,
                            }
                        )
                        new_quote_texts.append(
                            build_quote_embedding_text(book_title, claim, quote_text, speaker)
                        )

                if new_quote_payloads:
                    new_quote_embeddings = embedder.embed_batch(new_quote_texts, batch_size=100)
                    for payload_quote, embedding in zip(new_quote_payloads, new_quote_embeddings):
                        payload_quote["embedding"] = embedding
                    repaired_quotes.extend(new_quote_payloads)

            # Replace book slice in vectors DB.
            vector_store.delete_book_quotes(book)
            vector_store.delete_book_claims(book)
            vector_store.add_claims_batch(repaired_claims)
            if repaired_quotes:
                vector_store.add_quotes_batch(repaired_quotes)

            concept_count = update_concept_registry_for_book(concept_registry, book, payload)

            repaired_books += 1
            total_claims_written += len(repaired_claims)
            total_quotes_written += len(repaired_quotes)
            print(
                f"- repaired {book}: claims={len(repaired_claims)} "
                f"quotes={len(repaired_quotes)} (matched quote embeddings={matched_quotes}) "
                f"concepts={concept_count}"
            )

        removed_refs, deleted_concepts = cleanup_unknown_registry_book_refs(
            concept_registry, known_books_all
        )
        concept_registry.save()

        print("\n=== Repair Summary ===")
        print(f"Books repaired: {repaired_books}")
        print(f"Claims rewritten: {total_claims_written}")
        print(f"Quotes rewritten: {total_quotes_written}")
        if removed_refs or deleted_concepts:
            print(
                f"Concept registry cleanup: removed {removed_refs} stale book refs, "
                f"deleted {deleted_concepts} orphan concepts"
            )
        if embed_missing:
            print(f"Claims newly embedded: {total_missing_embedded}")
        if skipped_books:
            print(f"Books skipped: {len(skipped_books)}")
            for book, reason in skipped_books[:30]:
                print(f"- {book}: {reason}")
            if len(skipped_books) > 30:
                print(f"... and {len(skipped_books) - 30} more")

        print("\nNext:")
        print("1) Spot-check query results.")
        print("2) Re-run main.py only for skipped/problematic books.")
        print("3) Run scripts/migrate-vectors.py to sync Postgres.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
