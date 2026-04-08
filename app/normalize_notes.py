#!/usr/bin/env python3
"""
Normalize existing markdown notes in the notes/ folder.

Usage:
    python normalize_notes.py                    # Normalize all .md files
    python normalize_notes.py "twelve who ruled" # Normalize specific file
"""
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.core.normalizer import StructureNormalizer
from app.config import NOTES_DIR


def normalize_file(filepath: str) -> tuple[int, int]:
    """Normalize a single file. Returns (before_lines, after_lines)."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    before_lines = len(content.split('\n'))
    
    normalizer = StructureNormalizer()
    normalized = normalizer.normalize(content)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(normalized)
    
    after_lines = len(normalized.split('\n'))
    return before_lines, after_lines


def main():
    if len(sys.argv) > 1:
        # Normalize specific file
        book_name = sys.argv[1]
        if not book_name.endswith('.md'):
            book_name += '.md'
        filepath = os.path.join(NOTES_DIR, book_name)
        
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            sys.exit(1)
        
        before, after = normalize_file(filepath)
        print(f"Normalized: {book_name} ({before} → {after} lines)")
    else:
        # Normalize all markdown files in notes/
        files = [f for f in os.listdir(NOTES_DIR) if f.endswith('.md')]
        
        if not files:
            print(f"No .md files found in {NOTES_DIR}")
            sys.exit(0)
        
        print(f"Normalizing {len(files)} files in {NOTES_DIR}...\n")
        
        for filename in sorted(files):
            filepath = os.path.join(NOTES_DIR, filename)
            before, after = normalize_file(filepath)
            print(f"  {filename}: {before} → {after} lines")
        
        print(f"\nDone! Normalized {len(files)} files.")


if __name__ == "__main__":
    main()







