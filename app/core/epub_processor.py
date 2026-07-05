"""
EPUB Processor - Extracts text from EPUB files with semantic structure preservation.

Converts EPUB HTML content to Markdown, preserving heading hierarchy
(<h1> → #, <h2> → ##, etc.) for faithful outline generation.
"""

import os
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Optional
from ebooklib import epub
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from app.logger import log


# Filenames to skip (navigation, metadata, etc.) - matched against full filename
SKIP_FILENAMES = {'nav.xhtml', 'nav.html', 'toc.xhtml', 'toc.html', 'toc.ncx'}

# Item IDs to skip (exact match only)
SKIP_IDS = {'nav', 'cover', 'toc', 'ncx'}

# Sections to skip (prefaces, appendixes, etc.) - checked against headings and filenames
SKIP_SECTIONS = {
    # Front matter
    'preface', 'foreword', 'acknowledgment', 'acknowledgement', 'dedication',
    'copyright',
    'about the author', 'note to the reader', 'translator\'s note',
    'editor\'s note', 'introduction to the', 'a note on',
    'contents', 'landmarks', 'print page list', 'what\'s next on your reading list',
    # Back matter
    'appendix', 'appendices', 'bibliography', 'selected bibliography', 'works cited', 'references',
    'notes', 'endnotes', 'footnotes', 'index', 'glossary', 'about the publisher',
    'also by', 'other books', 'further reading', 'suggested reading',
}


def extract_epub_metadata(file_path: str) -> dict:
    """Extract source-visible EPUB metadata for deterministic note metadata."""
    if not os.path.exists(file_path):
        return {}

    try:
        book = epub.read_epub(file_path)
    except Exception as e:
        log.warning(f"Failed to extract EPUB metadata from {file_path}: {e}")
        return {}

    def clean(value) -> str:
        return str(value or "").strip().strip(";").strip()

    titles = book.get_metadata("DC", "title") or []
    main_title = ""
    subtitle = ""
    for value, attrs in titles:
        text = clean(value)
        if not text:
            continue
        meta_id = str((attrs or {}).get("id", "")).lower()
        if meta_id == "maintitle":
            main_title = text
        elif meta_id == "subtitle":
            subtitle = text
        elif not main_title:
            main_title = text
        elif not subtitle:
            subtitle = text

    full_title = main_title
    if subtitle and subtitle.lower() not in main_title.lower():
        full_title = f"{main_title}: {subtitle}" if main_title else subtitle

    creators = [clean(value) for value, _attrs in book.get_metadata("DC", "creator")]
    creators = [creator for creator in creators if creator]
    author = ", ".join(creators) if creators else None

    year = None
    for value, _attrs in book.get_metadata("DC", "date"):
        match = re.search(r"\b(\d{4})\b", clean(value))
        if match:
            year = int(match.group(1))
            break

    metadata = {}
    if full_title:
        metadata["title"] = full_title
    if author:
        metadata["author"] = author
    if year:
        metadata["year"] = year
    return metadata


def extract_toc_from_epub(file_path: str) -> list[tuple[str, str]]:
    """
    Extract structured table of contents from EPUB.

    Args:
        file_path: Path to the EPUB file

    Returns:
        List of (level, title) tuples where level is 'part' or 'chapter'.
        Example: [('chapter', 'Prologue'), ('part', 'Part One: WEATHERMAN'), ('chapter', 'You Say You Want a Revolution')]
        Returns empty list if TOC cannot be parsed.
    """
    import re
    
    all_entries = []

    try:
        with zipfile.ZipFile(file_path, 'r') as epub_zip:
            file_list = epub_zip.namelist()

            # Try .ncx file first (EPUB 2 format) - can be toc.ncx or other names like *_ncx_r1.ncx
            toc_file = None
            for f in file_list:
                if f.endswith('.ncx'):
                    toc_file = f
                    break

            if toc_file:
                all_entries = _parse_toc_ncx(epub_zip.read(toc_file))
            else:
                # Try nav.xhtml (EPUB 3 format)
                for f in file_list:
                    if 'nav' in f.lower() and f.endswith(('.xhtml', '.html')):
                        toc_file = f
                        break

                if toc_file:
                    all_entries = _parse_nav_xhtml(epub_zip.read(toc_file))

    except Exception as e:
        log.warning(f"Failed to extract TOC from EPUB: {e}")
        return []

    # Filter and categorize TOC entries into parts and chapters
    entries = []
    # Liberal pattern to strip chapter prefixes in various formats:
    # - "Chapter 1. Title", "Chapter 1: Title", "Chapter 1 - Title"
    # - "Chapter One - Title", "Chapter Two: Title" (spelled-out numbers)
    # - "Ch. 1. Title", "Ch 1: Title"
    # - Roman numerals: "Chapter IV.", "IV. Title"
    # Separators: period, colon, dash variants, or just whitespace after number
    spelled_numbers = r'(?:One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|Eleven|Twelve|Thirteen|Fourteen|Fifteen|Sixteen|Seventeen|Eighteen|Nineteen|Twenty)'
    chapter_pattern = re.compile(
        r'^(?:Chapter|Ch\.?)\s*'           # "Chapter" or "Ch." prefix
        rf'(?:[IVXLCDM]+|\d+|{spelled_numbers})'  # Roman numeral, Arabic number, or spelled-out
        r'\s*[.:\-–—]?\s*',                # Optional separator (., :, -, etc.) + whitespace
        re.IGNORECASE
    )
    # Pattern for bare numbers at start: "1. Title", "10: Title", "IV. Title"
    # Requires separator to avoid stripping numbers that are part of titles (e.g., "1984")
    bare_number_pattern = re.compile(
        r'^(?:[IVXLCDM]+|\d+)'              # Roman numeral or Arabic number at start
        r'\s*[.:\-–—]\s*',                  # Separator required
        re.IGNORECASE
    )

    # Terms that indicate back matter or non-chapter sections
    skip_terms = {'bibliography', 'index', 'glossary', 'appendix', 'appendices',
                  'notes', 'endnotes', 'footnotes', 'acknowledgments', 'acknowledgements',
                  'about the author', 'further reading', 'works cited', 'references'}

    for entry in all_entries:
        entry_lower = entry.lower().strip()

        # Skip back matter and metadata sections
        if any(term in entry_lower for term in skip_terms):
            continue

        # Detect "Part X" entries (structural dividers)
        if entry_lower.startswith('part '):
            entries.append(('part', entry.strip()))
            continue

        # Strip the "Chapter X - " prefix if present, then try bare numbers
        clean_title = chapter_pattern.sub('', entry).strip()
        # If "Chapter X" pattern didn't match, try bare number pattern
        if clean_title == entry.strip():
            clean_title = bare_number_pattern.sub('', entry).strip()
        if clean_title:
            entries.append(('chapter', clean_title))
        elif entry.strip():  # If neither pattern matched, keep original if non-empty
            entries.append(('chapter', entry.strip()))

    return entries


