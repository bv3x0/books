#!/usr/bin/env python3
"""
Migrate vectors from local SQLite (vectors.db) to Neon Postgres.

This script performs a full per-book sync:
- Reads all claim rows from SQLite
- Deletes existing Postgres rows for each book being synced
- Re-inserts that book's current rows

This prevents stale rows from surviving re-indexes (for example after claim-ID
scheme changes or deleting/re-adding a book).

Prerequisites:
1. Create Neon database via Vercel Marketplace
2. Run the schema SQL (at minimum id/book_name/text/embedding columns)
3. Set POSTGRES_URL_NON_POOLING or DATABASE_URL_UNPOOLED
4. pip install psycopg2-binary

Baseline schema:
    CREATE EXTENSION IF NOT EXISTS vector;

    CREATE TABLE claims (
        id TEXT PRIMARY KEY,
        book_name TEXT NOT NULL,
        chapter TEXT,
        text TEXT NOT NULL,
        concepts TEXT[],
        embedding vector(1536)
    );

Optional metadata columns (recommended for richer retrieval/filtering):
    chapter_index INTEGER,
    claim_index INTEGER,
    embedding_text TEXT,
    concepts_json JSONB,
    entities TEXT[],
    entities_json JSONB,
    sub_points_json JSONB

Usage:
    export DATABASE_URL_UNPOOLED="postgres://user:pass@host/db?sslmode=require"
    python scripts/migrate-vectors.py
    python scripts/migrate-vectors.py --prune-missing
"""

import argparse
import json
import os
import sqlite3
import struct
import sys
from pathlib import Path

try:
    import psycopg2
    from psycopg2.extras import Json, execute_values
except ImportError:
    print("Error: psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)

from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent / "app" / ".env")

PROJECT_ROOT = Path(__file__).parent.parent
INDEX_DIR = PROJECT_ROOT / "index"
VECTORS_DB = INDEX_DIR / "vectors.db"


def deserialize_vector(data: bytes) -> list:
    """Deserialize bytes to float vector."""
    num_floats = len(data) // 4
    return list(struct.unpack(f"{num_floats}f", data))


def parse_json_or_default(raw, default):
    """Parse JSON text safely."""
    if raw is None or raw == "":
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def parse_csv(raw: str) -> list[str]:
    """Split CSV-like metadata fields into list form."""
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def load_book_metadata(book_names: set[str] | None = None) -> dict:
    """Load claim metadata (chapter names) from JSON index files."""
    book_claims = {}

    for json_file in INDEX_DIR.glob("*.json"):
        if json_file.name.startswith("_"):
            continue
        book_name = json_file.stem
        if book_names is not None and book_name not in book_names:
            continue

        try:
            with open(json_file) as f:
                data = json.load(f)
                claims_by_id = {c["id"]: c for c in data.get("claims", [])}
                book_claims[book_name] = claims_by_id
        except Exception as e:
            print(f"Warning: Could not load {json_file.name}: {e}")

    return book_claims


def get_sqlite_columns(sqlite_conn: sqlite3.Connection) -> set[str]:
    cursor = sqlite_conn.execute("PRAGMA table_info(claims)")
    return {row[1] for row in cursor.fetchall()}


def get_postgres_columns(pg_cursor) -> dict[str, dict]:
    pg_cursor.execute(
        """
        SELECT column_name, data_type, udt_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'claims'
        """
    )
    rows = pg_cursor.fetchall()
    return {name: {"data_type": data_type, "udt_name": udt_name} for name, data_type, udt_name in rows}


def coerce_for_pg(value, column_info: dict):
    """Coerce Python values to match Postgres column types."""
    if value is None:
        return None

    data_type = column_info.get("data_type", "")
    udt_name = column_info.get("udt_name", "")

    if data_type in {"json", "jsonb"} or udt_name in {"json", "jsonb"}:
        return Json(value)

    if isinstance(value, list):
        if udt_name == "vector":
            return value
        if data_type == "ARRAY" or udt_name.startswith("_"):
            return value
        return ",".join(str(item) for item in value)

    if isinstance(value, dict):
        if data_type in {"json", "jsonb"} or udt_name in {"json", "jsonb"}:
            return Json(value)
        return json.dumps(value, ensure_ascii=False)

    return value


