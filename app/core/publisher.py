"""
Publisher module: converts notes/*.md to Hugo blog posts and builds the site.
"""

import json
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from app.config import NOTES_DIR
from app.core.glyph_manager import get_random_glyph
from app.logger import log

# Paths relative to project root
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Load environment variables from app/.env
load_dotenv(PROJECT_ROOT / "app" / ".env")
BLOG_DIR = PROJECT_ROOT / "blog"
CONTENT_DIR = BLOG_DIR / "content"
PUBLIC_DIR = BLOG_DIR / "public"
DATA_DIR = BLOG_DIR / "data"
INDEX_DIR = PROJECT_ROOT / "index"
VECTORS_DB = INDEX_DIR / "vectors.db"


def iter_publishable_notes(notes_path: Path):
    """Yield notes that should become real published books."""
    for note_path in sorted(notes_path.glob("*.md")):
        if note_path.stem.endswith(".test"):
            continue
        yield note_path


def update_stats():
    """Count books and concepts, write to blog/data/stats.json for Hugo."""
    notes_path = Path(NOTES_DIR)
    book_count = len(list(iter_publishable_notes(notes_path)))

    concept_count = 0
    concepts_file = INDEX_DIR / "_concepts.json"
    if concepts_file.exists():
        with open(concepts_file) as f:
            data = json.load(f)
            concepts = data.get("concepts", data) if isinstance(data, dict) else data
            concept_count = len(concepts)

    stats = {"books": book_count, "concepts": concept_count}
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_DIR / "stats.json", "w") as f:
        json.dump(stats, f)

    log.info(f"Stats: {book_count} books, {concept_count:,} concepts")


def report_semantic_backlog(max_books: int = 10) -> bool:
    """
    Report claim-vector backlog for indexed books.

    Backlog = indexed claims that do not yet have matching rows in vectors.db.
    This is expected after core ingest and is resolved by reconcile/apply-all.
    """
    index_counts = {}
    for path in sorted(INDEX_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
            index_counts[path.stem] = len(payload.get("claims", []))
        except Exception as e:
            log.warning(f"Could not read index file for backlog report ({path.name}): {e}")

    if not index_counts:
        log.info("Semantic backlog: no indexed books found.")
        return True

    if not VECTORS_DB.exists():
        total_claims = sum(index_counts.values())
        log.warning(
            f"Semantic backlog: vectors DB not found; {len(index_counts)} books "
            f"({total_claims:,} claims) are pending vector sync."
        )
        log.info("  Run: python3 scripts/reconcile_vectors.py --apply-all")
        return True

    db_counts = {}
    try:
        conn = sqlite3.connect(VECTORS_DB)
        conn.row_factory = sqlite3.Row
        has_claims_table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='claims'"
        ).fetchone()
        if has_claims_table:
            db_counts = {
                row["book_name"]: int(row["count"])
                for row in conn.execute(
                    "SELECT book_name, COUNT(*) AS count FROM claims GROUP BY book_name"
                ).fetchall()
            }
        conn.close()
    except Exception as e:
        log.warning(f"Semantic backlog: could not inspect vectors DB ({e})")
        return True

    backlog = []
    missing_claims_total = 0
    for book, index_count in index_counts.items():
        db_count = db_counts.get(book, 0)
        if db_count < index_count:
            missing = index_count - db_count
            missing_claims_total += missing
            backlog.append((book, missing, index_count, db_count))

    backlog.sort(key=lambda item: item[1], reverse=True)

    if not backlog:
        log.info("Semantic backlog: up to date (all indexed claims have vectors).")
        return True

    log.warning(
        f"Semantic backlog: {len(backlog)} books pending vectors "
        f"({missing_claims_total:,} missing claim rows)."
    )
    for book, missing, index_count, db_count in backlog[:max_books]:
        log.info(
            f"  - {book}: missing {missing:,} (index={index_count:,}, vectors={db_count:,})"
        )
    if len(backlog) > max_books:
        log.info(f"  ... and {len(backlog) - max_books} more")
    log.info("  Run: python3 scripts/reconcile_vectors.py --apply-all")
    return True


def slugify(title: str) -> str:
    """Convert a title to a URL-friendly slug."""
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug


