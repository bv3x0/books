"""
Exporter - Exports processed book data to notes and index files.

For the unified pipeline (v2.0), this module:
- Parses JSON responses from Claude
- Normalizes concepts against the concept registry
- Renders human-readable markdown for the blog (notes/)
- Generates machine-readable index JSON for retrieval (index/)

For legacy pipeline, maintains backward compatibility with markdown responses.
"""

import json
import os
import re
from collections import Counter
from datetime import datetime

from app.config import (
    CONCEPTS_PATH,
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    INDEX_DIR,
    MODEL_ID,
    NOTES_DIR,
    VECTORS_DB_PATH,
    get_index_path,
    get_notes_path,
)
from app.categories import validate_categories
from app.core.embedder import Embedder
from app.core.vector_store import VectorStore
from app.logger import log


class Exporter:
    def __init__(
        self,
        client,
        output_dir,
        book_name=None,
        summary_mode="quick",
        concept_registry=None,
        use_unified=True,
        enable_embeddings=True,
        model_id=MODEL_ID,
        export_index=True,
        update_concepts=True,
        notes_suffix="",
        cache_suffix="",
    ):
        """
        Initialize the Exporter.

        Args:
            client: Anthropic client (for legacy metadata generation)
            output_dir: Directory for intermediate files
            book_name: Name of the book being processed
            summary_mode: "quick" or "default"
            concept_registry: ConceptRegistry instance for unified pipeline
            use_unified: Whether to use unified JSON processing
            enable_embeddings: Whether to generate and store embeddings
            model_id: Model ID used for this run (for metadata)
            export_index: Whether to write index JSON output
            update_concepts: Whether to update global concept registry
            notes_suffix: Optional suffix for notes filename (e.g. ".gem")
            cache_suffix: Optional suffix for run cache filename
        """
        self.client = client
        self.output_dir = output_dir
        self.book_name = book_name or os.path.basename(output_dir)
        # Use book-specific cache in logs directory (matches monitor.py)
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
        cache_suffix = cache_suffix.strip()
        self.results_cache = os.path.join(
            logs_dir, f"{self.book_name}{cache_suffix}_cache.json"
        )
        self.summary_mode = "quick" if summary_mode == "quick" else "full"
        self.concept_registry = concept_registry
        self.use_unified = use_unified
        self.enable_embeddings = enable_embeddings
        self.model_id = model_id
        self.export_index = export_index
        self.update_concepts = update_concepts and export_index
        self.notes_suffix = notes_suffix.strip()
        self.last_notes_path = None
        self.last_index_path = None

        if not self.export_index:
            self.enable_embeddings = False

        # Initialize embedder and vector store if enabled
        if self.enable_embeddings:
            try:
                self.embedder = Embedder(
                    model=EMBEDDING_MODEL, dimensions=EMBEDDING_DIMENSIONS
                )
                self.vector_store = VectorStore(
                    db_path=VECTORS_DB_PATH, dimensions=EMBEDDING_DIMENSIONS
                )
                log.info("Exporter: Embeddings enabled")
            except Exception as e:
                log.warning(f"Exporter: Could not initialize embeddings: {e}")
                self.enable_embeddings = False
                self.embedder = None
                self.vector_store = None
        else:
            self.embedder = None
            self.vector_store = None

    # =========================================================================
    # UNIFIED PIPELINE (v2.0) - JSON Processing
    # =========================================================================

    def export_unified(self, results: list) -> tuple[str, str]:
        """
        Export unified JSON results to both notes and index.

        Args:
            results: List of result dicts from Monitor, each with 'data' key
                    containing parsed JSON

        Returns:
            (notes_path, index_path) tuple
        """
        log.info("Exporter: Processing unified JSON results...")

        # Merge results from multiple chunks
        unified_data = self._merge_unified_results(results)

        if not unified_data:
            log.error("Exporter: No valid data to export")
            return None, None

        self._apply_source_metadata(unified_data, results)
        self._preserve_existing_collections(unified_data)

        # Add processing metadata
        unified_data["metadata"] = {
            "processed_at": datetime.utcnow().isoformat() + "Z",
            "pipeline_version": "2.2",  # v2.2: stable claim IDs + richer embedding context
            "model": self.model_id,
            "mode": self.summary_mode,
        }

        # Normalize concepts if registry available
        if self.concept_registry:
            log.info("Exporter: Normalizing concepts against registry...")
            self._normalize_concepts(unified_data)

        concepts_used = set()

        # Generate embeddings and store in vector DB
        if self.enable_embeddings:
            self._generate_and_store_embeddings(unified_data)
            if self.concept_registry:
                concepts_used = self._collect_concepts_used(unified_data)

        # Generate markdown for human reading
        markdown = self._render_markdown(unified_data)
        notes_path = self._save_notes(markdown)

        index_path = None
        if self.export_index:
            # Generate index for machine retrieval
            index_data = self._build_index(unified_data)
            index_path = self._save_index(index_data)

        # Update concept registry with book references
        if self.concept_registry and self.update_concepts:
            self._update_concept_registry(unified_data)

        # Keep concept vectors synced with current registry book metadata.
        if self.enable_embeddings and self.concept_registry and concepts_used:
            self._update_concept_embeddings(concepts_used)

        # Report concept health for this book
        if self.concept_registry and self.update_concepts:
            self._report_concept_health(unified_data)

        if index_path:
            log.info(f"Exporter: Exported to {notes_path} and {index_path}")
        else:
            log.info(f"Exporter: Exported notes-only output to {notes_path}")
        return notes_path, index_path

    def _merge_unified_results(self, results: list) -> dict:
        """
        Merge results from multiple chunks into single unified output.

        For books processed in multiple API calls, combines chapter data.
        Deduplicates chapters by title (keeps first occurrence).
        """
        strict_fidelity = os.getenv("SUMMARIZER_FIDELITY_STRICT") == "1"
        successful = [
            r
            for r in results
            if r.get("data")
            and (
                r.get("status") == "SUCCESS"
                or (
                    not strict_fidelity
                    and r.get("status") == "FIDELITY_FAILED"
                )
            )
        ]

        if not successful:
            log.error("Exporter: No successful results to merge")
            return None

        # Merge chapters from all chunks
        log.info(f"Exporter: Merging {len(successful)} chunks...")

        merged = {"book": successful[0]["data"].get("book", {}), "chapters": []}

        seen_titles = set()
        duplicates = []

        for result in successful:
            data = result.get("data", {})
            chapters = data.get("chapters", [])
            for chapter in chapters:
                title = chapter.get("title", "")
                if title in seen_titles:
                    duplicates.append(title)
                    log.warning(f"Exporter: Skipping duplicate chapter: {title}")
                else:
                    seen_titles.add(title)
                    merged["chapters"].append(chapter)

        if duplicates:
            log.warning(
                f"Exporter: Removed {len(duplicates)} duplicate chapters: {duplicates}"
            )

        log.info(
            f"Exporter: Merged {len(merged['chapters'])} total chapters (after deduplication)"
        )
        return merged

    def _apply_source_metadata(self, data: dict, results: list) -> None:
        """Override model-derived book metadata with deterministic source metadata."""
        source_metadata = {}
        for result in results:
            file_metadata = result.get("file_metadata") or {}
            candidate = file_metadata.get("source_metadata") or {}
            for key in ("title", "author", "year"):
                if not source_metadata.get(key) and candidate.get(key):
                    source_metadata[key] = candidate[key]

        if not source_metadata:
            return

        book = data.setdefault("book", {})
        updated = []
        for key in ("title", "author", "year"):
            value = source_metadata.get(key)
            if value:
                book[key] = value
                updated.append(key)

        if updated:
            log.info(
                "Exporter: Applied source metadata for "
                + ", ".join(sorted(updated))
            )

    def _preserve_existing_collections(self, data: dict) -> None:
        """Carry forward curated collections when overwriting an existing note."""
        book = data.setdefault("book", {})
        if book.get("collections"):
            return

        collections = self._extract_existing_collections()
        if collections:
            book["collections"] = collections
            log.info(
                f"Exporter: Preserved existing collections: {', '.join(collections)}"
            )

    def _extract_existing_collections(self) -> list[str]:
        if self.notes_suffix:
            path = os.path.join(NOTES_DIR, f"{self.book_name}{self.notes_suffix}.md")
        else:
            path = get_notes_path(self.book_name)

        if not os.path.exists(path):
            return []

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError:
            return []

        match = re.search(r"^- Collections:\s*(.+?)\s*$", content, re.MULTILINE)
        if not match:
            return []

        return [
            item.strip()
            for item in match.group(1).split(",")
            if item.strip()
        ]

    def _normalize_concepts(self, data: dict) -> None:
        """Normalize all concept tags against the registry."""
        if not self.concept_registry:
            return

        for chapter in data.get("chapters", []):
            for kp in chapter.get("key_points", []):
                normalized = []
                seen = set()
                for concept in kp.get("concepts", []):
                    norm_id = self.concept_registry.normalize(concept)
                    if norm_id and norm_id not in seen:
                        normalized.append(norm_id)
                        seen.add(norm_id)
                kp["concepts"] = normalized

    def _generate_and_store_embeddings(self, data: dict) -> None:
        """
        Generate embeddings for all claims and quotes, store in vector database.

        This method:
        1. Extracts all claims from key_points
        2. Generates embeddings in batches for efficiency
        3. Stores claims with embeddings in the vector store
        4. Extracts and embeds quotes from structured sub_points
        5. Updates concept embeddings in the vector store
        """
        if not self.embedder or not self.vector_store:
            return

        log.info("Exporter: Generating embeddings for claims...")

        # Replace the entire book slice so re-runs cannot silently accumulate stale IDs.
        deleted_quotes = self.vector_store.delete_book_quotes(self.book_name)
        deleted_claims = self.vector_store.delete_book_claims(self.book_name)
        if deleted_claims or deleted_quotes:
            log.info(
                f"Exporter: Replaced existing vectors for '{self.book_name}' "
                f"({deleted_claims} claims, {deleted_quotes} quotes removed)"
            )

        # Collect all claims with metadata (extracted from key_points)
        all_claims = []
        claim_texts = []
        all_quotes = []  # Collect quotes for separate embedding

        book_info = data.get("book", {})
        book_title = book_info.get("title", self.book_name)

        for claim in self._iter_claim_records(data):
            chapter_title = claim.get("chapter_title", "")
            part = claim.get("part")
            claim_text = claim["text"]
            sub_points = claim.get("sub_points", [])
            entities = claim.get("entities", {})

            embedding_text = self._build_claim_embedding_text(
                book_title=book_title,
                chapter_title=chapter_title,
                part=part,
                claim_text=claim_text,
                sub_points=sub_points,
            )

            all_claims.append(
                {
                    "id": claim["id"],
                    "book_name": self.book_name,
                    "chapter_index": claim["chapter_index"],
                    "claim_index": claim["claim_index"],
                    "chapter_title": chapter_title,
                    "part": part,
                    "text": claim_text,
                    "embedding_text": embedding_text,
                    "concepts": claim.get("concepts", []),
                    "entities": entities,
                    "sub_points": sub_points,
                }
            )
            claim_texts.append(embedding_text)

            # Extract quotes from structured sub_points
            for sp_idx, sub_point in enumerate(sub_points):
                if isinstance(sub_point, dict) and sub_point.get("speaker"):
                    quote_id = f"{claim['id']}_q{sp_idx}"
                    all_quotes.append(
                        {
                            "id": quote_id,
                            "claim_id": claim["id"],
                            "book_name": self.book_name,
                            "chapter_title": chapter_title,
                            "claim_text": claim_text,
                            "text": sub_point.get("text", ""),
                            "speaker": sub_point.get("speaker", ""),
                        }
                    )

        if not all_claims:
            log.warning("Exporter: No claims found to embed")
            return

        # Generate embeddings in batch
        log.info(f"Exporter: Generating {len(claim_texts)} claim embeddings...")
        embeddings = self.embedder.embed_batch(claim_texts, batch_size=100)

        # Add embeddings to claim data
        for claim, embedding in zip(all_claims, embeddings):
            claim["embedding"] = embedding

        # Store in vector database
        log.info(f"Exporter: Storing {len(all_claims)} claims in vector store...")
        self.vector_store.add_claims_batch(all_claims)

        # Generate and store quote embeddings
        if all_quotes:
            log.info(f"Exporter: Generating {len(all_quotes)} quote embeddings...")
            quote_texts = [
                self._build_quote_embedding_text(quote, book_title=book_title)
                for quote in all_quotes
            ]
            quote_embeddings = self.embedder.embed_batch(quote_texts, batch_size=100)

            for quote, embedding in zip(all_quotes, quote_embeddings):
                quote["embedding"] = embedding

            log.info(f"Exporter: Storing {len(all_quotes)} quotes in vector store...")
            self.vector_store.add_quotes_batch(all_quotes)

            quote_count = self.vector_store.get_quote_count()
            log.info(f"Exporter: Vector store now contains {quote_count} total quotes")

        claim_count = self.vector_store.get_claim_count()
        log.info(f"Exporter: Vector store now contains {claim_count} total claims")

    def _update_concept_embeddings(self, concepts_used: set = None) -> None:
        """
        Update embeddings for concepts used in this book.

        Only embeds concepts that were actually used in this book and don't
        already have embeddings, to avoid re-embedding the entire registry.
        """
        if not self.embedder or not self.vector_store or not self.concept_registry:
            return

        if not concepts_used:
            log.info("Exporter: No concepts to embed")
            return

        concept_rows_updated = 0
        for concept_id in sorted(concepts_used):
            concept_data = self.concept_registry.concepts.get(concept_id)
            if not concept_data:
                continue
            if hasattr(self.vector_store, "upsert_concept_metadata"):
                self.vector_store.upsert_concept_metadata(
                    concept_id=concept_id,
                    label=concept_data.label,
                    books=concept_data.books,
                )
                concept_rows_updated += 1

        # Only embed concepts used in this book that don't have embeddings yet
        existing_concepts = self.vector_store.get_existing_concept_ids()
        new_concepts = concepts_used - existing_concepts

        if not new_concepts:
            if concept_rows_updated:
                log.info(
                    f"Exporter: Updated metadata for {concept_rows_updated} concepts; no new concept embeddings needed"
                )
            log.info(
                f"Exporter: All {len(concepts_used)} concepts already have embeddings"
            )
            return

        log.info(
            f"Exporter: Embedding {len(new_concepts)} new concepts (skipping {len(concepts_used) - len(new_concepts)} existing)..."
        )

        concept_count = 0
        for concept_id in sorted(new_concepts):
            concept_data = self.concept_registry.concepts.get(concept_id)
            if not concept_data:
                continue

            # Generate embedding for concept
            embedding = self.embedder.embed_concept(concept_id, book_context=None)

            # Store in vector database
            self.vector_store.add_concept(
                concept_id=concept_id,
                label=concept_data.label,
                embedding=embedding,
                books=concept_data.books,
            )
            concept_count += 1

        log.info(
            f"Exporter: Updated {concept_rows_updated} concept rows and embedded {concept_count} new concepts"
        )

    def _render_markdown(self, data: dict) -> str:
        """Render unified data as human-readable markdown."""
        lines = []

        # Title
        book = data.get("book", {})
        title = book.get("title", self.book_name)
        book_slug = self._slugify(title)  # For claim anchor IDs
        lines.append(f"# {title}\n")

        # Metadata section
        lines.append("## Metadata")
        if book.get("thesis"):
            lines.append(f"- Thesis: {book['thesis']}")
        if book.get("topics"):
            lines.append(f"- Topics: {', '.join(book['topics'])}")
        if book.get("categories"):
            valid_cats = validate_categories(book["categories"])
            if valid_cats:
                lines.append(f"- Categories: {', '.join(valid_cats)}")
            if len(valid_cats) != len(book["categories"]):
                rejected = set(c.lower().strip() for c in book["categories"]) - set(valid_cats)
                log.warning(f"Exporter: Rejected non-BISAC categories: {rejected}")
        if book.get("author"):
            lines.append(f"- Author: {book['author']}")
        lines.append(f"- Year: {book.get('year') or ''}")
        if book.get("collections"):
            lines.append(f"- Collections: {', '.join(book['collections'])}")
        lines.append(
            f"- Mode: {data.get('metadata', {}).get('mode', self.summary_mode)}"
        )
        lines.append("")

        # Chapters (with Part support)
        claim_counter = 1  # Track claim numbers for anchor IDs
        chapters = data.get("chapters", [])

        # Check if book has Parts
        has_parts = any(ch.get("part") for ch in chapters)
        current_part = None

        for chapter in chapters:
            chapter_title = chapter.get("title", "Untitled")
            chapter_part = chapter.get("part")

            # Output Part heading when part changes
            if has_parts and chapter_part and chapter_part != current_part:
                current_part = chapter_part
                lines.append(f"## {current_part}\n")

            # Use ### for chapters under Parts, ## for chapters without Parts
            heading_level = "###" if has_parts else "##"
            lines.append(f"{heading_level} {chapter_title}\n")

            if chapter.get("summary"):
                lines.append(f"{chapter['summary']}\n")

            # Pull quote: rendered as a styled list item midway through claims
            key_points = chapter.get("key_points", [])
            visible_key_points = [
                kp for kp in key_points if (kp.get("point", "") or "").strip()
            ]
            pull_quote = chapter.get("pull_quote")
            pull_quote_after = None
            if pull_quote and len(visible_key_points) >= 6:
                pull_quote_after = len(visible_key_points) // 2

            visible_idx = 0
            for kp_idx, kp in enumerate(key_points):
                point = (kp.get("point", "") or "").strip()
                if not point:
                    continue

                # Insert pull quote before this claim if we've hit the midpoint
                if pull_quote_after is not None and visible_idx == pull_quote_after:
                    lines.append(f'* <span class="pull-quote">{pull_quote}</span>')

                claim_id = self._make_claim_id(book_slug, claim_counter)
                # Include anchor span for deep linking
                lines.append(f'* <span id="{claim_id}"></span>**{point}**')
                for sub in kp.get("sub_points", []):
                    # Handle both new structured format and legacy string format
                    if isinstance(sub, dict):
                        text = sub.get("text", "")
                        speaker = sub.get("speaker")
                        if speaker:
                            # Escape internal quotes to avoid unbalanced markdown
                            safe_text = text.replace('"', "'")
                            lines.append(f'    - "{safe_text}" —{speaker}')
                        else:
                            lines.append(f"    - {text}")
                    else:
                        # Legacy string format
                        lines.append(f"    - {sub}")
                claim_counter += 1
                visible_idx += 1

            lines.append("")

        return "\n".join(lines)

    def _build_index(self, data: dict) -> dict:
        """Build index structure optimized for retrieval."""
        book = data.get("book", {})
        book_slug = self._slugify(book.get("title", self.book_name))

        # Collect all claims with IDs (one vector/index row per claim-sized key point).
        claims = []
        chapter_claim_ids_by_index = {}
        for claim in self._iter_claim_records(data):
            claim_data = {
                "id": claim["id"],
                "text": claim["text"],
                "chapter": claim.get("chapter_title", ""),
                "concepts": claim.get("concepts", []),
                "entities": claim.get("entities", {}),
                "sub_points": claim.get("sub_points", []),
            }
            if claim.get("part"):
                claim_data["part"] = claim["part"]
            claims.append(claim_data)
            chapter_claim_ids_by_index.setdefault(claim["chapter_index"], []).append(
                claim["id"]
            )

        chapters = []
        for ch_idx, chapter in enumerate(data.get("chapters", [])):
            chapter_id = f"{book_slug}-ch-{ch_idx + 1:03d}"
            chapter_data = {
                "id": chapter_id,
                "title": chapter.get("title", ""),
                "summary": chapter.get("summary", ""),
                "claim_ids": chapter_claim_ids_by_index.get(ch_idx, []),
            }
            if chapter.get("part"):
                chapter_data["part"] = chapter.get("part")
            chapters.append(chapter_data)

        return {
            "version": "2.2",
            "book": {
                "title": book.get("title", self.book_name),
                "author": book.get("author"),
                "year": book.get("year"),
                "categories": validate_categories(book.get("categories", [])),
                "collections": book.get("collections", []),
                "thesis": book.get("thesis", ""),
            },
            "claims": claims,
            "chapters": chapters,
            "stats": {
                "claim_count": len(claims),
                "chapter_count": len(chapters),
                "indexed_at": datetime.utcnow().isoformat() + "Z",
            },
        }

    def _update_concept_registry(self, data: dict) -> None:
        """Update concept registry with book references and claim counts."""
        if not self.concept_registry:
            return

        # Use stable book key so re-runs replace old counts instead of accumulating.
        book_name = self.book_name
        book_title = data.get("book", {}).get("title", "").strip()
        if book_title and book_title != book_name:
            self.concept_registry.remove_book_references(book_title)
        self.concept_registry.remove_book_references(book_name)

        concept_counts = Counter()
        for claim in self._iter_claim_records(data):
            for concept in claim.get("concepts", []):
                if concept:
                    concept_counts[concept] += 1

        for concept_id, count in concept_counts.items():
            if concept_id not in self.concept_registry.concepts:
                self.concept_registry.normalize(concept_id)
            self.concept_registry.set_book_claims(concept_id, book_name, count)

    def _collect_concepts_used(self, data: dict) -> set[str]:
        """Collect unique normalized concept IDs used in this dataset."""
        concepts = set()
        for claim in self._iter_claim_records(data):
            for concept in claim.get("concepts", []):
                if concept:
                    concepts.add(concept)
        return concepts

    @staticmethod
    def _make_claim_id(book_slug: str, claim_counter: int) -> str:
        """Generate stable claim IDs shared across notes anchors, index, and vectors."""
        return f"{book_slug}-{claim_counter:03d}"

    def _iter_claim_records(self, data: dict):
        """Yield claim-sized records in deterministic order with stable IDs."""
        book = data.get("book", {})
        book_slug = self._slugify(book.get("title", self.book_name))
        claim_counter = 1

        for chapter_idx, chapter in enumerate(data.get("chapters", [])):
            for kp_idx, kp in enumerate(chapter.get("key_points", [])):
                point = (kp.get("point", "") or "").strip()
                if not point:
                    continue

                yield {
                    "id": self._make_claim_id(book_slug, claim_counter),
                    "chapter_index": chapter_idx,
                    "claim_index": kp_idx,
                    "chapter_title": chapter.get("title", ""),
                    "part": chapter.get("part"),
                    "text": point,
                    "concepts": kp.get("concepts", []),
                    "entities": kp.get("entities", {}),
                    "sub_points": kp.get("sub_points", []),
                }
                claim_counter += 1

    @staticmethod
    def _truncate_text(text: str, limit: int = 240) -> str:
        """Trim text for embedding context fields without dropping semantics."""
        cleaned = (text or "").strip()
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: limit - 1].rstrip() + "…"

    def _format_sub_point_for_embedding(self, sub_point) -> str:
        """Normalize sub-point data into short support snippets."""
        if isinstance(sub_point, dict):
            text = self._truncate_text(sub_point.get("text", ""))
            speaker = (sub_point.get("speaker") or "").strip()
            evidence_type = (sub_point.get("type") or "").strip()
            if text and speaker:
                formatted = f'"{text}" —{speaker}'
            else:
                formatted = text
            if formatted and evidence_type:
                return f"{evidence_type}: {formatted}"
            return formatted
        if isinstance(sub_point, str):
            return self._truncate_text(sub_point)
        return self._truncate_text(str(sub_point))

    def _build_claim_embedding_text(
        self,
        book_title: str,
        chapter_title: str,
        part: str,
        claim_text: str,
        sub_points: list,
    ) -> str:
        """Build claim-level embedding text with enough context to stand alone."""
        context_lines = [f"Book: {book_title}"]
        if part:
            context_lines.append(f"Part: {part}")
        if chapter_title:
            context_lines.append(f"Chapter: {chapter_title}")
        context_lines.append(f"Claim: {claim_text.strip()}")

        support_lines = []
        for sub_point in sub_points or []:
            formatted = self._format_sub_point_for_embedding(sub_point)
            if formatted:
                support_lines.append(formatted)
            if len(support_lines) >= 2:
                break
        if support_lines:
            context_lines.append("Support: " + " | ".join(support_lines))

        return "\n".join(context_lines)

    def _build_quote_embedding_text(self, quote: dict, book_title: str) -> str:
        """Build quote embedding text with claim/chapter context."""
        text = (quote.get("text", "") or "").strip()
        speaker = (quote.get("speaker", "") or "").strip()
        chapter_title = (quote.get("chapter_title", "") or "").strip()
        claim_text = self._truncate_text(quote.get("claim_text", ""), limit=200)
        parts = [f'Quote: "{text}"']
        if speaker:
            parts.append(f"Speaker: {speaker}")
        parts.append(f"Book: {book_title}")
        if chapter_title:
            parts.append(f"Chapter: {chapter_title}")
        if claim_text:
            parts.append(f"Related claim: {claim_text}")
        return "\n".join(parts)

    def _report_concept_health(self, data: dict) -> None:
        """Report concept quality metrics for this book's processing run."""
        if not self.concept_registry:
            return

        # Gather concepts used in this book
        book_concepts = self._collect_concepts_used(data)

        if not book_concepts:
            return

        # Count singletons (concepts appearing in only this book)
        registry = self.concept_registry.concepts
        singletons = 0
        reused = []

        for cid in book_concepts:
            concept = registry.get(cid)
            if not concept:
                continue
            n_books = len(concept.book_claims)
            if n_books <= 1:
                singletons += 1
            else:
                reused.append((cid, n_books))

        total = len(book_concepts)
        singleton_rate = singletons / total if total else 0
        reused.sort(key=lambda x: x[1], reverse=True)

        # Print health report
        print(f"\n{'=' * 60}", flush=True)
        print("CONCEPT HEALTH REPORT", flush=True)
        print(f"{'=' * 60}", flush=True)
        print(f"Total concepts for this book:  {total}", flush=True)
        print(f"New (singleton) concepts:      {singletons} ({singleton_rate:.0%})", flush=True)
        print(f"Reused from existing registry: {total - singletons}", flush=True)

        if reused:
            print(f"\nTop reused concepts:", flush=True)
            for cid, n_books in reused[:10]:
                print(f"  {cid:40s} ({n_books} books)", flush=True)

        # Warnings
        if singleton_rate > 0.85 and total > 10:
            print(f"\n  WARNING: Singleton rate {singleton_rate:.0%} is high (>85%).", flush=True)
            print(f"  Most concepts are unique to this book — consider more general tagging.", flush=True)

        if total > 500:
            print(f"\n  WARNING: {total} concepts is unusually high.", flush=True)
            print(f"  Expected range: 50-300 for a typical book.", flush=True)

        print(f"{'=' * 60}\n", flush=True)

        log.info(
            f"Exporter: Concept health — {total} concepts, "
            f"{singletons} singletons ({singleton_rate:.0%}), "
            f"{total - singletons} reused"
        )

    def _save_notes(self, markdown: str) -> str:
        """Save markdown to notes directory."""
        os.makedirs(NOTES_DIR, exist_ok=True)
        if self.notes_suffix:
            path = os.path.join(NOTES_DIR, f"{self.book_name}{self.notes_suffix}.md")
        else:
            path = get_notes_path(self.book_name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(markdown)
        log.info(f"Exporter: Saved notes to {path} ({len(markdown):,} chars)")
        self.last_notes_path = path
        return path

    def _save_index(self, index_data: dict) -> str:
        """Save index to index directory."""
        os.makedirs(INDEX_DIR, exist_ok=True)
        path = get_index_path(self.book_name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(index_data, f, indent=2)
        log.info(f"Exporter: Saved index to {path}")
        self.last_index_path = path
        return path

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to URL-safe slug."""
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_]+", "-", text)
        text = re.sub(r"-+", "-", text)
        return text.strip("-")[:50]

    # =========================================================================
    # LEGACY PIPELINE - Markdown Processing (backward compatibility)
    # =========================================================================

    def save_results(self, job_name) -> bool:
        """
        Saves the results from sequential processing to local markdown files.
        Legacy method for backward compatibility.
        """
        log.info("Exporter: Retrieving results...")
        try:
            if os.path.exists(self.results_cache):
                with open(self.results_cache, "r") as f:
                    results = json.load(f)

                # Check if these are unified results
                if results and results[0].get("use_unified"):
                    log.info("Exporter: Detected unified results, using export_unified")
                    notes_path, index_path = self.export_unified(results)
                    if not notes_path:
                        log.error("Exporter: Unified export did not produce notes output")
                        return False
                    # Only delete cache if all chunks succeeded (for --retry support)
                    failed_chunks = [r for r in results if r.get("status") != "SUCCESS"]
                    if failed_chunks:
                        log.info(
                            f"Exporter: Keeping cache for retry ({len(failed_chunks)} failed chunks)"
                        )
                    else:
                        os.remove(self.results_cache)
                        log.debug(
                            "Exporter: Cleaned up cache file (all chunks succeeded)"
                        )
                    return True

                # Legacy markdown processing
                log.debug(f"Exporter: Loaded {len(results)} results from cache")

                saved_count = 0
                skipped_count = 0

                for result in results:
                    if result.get("status") == "SUCCESS":
                        output_text = result.get("response", "")

                        filename = f"part_{result['index']}.md"
                        filepath = os.path.join(self.output_dir, filename)

                        with open(filepath, "w") as f:
                            f.write(output_text)

                        log.info(
                            f"Exporter: Saved {filename} ({len(output_text):,} chars)"
                        )
                        saved_count += 1
                    else:
                        log.warning(
                            f"Exporter: Skipping failed result at index {result.get('index')}: {result.get('error', 'Unknown error')}"
                        )
                        skipped_count += 1

                log.info(
                    f"Exporter: Finished - saved {saved_count} files, skipped {skipped_count} failed"
                )

                # Only delete cache if all chunks succeeded (for --retry support)
                if skipped_count > 0:
                    log.info(
                        f"Exporter: Keeping cache for retry ({skipped_count} failed chunks)"
                    )
                else:
                    os.remove(self.results_cache)
                    log.debug("Exporter: Cleaned up cache file (all chunks succeeded)")
                return saved_count > 0

            else:
                log.error(f"Exporter: No cached results found at {self.results_cache}")
                return False

        except Exception as e:
            log.error(f"Exporter: Failed to export results: {e}")
            return False

    def merge_results(self):
        """
        Merges all part_*.md files in the output directory into a single summary file in notes/.
        Legacy method for backward compatibility.
        """
        log.info("Exporter: Merging results into single file...")
        try:
            # Find all part files
            files = [
                f
                for f in os.listdir(self.output_dir)
                if f.startswith("part_") and f.endswith(".md")
            ]

            # Sort them numerically based on the integer in the filename
            def get_part_num(filename):
                parts = filename.replace("part_", "").replace(".md", "")
                return int(parts) if parts.isdigit() else 999999

            files.sort(key=get_part_num)

            if not files:
                log.warning("Exporter: No part files found to merge.")
                return

            log.debug(f"Exporter: Merging {len(files)} files: {files}")

            # Ensure notes directory exists
            os.makedirs(NOTES_DIR, exist_ok=True)

            # Output to notes directory
            full_summary_path = get_notes_path(self.book_name)
            total_chars = 0

            with open(full_summary_path, "w") as outfile:
                # Write title placeholder (will be replaced by add_frontmatter)
                outfile.write(f"# {self.book_name}\n\n")
                for filename in files:
                    filepath = os.path.join(self.output_dir, filename)
                    with open(filepath, "r") as infile:
                        content = infile.read()
                        total_chars += len(content)
                        outfile.write(content)
                        outfile.write("\n\n")

            log.info(f"Exporter: Merged {len(files)} chapters into {full_summary_path}")
            log.info(f"Exporter: Total size: {total_chars:,} characters")

            # Normalize markdown structure
            log.info("Exporter: Normalizing markdown structure...")
            try:
                from app.core.normalizer import StructureNormalizer

                normalizer = StructureNormalizer()
                with open(full_summary_path, "r", encoding="utf-8") as f:
                    content = f.read()
                normalized_content = normalizer.normalize(content)
                with open(full_summary_path, "w", encoding="utf-8") as f:
                    f.write(normalized_content)
                log.info("Exporter: Markdown structure normalized successfully")
            except Exception as e:
                log.warning(
                    f"Exporter: Failed to normalize structure (continuing anyway): {e}"
                )

            # Delete individual chapter files after successful merge
            deleted_count = 0
            failed_count = 0
            for filename in files:
                filepath = os.path.join(self.output_dir, filename)
                try:
                    os.remove(filepath)
                    deleted_count += 1
                    log.debug(f"Exporter: Deleted {filename}")
                except Exception as e:
                    failed_count += 1
                    log.warning(f"Exporter: Failed to delete {filename}: {e}")

            if deleted_count > 0:
                log.info(
                    f"Exporter: Cleaned up {deleted_count} individual chapter files"
                )
            if failed_count > 0:
                log.warning(f"Exporter: Failed to delete {failed_count} chapter files")

        except Exception as e:
            log.error(f"Exporter: Failed to merge results: {e}")

    def add_frontmatter(self):
        """
        Generates thesis, keywords, and categories from the merged note and prepends metadata section.
        Legacy method - unified pipeline includes metadata in JSON.
        """
        # Check if this was a unified pipeline run (index file exists)
        index_path = get_index_path(self.book_name)
        if os.path.exists(index_path):
            log.info(
                "Exporter: Skipping add_frontmatter (unified pipeline already added metadata)"
            )
            return

        from app.categories import validate_categories
        from app.config import get_metadata_prompt

        log.info("Exporter: Generating frontmatter metadata...")

        notes_path = get_notes_path(self.book_name)

        if not os.path.exists(notes_path):
            log.error(f"Exporter: Notes file not found at {notes_path}")
            return

        try:
            # Read the current note content
            with open(notes_path, "r") as f:
                content = f.read()

            # Call LLM to generate thesis, keywords, and categories
            log.debug("Exporter: Calling LLM for thesis, keywords, and categories...")
            response = self.client.messages.create(
                model=MODEL_ID,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": get_metadata_prompt() + "\n\n" + content,
                    }
                ],
            )

            llm_output = response.content[0].text.strip()
            log.debug(f"Exporter: Full LLM response: {llm_output}")

            # Parse the response
            thesis = ""
            keywords = ""
            categories = ""

            for line in llm_output.split("\n"):
                line = line.strip()
                if line.startswith("THESIS:"):
                    thesis = line.replace("THESIS:", "").strip()
                elif line.startswith("TOPICS:"):
                    keywords = line.replace("TOPICS:", "").strip()
                elif line.startswith("CATEGORIES:"):
                    categories = line.replace("CATEGORIES:", "").strip()

            # Validate categories against BISAC list
            cat_list = []
            if categories:
                cat_list = [c.strip() for c in categories.split(",") if c.strip()]

            log.debug(f"Exporter: Extracted categories: {cat_list}")

            valid_cats = validate_categories(cat_list)
            log.debug(
                f"Exporter: Valid categories after BISAC validation: {valid_cats}"
            )

            categories_str = ", ".join(valid_cats) if valid_cats else ""

            if cat_list and not valid_cats:
                log.warning(
                    f"Exporter: No BISAC categories matched from extracted: {cat_list}"
                )

            # Build metadata section
            metadata = f"""## Metadata
- Thesis: {thesis}
- Topics: {keywords}
- Categories: {categories_str}
- Author:
- Year:
- Mode: {self.summary_mode}

"""

            # Remove existing title header if present
            lines = content.split("\n", 2)
            if lines[0].startswith("# "):
                title = lines[0][2:].strip()
                if len(lines) > 1 and lines[1] == "":
                    content = lines[2] if len(lines) > 2 else ""
                else:
                    content = "\n".join(lines[1:])
            else:
                title = self.book_name

            # Write the updated content with metadata at the top
            with open(notes_path, "w") as f:
                f.write(f"# {title}\n\n")
                f.write(metadata)
                f.write(content)

            log.info(f"Exporter: Added frontmatter to {notes_path}")
            log.info(f"Exporter: Thesis: {thesis[:100]}...")
            log.info(f"Exporter: Topics: {keywords}")
            log.info(f"Exporter: Categories: {categories_str}")

        except Exception as e:
            log.error(f"Exporter: Failed to add frontmatter: {e}")

    def cleanup_uploaded_files(self, uploaded_files):
        """
        No-op for Claude API - files are not uploaded to cloud storage.
        Kept for API compatibility.
        """
        if not uploaded_files:
            log.debug("Exporter: No files to cleanup.")
            return
        log.debug(
            f"Exporter: Skipping cleanup (files were processed locally, not uploaded)"
        )

    def validate_structure(self, toc_structured=None):
        """
        Validate the output structure against expected TOC.
        """
        if self.last_notes_path:
            notes_path = self.last_notes_path
        elif self.notes_suffix:
            notes_path = os.path.join(NOTES_DIR, f"{self.book_name}{self.notes_suffix}.md")
        else:
            notes_path = get_notes_path(self.book_name)

        if not os.path.exists(notes_path):
            log.warning(
                f"Exporter: Cannot validate - notes file not found at {notes_path}"
            )
            return {"valid": False, "error": "Notes file not found"}

        try:
            with open(notes_path, "r", encoding="utf-8") as f:
                content = f.read()

            warnings = []

            # Count heading levels
            h2_matches = re.findall(r"^## (.+)$", content, re.MULTILINE)
            h3_matches = re.findall(r"^### (.+)$", content, re.MULTILINE)

            h2_count = len(h2_matches)
            h3_count = len(h3_matches)

            log.info(
                f"Exporter: Structure validation - found {h2_count} ## headings, {h3_count} ### headings"
            )

            if toc_structured:
                expected_parts = sum(
                    1 for level, _ in toc_structured if level == "part"
                )
                expected_chapters = sum(
                    1 for level, _ in toc_structured if level == "chapter"
                )

                if expected_parts > 0:
                    # Book has parts: ## = parts, ### = chapters
                    # +1 for the ## Metadata heading we insert
                    if h2_count > expected_parts + 1:
                        diff = h2_count - expected_parts - 1
                        warnings.append(
                            f"Found {h2_count} ## headings but TOC has {expected_parts} parts (+{diff} extra)"
                        )

                    if h3_count > expected_chapters:
                        diff = h3_count - expected_chapters
                        warnings.append(
                            f"Found {h3_count} ### headings but TOC has {expected_chapters} chapters (+{diff} extra)"
                        )

                    if h3_count < expected_chapters * 0.5:
                        warnings.append(
                            f"Found only {h3_count} ### headings but TOC has {expected_chapters} chapters (missing content?)"
                        )
                else:
                    # Book has no parts: ## = chapters directly
                    if h2_count > expected_chapters + 1:  # +1 for Metadata heading
                        diff = h2_count - expected_chapters - 1
                        warnings.append(
                            f"Found {h2_count} ## headings but TOC has {expected_chapters} chapters (+{diff} extra)"
                        )

                    if h2_count < expected_chapters * 0.5:
                        warnings.append(
                            f"Found only {h2_count} ## headings but TOC has {expected_chapters} chapters (missing content?)"
                        )

            if h3_count > 50:
                warnings.append(
                    f"Suspiciously many ### headings ({h3_count}) - subsections may be treated as chapters"
                )

            h2_duplicates = [
                title for title, count in Counter(h2_matches).items() if count > 1
            ]
            h3_duplicates = [
                title for title, count in Counter(h3_matches).items() if count > 1
            ]

            if h2_duplicates:
                warnings.append(f"Duplicate ## headings found: {h2_duplicates[:5]}")

            if h3_duplicates:
                warnings.append(f"Duplicate ### headings found: {h3_duplicates[:5]}")

            if warnings:
                log.warning("Exporter: Structure validation found issues:")
                for w in warnings:
                    log.warning(f"  ⚠️  {w}")
                print("\n" + "=" * 60, flush=True)
                print("⚠️  STRUCTURE VALIDATION WARNINGS:", flush=True)
                for w in warnings:
                    print(f"  • {w}", flush=True)
                print("=" * 60 + "\n", flush=True)
            else:
                log.info("Exporter: Structure validation passed - no issues detected")

            return {
                "valid": len(warnings) == 0,
                "warnings": warnings,
                "h2_count": h2_count,
                "h3_count": h3_count,
                "h2_duplicates": h2_duplicates,
                "h3_duplicates": h3_duplicates,
            }

        except Exception as e:
            log.error(f"Exporter: Structure validation failed: {e}")
            return {"valid": False, "error": str(e)}

    def get_export_summary(self) -> dict:
        """Get summary of what was exported."""
        notes_path = self.last_notes_path or (
            os.path.join(NOTES_DIR, f"{self.book_name}{self.notes_suffix}.md")
            if self.notes_suffix
            else get_notes_path(self.book_name)
        )
        index_path = self.last_index_path or (get_index_path(self.book_name) if self.export_index else None)

        summary = {
            "book_name": self.book_name,
            "notes_path": notes_path if os.path.exists(notes_path) else None,
            "index_path": index_path if index_path and os.path.exists(index_path) else None,
        }

        if index_path and os.path.exists(index_path):
            try:
                with open(index_path) as f:
                    index_data = json.load(f)
                summary["claim_count"] = index_data.get("stats", {}).get(
                    "claim_count", 0
                )
                summary["chapter_count"] = index_data.get("stats", {}).get(
                    "chapter_count", 0
                )
                summary["concepts"] = list(
                    set(
                        c
                        for claim in index_data.get("claims", [])
                        for c in claim.get("concepts", [])
                    )
                )
            except Exception:
                pass

        return summary