def build_payload(row: sqlite3.Row, sqlite_columns: set[str], book_claims: dict) -> dict:
    """Build a normalized payload for one claim row."""
    claim_id = row["id"]
    book_name = row["book_name"]

    chapter_title = ""
    if "chapter_title" in sqlite_columns:
        chapter_title = row["chapter_title"] or ""
    if not chapter_title:
        claim_data = book_claims.get(book_name, {}).get(claim_id, {})
        chapter_title = claim_data.get("chapter", "")

    concepts = []
    if "concepts_json" in sqlite_columns and row["concepts_json"]:
        parsed = parse_json_or_default(row["concepts_json"], [])
        if isinstance(parsed, list):
            concepts = [str(item).strip() for item in parsed if str(item).strip()]
    if not concepts and "concepts" in sqlite_columns:
        concepts = parse_csv(row["concepts"])

    entities_json = {"people": [], "places": [], "events": [], "works": []}
    if "entities_json" in sqlite_columns and row["entities_json"]:
        parsed_entities = parse_json_or_default(row["entities_json"], entities_json)
        if isinstance(parsed_entities, dict):
            entities_json = parsed_entities
    entities_flat = parse_csv(row["entities"]) if "entities" in sqlite_columns else []
    if not entities_flat:
        entities_flat = []
        for key in ["people", "places", "events", "works"]:
            values = entities_json.get(key, [])
            if isinstance(values, list):
                entities_flat.extend(str(v) for v in values if str(v).strip())

    sub_points_json = []
    if "sub_points_json" in sqlite_columns and row["sub_points_json"]:
        parsed_sub_points = parse_json_or_default(row["sub_points_json"], [])
        if isinstance(parsed_sub_points, list):
            sub_points_json = parsed_sub_points

    payload = {
        "id": claim_id,
        "book_name": book_name,
        "chapter": chapter_title,
        "text": row["text"],
        "embedding": deserialize_vector(row["embedding"]),
        "concepts": concepts,
        "concepts_json": concepts,
        "entities": entities_flat,
        "entities_json": entities_json,
        "sub_points_json": sub_points_json,
        "chapter_index": row["chapter_index"] if "chapter_index" in sqlite_columns else None,
        "claim_index": row["claim_index"] if "claim_index" in sqlite_columns else None,
        "embedding_text": row["embedding_text"] if "embedding_text" in sqlite_columns else row["text"],
    }
    return payload


def resolve_selected_books(
    sqlite_conn: sqlite3.Connection, book_filters: list[str] | None
) -> set[str] | None:
    """Resolve CLI book filters to local SQLite book names."""
    if not book_filters:
        return None

    filters = [book.lower() for book in book_filters if book.strip()]
    if not filters:
        return set()

    rows = sqlite_conn.execute("SELECT DISTINCT book_name FROM claims").fetchall()
    selected = {
        row["book_name"]
        for row in rows
        if any(filter_text in row["book_name"].lower() for filter_text in filters)
    }
    return selected