def _parse_toc_ncx(content: bytes) -> list[str]:
    """
    Parse EPUB 2 toc.ncx format.
    
    Handles nested navPoints (Parts containing Chapters) by extracting
    all navPoint text labels recursively.
    """
    chapters = []

    # toc.ncx uses namespaces
    namespaces = {'ncx': 'http://www.daisy.org/z3986/2005/ncx/'}

    try:
        root = ET.fromstring(content)

        # Find all navPoint elements and extract their navLabel/text
        # This gets all levels (Parts and Chapters), we filter Parts later
        for nav_point in root.findall('.//ncx:navPoint', namespaces):
            label = nav_point.find('ncx:navLabel/ncx:text', namespaces)
            if label is not None and label.text:
                text = label.text.strip()
                if text:  # Skip empty labels
                    chapters.append(text)

    except ET.ParseError as e:
        log.warning(f"Failed to parse toc.ncx: {e}")
        return []

    return chapters


def _parse_nav_xhtml(content: bytes) -> list[str]:
    """
    Parse EPUB 3 nav.xhtml format.
    
    Looks for <nav epub:type="toc"> and extracts all <a> tag texts.
    """
    chapters = []

    try:
        soup = BeautifulSoup(content, 'html.parser')

        # Find the TOC nav element (may have epub:type="toc" or just be first nav)
        toc_nav = soup.find('nav', attrs={'epub:type': 'toc'}) or soup.find('nav')

        if toc_nav:
            for link in toc_nav.find_all('a'):
                if link.text:
                    text = link.text.strip()
                    if text:  # Skip empty links
                        chapters.append(text)

    except Exception as e:
        log.warning(f"Failed to parse nav.xhtml: {e}")
        return []

    return chapters


def extract_epub_to_markdown(epub_path: str) -> Optional[str]:
    """
    Extract text from EPUB and convert to Markdown with structure preserved.

    Args:
        epub_path: Path to the EPUB file

    Returns:
        Markdown string with preserved heading structure, or None if extraction fails
    """
    if not os.path.exists(epub_path):
        log.error(f"EPUB file not found: {epub_path}")
        return None
    
    try:
        # Parse with full navigation structure to preserve book organization
        book = epub.read_epub(epub_path)
    except Exception as e:
        log.error(f"Failed to read EPUB {epub_path}: {e}")
        return None
    
    log.info(f"Processing EPUB: {os.path.basename(epub_path)}")
    
    markdown_parts = []
    chapter_count = 0
    
    # Get items in reading order (spine)
    for item in book.get_items_of_type(9):  # 9 = ITEM_DOCUMENT
        # Skip navigation and metadata items
        item_id = item.get_id().lower() if item.get_id() else ''
        item_name = item.get_name().lower() if item.get_name() else ''
        filename = item_name.split('/')[-1]  # Get just the filename

        # Skip by exact ID match or filename match
        if item_id in SKIP_IDS or filename in SKIP_FILENAMES:
            log.debug(f"Skipping non-content item: {item.get_name()}")
            continue
        
        # Extract and convert content
        content = item.get_content().decode('utf-8', errors='ignore')
        markdown = _html_to_markdown(content)
        
        if markdown and markdown.strip():
            # Check if this looks like front matter (short, no headings)
            if _is_frontmatter(markdown):
                log.debug(f"Skipping likely frontmatter: {item.get_name()}")
                continue
            
            # Check if this is a skippable section (preface, appendix, etc.)
            skip_reason = _is_skippable_section(markdown, item_name)
            if skip_reason:
                log.info(f"Skipping {skip_reason}: {item.get_name()}")
                continue
                
            markdown_parts.append(markdown)
            chapter_count += 1
            log.debug(f"Extracted chapter {chapter_count}: {item.get_name()}")
    
    if not markdown_parts:
        log.warning(f"No content extracted from EPUB: {epub_path}")
        return None
    
    # Join all parts with double newlines
    full_text = '\n\n'.join(markdown_parts)

    # Clean up excessive whitespace
    full_text = _clean_markdown(full_text)

    # Estimate tokens (rough: ~4 chars per token)
    estimated_tokens = len(full_text) // 4
    log.info(f"EPUB extraction complete: {chapter_count} chapters, ~{estimated_tokens:,} estimated tokens")

    return full_text