def extract_title(filepath: Path) -> str:
    """Extract title from the first heading in the file content, fallback to filename."""
    try:
        content = filepath.read_text(encoding="utf-8")
        lines = content.split("\n")
        for line in lines:
            if line.startswith("# "):
                return line[2:].strip()
    except Exception:
        pass

    # Fallback to filename if no heading found
    return filepath.stem.replace("-", " ").replace("_", " ").title()


def get_file_date(filepath: Path) -> str:
    """Get file modification date in ISO format."""
    mtime = os.path.getmtime(filepath)
    return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")


def extract_tags(note_path: Path, content: str) -> list[str]:
    """
    Extract Categories from the metadata section for use as Hugo tags.
    Categories are used for blog navigation/filtering.

    Note: Keywords are separate and displayed in the post description.

    Example metadata format:
    ## Metadata
    - Categories: mathematics, social science  -> becomes Hugo tags
    - Topics: topic1, topic2                    -> displayed in description
    """
    tags = []

    # Look for Categories in the metadata section (these become Hugo tags)
    categories_match = re.search(
        r"- Categories:\s*(.+?)(?:\n|$)", content, re.IGNORECASE | re.MULTILINE
    )
    if categories_match:
        categories_str = categories_match.group(1).strip()
        if categories_str:
            tags = [tag.strip() for tag in categories_str.split(",") if tag.strip()]

    return tags


def extract_collections(content: str) -> list[str]:
    """
    Extract Collections from the metadata section for use as Hugo collections taxonomy.
    Collections are curated groupings shown in the sidebar.

    Example metadata format:
    ## Metadata
    - Collections: Christianity, Nick Land
    """
    match = re.search(
        r"- Collections:\s*(.+?)(?:\n|$)", content, re.IGNORECASE | re.MULTILINE
    )
    if match:
        raw = match.group(1).strip()
        if raw:
            return [c.strip() for c in raw.split(",") if c.strip()]
    return []


def extract_topics(content: str) -> Optional[str]:
    """
    Extract Topics from the metadata section for display in blog post.
    Topics are displayed as-is in the description section.
    Also supports legacy 'Keywords' field for backward compatibility.
    """
    # Try Topics first
    topics_match = re.search(
        r"- Topics:\s*(.+?)(?:\n|$)", content, re.IGNORECASE | re.MULTILINE
    )
    if topics_match:
        return topics_match.group(1).strip()
    # Fall back to Keywords for existing notes
    keywords_match = re.search(
        r"- Keywords:\s*(.+?)(?:\n|$)", content, re.IGNORECASE | re.MULTILINE
    )
    if keywords_match:
        return keywords_match.group(1).strip()
    return None


def extract_author(content: str) -> Optional[str]:
    """
    Extract Author from the metadata section.
    """
    # Match Author field - capture everything on that line after the colon
    author_match = re.search(
        r"^- Author:\s*([^\n]+)", content, re.IGNORECASE | re.MULTILINE
    )
    if author_match:
        author = author_match.group(1).strip()
        if author:  # Only return if not empty
            return author
    return None


def extract_year(content: str) -> Optional[str]:
    """
    Extract Year from the metadata section.
    """
    year_match = re.search(r"- Year:\s*(\d{4})", content, re.IGNORECASE | re.MULTILINE)
    if year_match:
        return year_match.group(1).strip()
    return None


def extract_thesis(content: str) -> Optional[str]:
    """
    Extract thesis from the metadata section if present.
    """
    thesis_match = re.search(r"- Thesis:\s*(.+)", content, re.IGNORECASE | re.MULTILINE)
    if thesis_match:
        return thesis_match.group(1).strip()
    return None


