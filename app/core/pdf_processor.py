"""
PDF Processor - Extracts text from PDF files with heading structure preservation.

Uses Docling (IBM Research) for high-quality PDF to Markdown conversion.
Falls back to PyMuPDF4LLM if Docling unavailable, or base64 for scanned PDFs.
"""

import os
import platform
import time
import base64
from typing import Optional, Dict, Any
from app.logger import log

# Pages per chunk for VLM processing (balances progress feedback vs overhead)
VLM_CHUNK_SIZE = 50


def _get_pdf_extractor_override() -> str:
    """
    Return an optional extractor override from the environment.

    Supported values:
    - ``docling``: force Docling before fallbacks
    - ``pymupdf``: skip Docling and use PyMuPDF first
    """
    return os.getenv("SUMMARIZER_PDF_EXTRACTOR", "").strip().lower()


def _prefer_pymupdf_by_default() -> bool:
    """
    Prefer PyMuPDF by default on environments where standard Docling is unstable.

    On this project, standard Docling extraction can crash the Python process on
    macOS/Apple Silicon due to native MLX/Metal initialization. PyMuPDF is slower
    but stable, so make that the default path there unless explicitly overridden.
    """
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def _resolve_pdf_extractor_order(use_vlm: bool) -> list[str]:
    """
    Return extractor order for standard PDF text extraction.

    ``use_vlm`` is handled first by the caller, so this only decides the standard
    text-extractor fallback chain.
    """
    extractor_override = _get_pdf_extractor_override()
    if extractor_override and extractor_override not in {"docling", "pymupdf"}:
        log.warning(f"Unknown SUMMARIZER_PDF_EXTRACTOR={extractor_override}; ignoring override")
        extractor_override = ""

    if extractor_override == "docling":
        log.info("PDF extractor override active: Docling first")
        return ["docling", "pymupdf"]
    if extractor_override == "pymupdf":
        log.info("PDF extractor override active: PyMuPDF first")
        return ["pymupdf", "docling"]

    if _prefer_pymupdf_by_default():
        log.info("PDF extractor default: PyMuPDF first on macOS/Apple Silicon")
        return ["pymupdf", "docling"]

    return ["docling", "pymupdf"]


def split_pdf_pages(pdf_path: str) -> str:
    """
    Split a two-pages-per-page scanned PDF into single pages.

    Each PDF page is normalized to rotation 0 in-memory, then cropped into
    left and right halves, producing a new PDF with twice the page count.
    The split PDF is saved next to the original with a '-split' suffix.

    Args:
        pdf_path: Path to the original PDF

    Returns:
        Path to the split PDF
    """
    import pymupdf

    doc = pymupdf.open(pdf_path)
    out = pymupdf.open()

    normalized_rotations = 0
    for page in doc:
        if page.rotation:
            page.remove_rotation()
            normalized_rotations += 1

    log.info(f"Splitting {os.path.basename(pdf_path)} ({len(doc)} pages → {len(doc) * 2} pages)")
    if normalized_rotations:
        log.info(f"Normalized rotation on {normalized_rotations} page(s) before splitting")
    print(f"  Splitting two-page spreads: {len(doc)} pages → {len(doc) * 2} pages", flush=True)

    for page in doc:
        rect = page.rect
        mid_x = (rect.x0 + rect.x1) / 2

        # Left half
        left_rect = pymupdf.Rect(rect.x0, rect.y0, mid_x, rect.y1)
        new_page = out.new_page(width=left_rect.width, height=left_rect.height)
        new_page.show_pdf_page(new_page.rect, doc, page.number, clip=left_rect)

        # Right half
        right_rect = pymupdf.Rect(mid_x, rect.y0, rect.x1, rect.y1)
        new_page = out.new_page(width=right_rect.width, height=right_rect.height)
        new_page.show_pdf_page(new_page.rect, doc, page.number, clip=right_rect)

    # Save next to original: book.pdf → book-split.pdf
    base, ext = os.path.splitext(pdf_path)
    split_path = f"{base}-split{ext}"
    out.save(split_path)
    out.close()
    doc.close()

    log.info(f"Split PDF saved: {split_path}")
    return split_path