def _html_to_markdown(html_content: str) -> str:
    """Convert HTML to Markdown preserving semantic structure."""
    # Parse XHTML (XML-based HTML in EPUBs)
    soup = BeautifulSoup(html_content, 'lxml-xml')

    # Remove script, style, and other non-content elements
    for tag in soup.find_all(['script', 'style', 'meta', 'link', 'head']):
        tag.decompose()

    # Remove images and figures (we can't process visuals, saves tokens)
    for tag in soup.find_all(['img', 'svg', 'figure', 'figcaption']):
        tag.decompose()

    # Remove figure captions by common class names
    for tag in soup.find_all(class_=['fcaption', 'figcaption', 'figlabel', 'caption']):
        tag.decompose()
    
    # Get just the body content if present
    body = soup.find('body')
    if body:
        html_content = str(body)
    else:
        html_content = str(soup)
    
    # Convert to Markdown with heading preservation
    markdown = md(
        html_content,
        heading_style='ATX',  # Use # style headings
        strip=['a'],  # Remove links (we don't need them for outlines)
        escape_asterisks=False,
        escape_underscores=False,
    )
    
    return markdown


def _is_frontmatter(text: str) -> bool:
    """
    Heuristically detect if text is likely frontmatter (title page, copyright, etc.)
    
    Frontmatter typically:
    - Is short (< 500 chars)
    - Has no major headings (##, ###)
    - Contains copyright-related words
    """
    if len(text) > 1500:
        return False
    
    # Check for content indicators (any markdown heading level)
    has_headings = '# ' in text
    if has_headings:
        return False
    
    # Check for frontmatter indicators
    frontmatter_words = ['copyright', 'isbn', 'published by', 'all rights reserved',
                         'library of congress', 'first edition', 'printed in']
    text_lower = text.lower()
    
    if any(word in text_lower for word in frontmatter_words):
        return True
    
    # Very short content without headings is likely frontmatter
    if len(text.strip()) < 300:
        return True
    
    return False


def _is_skippable_section(text: str, filename: str = '') -> Optional[str]:
    """
    Check if content is a skippable section (preface, appendix, bibliography, etc.)

    Args:
        text: The markdown content
        filename: The EPUB item filename (for additional hints)

    Returns:
        The reason for skipping (e.g., "preface") or None if not skippable
    """
    import re

    text_lower = text.lower()
    filename_lower = filename.lower()

    # Use standard skip sections
    skip_terms = SKIP_SECTIONS.copy()
    
    # Check filename first, but skip 'index' term for filename checks
    # (many EPUBs use index_split_XXX.html for regular chapter files)
    for skip_term in skip_terms:
        if skip_term == 'index':
            continue  # Don't skip based on 'index' in filename
        if skip_term in filename_lower:
            return skip_term
    
    def _starts_with_skip_term(candidate: str, skip_term: str) -> bool:
        normalized_candidate = _normalize_for_matching(candidate).lower()
        normalized_skip_term = _normalize_for_matching(skip_term).lower()
        return (
            normalized_candidate == normalized_skip_term
            or normalized_candidate.startswith(f"{normalized_skip_term} ")
        )

    # Extract the first heading to check section type.
    # Only match skip terms at the start so body prose like
    # "my introduction to the ..." does not hide a real chapter.
    heading_match = re.search(r'^#+\s*(.+?)(?:\n|$)', text, re.MULTILINE)
    if heading_match:
        first_heading = heading_match.group(1).lower().strip()
        
        for skip_term in skip_terms:
            if _starts_with_skip_term(first_heading, skip_term):
                return skip_term
    
    # Also check the start of the body for section indicators.
    # Keep this anchored to the beginning to avoid false positives from
    # ordinary prose mentioning phrases like "introduction to the".
    first_chunk = text_lower[:200]
    for skip_term in skip_terms:
        if _starts_with_skip_term(first_chunk, skip_term):
            return skip_term
    
    return None


