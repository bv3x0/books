"""
Manifest - Creates API requests for Claude processing.

Handles both text content (from EPUB/PDF extraction) and base64 documents
(for scanned PDFs), optimizing request structure for cost efficiency.
Automatically chunks oversized files to respect API token limits.
"""

import json
import math
import re
from collections import Counter

from app.config import (
    MODEL_ID,
    get_chunk_planning_settings,
    get_unified_analysis_prompt,
    get_request_max_output_tokens,
    get_single_request_token_limit,
    get_smart_chunk_settings,
    is_anthropic_long_context_model,
)
from app.core.epub_processor import chunk_markdown_by_chapters, estimate_tokens
from app.logger import log


def detect_duplicate_paragraphs(text: str, min_length: int = 150) -> list[tuple[str, int]]:
    """
    Detect duplicate paragraphs in text that might indicate overlapping content.

    Args:
        text: The combined text to check
        min_length: Minimum paragraph length to consider (shorter = more noise)

    Returns:
        List of (paragraph_preview, count) for paragraphs appearing more than once
    """
    # Split into paragraphs (double newline separated)
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]

    # Only consider paragraphs above minimum length
    significant_paragraphs = [p for p in paragraphs if len(p) >= min_length]

    # Normalize whitespace for comparison
    def normalize(p):
        return ' '.join(p.split()).lower()

    normalized = [normalize(p) for p in significant_paragraphs]

    # Count occurrences
    counts = Counter(normalized)

    # Find duplicates
    duplicates = []
    seen = set()
    for p, norm in zip(significant_paragraphs, normalized):
        if counts[norm] > 1 and norm not in seen:
            seen.add(norm)
            # Return first 80 chars as preview
            preview = p[:80].replace('\n', ' ') + '...' if len(p) > 80 else p.replace('\n', ' ')
            duplicates.append((preview, counts[norm]))

    return duplicates