def extract_pdf_to_markdown(pdf_path: str, use_vlm: bool = False) -> Optional[str]:
    """
    Extract text from PDF and convert to Markdown with heading structure.

    Uses Docling for high-quality extraction. Falls back to PyMuPDF4LLM
    if Docling is not installed, or to base64 encoding for scanned PDFs.

    When use_vlm=True, tries Granite-Docling VLM first (better for scanned/
    degraded PDFs), then falls back through the standard pipeline.

    Args:
        pdf_path: Path to the PDF file
        use_vlm: If True, use Granite-Docling VLM for extraction

    Returns:
        Markdown string with heading structure, or None if extraction fails
        (indicating the PDF should be processed as base64/vision)
    """
    if not os.path.exists(pdf_path):
        log.error(f"PDF file not found: {pdf_path}")
        return None

    # Try VLM extraction first if requested
    if use_vlm:
        markdown = _extract_with_docling_vlm(pdf_path)
        if markdown:
            return markdown

    for extractor in _resolve_pdf_extractor_order(use_vlm):
        if extractor == "docling":
            markdown = _extract_with_docling(pdf_path)
        else:
            markdown = _extract_with_pymupdf(pdf_path)
        if markdown:
            return markdown

    return None


def _deduplicate_chunk_boundaries(text: str) -> str:
    """
    Remove duplicate paragraphs introduced by VLM chunk boundaries.

    When processing a PDF in page-range chunks, the VLM may produce
    overlapping content at chunk edges. This removes exact duplicate
    paragraphs while preserving order (keeps first occurrence).
    """
    paragraphs = text.split('\n\n')
    seen = set()
    deduped = []
    removed = 0

    for para in paragraphs:
        stripped = para.strip()
        # Only deduplicate substantial paragraphs (short ones may legitimately repeat)
        if len(stripped) > 100 and stripped in seen:
            removed += 1
            continue
        if len(stripped) > 100:
            seen.add(stripped)
        deduped.append(para)

    if removed:
        log.info(f"VLM dedup: removed {removed} duplicate paragraph(s) from chunk boundaries")

    return '\n\n'.join(deduped)


def _get_pdf_page_count(pdf_path: str) -> Optional[int]:
    """Get total page count from a PDF file."""
    try:
        import pymupdf
        doc = pymupdf.open(pdf_path)
        count = len(doc)
        doc.close()
        return count
    except Exception:
        return None


def _extract_with_docling_vlm(pdf_path: str) -> Optional[str]:
    """
    Extract PDF using Granite-Docling VLM (vision-language model).

    Uses IBM's Granite-Docling-258M model via MLX to *see* page images
    instead of traditional OCR. Significantly better for scanned or
    degraded PDFs (~6-8 sec/page on Apple Silicon).

    Processes large PDFs in chunks of VLM_CHUNK_SIZE pages for progress
    feedback and resilience — if a chunk fails, previous chunks are kept.
    """
    try:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.pipeline_options import VlmPipelineOptions, VlmConvertOptions
        from docling.pipeline.vlm_pipeline import VlmPipeline
    except ImportError:
        log.warning("Docling VLM pipeline not available (requires docling with VLM support)")
        return None

    try:
        total_pages = _get_pdf_page_count(pdf_path)
        basename = os.path.basename(pdf_path)

        if total_pages:
            est_minutes = (total_pages * 7) / 60  # ~7 sec/page average
            log.info(f"VLM OCR: {basename} ({total_pages} pages, ~{est_minutes:.0f} min estimated)")
            print(f"  VLM OCR: {total_pages} pages (~{est_minutes:.0f} min estimated)", flush=True)
        else:
            log.info(f"VLM OCR: {basename} (page count unknown)")

        vlm_convert_options = VlmConvertOptions.from_preset("granite_docling")
        vlm_pipeline_options = VlmPipelineOptions(
            vlm_options=vlm_convert_options,
            generate_page_images=True,
            force_backend_text=False,
        )

        converter = DocumentConverter(
            format_options={
                "pdf": PdfFormatOption(
                    pipeline_cls=VlmPipeline,
                    pipeline_options=vlm_pipeline_options,
                ),
            }
        )

        # Small PDFs: process in one shot
        if not total_pages or total_pages <= VLM_CHUNK_SIZE:
            result = converter.convert(pdf_path, raises_on_error=False)
            markdown = result.document.export_to_markdown()

            if not markdown or len(markdown.strip()) < 100:
                log.warning("VLM extraction yielded minimal content")
                return None

            markdown = _clean_docling_markdown(markdown)
            estimated_tokens = len(markdown) // 4
            log.info(f"VLM extraction complete: ~{estimated_tokens:,} estimated tokens")
            return markdown

        # Large PDFs: process in page-range chunks
        markdown_chunks = []
        start_time = time.time()

        for chunk_start in range(1, total_pages + 1, VLM_CHUNK_SIZE):
            chunk_end = min(chunk_start + VLM_CHUNK_SIZE - 1, total_pages)
            chunk_label = f"pages {chunk_start}-{chunk_end}/{total_pages}"

            log.info(f"VLM processing {chunk_label}...")
            print(f"  VLM processing {chunk_label}...", flush=True)
            chunk_time = time.time()

            try:
                result = converter.convert(
                    pdf_path,
                    page_range=(chunk_start, chunk_end),
                    raises_on_error=False,
                )
                chunk_md = result.document.export_to_markdown()

                elapsed = time.time() - chunk_time
                if chunk_md and len(chunk_md.strip()) > 0:
                    markdown_chunks.append(chunk_md)
                    log.info(f"VLM chunk {chunk_label} done ({elapsed:.0f}s, {len(chunk_md):,} chars)")
                else:
                    log.warning(f"VLM chunk {chunk_label} yielded no content ({elapsed:.0f}s)")

            except Exception as e:
                log.warning(f"VLM chunk {chunk_label} failed: {e}")
                print(f"  WARNING: {chunk_label} failed, continuing with remaining pages", flush=True)

        if not markdown_chunks:
            log.warning("VLM extraction yielded no content from any chunk")
            return None

        total_elapsed = time.time() - start_time
        markdown = "\n\n".join(markdown_chunks)
        markdown = _deduplicate_chunk_boundaries(markdown)
        markdown = _clean_docling_markdown(markdown)

        estimated_tokens = len(markdown) // 4
        log.info(
            f"VLM extraction complete: ~{estimated_tokens:,} tokens from "
            f"{len(markdown_chunks)} chunks in {total_elapsed:.0f}s"
        )
        print(
            f"  VLM extraction complete: ~{estimated_tokens:,} tokens ({total_elapsed/60:.1f} min)",
            flush=True,
        )

        return markdown

    except Exception as e:
        log.warning(f"VLM extraction failed: {e}")
        return None