def _clean_markdown(text: str) -> str:
    """Clean up markdown output."""
    import re
    
    # Remove excessive newlines (more than 2 in a row)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Remove empty heading lines
    text = re.sub(r'^#+\s*$', '', text, flags=re.MULTILINE)
    
    # Normalize heading spacing (ensure blank line before headings)
    text = re.sub(r'([^\n])\n(#+\s)', r'\1\n\n\2', text)
    
    return text.strip()


def estimate_tokens(text: str) -> int:
    """
    More accurate token estimation for Claude.
    Based on empirical analysis of Claude tokenization patterns.
    """
    # More accurate estimation based on text characteristics
    char_count = len(text)
    word_count = len(text.split())
    
    # Claude tokenizer efficiency varies by text type. Opus 4.8's tokenizer can
    # count the same source text more densely than Sonnet 4.6, so keep this
    # deliberately conservative for chunk planning.
    
    # Use word count as secondary signal (avg 1.3 tokens per word)
    char_estimate = char_count / 3.4
    word_estimate = word_count * 1.4
    
    # Average the two estimates for better accuracy
    return int((char_estimate + word_estimate) / 2)


def chunk_markdown_by_chapters(markdown: str, max_tokens: int = 75000, toc: list[str] = None, toc_structured: list = None) -> list[str]:
    """
    Split markdown into chunks respecting chapter boundaries.

    Args:
        markdown: Full markdown text
        max_tokens: Maximum tokens per chunk
        toc: Optional flat list of chapter titles from TOC (used when markdown lacks headings)
        toc_structured: Optional structured TOC as list of (level, title) tuples
                        where level is 'part' or 'chapter'

    Returns:
        List of markdown chunks, each under max_tokens
    """
    import re

    # Check if markdown has headings
    has_headings = bool(re.search(r'^#{1,2}\s+', markdown, re.MULTILINE))

    # If no headings but we have a TOC, try to inject chapter markers
    if not has_headings and (toc or toc_structured):
        toc_for_injection = toc_structured if toc_structured else toc
        is_structured = toc_structured is not None
        entry_count = len(toc_for_injection) if toc_for_injection else 0

        log.info(f"No headings found in markdown. Attempting to inject {entry_count} chapter markers from TOC...")
        markdown_before = markdown
        markdown = _inject_chapter_headings(markdown, toc_for_injection, structured=is_structured)
        has_headings = bool(re.search(r'^#{1,2}\s+', markdown, re.MULTILINE))

        if has_headings:
            # Verify headings are well-distributed (not all clustered at the start)
            first_heading_pos = markdown.find('##')
            last_heading_pos = markdown.rfind('##')
            text_span = last_heading_pos - first_heading_pos
            spread_ratio = text_span / len(markdown) if len(markdown) > 0 else 0

            if spread_ratio < 0.3:  # Headings span less than 30% of text
                log.warning(f"Injected headings are clustered (spread: {spread_ratio:.1%}) - likely matched TOC instead of chapters. Falling back to simple chunking")
                markdown = markdown_before  # Revert injection
                has_headings = False
            else:
                log.info(f"Successfully injected chapter headings (spread: {spread_ratio:.1%})")
        else:
            log.warning(f"Could not inject chapter headings - falling back to simple chunking")

    # If still no headings, fall back to simple token-based chunking
    if not has_headings:
        log.warning("No chapter headings found - using simple token-based chunking")
        return _chunk_by_tokens(markdown, max_tokens)

    # Split by major headings (# or ##)
    # Use capturing group so headings are included in the split parts
    chapter_pattern = r'^(#{1,2}\s+.+)$'
    parts = re.split(chapter_pattern, markdown, flags=re.MULTILINE)

    chunks = []
    current_chunk = ""

    i = 0
    chapter_num = 0
    while i < len(parts):
        part = parts[i]

        # If this is a heading, combine with following content
        if re.match(chapter_pattern, part.strip(), re.MULTILINE):
            chapter_num += 1
            # Get the content after this heading
            content = ""
            if i + 1 < len(parts):
                content = parts[i + 1]

            chapter_text = f"{part}\n{content}".strip()
            chapter_tokens = estimate_tokens(chapter_text)
            current_tokens = estimate_tokens(current_chunk)
            combined_tokens = estimate_tokens(current_chunk + chapter_text)

            log.debug(f"Chapter {chapter_num}: {chapter_tokens:,} tokens, current chunk: {current_tokens:,}, combined: {combined_tokens:,}, max: {max_tokens:,}")

            # If current chunk + new chapter exceeds limit, start new chunk
            if current_chunk and combined_tokens > max_tokens:
                log.info(f"Starting new chunk (would exceed limit: {combined_tokens:,} > {max_tokens:,})")
                chunks.append(current_chunk.strip())
                current_chunk = chapter_text
            else:
                current_chunk += "\n\n" + chapter_text if current_chunk else chapter_text

            i += 2  # Skip the content part since we processed it
        else:
            # Non-heading content, add to current chunk
            if part.strip():
                current_chunk += "\n" + part if current_chunk else part
            i += 1

    # Add final chunk if any
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


