#!/usr/bin/env python3
"""
Extract structured claims from existing markdown notes for books with 0 claims.

This script parses existing notes/*.md files and enriches them with concepts
and entities using Claude Haiku, then builds proper v2.2 index JSON files
with embeddings.

Usage:
    python scripts/extract_claims.py                    # Dry run (preview)
    python scripts/extract_claims.py --apply            # Apply changes
    python scripts/extract_claims.py --book "dark-age"  # Single book
    python scripts/extract_claims.py --estimate         # Cost estimate only

Cost: ~$0.03-0.05 per book using Claude Haiku
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from anthropic import Anthropic
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent / "app" / ".env")

from app.config import INDEX_DIR, NOTES_DIR
from app.core.concept_registry import ConceptRegistry
from app.core.embedder import Embedder
from app.core.vector_store import VectorStore

ENRICHMENT_MODEL = "claude-haiku-4-5-20251001"  # Fast and cheap
BATCH_SIZE = 15  # Claims per API call


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ParsedClaim:
    """A claim extracted from markdown."""

    id: str
    text: str
    chapter: str
    part: str = ""
    sub_points: list = field(default_factory=list)
    # Enriched fields (added by Claude)
    concepts: list = field(default_factory=list)
    entities: dict = field(default_factory=dict)


@dataclass
class ParsedMetadata:
    """Book metadata extracted from markdown."""

    title: str = ""
    thesis: str = ""
    topics: list = field(default_factory=list)
    categories: list = field(default_factory=list)
    author: str = ""
    year: int = None
    mode: str = ""


# =============================================================================
# Markdown Parser
# =============================================================================


class MarkdownParser:
    """Pure Python parser for existing markdown notes."""

    # Regex patterns
    METADATA_FIELD = re.compile(r"^- (Thesis|Topics|Categories|Author|Year|Mode):\s*(.*)$")
    NEW_FORMAT_CLAIM = re.compile(
        r"^\*\s*<span id=\"([^\"]+)\"></span>\*\*(.+?)\*\*(.*)$"
    )
    OLD_FORMAT_CLAIM = re.compile(r"^[-*]\s*\*\*(.+?)\*\*:?\s*(.*)$")
    # Plain bullet format (no bold) - used in some older books
    PLAIN_BULLET = re.compile(r"^- ([^*\s].+)$")
    SUB_POINT = re.compile(r"^    [-*]\s*(.+)$")
    CHAPTER_HEADING = re.compile(r"^(#{2,4})\s+(.+)$")
    QUOTE_ATTRIBUTION = re.compile(r'^["\u201c](.+?)["\u201d]\s*[—\-]\s*(.+)$')

    def __init__(self, content: str, book_name: str):
        self.content = content
        self.book_name = book_name
        self.book_slug = self._slugify(book_name)
        self.lines = content.split("\n")

    def extract_metadata(self) -> ParsedMetadata:
        """Extract metadata from ## Metadata section."""
        metadata = ParsedMetadata()

        # Find title (first # heading)
        for line in self.lines:
            if line.startswith("# ") and not line.startswith("## "):
                metadata.title = line[2:].strip()
                break

        # Find metadata section
        in_metadata = False
        for line in self.lines:
            if line.strip() == "## Metadata":
                in_metadata = True
                continue
            if in_metadata:
                if line.startswith("## "):
                    break  # End of metadata section
                match = self.METADATA_FIELD.match(line)
                if match:
                    field_name, value = match.groups()
                    value = value.strip()
                    if field_name == "Thesis":
                        metadata.thesis = value
                    elif field_name == "Topics":
                        metadata.topics = [t.strip() for t in value.split(",") if t.strip()]
                    elif field_name == "Categories":
                        metadata.categories = [c.strip() for c in value.split(",") if c.strip()]
                    elif field_name == "Author":
                        metadata.author = value
                    elif field_name == "Year":
                        try:
                            metadata.year = int(value) if value else None
                        except ValueError:
                            metadata.year = None
                    elif field_name == "Mode":
                        metadata.mode = value

        if not metadata.title:
            metadata.title = self.book_name

        return metadata

    def extract_chapters_and_claims(self) -> tuple[list, list]:
        """
        Extract chapter structure and claims from markdown.

        Returns (chapters, claims) tuple.
        """
        chapters = []
        claims = []
        claim_counter = 1

        current_part = ""
        current_chapter = ""
        current_chapter_summary = ""
        current_claim = None
        chapter_claim_ids = []

        # Determine heading levels used
        has_parts = any(
            line.startswith("## ") and not line.startswith("## Metadata")
            for line in self.lines
        ) and any(line.startswith("### ") for line in self.lines)

        for i, line in enumerate(self.lines):
            # Check for chapter headings
            heading_match = self.CHAPTER_HEADING.match(line)
            if heading_match:
                level, title = heading_match.groups()
                title = title.strip()

                # Skip metadata section
                if title == "Metadata":
                    continue

                # Determine if this is a part or chapter
                if has_parts:
                    if level == "##":
                        # Save previous chapter if exists
                        if current_chapter and chapter_claim_ids:
                            chapters.append({
                                "title": current_chapter,
                                "summary": current_chapter_summary.strip(),
                                "part": current_part,
                                "claim_ids": chapter_claim_ids,
                            })
                            chapter_claim_ids = []
                            current_chapter_summary = ""
                        current_part = title
                        current_chapter = ""
                    elif level == "###":
                        # Save previous chapter if exists
                        if current_chapter and chapter_claim_ids:
                            chapters.append({
                                "title": current_chapter,
                                "summary": current_chapter_summary.strip(),
                                "part": current_part,
                                "claim_ids": chapter_claim_ids,
                            })
                            chapter_claim_ids = []
                            current_chapter_summary = ""
                        current_chapter = title
                else:
                    if level == "##":
                        # Save previous chapter if exists
                        if current_chapter and chapter_claim_ids:
                            chapters.append({
                                "title": current_chapter,
                                "summary": current_chapter_summary.strip(),
                                "part": "",
                                "claim_ids": chapter_claim_ids,
                            })
                            chapter_claim_ids = []
                            current_chapter_summary = ""
                        current_chapter = title
                continue

            # Check for claims (new format with anchor)
            new_match = self.NEW_FORMAT_CLAIM.match(line)
            if new_match:
                # Save previous claim if exists
                if current_claim:
                    claims.append(current_claim)
                    chapter_claim_ids.append(current_claim.id)

                claim_id, bold_text, rest = new_match.groups()
                full_text = bold_text.strip()
                if rest.strip():
                    full_text += " " + rest.strip()

                current_claim = ParsedClaim(
                    id=claim_id,
                    text=full_text,
                    chapter=current_chapter or "Introduction",
                    part=current_part,
                )
                claim_counter += 1
                continue

            # Check for claims (old format without anchor)
            old_match = self.OLD_FORMAT_CLAIM.match(line)
            if old_match and not line.startswith("    "):
                # Save previous claim if exists
                if current_claim:
                    claims.append(current_claim)
                    chapter_claim_ids.append(current_claim.id)

                bold_text, rest = old_match.groups()
                full_text = bold_text.strip()
                if rest.strip():
                    full_text += ": " + rest.strip()

                # Generate ID for old format
                claim_id = f"{self.book_slug}-{claim_counter:03d}"

                current_claim = ParsedClaim(
                    id=claim_id,
                    text=full_text,
                    chapter=current_chapter or "Introduction",
                    part=current_part,
                )
                claim_counter += 1
                continue

            # Check for plain bullet claims (no bold formatting)
            plain_match = self.PLAIN_BULLET.match(line)
            if plain_match and not line.startswith("    ") and current_chapter:
                # Save previous claim if exists
                if current_claim:
                    claims.append(current_claim)
                    chapter_claim_ids.append(current_claim.id)

                bullet_text = plain_match.group(1).strip()

                # Generate ID for plain format
                claim_id = f"{self.book_slug}-{claim_counter:03d}"

                current_claim = ParsedClaim(
                    id=claim_id,
                    text=bullet_text,
                    chapter=current_chapter or "Introduction",
                    part=current_part,
                )
                claim_counter += 1
                continue

            # Check for sub-points
            sub_match = self.SUB_POINT.match(line)
            if sub_match and current_claim:
                sub_text = sub_match.group(1).strip()
                # Check for quote attribution
                quote_match = self.QUOTE_ATTRIBUTION.match(sub_text)
                if quote_match:
                    quote_text, speaker = quote_match.groups()
                    current_claim.sub_points.append({
                        "text": quote_text.strip(),
                        "speaker": speaker.strip()
                    })
                else:
                    current_claim.sub_points.append({
                        "text": sub_text,
                        "speaker": None
                    })
                continue

            # Collect chapter summary (paragraphs before first claim in chapter)
            if (
                current_chapter
                and not current_claim
                and line.strip()
                and not line.startswith("#")
                and not line.startswith("-")
                and not line.startswith("*")
            ):
                current_chapter_summary += line.strip() + " "

        # Save final claim and chapter
        if current_claim:
            claims.append(current_claim)
            chapter_claim_ids.append(current_claim.id)
        if current_chapter and chapter_claim_ids:
            chapters.append({
                "title": current_chapter,
                "summary": current_chapter_summary.strip(),
                "part": current_part,
                "claim_ids": chapter_claim_ids,
            })

        return chapters, claims

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to URL-safe slug."""
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_]+", "-", text)
        text = re.sub(r"-+", "-", text)
        return text.strip("-")[:50]


# =============================================================================
# Claude Enricher
# =============================================================================


class ClaudeEnricher:
    """Use Claude Haiku to add concepts and entities to parsed claims."""

    ENRICHMENT_PROMPT = """Add concepts and entities to these claims extracted from book notes.

