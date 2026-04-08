"""
Evaluation service: assess notes, index, embeddings, cost, and concept-registry health.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path

from app.config import CONCEPTS_PATH, INDEX_DIR, NOTES_DIR, VECTORS_DB_PATH


class BookEvaluator:
    """Evaluate book processing quality and estimated costs."""

    def __init__(self, book_name: str):
        self.book_name = book_name
        self.notes_path = Path(NOTES_DIR) / f"{book_name}.md"
        self.index_path = Path(INDEX_DIR) / f"{book_name}.json"
        self.vectors_db = Path(VECTORS_DB_PATH)

    def evaluate_all(self) -> dict:
        results: dict = {}

        if self.notes_path.exists():
            results["notes"] = self.evaluate_notes()

        if self.index_path.exists():
            results["index"] = self.evaluate_index()

        if self.vectors_db.exists():
            results["embeddings"] = self.evaluate_embeddings()

        results["cost"] = self.estimate_costs(results)
        results["overall"] = self.calculate_overall_score(results)
        return results

    def evaluate_notes(self) -> dict:
        with open(self.notes_path, "r", encoding="utf-8") as f:
            content = f.read()

        metrics = {
            "file_size_kb": len(content.encode("utf-8")) / 1024,
            "total_chars": len(content),
            "total_words": len(content.split()),
            "total_lines": len(content.split("\n")),
        }

        h1_count = content.count("\n# ")
        h2_count = content.count("\n## ")
        h3_count = content.count("\n### ")
        h4_count = content.count("\n#### ")

        metrics["headings"] = {
            "h1": h1_count,
            "h2": h2_count,
            "h3": h3_count,
            "h4": h4_count,
            "total": h1_count + h2_count + h3_count + h4_count,
        }
        metrics["avg_words_per_chapter"] = metrics["total_words"] / h3_count if h3_count > 0 else 0

        has_metadata = "## Metadata" in content
        has_thesis = "- Thesis:" in content
        has_topics = "- Topics:" in content
        has_categories = "- Categories:" in content
        metrics["quality_indicators"] = {
            "has_metadata_section": has_metadata,
            "has_thesis": has_thesis,
            "has_topics": has_topics,
            "has_categories": has_categories,
            "completeness_score": sum([has_metadata, has_thesis, has_topics, has_categories]) / 4,
        }

        avg_sentence_length = metrics["total_words"] / max(content.count("."), 1)
        metrics["readability"] = {
            "avg_sentence_length": avg_sentence_length,
            "readability_rating": self._rate_readability(avg_sentence_length),
        }
        return metrics

    def evaluate_index(self) -> dict:
        with open(self.index_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        metrics = {
            "file_size_kb": self.index_path.stat().st_size / 1024,
        }

        book = data.get("book", {})
        chapters = data.get("chapters", [])
        claims = data.get("claims", [])
        metadata = data.get("metadata", {})
        version = data.get("version", metadata.get("pipeline_version", "unknown"))

        metrics["chapters"] = len(chapters)
        metrics["has_metadata"] = bool(metadata) or bool(book)
        metrics["pipeline_version"] = version

        total_claims = 0
        claims_per_chapter = Counter()
        all_concepts = []
        all_entities = []

        if claims:
            total_claims = len(claims)
            for claim in claims:
                chapter_name = claim.get("chapter", "")
                if chapter_name:
                    claims_per_chapter[chapter_name] += 1
                all_concepts.extend(claim.get("concepts", []))
                entities = claim.get("entities", [])
                if isinstance(entities, dict):
                    for _entity_type, entity_list in entities.items():
                        all_entities.extend(entity_list)
                else:
                    all_entities.extend(entities)
        else:
            for chapter in chapters:
                chapter_claims = chapter.get("claims", [])
                total_claims += len(chapter_claims)
                claims_per_chapter[chapter.get("title", "Unknown")] = len(chapter_claims)
                for claim in chapter_claims:
                    all_concepts.extend(claim.get("concepts", []))
                    all_entities.extend(claim.get("entities", []))

        unique_chapters = len(claims_per_chapter)
        chapter_counts = list(claims_per_chapter.values()) if claims_per_chapter else []

        metrics["claims"] = {
            "total": total_claims,
            "chapters_with_claims": unique_chapters,
            "avg_per_chapter": total_claims / unique_chapters if unique_chapters else 0,
            "min_per_chapter": min(chapter_counts) if chapter_counts else 0,
            "max_per_chapter": max(chapter_counts) if chapter_counts else 0,
        }

        unique_concepts = set(all_concepts)
        concept_freq = Counter(all_concepts)
        metrics["concepts"] = {
            "total_mentions": len(all_concepts),
            "unique_count": len(unique_concepts),
            "avg_per_claim": len(all_concepts) / total_claims if total_claims else 0,
            "most_common": concept_freq.most_common(5),
        }

        unique_entities = set(all_entities)
        entity_freq = Counter(all_entities)
        metrics["entities"] = {
            "total_mentions": len(all_entities),
            "unique_count": len(unique_entities),
            "avg_per_claim": len(all_entities) / total_claims if total_claims else 0,
            "most_common": entity_freq.most_common(5),
        }

        has_thesis = bool(book.get("thesis"))
        has_topics = bool(book.get("topics"))
        has_categories = bool(book.get("categories"))
        metrics["quality_score"] = sum(
            [
                metrics["chapters"] > 0,
                total_claims > 0,
                len(unique_concepts) > 0,
                has_thesis,
                has_topics,
                has_categories,
            ]
        ) / 6

        return metrics

    def evaluate_embeddings(self) -> dict:
        metrics = {
            "db_size_kb": self.vectors_db.stat().st_size / 1024,
        }

        conn = sqlite3.connect(self.vectors_db)
        row = None
        try:
            cursor = conn.execute(
                "SELECT COUNT(*), AVG(LENGTH(embedding)) FROM claims WHERE book_name = ?",
                (self.book_name,),
            )
            claim_count, avg_emb_size = cursor.fetchone()
            metrics["claims"] = {
                "count": claim_count or 0,
                "avg_embedding_bytes": avg_emb_size or 0,
                "dimensions": int((avg_emb_size or 0) / 4),
            }

            cursor = conn.execute(
                "SELECT embedding FROM claims WHERE book_name = ? LIMIT 1",
                (self.book_name,),
            )
            row = cursor.fetchone()
            if row:
                import struct

                embedding = list(struct.unpack(f"{len(row[0]) // 4}f", row[0]))
                metrics["sample_embedding"] = {
                    "mean": sum(embedding) / len(embedding),
                    "min": min(embedding),
                    "max": max(embedding),
                    "non_zero_ratio": sum(1 for x in embedding if abs(x) > 0.001)
                    / len(embedding),
                }

            cursor = conn.execute("SELECT COUNT(*) FROM concepts")
            concept_count = cursor.fetchone()[0]
            metrics["concepts_total"] = concept_count or 0
        finally:
            conn.close()

        quality_checks = {
            "has_claims": metrics["claims"]["count"] > 0,
            "correct_dimensions": metrics["claims"]["dimensions"] == 1536,
            "embeddings_populated": metrics["sample_embedding"]["non_zero_ratio"] > 0.9 if row else False,
            "sufficient_coverage": metrics["claims"]["count"] >= 20,
        }
        metrics["quality_score"] = sum(quality_checks.values()) / len(quality_checks)
        metrics["quality_checks"] = quality_checks
        return metrics

    def evaluate_concept_health(self) -> dict:
        concepts_path = Path(CONCEPTS_PATH)
        if not concepts_path.exists():
            return {}

        with open(concepts_path, encoding="utf-8") as f:
            data = json.load(f)

        concepts = data.get("concepts", {})
        total = len(concepts)
        if total == 0:
            return {}

        books_per_concept = []
        for _cid, cdata in concepts.items():
            book_claims = cdata.get("book_claims", {})
            n_books = len(book_claims) if book_claims else len(cdata.get("books", []))
            books_per_concept.append(n_books)

        singletons = sum(1 for count in books_per_concept if count <= 1)
        singleton_rate = singletons / total

        has_aliases = sum(1 for c in concepts.values() if c.get("aliases"))
        has_related = sum(1 for c in concepts.values() if c.get("related"))
        has_broader = sum(1 for c in concepts.values() if c.get("broader"))
        has_description = sum(1 for c in concepts.values() if c.get("description"))

        top_by_books = sorted(
            concepts.items(),
            key=lambda item: len(item[1].get("book_claims", item[1].get("books", []))),
            reverse=True,
        )[:15]

        embedded_count = None
        vectors_path = Path(VECTORS_DB_PATH)
        if vectors_path.exists():
            try:
                conn = sqlite3.connect(vectors_path)
                cursor = conn.execute("SELECT COUNT(*) FROM concepts WHERE embedding IS NOT NULL")
                embedded_count = cursor.fetchone()[0]
                conn.close()
            except Exception:
                embedded_count = None

        return {
            "total_concepts": total,
            "singleton_count": singletons,
            "singleton_rate": round(singleton_rate, 4),
            "multi_book_count": total - singletons,
            "distribution": dict(Counter(books_per_concept)),
            "has_aliases": has_aliases,
            "has_related": has_related,
            "has_broader": has_broader,
            "has_description": has_description,
            "top_by_books": [
                {
                    "concept_id": cid,
                    "book_count": len(cdata.get("book_claims", cdata.get("books", []))),
                    "claim_count": sum(cdata.get("book_claims", {}).values())
                    if cdata.get("book_claims")
                    else cdata.get("claim_count", 0),
                }
                for cid, cdata in top_by_books
            ],
            "embedded_count": embedded_count,
        }

    def estimate_costs(self, results: dict) -> dict:
        tokens_in = 0
        tokens_out = 0

        if "index" in results and self.index_path.exists():
            with open(self.index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            metadata = data.get("metadata", {})
            tokens_in = metadata.get("tokens_input", 0)
            tokens_out = metadata.get("tokens_output", 0)

        if tokens_in == 0 and "notes" in results:
            if self.index_path.exists():
                with open(self.index_path, "r", encoding="utf-8") as f:
                    index_content = f.read()
                tokens_out = len(index_content) // 4
            word_count = results["notes"]["total_words"]
            tokens_in = (word_count * 3 * 4) // 4

        claude_input_price = 3.0 / 1_000_000
        claude_output_price = 15.0 / 1_000_000
        openai_embedding_price = 0.02 / 1_000_000

        embedding_tokens = 0
        if "index" in results:
            total_claims = results["index"]["claims"]["total"]
            embedding_tokens = total_claims * 100

        claude_cost = (tokens_in * claude_input_price) + (tokens_out * claude_output_price)
        openai_cost = embedding_tokens * openai_embedding_price
        total_cost = claude_cost + openai_cost

        return {
            "tokens": {
                "claude_input": tokens_in,
                "claude_output": tokens_out,
                "claude_total": tokens_in + tokens_out,
                "openai_embedding": embedding_tokens,
            },
            "costs": {
                "claude": claude_cost,
                "openai": openai_cost,
                "total": total_cost,
            },
        }

    def calculate_overall_score(self, results: dict) -> dict:
        scores = []
        if "notes" in results:
            scores.append(results["notes"]["quality_indicators"]["completeness_score"])
        if "index" in results:
            scores.append(results["index"]["quality_score"])
        if "embeddings" in results:
            scores.append(results["embeddings"]["quality_score"])

        overall = sum(scores) / len(scores) if scores else 0
        if overall >= 0.9:
            rating = "Excellent ⭐⭐⭐⭐⭐"
        elif overall >= 0.75:
            rating = "Good ⭐⭐⭐⭐"
        elif overall >= 0.6:
            rating = "Fair ⭐⭐⭐"
        elif overall >= 0.4:
            rating = "Poor ⭐⭐"
        else:
            rating = "Very Poor ⭐"

        return {"score": overall, "rating": rating}

    @staticmethod
    def _rate_readability(avg_sentence_length: float) -> str:
        if avg_sentence_length < 15:
            return "Very Easy"
        if avg_sentence_length < 20:
            return "Easy"
        if avg_sentence_length < 25:
            return "Moderate"
        if avg_sentence_length < 30:
            return "Difficult"
        return "Very Difficult"