def _inject_chapter_headings(markdown: str, toc, structured: bool = False) -> str:
    """
    Inject headings into markdown by finding TOC titles in the text.

    Args:
        markdown: Plain text markdown without headings
        toc: Either a flat list of chapter titles, or a structured list of
             (level, title) tuples where level is 'part' or 'chapter'
        structured: If True, toc is structured with levels; if False, flat list

    Returns:
        Markdown with headings injected:
        - Parts get ## headings
        - Chapters get ### headings (or ## if no parts)
    """
    import re

    # Normalize toc to structured format
    if structured:
        toc_entries = toc
    else:
        # Flat list - all entries are chapters
        toc_entries = [('chapter', title) for title in toc]

    # Check if we have any parts
    has_parts = any(level == 'part' for level, title in toc_entries)

    # Track positions where we'll inject headings
    injections = []  # List of (position, heading_text, level)

    # Normalize markdown for matching (remove quotes and other noise)
    normalized_markdown = _normalize_for_matching(markdown)

    for level, chapter_title in toc_entries:
        # Normalize the chapter title (remove quotes)
        normalized_title = _normalize_for_matching(chapter_title)

        # Generate variations with different numeral formats (e.g., "1" -> "One", "I")
        title_variations = _generate_numeral_variations(normalized_title)

        # Try multiple matching strategies to find ALL matches across all variations
        all_matches = []

        for title_var in title_variations:
            escaped_title = re.escape(title_var)

            # Strategy 1: Exact match with word boundaries
            pattern = re.compile(r'\b' + escaped_title + r'\b', re.IGNORECASE)
            matches = list(pattern.finditer(normalized_markdown))
            if matches:
                all_matches.extend(matches)
                break  # Found matches, no need to try more variations

            # Strategy 2: Match without leading word boundary (handles "TWOFamilies" case)
            pattern = re.compile(escaped_title + r'\b', re.IGNORECASE)
            matches = list(pattern.finditer(normalized_markdown))
            if matches:
                all_matches.extend(matches)
                break

            # Strategy 3: Fuzzy match - allow flexible whitespace between words
            words = title_var.split()
            if len(words) > 1:
                fuzzy_pattern = r'\s*'.join(re.escape(w) for w in words)
                pattern = re.compile(fuzzy_pattern, re.IGNORECASE)
                matches = list(pattern.finditer(normalized_markdown))
                if matches:
                    all_matches.extend(matches)
                    break

        # Strategy 4: For Part entries with subtitles (e.g., "Part I: Solon's Warning"),
        # fall back to matching just the "Part N" prefix. EPUBs often split Part number
        # and subtitle across separate lines with decorative elements in between.
        if not all_matches and level == 'part':
            part_prefix_match = re.match(r'^(Part\s+(?:\d+|[IVXLCDM]+))\b', normalized_title, re.IGNORECASE)
            if part_prefix_match:
                prefix = part_prefix_match.group(1)
                escaped_prefix = re.escape(prefix)
                pattern = re.compile(r'\b' + escaped_prefix + r'\b', re.IGNORECASE)
                matches = list(pattern.finditer(normalized_markdown))
                if matches:
                    all_matches.extend(matches)

        if not all_matches:
            continue

        # Score each match to find the best one (most likely to be a chapter heading)
        best_match = None
        best_score = -1

        for match in all_matches:
            score = 0

            # Check context before the match (use normalized_markdown)
            line_start = normalized_markdown.rfind('\n', 0, match.start()) + 1
            chars_from_line_start = match.start() - line_start
            before_context = normalized_markdown[max(0, line_start - 50):line_start]

            # Check context after the match
            after_context = normalized_markdown[match.end():min(len(normalized_markdown), match.end() + 50)]

            # Prefer matches at line start (chapter titles are on their own line)
            if chars_from_line_start < 5:
                score += 10

            # Prefer matches after image markers (common EPUB chapter pattern)
            if '![image]' in before_context or 'img_' in before_context:
                score += 8

            # Prefer matches followed by paragraph break
            if after_context.startswith('\n\n') or after_context.startswith('\n '):
                score += 5

            # Prefer matches followed by bold text (chapter opening)
            if re.match(r'\s*\n+\s*\*\*', after_context):
                score += 3

            # Penalize matches in the middle of sentences (followed by lowercase)
            if re.match(r'\s+[a-z]', after_context):
                score -= 5

            # Prefer matches preceded by just a chapter number or chapter heading text
            pre_line = normalized_markdown[line_start:match.start()].strip()
            if re.match(r'^(\d+|#.*CHAPTER.*)$', pre_line, re.IGNORECASE):
                score += 7

            if score > best_score:
                best_score = score
                best_match = match

        if best_match:
            line_start = normalized_markdown.rfind('\n', 0, best_match.start()) + 1
            injections.append((line_start, chapter_title, level))

    if not has_parts:
        chapter_titles = [title for level, title in toc_entries if level == "chapter"]
        if len(injections) < len(chapter_titles):
            generic_injected = _inject_generic_chapter_mappings(markdown, toc_entries)
            if generic_injected is not None:
                return generic_injected

    # Sort by position (reverse order so we can inject from end to start)
    injections.sort(key=lambda x: x[0], reverse=True)

    # Inject headings from end to start (so positions don't shift)
    for pos, title, level in injections:
        # Determine heading level based on entry type
        if level == 'part':
            heading = f"## {title}"
        elif has_parts:
            heading = f"### {title}"  # Chapters under parts
        else:
            heading = f"## {title}"   # Chapters without parts

        # Insert heading at the start of the line (into normalized markdown)
        normalized_markdown = normalized_markdown[:pos] + f"{heading}\n\n" + normalized_markdown[pos:]

    log.info(f"Injected {len(injections)}/{len(toc_entries)} chapter headings into markdown")

    return normalized_markdown