def insert_chapter_glyphs(content: str, categories: list[str]) -> str:
    """Insert decorative glyph dividers between chapters in markdown content."""
    if not categories:
        return content

    lines = content.split("\n")

    # Find all content heading indices (## or ###), skip ## Metadata and first heading
    heading_indices = []
    found_first = False
    for i, line in enumerate(lines):
        if not (line.startswith("## ") or line.startswith("### ")):
            continue
        if line.startswith("## Metadata"):
            continue
        if not found_first:
            found_first = True
            continue
        heading_indices.append(i)

    heading_ordinals = {idx: ordinal for ordinal, idx in enumerate(heading_indices)}
    normalized_categories = sorted(categories)

    # Skip headings that have no real content before the next heading
    # (e.g. Part headers that are just section titles)
    def has_content_before(idx: int) -> bool:
        """Check if there's meaningful content between previous heading and this one."""
        for j in range(idx - 1, -1, -1):
            line = lines[j].strip()
            if line.startswith("## ") or line.startswith("### "):
                return False  # Hit another heading with no content between
            if line:  # Found non-empty, non-heading line
                return True
        return False

    # Insert glyphs in reverse so indices stay valid
    for idx in reversed(heading_indices):
        if not has_content_before(idx):
            continue
        seed = "\n".join([*normalized_categories, str(heading_ordinals[idx]), lines[idx].strip()])
        glyph_url = get_random_glyph(categories, seed=seed)
        if glyph_url:
            glyph_html = (
                '<div class="chapter-glyph">'
                f'<img src="{glyph_url}" alt="" role="presentation" loading="lazy">'
                "</div>"
            )
            lines.insert(idx, "")
            lines.insert(idx, glyph_html)
            lines.insert(idx, "")

    return "\n".join(lines)


def _make_short_author(author: str) -> str:
    """Extract last name(s) from author string for compact display.

    Examples:
        'Nassim Nicholas Taleb' -> 'Taleb'
        'Byrne Hobart and Tobias Huber' -> 'Hobart & Huber'
        'Thomas Cleary (translator)' -> 'Cleary'
    """
    # Strip parenthetical qualifiers like (translator)
    clean = re.sub(r"\s*\(.*?\)", "", author).strip()
    if " and " in clean:
        authors = [a.strip() for a in clean.split(" and ")]
        last_names = [a.split()[-1] for a in authors if a.split()]
        return " & ".join(last_names)
    parts = clean.split()
    return parts[-1] if parts else author


def _make_sort_title(title: str) -> str:
    """Strip leading articles (The, A, An) for alphabetical sorting."""
    for article in ("The ", "A ", "An "):
        if title.startswith(article):
            return title[len(article):]
    return title


def add_frontmatter(
    content: str,
    title: str,
    date: str,
    slug: str,
    tags: list[str] = None,
    collections: list[str] = None,
    thesis: Optional[str] = None,
    topics: Optional[str] = None,
    author: Optional[str] = None,
    year: Optional[str] = None,
    date_added: Optional[str] = None,
) -> str:
    """Add Hugo frontmatter to markdown content."""
    if tags is None:
        tags = []
    if collections is None:
        collections = []

    # Format tags for YAML frontmatter
    tags_yaml = "[]"
    if tags:
        tags_str = ", ".join([f'"{tag}"' for tag in tags])
        tags_yaml = f"[{tags_str}]"

    # Format collections for YAML frontmatter
    collections_yaml = "[]"
    if collections:
        collections_str = ", ".join([f'"{c}"' for c in collections])
        collections_yaml = f"[{collections_str}]"

    # Build frontmatter
    sort_title = _make_sort_title(title)
    frontmatter_lines = [
        "---",
        f'title: "{title}"',
        f'sortTitle: "{sort_title}"',
        f"date: {date}",
        f'slug: "{slug}"',
        "draft: false",
    ]

    # Add dateAdded (for tracking when book was first added)
    if date_added:
        frontmatter_lines.append(f"dateAdded: {date_added}")

    # Add thesis as description if available
    if thesis:
        # Escape quotes in thesis for YAML
        thesis_escaped = thesis.replace('"', '\\"')
        frontmatter_lines.append(f'description: "{thesis_escaped}"')

    # Add topics if available (use bookKeywords to avoid Hugo's default array handling)
    if topics:
        topics_escaped = topics.replace('"', '\\"')
        frontmatter_lines.append(f'bookKeywords: "{topics_escaped}"')

    # Add author if available
    if author:
        author_escaped = author.replace('"', '\\"')
        frontmatter_lines.append(f'author: "{author_escaped}"')
        short_author = _make_short_author(author)
        frontmatter_lines.append(f'shortAuthor: "{short_author}"')

    # Add year if available
    if year:
        frontmatter_lines.append(f'year: "{year}"')

    # Add tags and collections
    frontmatter_lines.append(f"tags: {tags_yaml}")
    if collections:
        frontmatter_lines.append(f"collections: {collections_yaml}")
    frontmatter_lines.append("---")
    frontmatter = "\n".join(frontmatter_lines) + "\n\n"

    # Remove existing frontmatter if present
    if content.startswith("---"):
        # Find the closing ---
        end = content.find("---", 3)
        if end != -1:
            content = content[end + 3 :].strip()

    # Remove the metadata section if it exists (we've extracted what we need)
    # Look for "## Metadata" section and remove it (stop at any header level: #, ##, ###, etc.)
    metadata_pattern = r"## Metadata.*?(?=\n#+ |\Z)"
    content = re.sub(metadata_pattern, "", content, flags=re.DOTALL)

    # Remove the title header if it's just the book name (we have it in frontmatter)
    # But keep it if it's different or if there's no frontmatter title
    lines = content.split("\n", 1)
    if lines[0].startswith("# "):
        # Check if the title matches what we extracted
        header_title = lines[0][2:].strip()
        if header_title.lower() == title.lower():
            # Remove the redundant title
            content = lines[1] if len(lines) > 1 else ""

    return frontmatter + content


