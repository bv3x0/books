"""
Query service: semantic search and concept comparison over canonical index data.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from app.core.embedder import Embedder
from app.core.publisher import INDEX_DIR, PROJECT_ROOT, VECTORS_DB
from app.core.vector_store import VectorStore

load_dotenv(PROJECT_ROOT / "app" / ".env")


@dataclass(frozen=True)
class ClaimSearchResult:
    claim_id: str
    claim_text: str
    score: float
    book_name: str | None
    book_title: str
    author: str
    chapter: str
    concepts: list[str]


@dataclass(frozen=True)
class ConceptSearchResult:
    concept_id: str
    label: str
    score: float
    books: list[str]
    claim_count: int
    aliases: list[str]


@dataclass(frozen=True)
class BookOverlap:
    book1: str
    book2: str
    title1: str
    title2: str
    shared_count: int
    jaccard: float
    shared_concepts: list[str]


@dataclass(frozen=True)
class BookComparison:
    name1: str
    name2: str
    title1: str
    title2: str
    concepts1_count: int
    concepts2_count: int
    shared: list[str]
    only1: list[str]
    only2: list[str]


@dataclass(frozen=True)
class QuerySelfTestResult:
    claim_count: int
    concept_count: int
    embedding_dimensions: int
    sample_books: list[str]


def _open_vector_store() -> VectorStore:
    return VectorStore(str(VECTORS_DB))


def _load_embedder() -> Embedder:
    return Embedder()


def load_book_metadata(index_dir: Path = INDEX_DIR) -> dict[str, dict]:
    """Load metadata from canonical index JSON files for enriched query results."""
    metadata: dict[str, dict] = {}

    for json_file in sorted(index_dir.glob("*.json")):
        if json_file.name.startswith("_"):
            continue
        try:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        book_name = json_file.stem
        metadata[book_name] = {
            "title": data.get("book", {}).get("title", book_name),
            "author": data.get("book", {}).get("author", "Unknown"),
            "chapters": {ch["id"]: ch["title"] for ch in data.get("chapters", [])},
            "claims_by_id": {c["id"]: c for c in data.get("claims", [])},
        }

    return metadata


def get_book_name_from_claim_id(claim_id: str, db_path: Path = VECTORS_DB) -> str | None:
    """Look up the book slug for a claim ID in the vector database."""
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute("SELECT book_name FROM claims WHERE id = ?", (claim_id,))
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def search_claims(
    query: str,
    top_k: int = 10,
    book_filter: str | None = None,
) -> tuple[int, list[ClaimSearchResult]]:
    """Search semantic claim vectors and enrich results with book metadata."""
    store = _open_vector_store()
    embedder = _load_embedder()
    metadata = load_book_metadata()

    query_vector = embedder.embed(query)
    total_claims = store.get_claim_count(book_filter)
    results = store.search_claims(query_vector, top_k=top_k, book_filter=book_filter)

    enriched: list[ClaimSearchResult] = []
    for claim_id, claim_text, score in results:
        book_name = get_book_name_from_claim_id(claim_id)
        book_meta = metadata.get(book_name, {})
        claim_data = book_meta.get("claims_by_id", {}).get(claim_id, {})
        enriched.append(
            ClaimSearchResult(
                claim_id=claim_id,
                claim_text=claim_text,
                score=score,
                book_name=book_name,
                book_title=book_meta.get("title", book_name or "Unknown"),
                author=book_meta.get("author", "Unknown"),
                chapter=claim_data.get("chapter", "Unknown"),
                concepts=claim_data.get("concepts", []),
            )
        )

    return total_claims, enriched


def search_concepts(query: str, top_k: int = 10) -> tuple[int, list[ConceptSearchResult]]:
    """Search semantic concept vectors and enrich results from the concept registry."""
    store = _open_vector_store()
    embedder = _load_embedder()
    registry = load_concept_registry()

    query_vector = embedder.embed(query)
    total_concepts = store.get_concept_count()
    results = store.search_concepts(query_vector, top_k=top_k)

    enriched: list[ConceptSearchResult] = []
    for concept_id, label, score in results:
        concept_data = registry.get("concepts", {}).get(concept_id, {})
        enriched.append(
            ConceptSearchResult(
                concept_id=concept_id,
                label=label,
                score=score,
                books=concept_data.get("books", []),
                claim_count=concept_data.get("claim_count", 0),
                aliases=concept_data.get("aliases", []),
            )
        )

    return total_concepts, enriched


def load_concept_registry(index_dir: Path = INDEX_DIR) -> dict:
    """Load the global concept registry from canonical index output."""
    concepts_file = index_dir / "_concepts.json"
    if concepts_file.exists():
        with open(concepts_file, encoding="utf-8") as f:
            return json.load(f)
    return {"concepts": {}}


def get_book_concepts(index_dir: Path = INDEX_DIR) -> dict[str, dict]:
    """Collect concept sets for each book from canonical index JSON files."""
    book_concepts: dict[str, dict] = {}

    for json_file in sorted(index_dir.glob("*.json")):
        if json_file.name.startswith("_"):
            continue
        try:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        concepts = set()
        for claim in data.get("claims", []):
            concepts.update(claim.get("concepts", []))

        book_name = json_file.stem
        book_concepts[book_name] = {
            "title": data.get("book", {}).get("title", book_name),
            "concepts": concepts,
        }

    return book_concepts


def compute_book_overlap(top_k: int = 15) -> list[BookOverlap]:
    """Rank book pairs by shared concepts."""
    book_concepts = get_book_concepts()
    books = list(book_concepts.keys())
    overlaps: list[BookOverlap] = []

    for i, book1 in enumerate(books):
        for book2 in books[i + 1 :]:
            concepts1 = book_concepts[book1]["concepts"]
            concepts2 = book_concepts[book2]["concepts"]
            shared = concepts1 & concepts2
            if not shared:
                continue
            overlaps.append(
                BookOverlap(
                    book1=book1,
                    book2=book2,
                    title1=book_concepts[book1]["title"],
                    title2=book_concepts[book2]["title"],
                    shared_count=len(shared),
                    jaccard=len(shared) / len(concepts1 | concepts2),
                    shared_concepts=sorted(shared),
                )
            )

    overlaps.sort(key=lambda item: item.shared_count, reverse=True)
    return overlaps[:top_k]


def compare_books(book1: str, book2: str) -> tuple[BookComparison | None, str | None]:
    """Compare concept sets between two books using fuzzy title/slug matching."""
    book_concepts = get_book_concepts()

    def find_book(query: str):
        query_lower = query.lower()
        for name, data in book_concepts.items():
            if query_lower in name.lower() or query_lower in data["title"].lower():
                return name, data
        return None, None

    name1, data1 = find_book(book1)
    if not data1:
        return None, book1

    name2, data2 = find_book(book2)
    if not data2:
        return None, book2

    concepts1 = data1["concepts"]
    concepts2 = data2["concepts"]
    shared = sorted(concepts1 & concepts2)
    only1 = sorted(concepts1 - concepts2)
    only2 = sorted(concepts2 - concepts1)

    return (
        BookComparison(
            name1=name1,
            name2=name2,
            title1=data1["title"],
            title2=data2["title"],
            concepts1_count=len(concepts1),
            concepts2_count=len(concepts2),
            shared=shared,
            only1=only1,
            only2=only2,
        ),
        None,
    )


def run_self_test() -> QuerySelfTestResult:
    """Run a small operational self-test for the semantic query stack."""
    store = _open_vector_store()
    embedder = _load_embedder()

    claim_count = store.get_claim_count()
    concept_count = store.get_concept_count()

    if claim_count == 0:
        raise RuntimeError("No claims in vectors database.")

    test_vector = embedder.embed("test query about technology")
    if len(test_vector) != 1536:
        raise RuntimeError(f"Unexpected embedding dimensions: {len(test_vector)}")

    conn = sqlite3.connect(VECTORS_DB)
    try:
        cursor = conn.execute("SELECT DISTINCT book_name FROM claims LIMIT 3")
        sample_books = [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()

    query_vec = test_vector
    store.search_claims(query_vec, top_k=3)
    store.search_concepts(query_vec, top_k=3)

    if sample_books:
        store.search_claims(query_vec, top_k=5, book_filter=sample_books[0])

    return QuerySelfTestResult(
        claim_count=claim_count,
        concept_count=concept_count,
        embedding_dimensions=len(test_vector),
        sample_books=sample_books,
    )
