"""
Vector storage module using sqlite-vec for efficient similarity search.
"""

import logging
import json
import sqlite3
import struct
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class VectorStore:
    """Manages vector storage and similarity search using SQLite with vec0 extension."""

    def __init__(self, db_path: str, dimensions: int = 1536):
        """
        Initialize the vector store.

        Args:
            db_path: Path to the SQLite database file
            dimensions: Dimensionality of the vectors
        """
        self.db_path = Path(db_path)
        self.dimensions = dimensions

        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()

        logger.info(f"Initialized vector store at {db_path} (dimensions={dimensions})")

    def _init_db(self):
        """Initialize database schema with vec0 virtual table."""
        conn = self._get_connection()

        try:
            # Load sqlite-vec extension if available
            try:
                conn.enable_load_extension(True)
                # Try common extension paths
                for ext_name in ["vec0", "sqlite-vec", "vector0"]:
                    try:
                        conn.load_extension(ext_name)
                        logger.info(f"Loaded sqlite-vec extension: {ext_name}")
                        break
                    except sqlite3.OperationalError:
                        continue
            except Exception as e:
                logger.warning(f"Could not load sqlite-vec extension: {e}")
                logger.warning(
                    "Falling back to regular SQLite tables (no vector search)"
                )

            # Create claims table with vector support
            conn.execute("""
                CREATE TABLE IF NOT EXISTS claims (
                    id TEXT PRIMARY KEY,
                    book_name TEXT NOT NULL,
                    chapter_index INTEGER NOT NULL,
                    claim_index INTEGER NOT NULL,
                    chapter_title TEXT,
                    part TEXT,
                    text TEXT NOT NULL,
                    embedding_text TEXT,
                    concepts TEXT,
                    concepts_json TEXT,
                    entities TEXT,
                    entities_json TEXT,
                    quotes TEXT,
                    sub_points_json TEXT,
                    embedding BLOB
                )
            """)

            # Add any newly introduced metadata columns to existing databases.
            self._ensure_column(conn, "claims", "chapter_title", "TEXT")
            self._ensure_column(conn, "claims", "part", "TEXT")
            self._ensure_column(conn, "claims", "embedding_text", "TEXT")
            self._ensure_column(conn, "claims", "concepts_json", "TEXT")
            self._ensure_column(conn, "claims", "entities_json", "TEXT")
            self._ensure_column(conn, "claims", "sub_points_json", "TEXT")

            # Create index for efficient filtering
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_claims_book
                ON claims(book_name)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_claims_chapter
                ON claims(book_name, chapter_index)
            """)

            # Create concepts table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS concepts (
                    id TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    books TEXT,
                    embedding BLOB
                )
            """)

            # Create quotes table for searchable quotes with attribution
            conn.execute("""
                CREATE TABLE IF NOT EXISTS quotes (
                    id TEXT PRIMARY KEY,
                    claim_id TEXT NOT NULL,
                    book_name TEXT NOT NULL,
                    text TEXT NOT NULL,
                    speaker TEXT NOT NULL,
                    embedding BLOB,
                    FOREIGN KEY (claim_id) REFERENCES claims(id) ON DELETE CASCADE
                )
            """)

            # Create indexes for quotes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_quotes_book
                ON quotes(book_name)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_quotes_speaker
                ON quotes(speaker)
            """)

            conn.commit()
            logger.info("Database schema initialized")

        finally:
            conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with foreign keys enabled."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str):
        """Add a column if it does not already exist."""
        existing = {
            row[1]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
            logger.info(f"Added '{column}' column to {table} table")

    def _serialize_vector(self, vector: List[float]) -> bytes:
        """Serialize a vector to bytes for storage."""
        return struct.pack(f"{len(vector)}f", *vector)

    def _deserialize_vector(self, data: bytes) -> List[float]:
        """Deserialize bytes back to a vector."""
        num_floats = len(data) // 4
        return list(struct.unpack(f"{num_floats}f", data))

    @staticmethod
    def _flatten_to_strings(value) -> List[str]:
        """
        Flatten nested metadata into a list of non-empty strings.

        Accepts legacy string lists plus newer nested shapes (dicts/lists) and
        returns a stable, deduplicated list suitable for CSV storage.
        """
        flattened = []

        def walk(item):
            if item is None:
                return
            if isinstance(item, str):
                text = item.strip()
                if text:
                    flattened.append(text)
                return
            if isinstance(item, dict):
                for sub_value in item.values():
                    walk(sub_value)
                return
            if isinstance(item, (list, tuple, set)):
                for sub_value in item:
                    walk(sub_value)
                return
            flattened.append(str(item))

        walk(value)

        # Preserve first-seen order while removing duplicates.
        seen = set()
        unique = []
        for item in flattened:
            if item not in seen:
                seen.add(item)
                unique.append(item)
        return unique

    @staticmethod
    def _to_json_text(value) -> str:
        """Serialize structured metadata as JSON for lossless storage."""
        try:
            return json.dumps(value if value is not None else [], ensure_ascii=False)
        except TypeError:
            # Fall back to flattened representation if an unexpected object appears.
            return json.dumps(VectorStore._flatten_to_strings(value), ensure_ascii=False)

    def add_claims_batch(self, claims: List[dict]):
        """
        Add multiple claims in a single transaction.

        Args:
            claims: List of claim dictionaries with keys:
                   id, book_name, chapter_index, claim_index, text, embedding,
                   concepts (optional), entities (optional), quotes (optional)
        """
        if not claims:
            return

        conn = self._get_connection()

        try:
            for claim in claims:
                concepts = claim.get("concepts", [])
                entities = claim.get("entities", {})
                sub_points = claim.get("sub_points", claim.get("quotes", []))
                concepts_csv = ",".join(self._flatten_to_strings(concepts))
                entities_csv = ",".join(self._flatten_to_strings(entities))
                quotes_csv = ",".join(self._flatten_to_strings(sub_points))
                conn.execute(
                    """
                    INSERT OR REPLACE INTO claims
                    (
                        id, book_name, chapter_index, claim_index, chapter_title, part,
                        text, embedding_text, concepts, concepts_json, entities, entities_json,
                        quotes, sub_points_json, embedding
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        claim["id"],
                        claim["book_name"],
                        claim["chapter_index"],
                        claim["claim_index"],
                        claim.get("chapter_title", ""),
                        claim.get("part", ""),
                        claim["text"],
                        claim.get("embedding_text", claim["text"]),
                        concepts_csv,
                        self._to_json_text(concepts),
                        entities_csv,
                        self._to_json_text(entities),
                        quotes_csv,
                        self._to_json_text(sub_points),
                        self._serialize_vector(claim["embedding"]),
                    ),
                )

            conn.commit()
            logger.info(f"Added {len(claims)} claims to vector store")

        finally:
            conn.close()

    def upsert_concept_metadata(
        self, concept_id: str, label: str, books: Optional[List[str]] = None
    ):
        """
        Upsert concept label/book metadata without touching existing embedding blobs.
        """
        conn = self._get_connection()
        try:
            conn.execute(
                """
                INSERT INTO concepts (id, label, books, embedding)
                VALUES (?, ?, ?, NULL)
                ON CONFLICT(id) DO UPDATE SET
                    label = excluded.label,
                    books = excluded.books
                """,
                (concept_id, label, ",".join(books) if books else ""),
            )
            conn.commit()
        finally:
            conn.close()

    def add_concept(
        self,
        concept_id: str,
        label: str,
        embedding: List[float],
        books: Optional[List[str]] = None,
    ):
        """
        Add or update a concept in the vector store.

        Args:
            concept_id: Concept identifier (snake_case)
            label: Human-readable label
            embedding: Embedding vector
            books: List of books using this concept
        """
        conn = self._get_connection()

        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO concepts
                (id, label, books, embedding)
                VALUES (?, ?, ?, ?)
                """,
                (
                    concept_id,
                    label,
                    ",".join(books) if books else "",
                    self._serialize_vector(embedding),
                ),
            )

            conn.commit()
            logger.debug(f"Added concept {concept_id} to vector store")

        finally:
            conn.close()

    def search_claims(
        self,
        query_vector: List[float],
        top_k: int = 10,
        book_filter: Optional[str] = None,
    ) -> List[Tuple[str, str, float]]:
        """
        Search for similar claims using cosine similarity.

        Args:
            query_vector: Query embedding vector
            top_k: Number of results to return
            book_filter: Optional book name to filter results

        Returns:
            List of (claim_id, claim_text, similarity_score) tuples
        """
        conn = self._get_connection()

        try:
            # Fetch all claims (with optional book filter)
            if book_filter:
                cursor = conn.execute(
                    "SELECT id, text, embedding FROM claims WHERE book_name = ?",
                    (book_filter,),
                )
            else:
                cursor = conn.execute("SELECT id, text, embedding FROM claims")

            results = []

            for claim_id, text, embedding_blob in cursor:
                embedding = self._deserialize_vector(embedding_blob)
                similarity = self._cosine_similarity(query_vector, embedding)
                results.append((claim_id, text, similarity))

            # Sort by similarity (descending) and return top_k
            results.sort(key=lambda x: x[2], reverse=True)
            return results[:top_k]

        finally:
            conn.close()

    def search_concepts(
        self, query_vector: List[float], top_k: int = 10
    ) -> List[Tuple[str, str, float]]:
        """
        Search for similar concepts.

        Args:
            query_vector: Query embedding vector
            top_k: Number of results to return

        Returns:
            List of (concept_id, label, similarity_score) tuples
        """
        conn = self._get_connection()

        try:
            cursor = conn.execute("SELECT id, label, embedding FROM concepts")

            results = []

            for concept_id, label, embedding_blob in cursor:
                embedding = self._deserialize_vector(embedding_blob)
                similarity = self._cosine_similarity(query_vector, embedding)
                results.append((concept_id, label, similarity))

            # Sort by similarity (descending) and return top_k
            results.sort(key=lambda x: x[2], reverse=True)
            return results[:top_k]

        finally:
            conn.close()

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(vec1) != len(vec2):
            raise ValueError("Vectors must have the same dimensions")

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    def get_claim_count(self, book_name: Optional[str] = None) -> int:
        """Get total number of claims, optionally filtered by book."""
        conn = self._get_connection()

        try:
            if book_name:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM claims WHERE book_name = ?", (book_name,)
                )
            else:
                cursor = conn.execute("SELECT COUNT(*) FROM claims")

            return cursor.fetchone()[0]

        finally:
            conn.close()

    def get_concept_count(self) -> int:
        """Get total number of concepts."""
        conn = self._get_connection()

        try:
            cursor = conn.execute("SELECT COUNT(*) FROM concepts")
            return cursor.fetchone()[0]

        finally:
            conn.close()

    def get_existing_concept_ids(self) -> set:
        """Get set of all concept IDs that already have embeddings."""
        conn = self._get_connection()

        try:
            cursor = conn.execute("SELECT id FROM concepts WHERE embedding IS NOT NULL")
            return {row[0] for row in cursor.fetchall()}

        finally:
            conn.close()

    def delete_book_claims(self, book_name: str) -> int:
        """
        Delete all claims for a given book.

        Args:
            book_name: Name of the book to remove

        Returns:
            Number of claims deleted
        """
        conn = self._get_connection()

        try:
            # Get count before deletion
            cursor = conn.execute(
                "SELECT COUNT(*) FROM claims WHERE book_name = ?", (book_name,)
            )
            count = cursor.fetchone()[0]

            # Delete claims
            conn.execute("DELETE FROM claims WHERE book_name = ?", (book_name,))
            conn.commit()

            logger.info(f"Deleted {count} claims for book '{book_name}'")
            return count

        finally:
            conn.close()

    def add_quotes_batch(self, quotes: List[dict]):
        """
        Add multiple quotes in a single transaction.

        Args:
            quotes: List of quote dictionaries with keys:
                   id, claim_id, book_name, text, speaker, embedding
        """
        if not quotes:
            return

        conn = self._get_connection()

        try:
            for quote in quotes:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO quotes
                    (id, claim_id, book_name, text, speaker, embedding)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        quote["id"],
                        quote["claim_id"],
                        quote["book_name"],
                        quote["text"],
                        quote["speaker"],
                        self._serialize_vector(quote["embedding"]),
                    ),
                )

            conn.commit()
            logger.info(f"Added {len(quotes)} quotes to vector store")

        finally:
            conn.close()

    def get_quote_count(self, book_name: Optional[str] = None) -> int:
        """Get total number of quotes, optionally filtered by book."""
        conn = self._get_connection()

        try:
            if book_name:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM quotes WHERE book_name = ?", (book_name,)
                )
            else:
                cursor = conn.execute("SELECT COUNT(*) FROM quotes")

            return cursor.fetchone()[0]

        finally:
            conn.close()

    def delete_book_quotes(self, book_name: str) -> int:
        """
        Delete all quotes for a given book.

        Args:
            book_name: Name of the book to remove

        Returns:
            Number of quotes deleted
        """
        conn = self._get_connection()

        try:
            # Get count before deletion
            cursor = conn.execute(
                "SELECT COUNT(*) FROM quotes WHERE book_name = ?", (book_name,)
            )
            count = cursor.fetchone()[0]

            # Delete quotes
            conn.execute("DELETE FROM quotes WHERE book_name = ?", (book_name,))
            conn.commit()

            logger.info(f"Deleted {count} quotes for book '{book_name}'")
            return count

        finally:
            conn.close()