def _inject_generic_chapter_mappings(markdown: str, toc_entries: list[tuple[str, str]]) -> str | None:
    """
    Fallback for books whose source only labels chapters generically.

    Some PDFs contain headings like "Chapter One", "Chapter Two", etc. while the
    operator provides descriptive chapter titles in ``books/toc.txt``. In that
    case, title-based matching fails even though ordinal chapter boundaries are
    still present in the text. This fallback maps chapter N in the manual TOC to
    the Nth generic chapter marker found in the source and injects the
    descriptive heading there.

    Returns the injected markdown, or ``None`` if the fallback is not confident
    enough to apply.
    """
    import re

    chapter_titles = [title for level, title in toc_entries if level == "chapter"]
    if not chapter_titles:
        return None

    word_numbers = (
        "One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|Eleven|Twelve|"
        "Thirteen|Fourteen|Fifteen|Sixteen|Seventeen|Eighteen|Nineteen|Twenty"
    )
    generic_chapter_pattern = re.compile(
        rf"^(?:\*\*)?(?:#+\s+)?(?:Chapter|Ch\.?)\s+(?:\d+|[IVXLCDM]+|{word_numbers})\b(?:\s*[:.\-–—]?\s*.*)?(?:\*\*)?\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    matches = list(generic_chapter_pattern.finditer(markdown))

    if len(matches) < len(chapter_titles):
        matches = _find_sequential_generic_chapter_matches(markdown, len(chapter_titles))

    if len(matches) < len(chapter_titles):
        log.info(
            "Generic chapter fallback skipped: found "
            f"{len(matches)} generic markers for {len(chapter_titles)} manual TOC chapters"
        )
        return None

    injected_markdown = markdown
    for match, title in zip(reversed(matches[: len(chapter_titles)]), reversed(chapter_titles)):
        line_start = injected_markdown.rfind("\n", 0, match.start()) + 1
        injected_markdown = (
            injected_markdown[:line_start]
            + f"## {title}\n\n"
            + injected_markdown[line_start:]
        )

    log.info(
        "Injected generic chapter mapping for "
        f"{len(chapter_titles)} manual TOC chapters using ordinal source headings"
    )
    return injected_markdown


def _find_sequential_generic_chapter_matches(markdown: str, chapter_count: int) -> list:
    """
    Find chapter markers by ordinal sequence rather than exact line shape.

    This handles PDFs where extraction merges the chapter marker into nearby text,
    e.g. "Chapter One I returned..." instead of a clean standalone heading line.
    """
    import re

    word_numbers = [
        "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
        "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
        "eighteen", "nineteen", "twenty",
    ]
    roman_numbers = [
        "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
        "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX",
    ]

    matches = []
    search_start = 0
    for idx in range(chapter_count):
        number = idx + 1
        variants = [str(number)]
        if idx < len(word_numbers):
            variants.append(word_numbers[idx])
        if idx < len(roman_numbers):
            variants.append(roman_numbers[idx])

        pattern = re.compile(
            r"\b(?:Chapter|Ch\.?)\s+(?:" + "|".join(re.escape(v) for v in variants) + r")\b",
            re.IGNORECASE,
        )
        match = pattern.search(markdown, search_start)
        if not match:
            break
        matches.append(match)
        search_start = match.end()

    return matches


def parse_manual_toc(file_path: str) -> list[tuple[str, str]]:
    """
    Parse a manual TOC file with part/chapter hierarchy.

    Supports multiple formats:
    1. Indented format:
        Part One: The World of Tradition
            The Beginning
            Regality

    2. Flat format with "Part" markers:
        Ghosts at the Beginning
        Ancient Mesopotamia
        Part 1: An Assyrian Prince
        The Delicate Art

    3. Flat format with chapter numbers:
        1. Introduction
        2. The Beginning
        Part I: First Section
        3. Continuing On

    Detection logic:
    - Lines starting with "Part" followed by number/roman numeral = Parts
    - Lines with leading whitespace = Chapters (indented format)
    - All other lines = Chapters

    Args:
        file_path: Path to the manual TOC text file

    Returns:
        List of (level, title) tuples where level is 'part' or 'chapter'
    """
    import re

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    entries = []

    # Pattern to detect "Part" entries (e.g., "Part 1:", "Part One:", "Part I:", etc.)
    # Matches: "Part" + (number/roman/word) + optional colon/punctuation
    part_pattern = re.compile(
        r'^Part\s+(?:\d+|[IVXLCDM]+|One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten)\s*[:\-–—]?',
        re.IGNORECASE
    )

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Check if line is indented (traditional hierarchical format)
        is_indented = line[0].isspace()

        if is_indented:
            # Indented lines are always chapters
            entries.append(('chapter', stripped))
        elif part_pattern.match(stripped):
            # Lines matching "Part X:" pattern are parts
            entries.append(('part', stripped))
        else:
            # All other lines (including those with leading numbers like "1. Chapter")
            # are chapters
            entries.append(('chapter', stripped))

    return entries


def get_flat_toc(toc_entries: list[tuple[str, str]]) -> list[str]:
    """
    Convert structured TOC entries to flat list for matching.

    Args:
        toc_entries: List of (level, title) tuples

    Returns:
        Flat list of all titles (parts and chapters)
    """
    return [title for level, title in toc_entries]


def _normalize_for_matching(text: str) -> str:
    """
    Normalize text for matching by removing quote characters and other noise.

    Removes all quote variations (straight, curly, single, double) to make
    matching more robust regardless of typography choices.
    Also normalizes spacing around colons and other punctuation.
    """
    import re
    import unicodedata

    # Canonicalize Unicode so ligatures/compat glyphs match plain text.
    # Example: "Seﬁrot" (U+FB01) -> "Sefirot"
    text = unicodedata.normalize("NFKC", text)

    # Normalize odd whitespace from PDF extraction/copy-paste.
    text = (
        text
        .replace('\u00a0', ' ')   # NO-BREAK SPACE
        .replace('\u202f', ' ')   # NARROW NO-BREAK SPACE
        .replace('\u2009', ' ')   # THIN SPACE
        .replace('\u200a', ' ')   # HAIR SPACE
        .replace('\u200b', '')    # ZERO WIDTH SPACE
        .replace('\u200c', '')    # ZERO WIDTH NON-JOINER
        .replace('\u200d', '')    # ZERO WIDTH JOINER
        .replace('\ufeff', '')    # ZERO WIDTH NO-BREAK SPACE / BOM
        .replace('\u00ad', '')    # SOFT HYPHEN
    )

    # Remove all quote characters (both straight and curly) using Unicode escapes
    text = text.replace('"', '')  # Straight double quote
    text = text.replace('\u201c', '')  # Left double quote "
    text = text.replace('\u201d', '')  # Right double quote "
    text = text.replace("'", '')  # Straight single quote/apostrophe
    text = text.replace('\u2018', '')  # Left single quote '
    text = text.replace('\u2019', '')  # Right single quote/apostrophe '

    # Remove markdown bold/italic markers (from <i>, <b>, <em>, <strong> in EPUB headings)
    text = text.replace('*', '').replace('_', '')

    # Normalize hyphens and dashes before punctuation folding.
    text = text.replace('\\-', '-').replace('\\', '')
    text = text.replace('\u2013', '-')  # En-dash –
    text = text.replace('\u2014', '-')  # Em-dash —

    # Fold punctuation differences into spaces so manual TOCs can match
    # headings that drop separators such as ":" and "—".
    text = re.sub(r'[^\w\s]', ' ', text)

    # Collapse internal whitespace runs for robust matching.
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def _generate_numeral_variations(title: str) -> list[str]:
    """
    Generate variations of a title with different numeral formats.

    For example, "Ghost Magic 1: Words" generates:
    - "Ghost Magic 1: Words" (original)
    - "Ghost Magic One: Words" (spelled out)
    - "Ghost Magic I: Words" (Roman numeral)

    Args:
        title: Chapter title that may contain numerals

    Returns:
        List of title variations with different numeral formats
    """
    import re

    # Mappings for common numerals
    arabic_to_word = {
        '1': 'One', '2': 'Two', '3': 'Three', '4': 'Four', '5': 'Five',
        '6': 'Six', '7': 'Seven', '8': 'Eight', '9': 'Nine', '10': 'Ten',
        '11': 'Eleven', '12': 'Twelve', '13': 'Thirteen', '14': 'Fourteen',
        '15': 'Fifteen', '16': 'Sixteen', '17': 'Seventeen', '18': 'Eighteen',
        '19': 'Nineteen', '20': 'Twenty'
    }

    arabic_to_roman = {
        '1': 'I', '2': 'II', '3': 'III', '4': 'IV', '5': 'V',
        '6': 'VI', '7': 'VII', '8': 'VIII', '9': 'IX', '10': 'X',
        '11': 'XI', '12': 'XII', '13': 'XIII', '14': 'XIV', '15': 'XV',
        '16': 'XVI', '17': 'XVII', '18': 'XVIII', '19': 'XIX', '20': 'XX'
    }

    variations = [title]  # Include original

    # Find all standalone numerals (not part of larger numbers)
    # Pattern: numeral surrounded by non-digit characters or at boundaries
    numeral_pattern = re.compile(r'\b(\d+)\b')

    for match in numeral_pattern.finditer(title):
        numeral = match.group(1)

        # Generate word variation
        if numeral in arabic_to_word:
            word_version = title[:match.start()] + arabic_to_word[numeral] + title[match.end():]
            if word_version not in variations:
                variations.append(word_version)

        # Generate Roman numeral variation
        if numeral in arabic_to_roman:
            roman_version = title[:match.start()] + arabic_to_roman[numeral] + title[match.end():]
            if roman_version not in variations:
                variations.append(roman_version)

    return variations


def test_toc_matches(markdown: str, toc: list[str]) -> dict:
    """
    Test which TOC entries can be found in the markdown text.

    Used for pre-flight validation before processing to catch
    TOC extraction issues early.

    Args:
        markdown: Extracted markdown text from EPUB
        toc: List of chapter titles from TOC

    Returns:
        Dict with:
        - matched: List of (title, context) tuples for successful matches
        - unmatched: List of titles that weren't found
        - match_rate: Float 0-1 indicating success rate
    """
    import re

    matched = []
    unmatched = []

    # Normalize markdown for matching (remove quotes and other noise)
    normalized_markdown = _normalize_for_matching(markdown)

    for chapter_title in toc:
        # Normalize the chapter title (remove quotes)
        normalized_title = _normalize_for_matching(chapter_title)

        # Generate variations with different numeral formats (e.g., "1" -> "One", "I")
        title_variations = _generate_numeral_variations(normalized_title)

        # Try multiple matching strategies for each variation
        found = False
        match = None

        for title_var in title_variations:
            # Strategy 1: Exact match with word boundaries
            escaped_title = re.escape(title_var)
            pattern = re.compile(r'\b' + escaped_title + r'\b', re.IGNORECASE)
            match = pattern.search(normalized_markdown)

            if not match:
                # Strategy 2: Match without leading word boundary (handles "TWOFamilies" case)
                pattern = re.compile(escaped_title + r'\b', re.IGNORECASE)
                match = pattern.search(normalized_markdown)

            if not match:
                # Strategy 3: Fuzzy match - allow extra characters between words
                # e.g., "Families Rigged to Fail" matches "Families  Rigged to Fail"
                words = title_var.split()
                if len(words) > 1:
                    fuzzy_pattern = r'\s*'.join(re.escape(w) for w in words)
                    pattern = re.compile(fuzzy_pattern, re.IGNORECASE)
                    match = pattern.search(normalized_markdown)

            if match:
                found = True
                break  # Found a match, no need to try more variations

        # Strategy 4: For Part entries (e.g., "Part I: Solon's Warning"),
        # fall back to matching just the "Part N" prefix
        if not match:
            part_prefix_match = re.match(r'^(Part\s+(?:\d+|[IVXLCDM]+))\b', normalized_title, re.IGNORECASE)
            if part_prefix_match:
                prefix = part_prefix_match.group(1)
                escaped_prefix = re.escape(prefix)
                pattern = re.compile(r'\b' + escaped_prefix + r'\b', re.IGNORECASE)
                match = pattern.search(normalized_markdown)

        if match:
            # Get some context around the match
            start = max(0, match.start() - 20)
            end = min(len(normalized_markdown), match.end() + 30)
            context = normalized_markdown[start:end].replace('\n', ' ').strip()
            matched.append((chapter_title, context))
        else:
            unmatched.append(chapter_title)

    total = len(toc)
    match_rate = len(matched) / total if total > 0 else 0.0

    return {
        'matched': matched,
        'unmatched': unmatched,
        'match_rate': match_rate,
        'total': total
    }


def _chunk_by_tokens(text: str, max_tokens: int) -> list[str]:
    """
    Simple fallback: split text into roughly equal chunks by token count.

    Tries to break at paragraph boundaries when possible, then merges an
    undersized trailing chunk back into its predecessor when the overage is small.
    """
    total_tokens = estimate_tokens(text)
    num_chunks = max(1, (total_tokens + max_tokens - 1) // max_tokens)

    log.info(f"Splitting {total_tokens:,} tokens into {num_chunks} chunks of ~{max_tokens:,} tokens each")

    # Split by paragraphs
    paragraphs = text.split('\n\n')

    chunks = []
    current_chunk = ""
    target_tokens = max_tokens

    for para in paragraphs:
        para_with_spacing = para + "\n\n"
        chunk_tokens = estimate_tokens(current_chunk + para_with_spacing)

        if chunk_tokens > target_tokens and current_chunk:
            # Start new chunk
            chunks.append(current_chunk.strip())
            current_chunk = para_with_spacing
        else:
            current_chunk += para_with_spacing

    # Add final chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return _rebalance_small_tail_chunk(chunks, max_tokens)


def _rebalance_small_tail_chunk(chunks: list[str], max_tokens: int) -> list[str]:
    """Avoid tiny final chunks when a small overage would keep context together."""
    if len(chunks) < 2:
        return chunks

    tail_tokens = estimate_tokens(chunks[-1])
    if tail_tokens >= max_tokens * 0.35:
        return chunks

    merged_chunk = f"{chunks[-2].rstrip()}\n\n{chunks[-1].lstrip()}"
    merged_tokens = estimate_tokens(merged_chunk)
    if merged_tokens > int(max_tokens * 1.15):
        return chunks

    log.info(
        "Rebalancing undersized trailing chunk (%s tokens) into previous chunk (%s tokens)",
        tail_tokens,
        estimate_tokens(chunks[-2]),
    )
    return chunks[:-2] + [merged_chunk]
