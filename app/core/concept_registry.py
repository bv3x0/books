"""
Concept Registry - Normalizes and tracks concepts across books.

Provides concept normalization via exact match, alias lookup, and optional
embedding similarity for detecting semantically equivalent concepts.
"""

import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.logger import log


@dataclass
class Concept:
    """A concept that can appear across multiple books."""

    id: str
    label: str
    description: str = ""
    aliases: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    broader: Optional[str] = None  # SKOS-inspired parent concept ID
    book_claims: dict[str, int] = field(
        default_factory=dict
    )  # {book_name: claim_count}

    @property
    def books(self) -> list[str]:
        """Get list of books that reference this concept."""
        return list(self.book_claims.keys())

    @property
    def claim_count(self) -> int:
        """Get total claim count across all books."""
        return sum(self.book_claims.values())


class ConceptRegistry:
    """
    Registry for normalizing and tracking concepts across books.

    Supports:
    - Exact match lookup
    - Alias-based matching
    - Embedding similarity matching (optional, requires embedder)
    """
    SEMANTIC_THRESHOLD = 0.85
    SEMANTIC_CANDIDATE_LIMIT = 300
    SEMANTIC_EMBED_BATCH_SIZE = 100

    def __init__(self, path: str, embedder=None):
        """
        Initialize the concept registry.

        Args:
            path: Path to the _concepts.json file
            embedder: Optional embedder instance for similarity matching
        """
        self.path = Path(path)
        self.embedder = embedder
        self.concepts: dict[str, Concept] = {}
        self._embedding_cache: dict[str, list[float]] = {}
        self._token_cache: dict[str, set[str]] = {}
        self._load()

    def _load(self):
        """Load existing registry from disk, migrating from old format if needed."""
        if self.path.exists():
            try:
                with open(self.path) as f:
                    data = json.load(f)

                for cid, cdata in data.get("concepts", {}).items():
                    # Check if this is old format (has 'books' list and 'claim_count' int)
                    # or new format (has 'book_claims' dict)
                    if "book_claims" in cdata:
                        # New format
                        book_claims = cdata.get("book_claims", {})
                    else:
                        # Old format - migrate
                        # We can't perfectly reconstruct per-book counts, so distribute evenly
                        # or assign all to first book if only one
                        old_books = cdata.get("books", [])
                        old_count = cdata.get("claim_count", 0)

                        if old_books and old_count > 0:
                            # Distribute claims evenly across books
                            per_book = old_count // len(old_books)
                            remainder = old_count % len(old_books)
                            book_claims = {}
                            for i, book in enumerate(old_books):
                                book_claims[book] = per_book + (
                                    1 if i < remainder else 0
                                )
                        else:
                            book_claims = {}

                    self.concepts[cid] = Concept(
                        id=cdata.get("id", cid),
                        label=cdata.get("label", cid),
                        description=cdata.get("description", ""),
                        aliases=cdata.get("aliases", []),
                        related=cdata.get("related", []),
                        broader=cdata.get("broader"),
                        book_claims=book_claims,
                    )

                log.info(
                    f"ConceptRegistry: Loaded {len(self.concepts)} concepts from {self.path}"
                )
            except (json.JSONDecodeError, KeyError) as e:
                log.warning(f"ConceptRegistry: Failed to load {self.path}: {e}")
                self.concepts = {}
        else:
            log.info(
                f"ConceptRegistry: No existing registry at {self.path}, starting fresh"
            )

    def save(self):
        """Save registry to disk."""
        # Serialize concepts, converting book_claims to the format we want
        concepts_data = {}
        for cid, c in self.concepts.items():
            concept_data = {
                "id": c.id,
                "label": c.label,
                "description": c.description,
                "aliases": c.aliases,
                "related": c.related,
                "book_claims": c.book_claims,
                # Include computed properties for backward compatibility with readers
                "books": c.books,
                "claim_count": c.claim_count,
            }
            if c.broader:
                concept_data["broader"] = c.broader
            concepts_data[cid] = concept_data

        data = {
            "version": "2.0",
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "concepts": concepts_data,
            "stats": {
                "total_concepts": len(self.concepts),
                "total_claims": sum(c.claim_count for c in self.concepts.values()),
                "books_indexed": len(
                    set(b for c in self.concepts.values() for b in c.books)
                ),
            },
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)
        log.info(f"ConceptRegistry: Saved {len(self.concepts)} concepts to {self.path}")

    def normalize(self, raw_concept: str) -> str:
        """
        Normalize a concept tag, merging with existing if similar.

        Args:
            raw_concept: The raw concept string from Claude

        Returns:
            The canonical concept ID
        """
        # Clean and convert to snake_case
        concept_id = self._to_snake_case(raw_concept)

        if not concept_id:
            return "unknown"

        # Exact match
        if concept_id in self.concepts:
            return concept_id

        # Check aliases
        for cid, concept in self.concepts.items():
            if concept_id in concept.aliases:
                return cid

        # Semantic similarity check (if embedder available and we have concepts)
        if self.embedder and len(self.concepts) > 0:
            similar = self._find_similar(raw_concept, threshold=self.SEMANTIC_THRESHOLD)
            if similar:
                # Add as alias to existing concept
                self.concepts[similar].aliases.append(concept_id)
                log.debug(f"ConceptRegistry: Merged '{raw_concept}' → '{similar}'")
                return similar

        # Create new concept
        self.concepts[concept_id] = Concept(
            id=concept_id, label=self._to_title_case(raw_concept), description=""
        )
        self._token_cache.pop(concept_id, None)
        log.debug(f"ConceptRegistry: Created new concept '{concept_id}'")
        return concept_id

    def _find_similar(self, text: str, threshold: float) -> Optional[str]:
        """Find semantically similar existing concept."""
        if not self.embedder:
            return None

        try:
            candidate_ids = self._select_semantic_candidates(
                text, limit=self.SEMANTIC_CANDIDATE_LIMIT
            )
            if not candidate_ids:
                return None

            # Warm candidate embeddings in batch to avoid one API call per concept.
            candidate_labels = [self.concepts[cid].label for cid in candidate_ids]
            self._ensure_embeddings(candidate_labels)

            query_emb = self._get_embedding(text)
            best_match = None
            best_score = 0

            for cid in candidate_ids:
                concept = self.concepts[cid]
                concept_emb = self._embedding_cache.get(concept.label)
                if not concept_emb:
                    continue
                score = self._cosine_similarity(query_emb, concept_emb)
                if score > threshold and score > best_score:
                    best_match = cid
                    best_score = score

            return best_match
        except Exception as e:
            log.warning(f"ConceptRegistry: Embedding similarity check failed: {e}")
            return None

    def _select_semantic_candidates(self, text: str, limit: int) -> list[str]:
        """
        Select candidate concepts for semantic comparison.

        Prefilters by token overlap so semantic merge cost scales with related concepts
        instead of the full registry size.
        """
        query_tokens = self._tokenize(text)
        if not query_tokens:
            return []

        scored = []
        for cid, concept in self.concepts.items():
            concept_tokens = self._get_concept_tokens(cid, concept.label)
            if not concept_tokens:
                continue

            overlap = len(query_tokens & concept_tokens)
            if overlap == 0:
                continue

            union = len(query_tokens | concept_tokens)
            jaccard = overlap / union if union else 0.0
            scored.append((overlap, jaccard, cid))

        if not scored:
            return []

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [cid for _, _, cid in scored[:limit]]

    def _ensure_embeddings(self, texts: list[str]) -> None:
        """Fetch and cache missing embeddings, preferring batched API calls."""
        if not self.embedder:
            return

        missing = [text for text in texts if text and text not in self._embedding_cache]
        if not missing:
            return

        batch_size = self.SEMANTIC_EMBED_BATCH_SIZE
        for i in range(0, len(missing), batch_size):
            batch = missing[i : i + batch_size]
            embeddings = self.embedder.embed_batch(batch, batch_size=batch_size)
            for text, emb in zip(batch, embeddings):
                self._embedding_cache[text] = emb

    def _get_embedding(self, text: str) -> list[float]:
        """Get embedding for text, with caching."""
        if text not in self._embedding_cache:
            self._embedding_cache[text] = self.embedder.embed(text)
        return self._embedding_cache[text]

    def _get_concept_tokens(self, concept_id: str, label: str) -> set[str]:
        """Get tokenized label for a concept, with caching."""
        tokens = self._token_cache.get(concept_id)
        if tokens is None:
            tokens = self._tokenize(label)
            self._token_cache[concept_id] = tokens
        return tokens

    def set_book_claims(self, concept_id: str, book_name: str, count: int):
        """
        Set the claim count for a specific book (replaces existing count).

        Args:
            concept_id: The concept ID
            book_name: Name of the book
            count: Total claim count for this book
        """
        if concept_id in self.concepts:
            if count > 0:
                self.concepts[concept_id].book_claims[book_name] = count
            elif book_name in self.concepts[concept_id].book_claims:
                del self.concepts[concept_id].book_claims[book_name]

    def get_stats(self) -> dict:
        """Get registry statistics."""
        return {
            "total_concepts": len(self.concepts),
            "total_claims": sum(c.claim_count for c in self.concepts.values()),
            "books_indexed": len(
                set(b for c in self.concepts.values() for b in c.books)
            ),
            "concepts_with_aliases": sum(
                1 for c in self.concepts.values() if c.aliases
            ),
        }

    def remove_book_references(self, book_name: str) -> int:
        """
        Remove all references to a book from concepts.

        Args:
            book_name: Name of the book to remove

        Returns:
            Number of concepts that referenced this book
        """
        removed_count = 0
        concepts_to_delete = []

        for cid, concept in self.concepts.items():
            if book_name in concept.book_claims:
                del concept.book_claims[book_name]
                removed_count += 1

                # Mark empty concepts for deletion
                if not concept.book_claims:
                    concepts_to_delete.append(cid)

        # Delete concepts with no remaining books
        for cid in concepts_to_delete:
            del self.concepts[cid]
            self._token_cache.pop(cid, None)

        log.info(
            f"ConceptRegistry: Removed '{book_name}' from {removed_count} concepts, deleted {len(concepts_to_delete)} empty concepts"
        )
        return removed_count

    def cleanup_orphaned_concepts(self) -> int:
        """
        Remove concepts that have no book references.

        Returns:
            Number of concepts removed
        """
        orphaned = [cid for cid, c in self.concepts.items() if not c.book_claims]
        for cid in orphaned:
            del self.concepts[cid]
            self._token_cache.pop(cid, None)

        if orphaned:
            log.info(f"ConceptRegistry: Cleaned up {len(orphaned)} orphaned concepts")
        return len(orphaned)

    @staticmethod
    def _to_snake_case(text: str) -> str:
        """Convert text to snake_case."""
        text = text.lower().strip()
        # Remove non-alphanumeric except spaces and underscores
        text = re.sub(r"[^\w\s]", "", text)
        # Replace spaces with underscores
        text = re.sub(r"\s+", "_", text)
        # Remove consecutive underscores
        text = re.sub(r"_+", "_", text)
        # Strip leading/trailing underscores
        text = text.strip("_")
        return text

    @staticmethod
    def _to_title_case(text: str) -> str:
        """Convert snake_case to Title Case."""
        return text.replace("_", " ").title()

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """Normalize text into lowercase alphanumeric tokens."""
        return set(re.findall(r"[a-z0-9]+", (text or "").lower()))

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not a or not b or len(a) != len(b):
            return 0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0