class Manifest:
    def __init__(self, client, use_unified=True, model_id: str = MODEL_ID):
        """
        Initialize the Manifest.

        Args:
            client: The Anthropic client
            use_unified: If True, use the new unified JSON prompt (v2.0 pipeline)
                        If False, use legacy markdown prompt
            model_id: Model identifier to include in requests
        """
        self.client = client
        self.use_unified = use_unified
        self.model_id = model_id
        self.single_request_limit = get_single_request_token_limit(model_id)
        self.smart_chunk_settings = get_smart_chunk_settings(model_id)
        self.request_max_output_tokens = get_request_max_output_tokens(model_id)
        self.chunk_planning_settings = get_chunk_planning_settings(model_id)
        self.use_prompt_caching = is_anthropic_long_context_model(model_id)

    def create_batch_job(self, prepared_files, mode="quick"):
        """
        Creates a list of requests for sequential processing with Claude API.

        Handles two content types:
        - 'text': Send as plain text message (cheaper)
        - 'data': Send as base64 document (for scanned PDFs)

        Args:
            prepared_files: Dict mapping filename to file data dict
            mode: Summary mode (kept for compatibility, always "quick")

        Returns:
            list of request dictionaries compatible with Claude Messages API
        """
        summary_prompt = get_unified_analysis_prompt()
        log.info("Manifest: Using unified JSON prompt")
        
        # Calculate total tokens for all text files
        total_tokens = sum(
            f.get('estimated_tokens', 0) 
            for f in prepared_files.values() 
            if f.get('format') == 'markdown'
        )
        
        # Check if we can combine all text files into a single request
        text_files = {k: v for k, v in prepared_files.items() if v.get('format') == 'markdown'}
        base64_files = {k: v for k, v in prepared_files.items() if v.get('format') == 'base64'}
        
        requests = []
        
        if text_files and total_tokens < self.single_request_limit:
            # Combine all text content into a single request
            log.info(f"Manifest: Combining {len(text_files)} text files into single request (~{total_tokens:,} tokens)")
            combined_request = self._create_combined_text_request(text_files, summary_prompt)
            if combined_request:
                requests.append(combined_request)
        else:
            # Process text files individually, chunking if needed
            # Check if we can do file-to-part mapping (file count = part count)
            toc_structured = None
            parts_count = 0
            for fd in text_files.values():
                if fd.get('toc_structured'):
                    toc_structured = fd.get('toc_structured')
                    parts_count = sum(1 for level, _ in toc_structured if level == 'part')
                    break

            file_list = list(text_files.items())
            can_map_files_to_parts = (toc_structured and len(file_list) == parts_count)

            if can_map_files_to_parts:
                log.info(f"Manifest: File count ({len(file_list)}) matches part count ({parts_count}) - using file-to-part mapping")

            for file_idx, (filename, file_data) in enumerate(file_list):
                file_tokens = file_data.get('estimated_tokens', 0)

                # If single file exceeds limit, chunk it
                if file_tokens > self.single_request_limit:
                    log.info(f"Manifest: File {filename} ({file_tokens:,} tokens) exceeds limit. Chunking...")
                    chunk_requests = self._create_chunked_requests(filename, file_data, summary_prompt)
                    requests.extend(chunk_requests)
                    log.info(f"Manifest: Created {len(chunk_requests)} chunks for {filename}")
                else:
                    # Pass file index for part mapping if applicable
                    file_part_idx = file_idx if can_map_files_to_parts else None
                    request = self._create_text_request(filename, file_data, summary_prompt, file_part_idx=file_part_idx)
                    if request:
                        requests.append(request)
        
        # Process base64 files (scanned PDFs) individually
        for filename, file_data in base64_files.items():
            request = self._create_base64_request(filename, file_data, summary_prompt)
            if request:
                requests.append(request)
        
        log.info(f"Manifest: Created {len(requests)} requests")
        return requests

    def get_chunk_plan_requests(self, prepared_files: dict) -> list[dict]:
        """Build whole-book planning requests for extra-long books."""
        requests = []
        for filename, file_data in prepared_files.items():
            if not self.should_create_chunk_plan(file_data):
                continue
            requests.append(
                {
                    "filename": filename,
                    "file_data": file_data,
                    "request": self._create_chunk_plan_request(filename, file_data),
                }
            )
        return requests

    def should_create_chunk_plan(self, file_data: dict) -> bool:
        """Return True when a file benefits from a whole-book planning pass."""
        if not self.chunk_planning_settings["enabled"]:
            return False
        if file_data.get("format") != "markdown":
            return False

        total_tokens = file_data.get("estimated_tokens", 0)
        if total_tokens < self.chunk_planning_settings["min_tokens"]:
            return False
        if total_tokens > self.chunk_planning_settings["max_tokens"]:
            return False

        chapter_count = self._get_chapter_count(file_data)
        if chapter_count < self.chunk_planning_settings["min_chapters"]:
            return False

        return bool(file_data.get("toc") or file_data.get("toc_structured"))
    
    def _create_text_request(self, filename: str, file_data: dict, prompt: str, file_part_idx: int = None) -> dict:
        """Create a request for text-based content.

        Args:
            filename: Name of the file being processed
            file_data: Dict with text content and TOC info
            prompt: The summary prompt
            file_part_idx: If provided, indicates this file maps to Part N (0-indexed)
        """
        text_content = file_data.get('text', '')
        toc = file_data.get('toc', [])  # TOC from EPUB extraction
        toc_structured = file_data.get('toc_structured')  # Structured TOC with Parts/Chapters

        file_specific_guidance = ""
        if file_part_idx is not None and toc_structured:
            file_specific_guidance = self._build_file_part_guidance(
                toc_structured, file_part_idx
            )
        chapter_guidance = self._build_chapter_guidance(
            toc=toc,
            toc_structured=toc_structured,
            location_label="file",
            extra_guidance=file_specific_guidance,
        )
        
        user_content = f"""Here is the book content to outline:

---

{text_content}

---

{chapter_guidance}"""
        
        return {
            "request": self._build_text_request_payload(user_content, prompt),
            "file_metadata": {
                "filename": filename,
                "size_bytes": file_data.get("size_bytes", 0),
                "format": "text",
                "estimated_tokens": file_data.get("estimated_tokens", 0),
                "source_metadata": file_data.get("source_metadata", {}),
                "use_unified": self.use_unified
            }
        }
    
    def _create_combined_text_request(self, text_files: dict, prompt: str) -> dict:
        """Create a single request combining all text files."""
        # Combine all text content
        combined_parts = []
        total_bytes = 0
        total_tokens = 0
        filenames = []
        toc = None
        toc_structured = None
        source_metadata = {}

        for filename, file_data in text_files.items():
            combined_parts.append(file_data.get('text', ''))
            total_bytes += file_data.get('size_bytes', 0)
            total_tokens += file_data.get('estimated_tokens', 0)
            filenames.append(filename)
            if not source_metadata and file_data.get("source_metadata"):
                source_metadata = file_data.get("source_metadata")
            # Grab TOC from first file that has it (all PDFs share the same manual TOC)
            if not toc and file_data.get('toc'):
                toc = file_data.get('toc')
                toc_structured = file_data.get('toc_structured')

        combined_text = '\n\n'.join(combined_parts)

        # Check for duplicate paragraphs (may indicate overlapping PDF content)
        duplicates = detect_duplicate_paragraphs(combined_text)
        if duplicates:
            log.warning(f"Manifest: Found {len(duplicates)} duplicate paragraphs in combined text:")
            for preview, count in duplicates[:5]:
                log.warning(f"  [{count}x] {preview}")
            print("\n" + "="*60, flush=True)
            print("⚠️  DUPLICATE CONTENT WARNING:", flush=True)
            print(f"Found {len(duplicates)} paragraphs that appear multiple times.", flush=True)
            print("This may indicate overlapping content between PDF files.", flush=True)
            for preview, count in duplicates[:3]:
                print(f"  [{count}x] {preview}", flush=True)
            if len(duplicates) > 3:
                print(f"  ... and {len(duplicates) - 3} more", flush=True)
            print("="*60 + "\n", flush=True)

        chapter_guidance = self._build_chapter_guidance(
            toc=toc,
            toc_structured=toc_structured,
            location_label="book",
        )

        user_content = f"""Here is the complete book content to outline:

---

{combined_text}

---

{chapter_guidance}"""
        
        return {
            "request": self._build_text_request_payload(user_content, prompt),
            "file_metadata": {
                "filename": ", ".join(filenames),
                "size_bytes": total_bytes,
                "format": "text_combined",
                "estimated_tokens": total_tokens,
                "source_metadata": source_metadata,
                "use_unified": self.use_unified
            }
        }
    
    def _calculate_smart_chunk_size(self, total_tokens: int, chapter_count: int) -> int:
        """
        Calculate optimal chunk size based on chapter density and expected output.

        For chapter-heavy books, smaller chunks prevent output truncation.

        Args:
            total_tokens: Total input tokens in the file
            chapter_count: Number of chapters (from TOC)

        Returns:
            Optimal max tokens per chunk
        """
        tokens_per_chapter = total_tokens / max(1, chapter_count)
        output_per_chapter = self._estimate_output_tokens_per_chapter(tokens_per_chapter)

        # Keep output comfortably below the model ceiling. Smaller chunks tend to
        # return faster and reduce long-tail latency on dense books.
        target_max_output = self.smart_chunk_settings["target_output_tokens"]

        # Calculate how many chapters we can safely fit per chunk
        chapters_per_chunk = max(3, target_max_output // output_per_chapter)

        # Calculate chunk size in input tokens
        smart_chunk_tokens = int(chapters_per_chunk * tokens_per_chapter)

        # Apply bounds: avoid too many tiny chunks, but keep request size moderate
        # enough that the model is less likely to stall on very dense books.
        min_tokens = self.smart_chunk_settings["min_tokens"]
        max_tokens = self.smart_chunk_settings["max_tokens"]
        if smart_chunk_tokens < min_tokens:
            floor_chapters = math.ceil(min_tokens / max(1, tokens_per_chapter))
            floor_output_tokens = floor_chapters * output_per_chapter
            if floor_output_tokens <= target_max_output * 1.25:
                smart_chunk_tokens = min_tokens
        smart_chunk_tokens = min(max_tokens, smart_chunk_tokens)

        log.info(f"Manifest: Smart chunking - {chapter_count} chapters, ~{tokens_per_chapter:.0f} tokens/ch, "
                 f"~{output_per_chapter} output/ch → {chapters_per_chunk} ch/chunk → {smart_chunk_tokens:,} tokens/chunk")

        return smart_chunk_tokens

    @staticmethod
    def _estimate_output_tokens_per_chapter(tokens_per_chapter: float) -> int:
        """Estimate richer source-anchored output density by chapter size."""
        if tokens_per_chapter >= 9000:
            return 2400
        if tokens_per_chapter >= 6500:
            return 2100
        if tokens_per_chapter >= 4000:
            return 1800
        return 1400

    def _build_file_part_guidance(
        self, toc_structured: list[tuple[str, str]], file_part_idx: int
    ) -> str:
        parts_count = sum(1 for level, _ in toc_structured if level == "part")
        current_part_idx = -1
        target_part_title = None
        target_chapters = []

        for level, title in toc_structured:
            if level == "part":
                current_part_idx += 1
                if current_part_idx == file_part_idx:
                    target_part_title = title
                    target_chapters = []
                elif current_part_idx > file_part_idx:
                    break
            elif level == "chapter" and current_part_idx == file_part_idx:
                target_chapters.append(title)

        if not target_part_title:
            return ""

        chapters_list = "\n".join(f"    ### {ch}" for ch in target_chapters)
        return f"""
FILE-TO-PART MAPPING: This is file {file_part_idx + 1} of {parts_count}.
This file should contain ONLY:
  ## {target_part_title}
{chapters_list}

Do NOT create headings for other Parts — they are in different files.

"""

    @staticmethod
    def _get_chapter_count(file_data: dict) -> int:
        toc_structured = file_data.get("toc_structured")
        if toc_structured:
            return sum(1 for level, _ in toc_structured if level == "chapter")
        toc = file_data.get("toc") or []
        return len(toc)

    def _create_chunk_plan_request(self, filename: str, file_data: dict) -> dict:
        total_tokens = file_data.get("estimated_tokens", 0)
        chapter_count = self._get_chapter_count(file_data)
        max_chunk_tokens = self._calculate_smart_chunk_size(total_tokens, chapter_count)
        desired_chunks = max(2, math.ceil(total_tokens / max_chunk_tokens))
        toc_guidance = self._build_chapter_guidance(
            toc=file_data.get("toc"),
            toc_structured=file_data.get("toc_structured"),
            location_label="book",
        )
        planning_prompt = f"""You are planning how to split an extra-long book into contiguous processing chunks.

Goal:
- Divide the book into {desired_chunks} contiguous chunks.
- Keep chapters in order.
- Keep each chunk close to {max_chunk_tokens:,} input tokens, but preserve chapter coherence.
- Use the provided TOC titles exactly.

Return JSON only with this shape:
{{
  "chunks": [
    {{
      "chunk_number": 1,
      "chapter_titles": ["Exact TOC title 1", "Exact TOC title 2"],
      "start_anchor": null,
      "notes": "short rationale"
    }},
    {{
      "chunk_number": 2,
      "chapter_titles": ["Exact TOC title 3"],
      "start_anchor": "Exact 12-30 word snippet from the first paragraph where this chunk should begin",
      "notes": "short rationale"
    }}
  ]
}}

Rules:
- `chapter_titles` must be consecutive and cover the book in order with no gaps or duplicates.
- `start_anchor` is required for chunks 2..N.
- Every `start_anchor` must be copied verbatim from the provided text, with no ellipses or quotes.
- Choose anchors that are likely unique in the book.
- Keep `notes` brief.

{toc_guidance}"""
        request_content = f"""Here is the complete book content to plan:

---

{file_data.get('text', '')}

---

{planning_prompt}"""
        return {
            "request": {
                "model": self.model_id,
                "max_tokens": self.chunk_planning_settings["max_output_tokens"],
                "messages": [
                    {
                        "role": "user",
                        "content": request_content,
                    }
                ],
            },
            "file_metadata": {
                "filename": f"{filename} (planning)",
                "size_bytes": file_data.get("size_bytes", 0),
                "format": "chunk_plan",
                "use_unified": False,
            },
        }

    @staticmethod
    def _extract_json_payload(response_text: str) -> str:
        text = (response_text or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return text[start : end + 1]
        return text

    def parse_chunk_plan_response(self, response_text: str, file_data: dict) -> dict | None:
        """Parse a whole-book planning response into a validated chunk plan."""
        try:
            payload = json.loads(self._extract_json_payload(response_text))
        except json.JSONDecodeError as exc:
            log.warning(f"Manifest: Could not parse chunk plan JSON: {exc}")
            return None

        chunks = payload.get("chunks")
        if not isinstance(chunks, list) or len(chunks) < 2:
            log.warning("Manifest: Chunk plan did not contain multiple chunks")
            return None

        expected_titles = self._expected_plan_titles(file_data)
        seen_titles = []
        parsed_chunks = []
        for index, chunk in enumerate(chunks, start=1):
            if not isinstance(chunk, dict):
                log.warning("Manifest: Chunk plan entry was not an object")
                return None
            chapter_titles = chunk.get("chapter_titles") or []
            if not isinstance(chapter_titles, list) or not chapter_titles:
                log.warning("Manifest: Chunk plan entry missing chapter_titles")
                return None
            if index > 1 and not chunk.get("start_anchor"):
                log.warning("Manifest: Chunk plan entry missing start_anchor")
                return None
            seen_titles.extend(chapter_titles)
            parsed_chunks.append(
                {
                    "chunk_number": index,
                    "chapter_titles": [str(title).strip() for title in chapter_titles if str(title).strip()],
                    "start_anchor": chunk.get("start_anchor"),
                    "notes": str(chunk.get("notes", "")).strip(),
                }
            )

        if expected_titles and seen_titles != expected_titles:
            log.warning("Manifest: Chunk plan titles did not match expected TOC order")
            return None

        return {"chunks": parsed_chunks}

    def _expected_plan_titles(self, file_data: dict) -> list[str]:
        toc_structured = file_data.get("toc_structured")
        if toc_structured:
            return [title for level, title in toc_structured if level == "chapter"]
        return list(file_data.get("toc") or [])

    def _extract_chunk_toc(
        self,
        chunk: str,
        toc: list[str] | None = None,
        toc_structured: list[tuple[str, str]] | None = None,
    ) -> tuple[list[str], list[tuple[str, str]] | None]:
        heading_titles = {
            match.group(1).strip()
            for match in re.finditer(r"^#{2,3}\s+(.+)$", chunk, flags=re.MULTILINE)
        }
        if not heading_titles:
            return toc or [], toc_structured

        if toc_structured:
            selected = []
            current_part = None
            part_added = None
            for level, title in toc_structured:
                if level == "part":
                    current_part = title
                    if title in heading_titles:
                        selected.append((level, title))
                        part_added = title
                elif title in heading_titles:
                    if current_part and current_part != part_added:
                        selected.append(("part", current_part))
                        part_added = current_part
                    selected.append((level, title))
            if selected:
                return [title for _level, title in selected], selected

        if toc:
            selected_flat = [title for title in toc if title in heading_titles]
            if selected_flat:
                return selected_flat, None

        return toc or [], toc_structured

    @staticmethod
    def _filter_structured_toc_by_titles(
        toc_structured: list[tuple[str, str]] | None,
        chapter_titles: list[str],
    ) -> list[tuple[str, str]] | None:
        if not toc_structured or not chapter_titles:
            return None

        selected = []
        current_part = None
        part_added = None
        target_titles = set(chapter_titles)
        for level, title in toc_structured:
            if level == "part":
                current_part = title
                continue
            if title not in target_titles:
                continue
            if current_part and current_part != part_added:
                selected.append(("part", current_part))
                part_added = current_part
            selected.append((level, title))
        return selected or None

    def _build_chapter_guidance(
        self,
        toc: list[str] | None = None,
        toc_structured: list[tuple[str, str]] | None = None,
        location_label: str = "file",
        extra_guidance: str = "",
    ) -> str:
        if toc_structured:
            parts_count = sum(1 for level, _ in toc_structured if level == "part")
            chapters_count = sum(1 for level, _ in toc_structured if level == "chapter")
            has_parts = parts_count > 0

            toc_lines = []
            for level, title in toc_structured:
                if level == "part":
                    toc_lines.append(f"  ## {title}")
                elif has_parts:
                    toc_lines.append(f"    ### {title}")
                else:
                    toc_lines.append(f"  ## {title}")
            toc_display = "\n".join(toc_lines)

            if has_parts:
                return f"""THE ACTUAL STRUCTURE OF THIS {location_label.upper()} IS (from Table of Contents):
{toc_display}
{extra_guidance}CRITICAL RULES:
- Use ## headings ONLY for the {parts_count} Parts listed above
- Use ### headings ONLY for the {chapters_count} Chapters listed above
- ONLY summarize Parts/Chapters whose TEXT IS PRESENT in this {location_label}
- Do NOT generate summaries for Parts/Chapters not included
- All other headings in the source are SUBSECTIONS — convert them to bullet points, NOT headings

"""

            return f"""THE ACTUAL CHAPTERS IN THIS {location_label.upper()} ARE (from Table of Contents):
{toc_display}

CRITICAL RULES:
- Use ## headings ONLY for the {chapters_count} chapters listed above
- ONLY summarize chapters whose TEXT IS PRESENT in this {location_label}
- Do NOT generate summaries for chapters not included
- All other headings in the source are SUBSECTIONS — convert them to bullet points, NOT headings

"""

        if toc:
            chapter_list = "\n".join(f"  {i+1}. {title}" for i, title in enumerate(toc))
            return f"""THE ACTUAL CHAPTERS IN THIS {location_label.upper()} ARE (from Table of Contents):
{chapter_list}

CRITICAL: Use ## headings ONLY for these {len(toc)} chapters.
- Match chapter titles to the list above
- ONLY summarize chapters whose TEXT IS PRESENT in this {location_label}
- Do NOT generate summaries for chapters not included
- All other headings in the source are SUBSECTIONS — convert them to bullet points

"""

        return ""

    def _create_chunked_requests(self, filename: str, file_data: dict, prompt: str) -> list:
        """
        Create multiple requests for oversized files by chunking at chapter boundaries.

        Args:
            filename: Original filename
            file_data: File data dict with 'text' content
            prompt: The summary prompt to apply

        Returns:
            List of request dicts, one per chunk
        """
        text_content = file_data.get('text', '')
        toc = file_data.get('toc', [])  # TOC from EPUB extraction
        toc_structured = file_data.get('toc_structured')  # Structured TOC if provided manually
        total_tokens = file_data.get('estimated_tokens', 0)

        # Count chapters for smart chunking
        chapter_count = len(toc) if toc else 0
        if toc_structured:
            chapter_count = sum(1 for level, _ in toc_structured if level == 'chapter')

        # Use smart chunking if we have chapter info, otherwise fall back to fixed ratio
        if chapter_count > 10:
            max_chunk_tokens = self._calculate_smart_chunk_size(total_tokens, chapter_count)
        else:
            # Fall back to 60% of max tokens for books without good chapter info
            max_chunk_tokens = int(self.single_request_limit * 0.60)

        chunk_plan = file_data.get("chunk_plan")
        chunk_specs = None
        if chunk_plan:
            chunk_specs = self._build_chunk_specs_from_plan(
                text_content,
                chunk_plan,
                max_chunk_tokens=max_chunk_tokens,
            )
            if chunk_specs:
                log.info(
                    f"Manifest: Applied whole-book plan to split {filename} into {len(chunk_specs)} chunks"
                )
            else:
                log.warning("Manifest: Planned chunk boundaries could not be applied, falling back")

        if not chunk_specs:
            chunks = chunk_markdown_by_chapters(
                text_content,
                max_tokens=max_chunk_tokens,
                toc=toc,
                toc_structured=toc_structured,
            )
            chunk_specs = [{"text": chunk} for chunk in chunks]

        log.info(f"Manifest: Split {filename} into {len(chunk_specs)} chunks")

        requests = []
        for i, chunk_spec in enumerate(chunk_specs, 1):
            chunk = chunk_spec["text"]
            chunk_tokens = estimate_tokens(chunk)
            log.info(f"Manifest: Chunk {i}/{len(chunk_specs)}: ~{chunk_tokens:,} tokens")

            planned_titles = chunk_spec.get("chapter_titles") or []
            if planned_titles:
                chunk_toc_structured = self._filter_structured_toc_by_titles(
                    toc_structured,
                    planned_titles,
                )
                chunk_toc = (
                    [title for _level, title in chunk_toc_structured]
                    if chunk_toc_structured
                    else planned_titles
                )
            else:
                chunk_toc, chunk_toc_structured = self._extract_chunk_toc(
                    chunk, toc=toc, toc_structured=toc_structured
                )
            chapter_guidance = self._build_chapter_guidance(
                toc=chunk_toc,
                toc_structured=chunk_toc_structured,
                location_label="chunk",
            )
            if not chapter_guidance:
                chapter_guidance = """Could not extract TOC from this chunk. Use your judgment to identify actual chapters vs. subsections.
            
GUIDANCE:
- A typical book has 10-20 chapters total, not 50+
- A CHAPTER is a major division (starts on its own page, has a title)
- SUBSECTIONS within chapters become bullet points, not ### headings
- If you find yourself creating 15+ ### headings in one chunk, STOP — you are treating subsections as chapters"""

            # Build continuity instructions based on position
            if i == 1:
                continuity = f"""This is part {i} of {len(chunk_specs)} of the book. More content will follow in subsequent parts.

CRITICAL: Do NOT write any concluding statements, summaries, or "This concludes Part X" messages. Simply outline the chapters present in this section and stop."""
            elif i == len(chunk_specs):
                continuity = f"""This is part {i} of {len(chunk_specs)} of the book, continuing from previous parts.

CRITICAL INSTRUCTIONS FOR CONTINUATION CHUNKS:
- This chunk contains REAL CHAPTER CONTENT, not front matter or minimal content
- Do NOT trigger the "minimal content" rule — that only applies to title pages, copyright pages, etc.
- Do NOT add a title, overview, or introduction — begin directly with chapter outlines
- The chapters in this chunk are a CONTINUATION of the book's actual content"""
            else:
                continuity = f"""This is part {i} of {len(chunk_specs)} of the book, continuing from previous parts. More content will follow.

CRITICAL INSTRUCTIONS FOR CONTINUATION CHUNKS:
- This chunk contains REAL CHAPTER CONTENT, not front matter or minimal content
- Do NOT trigger the "minimal content" rule — that only applies to title pages, copyright pages, etc.
- Do NOT add any introduction, title, overview, or concluding statements
- Begin directly with the chapter outlines for chapters present in this section"""

            # Keep chunk-local guidance with the user content; the shared prompt is
            # attached separately so Anthropic can cache it across requests.
            chunk_prompt = f"""{continuity}

{chapter_guidance}"""

            user_content = f"""Here is part {i} of {len(chunk_specs)} of the book content:

---

{chunk}

---

{chunk_prompt}"""

            request = {
                "request": self._build_text_request_payload(user_content, prompt),
                "file_metadata": {
                    "filename": f"{filename} (part {i}/{len(chunk_specs)})",
                    "size_bytes": file_data.get("size_bytes", 0) // len(chunk_specs),
                    "format": "text_chunk",
                    "estimated_tokens": chunk_tokens,
                    "chunk_info": {
                        "chunk_number": i,
                        "total_chunks": len(chunk_specs),
                        "original_filename": filename,
                        "planned": bool(planned_titles),
                    },
                    "source_metadata": file_data.get("source_metadata", {}),
                    "use_unified": self.use_unified
                }
            }
            requests.append(request)

        return requests

    def _create_base64_request(self, filename: str, file_data: dict, prompt: str) -> dict:
        """Create a request for base64-encoded PDF content (scanned PDFs)."""
        request = {
            "model": self.model_id,
            "max_tokens": self.request_max_output_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": file_data.get("mime_type", "application/pdf"),
                                "data": file_data["data"]
                            }
                        }
                    ]
                }
            ],
        }
        if self.use_prompt_caching:
            request["system"] = [
                {
                    "type": "text",
                    "text": prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            request["messages"][0]["content"].append(
                {
                    "type": "text",
                    "text": prompt,
                }
            )

        return {
            "request": request,
            "file_metadata": {
                "filename": filename,
                "size_bytes": file_data.get("size_bytes", 0),
                "format": "base64",
                "source_metadata": file_data.get("source_metadata", {}),
                "use_unified": self.use_unified
            }
        }

    def _build_text_request_payload(self, user_content: str, prompt: str) -> dict:
        request = {
            "model": self.model_id,
            "max_tokens": self.request_max_output_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": user_content,
                }
            ],
        }

        if self.use_prompt_caching:
            request["system"] = [
                {
                    "type": "text",
                    "text": prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            request["messages"][0]["content"] = f"{user_content}\n\n{prompt}"

        return request

    def _build_chunk_specs_from_plan(
        self,
        text_content: str,
        chunk_plan: dict,
        max_chunk_tokens: int,
    ) -> list[dict] | None:
        chunks = chunk_plan.get("chunks") or []
        if len(chunks) < 2:
            return None

        boundaries = []
        search_start = 0
        for chunk in chunks[1:]:
            anchor = chunk.get("start_anchor")
            if not anchor:
                return None
            position = self._find_anchor_position(text_content, anchor, search_start)
            if position is None:
                log.warning("Manifest: Could not find planned anchor in text: %s", anchor[:80])
                return None
            boundaries.append(position)
            search_start = position + 1

        slices = [0, *boundaries, len(text_content)]
        specs = []
        for idx, chunk in enumerate(chunks):
            start = slices[idx]
            end = slices[idx + 1]
            chunk_text = text_content[start:end].strip()
            if not chunk_text:
                return None
            token_count = estimate_tokens(chunk_text)
            if token_count > int(max_chunk_tokens * 1.25):
                log.warning(
                    "Manifest: Planned chunk %s exceeded size budget (%s > %s)",
                    idx + 1,
                    token_count,
                    int(max_chunk_tokens * 1.25),
                )
                return None
            specs.append(
                {
                    "text": chunk_text,
                    "chapter_titles": chunk.get("chapter_titles") or [],
                    "notes": chunk.get("notes", ""),
                }
            )
        return specs

    @staticmethod
    def _find_anchor_position(text: str, anchor: str, start_at: int = 0) -> int | None:
        exact_pos = text.find(anchor, start_at)
        if exact_pos >= 0:
            return exact_pos

        tokens = [token for token in anchor.split() if token]
        if len(tokens) < 4:
            return None
        pattern = re.compile(r"\s+".join(re.escape(token) for token in tokens), re.MULTILINE)
        match = pattern.search(text, start_at)
        if match:
            return match.start()
        return None
