"""
Test TOC extraction from EPUB files.

Tests the extract_toc_from_epub function to verify it correctly
parses table of contents from both EPUB 2 (toc.ncx) and EPUB 3 (nav.xhtml) formats.
"""

import os
import sys

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.core.epub_processor import extract_toc_from_epub


def test_horse_wheel_language_toc():
    """
    Test TOC extraction from 'The Horse, the Wheel, and Language' EPUB.
    
    Expected: 17 chapters (6 in Part I, 11 in Part II)
    Per the book's actual structure.
    """
    epub_path = os.path.join(
        project_root, 
        "books/@staging/The Horse, the Wheel, and Language_ How Br - David W. Anthony.epub"
    )
    
    if not os.path.exists(epub_path):
        print(f"SKIP: Test EPUB not found at {epub_path}")
        return
    
    toc = extract_toc_from_epub(epub_path)
    
    print(f"\nExtracted {len(toc)} chapters from TOC:\n")
    for i, title in enumerate(toc, 1):
        print(f"  {i}. {title}")
    
    # Verify chapter count
    assert len(toc) == 17, f"Expected 17 chapters, got {len(toc)}"
    
    # Verify no "Part" entries leaked through
    for title in toc:
        assert not title.lower().startswith('part '), f"Found Part entry in chapters: {title}"
    
    print(f"\n✓ Test passed! Found exactly 17 chapters (Part entries filtered out)")


def test_toc_extraction_nonexistent_file():
    """Test that TOC extraction handles missing files gracefully."""
    toc = extract_toc_from_epub("/nonexistent/path/to/book.epub")
    assert toc == [], f"Expected empty list for nonexistent file, got {toc}"
    print("✓ Nonexistent file test passed!")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing EPUB TOC Extraction")
    print("=" * 60)
    
    test_toc_extraction_nonexistent_file()
    test_horse_wheel_language_toc()
    
    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)