def extract_date_added(post_path: Path) -> Optional[str]:
    """Extract dateAdded from existing post frontmatter, falling back to date."""
    if not post_path.exists():
        return None
    try:
        content = post_path.read_text(encoding="utf-8")
        # First try to get dateAdded
        match = re.search(r"^dateAdded:\s*(.+?)$", content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        # Fall back to existing date field for legacy posts
        match = re.search(r"^date:\s*(.+?)$", content, re.MULTILINE)
        if match:
            return match.group(1).strip()
    except Exception:
        pass
    return None


def compute_related_books(min_shared: int = 5, min_jaccard: float = 0.01, top_k: int = 3) -> dict:
    """
    Compute related books based on shared concepts using Jaccard similarity.

    Args:
        min_shared: Minimum shared concepts to consider books related
        min_jaccard: Minimum Jaccard similarity score (filters out generic overlaps)
        top_k: Maximum number of related books per book

    Returns:
        Dict mapping book slugs to list of related books with metadata
    """
    # Load all book index files and extract concepts
    book_data = {}

    for json_file in INDEX_DIR.glob("*.json"):
        if json_file.name.startswith("_"):
            continue
        try:
            with open(json_file) as f:
                data = json.load(f)
                book_slug = json_file.stem
                book_info = data.get("book", {})

                # Collect all concepts from claims
                concepts = set()
                for claim in data.get("claims", []):
                    concepts.update(claim.get("concepts", []))

                book_data[book_slug] = {
                    "title": book_info.get("title", book_slug),
                    "author": book_info.get("author", ""),
                    "concepts": concepts
                }
        except Exception as e:
            log.warning(f"Could not load {json_file.name}: {e}")

    if len(book_data) < 2:
        log.warning("Not enough books for relatedness computation")
        return {}

    # Compute pairwise Jaccard similarity
    books = list(book_data.keys())
    similarities = {}  # {(book1, book2): {"shared": count, "jaccard": score}}

    for i, book1 in enumerate(books):
        for book2 in books[i+1:]:
            concepts1 = book_data[book1]["concepts"]
            concepts2 = book_data[book2]["concepts"]
            shared = concepts1 & concepts2

            if len(shared) >= min_shared:
                union = concepts1 | concepts2
                jaccard = len(shared) / len(union) if union else 0
                # Require both minimum shared count AND minimum Jaccard score
                if jaccard >= min_jaccard:
                    similarities[(book1, book2)] = {
                        "shared_count": len(shared),
                        "jaccard": jaccard
                    }

    # For each book, find its top-k related books
    related = {}

    for book_slug in books:
        # Find all pairs involving this book
        book_pairs = []
        for (b1, b2), sim in similarities.items():
            if b1 == book_slug:
                book_pairs.append((b2, sim))
            elif b2 == book_slug:
                book_pairs.append((b1, sim))

        # Sort by shared count (descending), then by Jaccard
        book_pairs.sort(key=lambda x: (x[1]["shared_count"], x[1]["jaccard"]), reverse=True)

        # Take top-k
        top_related = []
        for other_slug, sim in book_pairs[:top_k]:
            top_related.append({
                "slug": slugify(other_slug),  # Slugify to match Hugo content files
                "title": book_data[other_slug]["title"],
                "shared_count": sim["shared_count"]
            })

        if top_related:
            # Use slugified key to match Hugo's .File.BaseFileName
            related[slugify(book_slug)] = top_related

    return related


def write_related_books_data(related: dict) -> bool:
    """Write related books data to Hugo data file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_DIR / "related.json"

    try:
        with open(output_path, "w") as f:
            json.dump(related, f, indent=2)
        log.info(f"Wrote related books data: {len(related)} books with relations")
        return True
    except Exception as e:
        log.error(f"Failed to write related books data: {e}")
        return False


def convert_note_to_post(note_path: Path) -> Optional[Path]:
    """Convert a single note to a Hugo post."""
    # Read the note
    try:
        content = note_path.read_text(encoding="utf-8")
    except Exception as e:
        log.error(f"Failed to read {note_path}: {e}")
        return None

    # Skip empty files
    if not content.strip():
        log.debug(f"Skipping empty file: {note_path.name}")
        return None

    # Extract metadata
    title = extract_title(note_path)
    date = get_file_date(note_path)
    slug = slugify(note_path.stem)  # Use filename for slug, not title
    tags = extract_tags(note_path, content)
    collections = extract_collections(content)
    thesis = extract_thesis(content)
    topics = extract_topics(content)
    author = extract_author(content)
    year = extract_year(content)

    # Check for existing dateAdded, or use current date for new posts
    books_dir = CONTENT_DIR / "books"
    post_path = books_dir / f"{slug}.md"
    date_added = extract_date_added(post_path)
    if not date_added:
        date_added = date  # Use current date for new posts

    # Content is already normalized by exporter during summarization
    # Manual edits in notes/ should be preserved

    # Insert glyph dividers between chapters
    if tags:
        content = insert_chapter_glyphs(content, tags)

    # Add frontmatter
    post_content = add_frontmatter(
        content, title, date, slug, tags, collections, thesis, topics, author, year, date_added
    )

    # Write to content/books directory for proper URL structure
    books_dir = CONTENT_DIR / "books"
    books_dir.mkdir(parents=True, exist_ok=True)
    post_path = books_dir / f"{slug}.md"
    try:
        post_path.write_text(post_content, encoding="utf-8")
        log.info(f"Converted: {note_path.name} -> {post_path.name}")
        return post_path
    except Exception as e:
        log.error(f"Failed to write {post_path}: {e}")
        return None


def sync_notes_to_posts() -> list[Path]:
    """Sync all notes to Hugo posts, only converting changed files."""
    # Ensure content directory exists
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    books_dir = CONTENT_DIR / "books"
    books_dir.mkdir(parents=True, exist_ok=True)

    # Convert notes (only if changed)
    converted = []
    skipped = 0
    deleted = 0
    notes_path = Path(NOTES_DIR)

    if not notes_path.exists():
        log.error(f"Notes directory not found: {notes_path}")
        return converted

    # Get slugified versions of all note filenames for comparison
    current_note_slugs = {slugify(note_path.stem) for note_path in iter_publishable_notes(notes_path)}

    # Remove blog posts that no longer have corresponding notes
    for post_path in books_dir.glob("*.md"):
        post_slug = post_path.stem

        # Compare slugs directly (handles punctuation differences)
        if post_slug not in current_note_slugs:
            try:
                post_path.unlink()
                log.info(f"Deleted orphaned post: {post_path.name}")
                deleted += 1
            except Exception as e:
                log.error(f"Failed to delete orphaned post {post_path.name}: {e}")

    if deleted > 0:
        log.info(f"Deleted {deleted} orphaned blog posts")

    for note_path in iter_publishable_notes(notes_path):
        # Determine the target post path
        title = extract_title(note_path)
        slug = slugify(note_path.stem)  # Use filename for slug, not title
        post_path = books_dir / f"{slug}.md"

        # Check if post exists and is newer than note
        if post_path.exists():
            note_mtime = note_path.stat().st_mtime
            post_mtime = post_path.stat().st_mtime
            if post_mtime >= note_mtime:
                # Also reconvert if post is missing glyphs (e.g. first run after feature added)
                post_text = post_path.read_text(encoding="utf-8")
                has_tags = "tags:" in post_text and 'tags: []' not in post_text
                if has_tags and "chapter-glyph" not in post_text:
                    pass  # Fall through to reconvert
                else:
                    skipped += 1
                    continue

        # Convert the note
        result_path = convert_note_to_post(note_path)
        if result_path:
            converted.append(result_path)

    log.info(
        f"Sync complete: {len(converted)} converted, {skipped} skipped, {deleted} deleted"
    )

    return converted