def migrate(prune_missing: bool = False, book_filters: list[str] | None = None):
    """Migrate vectors from SQLite to Postgres."""
    database_url = os.environ.get("DATABASE_URL_UNPOOLED") or os.environ.get(
        "POSTGRES_URL_NON_POOLING"
    )
    if not database_url:
        print("Error: DATABASE_URL_UNPOOLED environment variable not set")
        print("\nTo set it:")
        print("  1. Go to Vercel Dashboard → Project → Storage")
        print("  2. Click on your Neon database")
        print("  3. Copy the 'Unpooled URL' from connection details")
        print("  4. Run: export DATABASE_URL_UNPOOLED='postgres://...'")
        sys.exit(1)

    if not VECTORS_DB.exists():
        print(f"Error: SQLite database not found at {VECTORS_DB}")
        print("Run book processing first to generate embeddings.")
        sys.exit(1)

    print(f"Connecting to SQLite: {VECTORS_DB}", flush=True)
    sqlite_conn = sqlite3.connect(VECTORS_DB)
    sqlite_conn.row_factory = sqlite3.Row
    selected_books = resolve_selected_books(sqlite_conn, book_filters)
    if selected_books is not None:
        if not selected_books:
            print(
                "No local SQLite books matched the given --book filter(s); nothing to sync.",
                flush=True,
            )
            sqlite_conn.close()
            return
        print(
            f"Scoped vector sync: {', '.join(sorted(selected_books))}",
            flush=True,
        )

    print("Connecting to Postgres...", flush=True)
    pg_conn = psycopg2.connect(database_url)
    pg_cursor = pg_conn.cursor()

    try:
        pg_cursor.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        if not pg_cursor.fetchone():
            print("Error: pgvector extension not enabled in Postgres")
            print(
                "Run this SQL in Neon console: CREATE EXTENSION IF NOT EXISTS vector;"
            )
            sys.exit(1)
    except Exception as e:
        print(f"Error checking pgvector: {e}")
        sys.exit(1)

    print("Loading index metadata...", flush=True)
    book_claims = load_book_metadata(selected_books)
    print(f"  Found metadata for {len(book_claims)} books", flush=True)

    sqlite_columns = get_sqlite_columns(sqlite_conn)
    print(f"SQLite claims columns: {', '.join(sorted(sqlite_columns))}", flush=True)

    pg_columns = get_postgres_columns(pg_cursor)
    print(f"Postgres claims columns: {', '.join(sorted(pg_columns.keys()))}", flush=True)

    required_pg = {"id", "book_name", "text", "embedding"}
    missing_required = required_pg - set(pg_columns.keys())
    if missing_required:
        print(f"Error: Postgres claims table missing required columns: {sorted(missing_required)}")
        sys.exit(1)

    if selected_books is None:
        cursor = sqlite_conn.execute("SELECT * FROM claims")
    else:
        placeholders = ", ".join(["?"] * len(selected_books))
        cursor = sqlite_conn.execute(
            f"SELECT * FROM claims WHERE book_name IN ({placeholders})",
            tuple(sorted(selected_books)),
        )
    rows = cursor.fetchall()
    total_claims = len(rows)
    if total_claims == 0:
        print("No claims in SQLite to migrate.")
        sqlite_conn.close()
        pg_cursor.close()
        pg_conn.close()
        return

    rows_by_book = {}
    for row in rows:
        rows_by_book.setdefault(row["book_name"], []).append(row)

    print(
        f"Loaded {total_claims} claim rows across {len(rows_by_book)} books from SQLite",
        flush=True,
    )
    local_books = set(rows_by_book.keys())

    candidate_columns = [
        "id",
        "book_name",
        "chapter",
        "chapter_index",
        "claim_index",
        "text",
        "embedding_text",
        "concepts",
        "concepts_json",
        "entities",
        "entities_json",
        "sub_points_json",
        "embedding",
    ]
    insert_columns = [col for col in candidate_columns if col in pg_columns]
    if "embedding" not in insert_columns:
        insert_columns.append("embedding")

    print(f"Syncing columns: {', '.join(insert_columns)}", flush=True)

    column_sql = ", ".join(insert_columns)
    update_columns = [c for c in insert_columns if c != "id"]
    update_sql = ", ".join(f"{col} = EXCLUDED.{col}" for col in update_columns)
    insert_sql = (
        f"INSERT INTO claims ({column_sql}) VALUES %s "
        f"ON CONFLICT (id) DO UPDATE SET {update_sql}"
    )

    if prune_missing and selected_books is not None:
        print(
            "\nPrune check skipped for scoped sync. Run an unscoped --prune-missing "
            "sync to remove Postgres-only books.",
            flush=True,
        )
    elif prune_missing:
        pg_cursor.execute("SELECT DISTINCT book_name FROM claims")
        pg_books = {row[0] for row in pg_cursor.fetchall() if row and row[0]}
        stale_books = sorted(pg_books - local_books)
        if stale_books:
            print(
                f"\nPruning {len(stale_books)} Postgres-only books missing locally...",
                flush=True,
            )
            for stale_book in stale_books:
                pg_cursor.execute("DELETE FROM claims WHERE book_name = %s", (stale_book,))
                print(f"  Pruned: {stale_book}", flush=True)
            pg_conn.commit()
        else:
            print("\nPrune check: no Postgres-only books found.", flush=True)

    synced_total = 0
    for book_name, book_rows in sorted(rows_by_book.items()):
        print(f"\nSyncing book: {book_name} ({len(book_rows)} claims)", flush=True)
        pg_cursor.execute("DELETE FROM claims WHERE book_name = %s", (book_name,))

        payload_rows = []
        for row in book_rows:
            payload = build_payload(row, sqlite_columns, book_claims)
            values = []
            for col in insert_columns:
                values.append(coerce_for_pg(payload.get(col), pg_columns[col]))
            payload_rows.append(tuple(values))

        execute_values(pg_cursor, insert_sql, payload_rows, page_size=100)

        pg_conn.commit()
        synced_total += len(book_rows)
        print(f"  Synced {len(book_rows)} claims", flush=True)

    pg_cursor.execute("SELECT COUNT(*) FROM claims")
    pg_count = pg_cursor.fetchone()[0]

    print(f"\nSync complete!", flush=True)
    print(f"  Claims synced this run: {synced_total}", flush=True)
    print(f"  Total claims in Postgres: {pg_count}", flush=True)
    print(
        "  Mode: full per-book replace (prevents stale claim IDs/metadata)",
        flush=True,
    )

    sqlite_conn.close()
    pg_cursor.close()
    pg_conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync SQLite claim vectors to Postgres")
    parser.add_argument(
        "--prune-missing",
        action="store_true",
        help="Delete Postgres books that are no longer present in local SQLite",
    )
    parser.add_argument(
        "--book",
        action="append",
        help="Sync only matching SQLite book names (substring match; repeatable)",
    )
    args = parser.parse_args()
    migrate(prune_missing=args.prune_missing, book_filters=args.book)
