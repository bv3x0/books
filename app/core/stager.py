"""
Stager - Prepares files for processing with format-aware extraction.

Handles both EPUB and PDF files:
- EPUBs: Extract to Markdown with semantic structure
- PDFs: Try text extraction first, fall back to base64 for scanned docs
"""

import os
import re
from app.config import INPUT_DIR, BOOKS_DIR
from app.utils import natural_sort_key
from app.logger import log
from app.core.epub_processor import extract_epub_to_markdown, estimate_tokens, extract_toc_from_epub, parse_manual_toc, get_flat_toc
from app.core.pdf_processor import extract_pdf_to_markdown, prepare_pdf_as_base64, split_pdf_pages

# Standard location for manual TOC file
MANUAL_TOC_PATH = os.path.join(BOOKS_DIR, 'toc.txt')


def normalize_pdf_headings(text: str) -> str:
    """
    Strip markdown heading markers from PDF-extracted text.

    When using a manual TOC, we want Claude to rely on the TOC for structure
    rather than the (often incorrect) headings detected by font size in PDFs.
    This converts headings to bold text so content is preserved but structure
    comes from TOC.

    Example:
        ## The Lure of the Mother Tongue  →  **The Lure of the Mother Tongue**
    """
    # Match lines starting with 1-6 # characters followed by space and text
    # Convert to bold text instead
    def replace_heading(match):
        heading_text = match.group(2).strip()
        return f"**{heading_text}**"

    # Pattern: start of line, 1-6 hashes, space, then the heading text
    normalized = re.sub(r'^(#{1,6})\s+(.+)$', replace_heading, text, flags=re.MULTILINE)

    return normalized


# Supported file extensions
SUPPORTED_EXTENSIONS = {'.pdf', '.epub'}


