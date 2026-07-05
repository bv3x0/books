"""Local fidelity checks for unified summary chunks."""

from __future__ import annotations

import difflib
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any


HARD_FAILURE_TYPES = {"QUOTE_NOT_IN_SOURCE", "CHAPTER_MISSING"}


def _normalize_text(text: str) -> str:
    replacements = {
        ord("\u2018"): "'",
        ord("\u2019"): "'",
        ord("\u201c"): '"',
        ord("\u201d"): '"',
        ord("\u2013"): "-",
        ord("\u2014"): "-",
        ord("\u2212"): "-",
    }
    text = (text or "").translate(replacements)
    text = re.sub(r"\s+", " ", text)
    return text.casefold().strip()


def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _normalize_text(title)).strip()


def _quote_matches_source(quote: str, source_text: str, min_ratio: float = 0.85) -> bool:
    quote_norm = _normalize_text(quote)
    source_norm = _normalize_text(source_text)
    if not quote_norm:
        return True
    if quote_norm in source_norm:
        return True
    if len(quote_norm) < 20 or len(source_norm) < len(quote_norm):
        return False

    quote_tokens = re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", quote_norm)
    source_tokens = re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", source_norm)
    fragments = [
        fragment.strip()
        for fragment in re.split(r"[.!?;:,]+", quote_norm)
        if len(fragment.split()) >= 3 and len(fragment.strip()) >= 12
    ]
    if fragments and quote_tokens:
        position = 0
        matched_words = 0
        matched_count = 0
        for fragment in fragments:
            found_at = source_norm.find(fragment, position)
            if found_at < 0:
                continue
            matched_count += 1
            matched_words += len(fragment.split())
            position = found_at + len(fragment)
        if matched_count == len(fragments) and matched_count >= 2:
            return True
        if matched_words / max(1, len(quote_tokens)) >= 0.6:
            return True

    window_len = len(quote_norm)
    best_ratio = 0.0
    distinctive_tokens = sorted(
        {token for token in quote_tokens if len(token) >= 6},
        key=len,
        reverse=True,
    )[:5]
    if quote_tokens and source_tokens and distinctive_tokens:
        for token in distinctive_tokens:
            token_positions = [
                idx for idx, source_token in enumerate(source_tokens) if source_token == token
            ][:30]
            for token_index in token_positions:
                start = max(0, token_index - len(quote_tokens) - 8)
                end = min(
                    len(source_tokens),
                    token_index + len(quote_tokens) + 20,
                )
                matcher = difflib.SequenceMatcher(
                    None,
                    quote_tokens,
                    source_tokens[start:end],
                )
                matched = sum(block.size for block in matcher.get_matching_blocks())
                if matched / max(1, len(quote_tokens)) >= 0.75 and matched >= 4:
                    return True

    for token in distinctive_tokens:
        search_from = 0
        for _ in range(20):
            found_at = source_norm.find(token, search_from)
            if found_at < 0:
                break
            start = max(0, found_at - window_len // 2)
            end = min(len(source_norm), found_at + int(window_len * 1.8))
            window = source_norm[start:end]
            ratio = difflib.SequenceMatcher(None, quote_norm, window).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
            if best_ratio >= min_ratio:
                return True
            search_from = found_at + len(token)
    return False


def _iter_key_points(chapter: dict[str, Any]):
    for point in chapter.get("key_points") or []:
        if isinstance(point, dict):
            yield point


def _chapter_source_segment(source_text: str, title: str, expected_titles: list[str]) -> str:
    if not source_text or not title:
        return ""
    if len(expected_titles) == 1:
        return source_text

    target = _normalize_title(title)
    if not target:
        return ""

    headings = []
    offset = 0
    for line in source_text.splitlines(keepends=True):
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
        if match:
            headings.append((offset, _normalize_title(match.group(1))))
        offset += len(line)

    for heading_index, (start, heading_title) in enumerate(headings):
        if heading_title != target:
            continue
        end = headings[heading_index + 1][0] if heading_index + 1 < len(headings) else len(source_text)
        return source_text[start:end]

    return ""


class FidelityVerifier:
    def __init__(self, book_name: str, logs_dir: str):
        self.book_name = book_name
        self.logs_dir = logs_dir

    def verify_results(self, results: list[dict], requests: list[dict]) -> dict:
        request_by_index = {index: request for index, request in enumerate(requests)}
        chunk_reports = []
        counts = Counter()

        for result in results:
            index = result.get("index")
            request = request_by_index.get(index, {})
            verification = request.get("verification") or {}
            source_text = verification.get("source_text") or ""
            expected_titles = verification.get("expected_chapter_titles") or []
            findings = []

            if result.get("status") == "SUCCESS" and result.get("data") and source_text:
                findings = self.verify_chunk(
                    result["data"],
                    source_text=source_text,
                    expected_chapter_titles=expected_titles,
                )

            for finding in findings:
                counts[finding["type"]] += 1

            hard_failures = sum(
                1 for finding in findings if finding["type"] in HARD_FAILURE_TYPES
            )
            chunk_reports.append(
                {
                    "index": index,
                    "filename": (result.get("file_metadata") or {}).get("filename")
                    or (request.get("file_metadata") or {}).get("filename"),
                    "status": result.get("status"),
                    "expected_chapter_titles": expected_titles,
                    "findings": findings,
                    "hard_failures": hard_failures,
                }
            )

        return {
            "book": self.book_name,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "summary": dict(sorted(counts.items())),
            "hard_failures": sum(chunk["hard_failures"] for chunk in chunk_reports),
            "chunks": chunk_reports,
        }

    def verify_chunk(
        self,
        data: dict,
        source_text: str,
        expected_chapter_titles: list[str] | None = None,
    ) -> list[dict]:
        expected_chapter_titles = expected_chapter_titles or []
        findings = []
        chapters = data.get("chapters") or []

        findings.extend(self._verify_quotes(chapters, source_text))
        findings.extend(self._verify_entities(chapters, source_text))
        findings.extend(self._verify_chapter_coverage(chapters, expected_chapter_titles))
        findings.extend(
            self._verify_thin_chapters(chapters, source_text, expected_chapter_titles)
        )
        return findings

    def _verify_quotes(self, chapters: list[dict], source_text: str) -> list[dict]:
        findings = []
        for chapter in chapters:
            chapter_title = chapter.get("title", "")
            pull_quote = chapter.get("pull_quote")
            if pull_quote and not _quote_matches_source(pull_quote, source_text):
                findings.append(
                    {
                        "type": "QUOTE_NOT_IN_SOURCE",
                        "severity": "hard",
                        "chapter": chapter_title,
                        "field": "pull_quote",
                        "text": pull_quote,
                    }
                )

            for point_index, point in enumerate(_iter_key_points(chapter)):
                for sub_index, sub_point in enumerate(point.get("sub_points") or []):
                    if not isinstance(sub_point, dict):
                        continue
                    if sub_point.get("type") != "quote":
                        continue
                    quote = sub_point.get("text") or ""
                    if _quote_matches_source(quote, source_text):
                        continue
                    findings.append(
                        {
                            "type": "QUOTE_NOT_IN_SOURCE",
                            "severity": "hard",
                            "chapter": chapter_title,
                            "field": f"key_points[{point_index}].sub_points[{sub_index}]",
                            "text": quote,
                        }
                    )
        return findings

    def _verify_entities(self, chapters: list[dict], source_text: str) -> list[dict]:
        source_norm = _normalize_text(source_text)
        findings = []
        for chapter in chapters:
            chapter_title = chapter.get("title", "")
            for point_index, point in enumerate(_iter_key_points(chapter)):
                entities = point.get("entities") or {}
                for group in ("people", "places", "events", "works"):
                    for entity in entities.get(group) or []:
                        entity_norm = _normalize_text(str(entity))
                        if not entity_norm:
                            continue
                        found = entity_norm in source_norm
                        if not found and group == "people":
                            parts = entity_norm.split()
                            if len(parts) > 1:
                                found = parts[-1] in source_norm
                        if found:
                            continue
                        findings.append(
                            {
                                "type": "ENTITY_NOT_IN_SOURCE",
                                "severity": "warning",
                                "chapter": chapter_title,
                                "field": f"key_points[{point_index}].entities.{group}",
                                "text": str(entity),
                            }
                        )
        return findings

    def _verify_chapter_coverage(
        self,
        chapters: list[dict],
        expected_chapter_titles: list[str],
    ) -> list[dict]:
        if not expected_chapter_titles:
            return []

        expected_by_norm = {
            _normalize_title(title): title for title in expected_chapter_titles if title
        }
        actual_by_norm = {
            _normalize_title(chapter.get("title", "")): chapter.get("title", "")
            for chapter in chapters
            if chapter.get("title")
        }
        findings = []

        for norm_title, title in expected_by_norm.items():
            if norm_title and norm_title not in actual_by_norm:
                findings.append(
                    {
                        "type": "CHAPTER_MISSING",
                        "severity": "hard",
                        "chapter": title,
                        "text": title,
                    }
                )

        for norm_title, title in actual_by_norm.items():
            if norm_title and norm_title not in expected_by_norm:
                findings.append(
                    {
                        "type": "CHAPTER_UNEXPECTED",
                        "severity": "warning",
                        "chapter": title,
                        "text": title,
                    }
                )

        return findings

    def _verify_thin_chapters(
        self,
        chapters: list[dict],
        source_text: str,
        expected_chapter_titles: list[str],
    ) -> list[dict]:
        findings = []
        for chapter in chapters:
            title = chapter.get("title", "")
            segment = _chapter_source_segment(source_text, title, expected_chapter_titles)
            if not segment:
                continue
            word_count = len(re.findall(r"\b\w+\b", segment))
            key_point_count = len(chapter.get("key_points") or [])
            if word_count > 4000 and key_point_count <= 1:
                findings.append(
                    {
                        "type": "POSSIBLY_UNDERSUMMARIZED",
                        "severity": "warning",
                        "chapter": title,
                        "word_count": word_count,
                        "key_point_count": key_point_count,
                    }
                )
        return findings

    def write_report(self, report: dict) -> str:
        os.makedirs(self.logs_dir, exist_ok=True)
        path = os.path.join(self.logs_dir, f"{self.book_name}_fidelity.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        return path