Each claim already has: id, text, chapter, sub_points

Add these fields:
- concepts: 2-5 snake_case tags representing abstract themes (e.g., cultural_decline, mass_amnesia)
- entities: {{"people": [], "places": [], "events": [], "works": []}} - specific named things mentioned

RULES:
- Concepts are abstract themes that could appear in other books (not proper nouns)
- Entities are specific named things (proper nouns)
- Extract from both the claim text AND sub_points
- Don't invent content not in the original text
- Use snake_case for concepts (e.g., oral_tradition, not "Oral Tradition")

Claims to enrich:
{claims_json}

Return ONLY a valid JSON array with the enriched claims. No explanation, no markdown fences."""

    def __init__(self, client: Anthropic):
        self.client = client

    def enrich_claims(
        self, claims: list[ParsedClaim], dry_run: bool = True
    ) -> list[ParsedClaim]:
        """Add concepts and entities to claims using Claude."""
        if dry_run:
            # In dry run, just return claims with empty concepts/entities
            return claims

        enriched = []
        batches = [claims[i : i + BATCH_SIZE] for i in range(0, len(claims), BATCH_SIZE)]

        for batch_idx, batch in enumerate(batches):
            print(f"    Enriching batch {batch_idx + 1}/{len(batches)}...", end=" ", flush=True)

            # Convert to JSON for API
            claims_data = [
                {
                    "id": c.id,
                    "text": c.text,
                    "chapter": c.chapter,
                    "sub_points": c.sub_points,
                }
                for c in batch
            ]

            try:
                response = self.client.messages.create(
                    model=ENRICHMENT_MODEL,
                    max_tokens=4096,
                    messages=[
                        {
                            "role": "user",
                            "content": self.ENRICHMENT_PROMPT.format(
                                claims_json=json.dumps(claims_data, indent=2)
                            ),
                        }
                    ],
                )

                result_text = response.content[0].text.strip()

                # Clean up response
                if result_text.startswith("```json"):
                    result_text = result_text[7:]
                if result_text.startswith("```"):
                    result_text = result_text[3:]
                if result_text.endswith("```"):
                    result_text = result_text[:-3]
                result_text = result_text.strip()

                result = json.loads(result_text)

                # Merge enriched data back into claims
                result_map = {r["id"]: r for r in result}
                for claim in batch:
                    if claim.id in result_map:
                        r = result_map[claim.id]
                        claim.concepts = r.get("concepts", [])
                        # Ensure entities has proper structure
                        raw_entities = r.get("entities", {})
                        if isinstance(raw_entities, dict):
                            claim.entities = {
                                "people": raw_entities.get("people", []),
                                "places": raw_entities.get("places", []),
                                "events": raw_entities.get("events", []),
                                "works": raw_entities.get("works", []),
                            }
                        else:
                            claim.entities = {"people": [], "places": [], "events": [], "works": []}
                    enriched.append(claim)

                print(f"done ({len(batch)} claims)")

            except json.JSONDecodeError as e:
                print(f"JSON error: {e}")
                print(f"    Raw response: {result_text[:200]}...")
                # Return claims without enrichment on error
                enriched.extend(batch)
            except Exception as e:
                import traceback
                print(f"Error: {type(e).__name__}: {e}")
                traceback.print_exc()
                enriched.extend(batch)

        return enriched

    def estimate_tokens(self, claims: list[ParsedClaim]) -> int:
        """Estimate tokens for enrichment."""
        claims_data = [
            {"id": c.id, "text": c.text, "chapter": c.chapter, "sub_points": c.sub_points}
            for c in claims
        ]
        text = json.dumps(claims_data)
        # Rough estimate: 1 token per 4 characters
        return len(text) // 4


# =============================================================================
# Index Builder
# =============================================================================


class IndexBuilder:
    """Build v2.2 index from parsed and enriched data."""

    def __init__(
        self,
        book_name: str,
        embedder: Embedder = None,
        vector_store: VectorStore = None,
        concept_registry: ConceptRegistry = None,
    ):
        self.book_name = book_name
        self.book_slug = MarkdownParser._slugify(book_name)
        self.embedder = embedder
        self.vector_store = vector_store
        self.concept_registry = concept_registry
        self._chapter_lookup = {}

    @staticmethod
    def _truncate_text(text: str, limit: int = 240) -> str:
        cleaned = (text or "").strip()
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: limit - 1].rstrip() + "…"

    def _format_sub_point_for_embedding(self, sub_point) -> str:
        if isinstance(sub_point, dict):
            text = self._truncate_text(sub_point.get("text", ""))
            speaker = (sub_point.get("speaker") or "").strip()
            if text and speaker:
                return f'"{text}" —{speaker}'
            return text
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
        lines = [f"Book: {book_title}"]
        if part:
            lines.append(f"Part: {part}")
        if chapter_title:
            lines.append(f"Chapter: {chapter_title}")
        lines.append(f"Claim: {claim_text.strip()}")

        support = []
        for sub_point in sub_points or []:
            formatted = self._format_sub_point_for_embedding(sub_point)
            if formatted:
                support.append(formatted)
            if len(support) >= 2:
                break
        if support:
            lines.append("Support: " + " | ".join(support))

        return "\n".join(lines)

    def _build_quote_embedding_text(self, quote: dict, book_title: str) -> str:
        parts = [f'Quote: "{(quote.get("text", "") or "").strip()}"']
        speaker = (quote.get("speaker", "") or "").strip()
        if speaker:
            parts.append(f"Speaker: {speaker}")
        parts.append(f"Book: {book_title}")
        chapter_title = (quote.get("chapter_title", "") or "").strip()
        if chapter_title:
            parts.append(f"Chapter: {chapter_title}")
        claim_text = self._truncate_text(quote.get("claim_text", ""), limit=200)
        if claim_text:
            parts.append(f"Related claim: {claim_text}")
        return "\n".join(parts)

    def normalize_claim_concepts(self, claims: list[ParsedClaim], dry_run: bool = True):
        """Normalize concepts in-place so index + vectors use canonical IDs."""
        if dry_run or not self.concept_registry:
            return

        for claim in claims:
            normalized = []
            seen = set()
            for concept in claim.concepts:
                concept_id = self.concept_registry.normalize(concept)
                if concept_id and concept_id not in seen:
                    normalized.append(concept_id)
                    seen.add(concept_id)
            claim.concepts = normalized

    def build_index(
        self,
        metadata: ParsedMetadata,
        chapters: list,
        claims: list[ParsedClaim],
    ) -> dict:
        """Create v2.2 JSON structure."""
        # Convert claims to index format
        claims_data = []
        for claim in claims:
            claim_data = {
                "id": claim.id,
                "text": claim.text,
                "chapter": claim.chapter,
                "concepts": claim.concepts,
                "entities": claim.entities if claim.entities else {
                    "people": [],
                    "places": [],
                    "events": [],
                    "works": [],
                },
                "sub_points": claim.sub_points,
            }
            if claim.part:
                claim_data["part"] = claim.part
            claims_data.append(claim_data)

        # Build chapters with claim_ids
        chapters_data = []
        for i, ch in enumerate(chapters):
            chapter_data = {
                "id": f"{self.book_slug}-ch-{i + 1:03d}",
                "title": ch["title"],
                "summary": ch.get("summary", ""),
                "claim_ids": ch.get("claim_ids", []),
            }
            if ch.get("part"):
                chapter_data["part"] = ch["part"]
            chapters_data.append(chapter_data)

        return {
            "version": "2.2",
            "book": {
                "title": metadata.title,
                "author": metadata.author,
                "year": metadata.year,
                "categories": metadata.categories,
                "thesis": metadata.thesis,
            },
            "claims": claims_data,
            "chapters": chapters_data,
            "stats": {
                "claim_count": len(claims_data),
                "chapter_count": len(chapters_data),
                "indexed_at": datetime.utcnow().isoformat() + "Z",
            },
        }

    def update_embeddings(
        self,
        metadata: ParsedMetadata,
        chapters: list,
        claims: list[ParsedClaim],
        dry_run: bool = True,
    ):
        """Generate and store embeddings."""
        if dry_run or not self.embedder or not self.vector_store:
            return

        print(f"    Generating embeddings for {len(claims)} claims...", end=" ", flush=True)

        # Replace this book's vectors so re-runs don't leave stale rows behind.
        self.vector_store.delete_book_quotes(self.book_name)
        self.vector_store.delete_book_claims(self.book_name)

        chapter_lookup = {}
        for idx, chapter in enumerate(chapters):
            title = chapter.get("title", "")
            if title and title not in chapter_lookup:
                chapter_lookup[title] = idx
        self._chapter_lookup = chapter_lookup

        # Prepare claim data for vector store
        all_claims = []
        claim_texts = []
        all_quotes = []
        book_title = metadata.title or self.book_name

        for fallback_idx, claim in enumerate(claims):
            chapter_idx = chapter_lookup.get(claim.chapter, 0)
            claim_id = claim.id
            embedding_text = self._build_claim_embedding_text(
                book_title=book_title,
                chapter_title=claim.chapter,
                part=claim.part,
                claim_text=claim.text,
                sub_points=claim.sub_points,
            )
            all_claims.append({
                "id": claim_id,
                "book_name": self.book_name,
                "chapter_index": chapter_idx,
                "claim_index": fallback_idx,
                "chapter_title": claim.chapter,
                "part": claim.part,
                "text": claim.text,
                "embedding_text": embedding_text,
                "concepts": claim.concepts,
                "entities": claim.entities,
                "sub_points": claim.sub_points,
            })
            claim_texts.append(embedding_text)

            for sp_idx, sub_point in enumerate(claim.sub_points):
                if isinstance(sub_point, dict) and sub_point.get("speaker"):
                    quote_id = f"{claim_id}_q{sp_idx}"
                    all_quotes.append(
                        {
                            "id": quote_id,
                            "claim_id": claim_id,
                            "book_name": self.book_name,
                            "chapter_title": claim.chapter,
                            "claim_text": claim.text,
                            "text": sub_point.get("text", ""),
                            "speaker": sub_point.get("speaker", ""),
                        }
                    )

        # Generate embeddings in batch
        embeddings = self.embedder.embed_batch(claim_texts, batch_size=100)

        # Add embeddings to claim data
        for claim_data, embedding in zip(all_claims, embeddings):
            claim_data["embedding"] = embedding

        # Store in vector database
        self.vector_store.add_claims_batch(all_claims)

        if all_quotes:
            quote_texts = [
                self._build_quote_embedding_text(quote, book_title=book_title)
                for quote in all_quotes
            ]
            quote_embeddings = self.embedder.embed_batch(quote_texts, batch_size=100)
            for quote_data, embedding in zip(all_quotes, quote_embeddings):
                quote_data["embedding"] = embedding
            self.vector_store.add_quotes_batch(all_quotes)

        print("done")

    def update_concepts(self, claims: list[ParsedClaim], dry_run: bool = True):
        """Update concept registry with book references."""
        if dry_run or not self.concept_registry:
            return

        print("    Updating concept registry...", end=" ", flush=True)

        self.concept_registry.remove_book_references(self.book_name)

        concept_counts = {}
        for claim in claims:
            for concept in claim.concepts:
                if concept:
                    concept_counts[concept] = concept_counts.get(concept, 0) + 1

        # Update registry
        for concept_id, count in concept_counts.items():
            self.concept_registry.set_book_claims(concept_id, self.book_name, count)

        self.concept_registry.save()
        print(f"done ({len(concept_counts)} concepts)")


# =============================================================================
# Main Script
# =============================================================================


def find_books_needing_extraction() -> list[str]:
    """Find books with notes but 0 claims in index."""
    books = []

    notes_dir = Path(NOTES_DIR)
    index_dir = Path(INDEX_DIR)

    for notes_file in notes_dir.glob("*.md"):
        book_name = notes_file.stem
        index_file = index_dir / f"{book_name}.json"

        if index_file.exists():
            try:
                with open(index_file) as f:
                    data = json.load(f)
                claim_count = len(data.get("claims", []))
                if claim_count == 0:
                    books.append(book_name)
            except Exception:
                books.append(book_name)  # Include if index is corrupt
        else:
            books.append(book_name)  # Include if no index exists

    return sorted(books)


def process_book(
    book_name: str,
    client: Anthropic,
    enricher: ClaudeEnricher,
    embedder: Embedder,
    vector_store: VectorStore,
    concept_registry: ConceptRegistry,
    dry_run: bool = True,
) -> dict:
    """Process a single book."""
    print(f"\n{'=' * 60}")
    print(f"Processing: {book_name}")

    stats = {
        "book": book_name,
        "claims_extracted": 0,
        "chapters_found": 0,
        "api_calls": 0,
        "estimated_tokens": 0,
    }

    # Read markdown
    notes_path = Path(NOTES_DIR) / f"{book_name}.md"
    if not notes_path.exists():
        print(f"  ERROR: Notes file not found: {notes_path}")
        return stats

    with open(notes_path, encoding="utf-8") as f:
        content = f.read()

    # Parse markdown
    parser = MarkdownParser(content, book_name)
    metadata = parser.extract_metadata()
    chapters, claims = parser.extract_chapters_and_claims()

    stats["claims_extracted"] = len(claims)
    stats["chapters_found"] = len(chapters)
    stats["estimated_tokens"] = enricher.estimate_tokens(claims)
    stats["api_calls"] = (len(claims) + BATCH_SIZE - 1) // BATCH_SIZE

    print(f"  Parsed: {len(chapters)} chapters, {len(claims)} claims")
    print(f"  Estimated tokens: ~{stats['estimated_tokens']:,}")
    print(f"  API calls needed: {stats['api_calls']}")

    if len(claims) == 0:
        print("  WARNING: No claims found in markdown")
        return stats

    if dry_run:
        print("  DRY RUN - no changes made")
        return stats

    # Enrich claims with concepts/entities
    print("  Enriching claims with Claude...")
    claims = enricher.enrich_claims(claims, dry_run=False)

    builder = IndexBuilder(book_name, embedder, vector_store, concept_registry)
    builder.normalize_claim_concepts(claims, dry_run=False)

    # Build index
    index_data = builder.build_index(metadata, chapters, claims)

    # Save index
    index_path = Path(INDEX_DIR) / f"{book_name}.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2, ensure_ascii=False)
    print(f"  Saved index to {index_path}")

    # Update embeddings
    builder.update_embeddings(metadata, chapters, claims, dry_run=False)

    # Update concept registry
    builder.update_concepts(claims, dry_run=False)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Extract claims from existing markdown notes"
    )
    parser.add_argument(
        "--apply", action="store_true", help="Apply changes (default is dry run)"
    )
    parser.add_argument("--book", type=str, help="Process single book by name")
    parser.add_argument("--estimate", action="store_true", help="Only estimate cost")
    args = parser.parse_args()

    dry_run = not args.apply

    if dry_run and not args.estimate:
        print("DRY RUN MODE - use --apply to make changes")
        print()

    # Find books to process
    books = find_books_needing_extraction()

    if args.book:
        # Filter to matching book
        matching = [b for b in books if args.book.lower() in b.lower()]
        if not matching:
            print(f"No book found matching: {args.book}")
            print(f"Books needing extraction: {books[:10]}...")
            sys.exit(1)
        books = matching

    print(f"Found {len(books)} book(s) to process")

    if not books:
        print("No books need claim extraction!")
        return

    # Initialize clients
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key and not dry_run:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client = Anthropic(api_key=api_key) if api_key else None
    enricher = ClaudeEnricher(client) if client else None

    # Initialize embedder and vector store
    embedder = None
    vector_store = None
    concept_registry = None

    if not dry_run:
        try:
            from app.config import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL, VECTORS_DB_PATH, CONCEPTS_PATH

            embedder = Embedder(model=EMBEDDING_MODEL, dimensions=EMBEDDING_DIMENSIONS)
            vector_store = VectorStore(db_path=VECTORS_DB_PATH, dimensions=EMBEDDING_DIMENSIONS)
            concept_registry = ConceptRegistry(path=CONCEPTS_PATH, embedder=embedder)
        except Exception as e:
            print(f"WARNING: Could not initialize embeddings: {e}")

    # Process each book
    all_stats = []
    total_tokens = 0
    total_api_calls = 0

    for book in books:
        stats = process_book(
            book,
            client,
            enricher,
            embedder,
            vector_store,
            concept_registry,
            dry_run=dry_run or args.estimate,
        )
        all_stats.append(stats)
        total_tokens += stats["estimated_tokens"]
        total_api_calls += stats["api_calls"]

    # Summary
    print(f"\n{'=' * 60}")
    print("EXTRACTION SUMMARY")
    print(f"{'=' * 60}")

    total_claims = sum(s["claims_extracted"] for s in all_stats)
    total_chapters = sum(s["chapters_found"] for s in all_stats)

    print(f"Books processed: {len(all_stats)}")
    print(f"Total claims: {total_claims}")
    print(f"Total chapters: {total_chapters}")
    print(f"API calls: {total_api_calls}")
    print(f"Estimated tokens: ~{total_tokens:,}")

    # Cost estimate (Haiku: $0.80/M input, $4.00/M output)
    # Assume output is ~same size as input
    estimated_cost = (total_tokens * 0.80 / 1_000_000) + (total_tokens * 4.00 / 1_000_000)
    print(f"Estimated cost: ~${estimated_cost:.2f}")

    if dry_run and not args.estimate:
        print(f"\nRun with --apply to perform extraction")


if __name__ == "__main__":
    main()