class Stager:
    def __init__(
        self,
        client,
        use_manual_toc=False,
        use_vlm=False,
        split_pages=False,
        input_dir: str | None = None,
        toc_path: str | None = None,
    ):
        self.client = client
        self.use_manual_toc = use_manual_toc
        self.use_vlm = use_vlm
        self.split_pages = split_pages
        self.input_dir = input_dir or INPUT_DIR
        if toc_path is not None:
            self.toc_path = toc_path
        elif use_manual_toc:
            self.toc_path = MANUAL_TOC_PATH
        else:
            self.toc_path = None
    
    def list_local_files(self):
        """
        Lists and sorts supported files (EPUB, PDF) in the input directory.
        """
        files = []
        for f in os.listdir(self.input_dir):
            ext = os.path.splitext(f.lower())[1]
            if ext in SUPPORTED_EXTENSIONS:
                files.append(f)
        
        sorted_files = sorted(files, key=natural_sort_key)
        log.debug(f"Stager: Found files in order: {sorted_files}")
        return sorted_files

    def prepare_files(self):
        """
        Prepares files for Claude API with format-aware processing.

        Returns a dictionary mapping filename to file data dict.
        The dict contains either:
        - 'text': Extracted Markdown text (for EPUBs and text-based PDFs)
        - 'data': Base64-encoded PDF (for scanned PDFs)
        """
        local_files = self.list_local_files()
        prepared_files = {}

        log.info(f"Stager: Found {len(local_files)} files to process.")
        log.debug(f"Stager: Input directory: {self.input_dir}")

        # Load manual TOC if --toc flag was provided
        manual_toc = None
        manual_toc_structured = None
        if self.toc_path:
            if os.path.exists(self.toc_path):
                try:
                    manual_toc_structured = parse_manual_toc(self.toc_path)
                    manual_toc = get_flat_toc(manual_toc_structured)
                    parts_count = sum(1 for level, _ in manual_toc_structured if level == 'part')
                    chapters_count = sum(1 for level, _ in manual_toc_structured if level == 'chapter')
                    log.info(f"Stager: Loaded manual TOC from {self.toc_path} ({parts_count} parts, {chapters_count} chapters)")
                except Exception as e:
                    log.warning(f"Stager: Failed to parse manual TOC: {e}")
            else:
                log.warning(f"Stager: manual TOC path not found: {self.toc_path}")
        
        for i, filename in enumerate(local_files):
            file_path = os.path.join(self.input_dir, filename)
            file_size = os.path.getsize(file_path)
            ext = os.path.splitext(filename.lower())[1]
            
            log.info(f"Stager: Processing {filename} ({i+1}/{len(local_files)}, {file_size:,} bytes)...")
            
            try:
                if ext == '.epub':
                    # EPUB: Extract to Markdown
                    result = self._prepare_epub(file_path, filename)
                    # Override EPUB's extracted TOC with manual TOC if --toc flag was used
                    if result and manual_toc:
                        result['toc'] = manual_toc
                        result['toc_structured'] = manual_toc_structured
                        log.info(f"Stager: Using manual TOC for {filename} (overriding EPUB's extracted TOC)")
                elif ext == '.pdf':
                    # PDF: Try text extraction, fall back to base64
                    result = self._prepare_pdf(file_path, filename, use_vlm=self.use_vlm, split_pages=self.split_pages)
                    # Attach manual TOC to PDF files if available
                    if result and manual_toc and result.get('format') == 'markdown':
                        result['toc'] = manual_toc
                        result['toc_structured'] = manual_toc_structured
                        # Normalize headings: strip # markers so Claude relies on TOC for structure
                        original_text = result['text']
                        result['text'] = normalize_pdf_headings(original_text)
                        # Recalculate tokens after normalization
                        result['estimated_tokens'] = estimate_tokens(result['text'])
                        log.info(f"Stager: Normalized PDF headings for {filename} (using manual TOC for structure)")
                else:
                    log.warning(f"Unsupported file type: {filename}")
                    continue

                if result:
                    prepared_files[filename] = result
                    
            except Exception as e:
                log.error(f"Stager: Failed to prepare {filename}: {e}")
        
        # Log summary
        text_count = sum(1 for f in prepared_files.values() if 'text' in f)
        base64_count = sum(1 for f in prepared_files.values() if 'data' in f)
        log.info(f"Stager: Prepared {len(prepared_files)} files ({text_count} as text, {base64_count} as base64)")
        
        return prepared_files
    
    def _prepare_epub(self, file_path: str, filename: str) -> dict:
        """Prepare EPUB file by extracting to Markdown and TOC."""
        markdown = extract_epub_to_markdown(file_path)

        if not markdown:
            log.error(f"Failed to extract EPUB: {filename}")
            return None

        tokens = estimate_tokens(markdown)

        # Extract structured TOC for chapter guidance
        toc_structured = extract_toc_from_epub(file_path)
        if toc_structured:
            parts_count = sum(1 for level, _ in toc_structured if level == 'part')
            chapters_count = sum(1 for level, _ in toc_structured if level == 'chapter')
            log.info(f"Stager: Extracted TOC with {parts_count} parts, {chapters_count} chapters")
        else:
            log.warning(f"Stager: Could not extract TOC from {filename}")

        # Convert to flat list for backward compatibility (matching, validation)
        toc_flat = get_flat_toc(toc_structured) if toc_structured else []

        return {
            "text": markdown,
            "format": "markdown",
            "estimated_tokens": tokens,
            "size_bytes": os.path.getsize(file_path),
            "filename": filename,
            "toc": toc_flat,  # Flat list for matching/validation
            "toc_structured": toc_structured,  # Structured list with parts/chapters
        }
    
    def _prepare_pdf(self, file_path: str, filename: str, use_vlm: bool = False, split_pages: bool = False) -> dict:
        """
        Prepare PDF file - try text extraction first, fall back to base64.
        """
        original_size = os.path.getsize(file_path)

        # Split two-page spreads if requested (split file left in staging)
        if split_pages:
            file_path = split_pdf_pages(file_path)

        # Try text extraction first
        markdown = extract_pdf_to_markdown(file_path, use_vlm=use_vlm)

        if markdown:
            # Successfully extracted text
            tokens = estimate_tokens(markdown)
            log.info(f"Stager: PDF extracted as text (~{tokens:,} tokens)")

            return {
                "text": markdown,
                "format": "markdown",
                "estimated_tokens": tokens,
                "size_bytes": original_size,
                "filename": filename,
            }
        else:
            # Fall back to base64 for scanned PDFs
            log.info(f"Stager: Using base64 encoding for scanned PDF: {filename}")
            base64_data = prepare_pdf_as_base64(file_path)

            if not base64_data:
                return None

            return {
                "data": base64_data["data"],
                "mime_type": base64_data["mime_type"],
                "format": "base64",
                "size_bytes": base64_data["size_bytes"],
                "filename": filename,
            }
    
    # Alias for backward compatibility
    def upload_files(self):
        """Alias for prepare_files() for backward compatibility."""
        return self.prepare_files()
