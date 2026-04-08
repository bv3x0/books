import json
import os
import sqlite3
import sys
import tempfile

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.core.vector_store import VectorStore


def test_add_claims_batch_normalizes_nested_metadata_shapes():
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "vectors.db")
        store = VectorStore(db_path=db_path, dimensions=3)

        claims = [
            {
                "id": "claim-1",
                "book_name": "test-book",
                "chapter_index": 0,
                "claim_index": 0,
                "text": "A test claim",
                "concepts": ["liberal_education", {"alias": "nihilism"}],
                # Regression case: list containing dict (seen in cached run)
                "entities": [
                    {
                        "people": ["Allan Bloom"],
                        "places": ["United States"],
                        "events": ["French Revolution"],
                        "works": [],
                    }
                ],
                "quotes": [{"text": "Education is risky"}],
                "embedding": [0.1, 0.2, 0.3],
            }
        ]

        store.add_claims_batch(claims)

        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                "SELECT concepts, entities, quotes FROM claims WHERE id = ?",
                ("claim-1",),
            ).fetchone()
        finally:
            conn.close()

        assert row is not None
        concepts, entities, quotes = row

        assert "liberal_education" in concepts
        assert "nihilism" in concepts
        assert "Allan Bloom" in entities
        assert "United States" in entities
        assert "French Revolution" in entities
        assert "Education is risky" in quotes


def test_add_claims_batch_preserves_structured_metadata_json():
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "vectors.db")
        store = VectorStore(db_path=db_path, dimensions=3)

        claim = {
            "id": "claim-structured",
            "book_name": "test-book",
            "chapter_index": 1,
            "claim_index": 2,
            "chapter_title": "Education and Eros",
            "part": "Part I",
            "text": "Eros is the drive that keeps inquiry alive.",
            "embedding_text": "Book: Test\nChapter: Education and Eros\nClaim: Eros is the drive...",
            "concepts": ["eros", "education"],
            "entities": {
                "people": ["Plato"],
                "places": [],
                "events": [],
                "works": ["Symposium"],
            },
            "sub_points": [
                {"text": "Inquiry begins in desire", "speaker": "Socrates"},
                {"text": "Instruction without eros becomes mechanical", "speaker": None},
            ],
            "embedding": [0.2, 0.3, 0.4],
        }

        store.add_claims_batch([claim])

        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                """
                SELECT chapter_title, part, embedding_text, concepts_json, entities_json, sub_points_json
                FROM claims
                WHERE id = ?
                """,
                ("claim-structured",),
            ).fetchone()
        finally:
            conn.close()

        assert row is not None
        chapter_title, part, embedding_text, concepts_json, entities_json, sub_points_json = row

        assert chapter_title == "Education and Eros"
        assert part == "Part I"
        assert "Book: Test" in embedding_text
        assert json.loads(concepts_json) == ["eros", "education"]
        assert json.loads(entities_json)["people"] == ["Plato"]
        assert json.loads(sub_points_json)[0]["speaker"] == "Socrates"


def test_upsert_concept_metadata_preserves_existing_embedding():
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "vectors.db")
        store = VectorStore(db_path=db_path, dimensions=3)

        store.add_concept(
            concept_id="liberal_education",
            label="Liberal Education",
            embedding=[0.1, 0.2, 0.3],
            books=["book-a"],
        )
        store.upsert_concept_metadata(
            concept_id="liberal_education",
            label="Liberal Education",
            books=["book-b", "book-c"],
        )

        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                "SELECT books, embedding FROM concepts WHERE id = ?",
                ("liberal_education",),
            ).fetchone()
        finally:
            conn.close()

        assert row is not None
        books, embedding = row
        assert books == "book-b,book-c"
        assert embedding is not None
