#!/usr/bin/env python3
"""
Add claim anchor IDs to existing markdown notes.

Iterates through bullet points in each note and adds sequential anchor IDs
matching the pattern used in the JSON index (book-slug-001, book-slug-002, etc.)
"""

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
NOTES_DIR = PROJECT_ROOT / "notes"
INDEX_DIR = PROJECT_ROOT / "index"


def slugify(title: str) -> str:
    """Convert a title to a URL-friendly slug."""
    slug = title.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    return slug


def add_anchors_to_note(note_path: Path) -> tuple[bool, int]:
    """
    Add anchor IDs to claims in a note file.

    Returns (modified, claim_count)
    """
    with open(note_path) as f:
        content = f.read()

    # Check if already has anchors
    if '<span id="' in content:
        return False, 0

    # Use the note filename for the slug (matches JSON index naming)
    book_slug = slugify(note_path.stem)

    # Find all bullet points that are claims (bold text pattern)
    # Pattern: * **Title**: Description or *   **Title**: Description
    # Also handles: * **Title** (no colon)
    claim_pattern = r'^(\*\s+)\*\*([^*]+)\*\*(.*)$'

    lines = content.split('\n')
    new_lines = []
    claim_counter = 1

    for line in lines:
        match = re.match(claim_pattern, line)
        if match:
            bullet_prefix, claim_title, rest_of_line = match.groups()
            claim_id = f"{book_slug}-{claim_counter:03d}"
            # Insert anchor span after the bullet and before bold
            new_line = f'{bullet_prefix}<span id="{claim_id}"></span>**{claim_title}**{rest_of_line}'
            new_lines.append(new_line)
            claim_counter += 1
        else:
            new_lines.append(line)

    if claim_counter > 1:
        with open(note_path, 'w') as f:
            f.write('\n'.join(new_lines))
        return True, claim_counter - 1

    return False, 0


def main():
    print("Adding claim anchor IDs to existing notes...\n")

    notes = list(NOTES_DIR.glob("*.md"))
    print(f"Found {len(notes)} notes\n")

    updated = 0
    total_claims = 0

    for note_path in sorted(notes):
        modified, count = add_anchors_to_note(note_path)
        if modified:
            print(f"  Updated: {note_path.name} ({count} claims)")
            updated += 1
            total_claims += count

    print(f"\nDone. Updated {updated} notes with {total_claims} total claim anchors.")


if __name__ == "__main__":
    main()
