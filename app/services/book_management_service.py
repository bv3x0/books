"""
Book management service: delete and rename canonical book artifacts.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from app.config import CONCEPTS_PATH, INDEX_DIR, NOTES_DIR, VECTORS_DB_PATH
from app.core.concept_registry import ConceptRegistry
from app.core.vector_store import VectorStore


@dataclass(frozen=True)
class DeleteBookResult:
    book_name: str
    dry_run: bool
    notes_file: Path
    index_file: Path
    notes_exists: bool
    index_exists: bool
    book_title: str | None
    removed_quotes: int = 0
    removed_claims: int = 0
    removed_concepts: int = 0
    vector_error: str | None = None
    concepts_error: str | None = None

    @property
    def found(self) -> bool:
        return self.notes_exists or self.index_exists


@dataclass(frozen=True)
class RenameBookResult:
    old_name: str
    new_name: str
    dry_run: bool
    old_notes: Path
    new_notes: Path
    old_index: Path
    new_index: Path
    notes_exists: bool
    index_exists: bool
    destination_exists: bool
    updated_claims: int = 0
    updated_concepts: int = 0
    vector_error: str | None = None
    concepts_error: str | None = None

    @property
    def source_found(self) -> bool:
        return self.notes_exists or self.index_exists


def delete_book(book_name: str, dry_run: bool = False) -> DeleteBookResult:
    """Delete canonical notes/index data plus vector and concept references."""
    notes_file = Path(NOTES_DIR) / f"{book_name}.md"
    index_file = Path(INDEX_DIR) / f"{book_name}.json"
    notes_exists = notes_file.exists()
    index_exists = index_file.exists()

    book_title = None
    if index_exists:
        try:
            with open(index_file, encoding="utf-8") as f:
                index_data = json.load(f)
            book_title = (index_data.get("book", {}) or {}).get("title")
        except Exception:
            book_title = None

    if not notes_exists and not index_exists:
        return DeleteBookResult(
            book_name=book_name,
            dry_run=dry_run,
            notes_file=notes_file,
            index_file=index_file,
            notes_exists=False,
            index_exists=False,
            book_title=book_title,
        )

    removed_quotes = 0
    removed_claims = 0
    removed_concepts = 0
    vector_error = None
    concepts_error = None

    if not dry_run:
        if notes_exists:
            notes_file.unlink()
        if index_exists:
            index_file.unlink()

        try:
            vector_store = VectorStore(VECTORS_DB_PATH)
            removed_quotes = vector_store.delete_book_quotes(book_name)
            removed_claims = vector_store.delete_book_claims(book_name)
        except Exception as e:
            vector_error = str(e)

        try:
            concept_registry = ConceptRegistry(CONCEPTS_PATH)
            removed_concepts = concept_registry.remove_book_references(book_name)
            if book_title and book_title != book_name:
                removed_concepts += concept_registry.remove_book_references(book_title)
            concept_registry.save()
        except Exception as e:
            concepts_error = str(e)

    return DeleteBookResult(
        book_name=book_name,
        dry_run=dry_run,
        notes_file=notes_file,
        index_file=index_file,
        notes_exists=notes_exists,
        index_exists=index_exists,
        book_title=book_title,
        removed_quotes=removed_quotes,
        removed_claims=removed_claims,
        removed_concepts=removed_concepts,
        vector_error=vector_error,
        concepts_error=concepts_error,
    )


def rename_book(old_name: str, new_name: str, dry_run: bool = False) -> RenameBookResult:
    """Rename canonical notes/index data and update vector/concept references."""
    old_notes = Path(NOTES_DIR) / f"{old_name}.md"
    new_notes = Path(NOTES_DIR) / f"{new_name}.md"
    old_index = Path(INDEX_DIR) / f"{old_name}.json"
    new_index = Path(INDEX_DIR) / f"{new_name}.json"

    notes_exists = old_notes.exists()
    index_exists = old_index.exists()
    destination_exists = (notes_exists and new_notes.exists()) or (
        index_exists and new_index.exists()
    )

    updated_claims = 0
    updated_concepts = 0
    vector_error = None
    concepts_error = None

    if notes_exists or index_exists:
        if not destination_exists and not dry_run:
            if notes_exists:
                old_notes.rename(new_notes)

            if index_exists:
                with open(old_index, encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("book", {}).get("title") == old_name:
                    data["book"]["title"] = new_name
                with open(new_index, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                old_index.unlink()

            try:
                conn = sqlite3.connect(VECTORS_DB_PATH)
                cursor = conn.execute(
                    "UPDATE claims SET book_name = ? WHERE book_name = ?",
                    (new_name, old_name),
                )
                updated_claims = cursor.rowcount
                conn.commit()
                conn.close()
            except Exception as e:
                vector_error = str(e)

            try:
                concept_registry = ConceptRegistry(CONCEPTS_PATH)
                for concept in concept_registry.concepts.values():
                    if old_name in concept.book_claims:
                        existing_claims = concept.book_claims.pop(old_name)
                        concept.book_claims[new_name] = (
                            concept.book_claims.get(new_name, 0) + existing_claims
                        )
                        updated_concepts += 1
                concept_registry.save()
            except Exception as e:
                concepts_error = str(e)

    return RenameBookResult(
        old_name=old_name,
        new_name=new_name,
        dry_run=dry_run,
        old_notes=old_notes,
        new_notes=new_notes,
        old_index=old_index,
        new_index=new_index,
        notes_exists=notes_exists,
        index_exists=index_exists,
        destination_exists=destination_exists,
        updated_claims=updated_claims,
        updated_concepts=updated_concepts,
        vector_error=vector_error,
        concepts_error=concepts_error,
    )