def _extract_with_docling(pdf_path: str) -> Optional[str]:
    """Extract PDF using Docling (IBM Research) - highest quality extraction."""
    try:
        from docling.document_converter import DocumentConverter
    except ImportError:
        log.debug("Docling not installed, trying PyMuPDF4LLM")
        return None

    try:
        log.info(f"Extracting with Docling: {os.path.basename(pdf_path)}")

        converter = DocumentConverter()
        result = converter.convert(pdf_path)
        markdown = result.document.export_to_markdown()

        if not markdown or len(markdown.strip()) < 100:
            log.warning("Docling extraction yielded minimal content")
            return None

        # Light cleanup (Docling output is already clean)
        markdown = _clean_docling_markdown(markdown)

        estimated_tokens = len(markdown) // 4
        log.info(f"Docling extraction complete: ~{estimated_tokens:,} estimated tokens")

        return markdown

    except Exception as e:
        log.warning(f"Docling extraction failed: {e}")
        return None


def _extract_with_pymupdf(pdf_path: str) -> Optional[str]:
    """Extract PDF using PyMuPDF4LLM - fallback extractor."""
    try:
        # Import pymupdf.layout FIRST to activate enhanced layout detection
        try:
            import pymupdf.layout
            log.debug("pymupdf.layout loaded - enhanced layout detection enabled")
        except ImportError:
            log.debug("pymupdf-layout not installed - using standard extraction")

        import pymupdf4llm
    except ImportError:
        log.warning("pymupdf4llm not installed, falling back to base64 encoding")
        return None

    try:
        log.info(f"Extracting with PyMuPDF4LLM: {os.path.basename(pdf_path)}")

        markdown = pymupdf4llm.to_markdown(pdf_path)

        if not markdown or len(markdown.strip()) < 100:
            log.warning("PyMuPDF4LLM extraction yielded minimal content, likely scanned PDF")
            return None

        # Heavy cleanup (PyMuPDF has more artifacts)
        markdown = _clean_pymupdf_markdown(markdown)

        estimated_tokens = len(markdown) // 4
        log.info(f"PyMuPDF4LLM extraction complete: ~{estimated_tokens:,} estimated tokens")

        return markdown

    except Exception as e:
        log.warning(f"PyMuPDF4LLM extraction failed: {e}. Will use base64 encoding instead.")
        return None


def prepare_pdf_as_base64(pdf_path: str) -> Optional[Dict[str, Any]]:
    """
    Prepare PDF as base64 for vision/document processing.
    
    This is the fallback for scanned PDFs where text extraction fails.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Dict with 'data', 'mime_type', and 'size_bytes', or None on failure
    """
    if not os.path.exists(pdf_path):
        log.error(f"PDF file not found: {pdf_path}")
        return None
    
    try:
        file_size = os.path.getsize(pdf_path)
        
        with open(pdf_path, "rb") as f:
            pdf_data = base64.standard_b64encode(f.read()).decode("utf-8")
        
        log.info(f"Prepared PDF as base64: {os.path.basename(pdf_path)} ({file_size:,} bytes)")
        
        return {
            "data": pdf_data,
            "mime_type": "application/pdf",
            "size_bytes": file_size,
        }
        
    except Exception as e:
        log.error(f"Failed to read PDF {pdf_path}: {e}")
        return None


def _clean_docling_markdown(text: str) -> str:
    """
    Light cleanup for Docling output (already high quality).

    Only removes:
    - Standalone page numbers
    - Excessive newlines
    """
    import re

    original_len = len(text)

    # Remove standalone page numbers (single numbers on their own line)
    text = re.sub(r'^\s*\d{1,3}\s*$', '', text, flags=re.MULTILINE)

    # Normalize excessive newlines (more than 2 consecutive)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Normalize heading spacing (ensure blank line before headings)
    text = re.sub(r'([^\n])\n(#+\s)', r'\1\n\n\2', text)

    cleaned_len = len(text.strip())
    removed = original_len - cleaned_len
    if removed > 500:
        log.info(f"Docling cleanup: removed {removed:,} chars ({removed*100//original_len}%)")

    return text.strip()


def _clean_pymupdf_markdown(text: str) -> str:
    """
    Heavy cleanup for PyMuPDF4LLM output (has many artifacts).

    Removes:
    - Picture placeholders and garbled OCR from images
    - Running headers/footers (e.g., "Chapter Title 103")
    - Standalone page numbers
    - Photo credits and captions with garbled prefixes
    """
    import re

    original_len = len(text)

    # 1. Remove picture placeholders: **==> picture [X x Y] intentionally omitted <==**
    text = re.sub(r'\*\*==> picture \[\d+ x \d+\] intentionally omitted <==\*\*\n*', '', text)

    # 2. Remove picture text blocks (garbled OCR from images)
    #    Pattern: **----- Start of picture text -----**<br>...<br>**----- End of picture text -----**<br>
    text = re.sub(
        r'\*\*----- Start of picture text -----\*\*<br>.*?\*\*----- End of picture text -----\*\*<br>\n*',
        '',
        text,
        flags=re.DOTALL
    )

    # 3. Remove garbled caption prefixes (lines starting with underscores and symbols)
    #    Pattern: ___ .:. .. Caption text here
    text = re.sub(r'^[_\s.:]+\s*(?=[A-Z])', '', text, flags=re.MULTILINE)

    # 4. Remove photo credits: (Photo Name) or (Photo: Name)
    text = re.sub(r'^\s*\(Photo:?\s+[^)]+\)\s*$', '', text, flags=re.MULTILINE)

    # 5. Remove running headers: "Chapter Title 123" pattern at end of paragraphs
    #    These appear as "Weight of Numbers 103" etc.
    #    Also handles OCR errors like "5 I" instead of "51"
    text = re.sub(r'^[A-Z][a-z]+(?: [a-z]+)*(?: of| and| the)? [A-Z][a-z]+ \d[\dIl ]{0,3}\s*$', '', text, flags=re.MULTILINE)

    # 6. Remove standalone page numbers (single numbers on their own line)
    text = re.sub(r'^\s*\d{1,3}\s*$', '', text, flags=re.MULTILINE)

    # 7. Remove page break markers if present
    text = re.sub(r'-{3,}\s*Page\s*\d+\s*-{3,}', '', text, flags=re.IGNORECASE)

    # 8. Remove lines that are mostly non-ASCII or symbols (garbled OCR remnants)
    #    Keep lines where <15% of chars are non-ASCII AND line has actual words
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        if len(line) > 10:
            non_ascii_ratio = sum(1 for c in line if ord(c) > 127) / len(line)
            # Also check if line is mostly punctuation/symbols (garbled captions)
            alpha_ratio = sum(1 for c in line if c.isalpha()) / len(line)
            if non_ascii_ratio < 0.15 and alpha_ratio > 0.3:
                cleaned_lines.append(line)
            elif non_ascii_ratio == 0 and alpha_ratio > 0.2:
                # Pure ASCII but low alpha - might be symbols, keep if has some letters
                cleaned_lines.append(line)
        else:
            cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)

    # 9. Remove <br> tags that may remain
    text = re.sub(r'<br>\n*', '\n', text)

    # 10. Normalize excessive newlines (more than 2 consecutive)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 11. Normalize heading spacing (ensure blank line before headings)
    text = re.sub(r'([^\n])\n(#+\s)', r'\1\n\n\2', text)

    cleaned_len = len(text.strip())
    removed = original_len - cleaned_len
    if removed > 1000:
        log.info(f"PyMuPDF cleanup: removed {removed:,} chars of noise ({removed*100//original_len}%)")

    return text.strip()


def estimate_tokens(text: str) -> int:
    """Estimate token count for text (rough approximation)."""
    return len(text) // 4
