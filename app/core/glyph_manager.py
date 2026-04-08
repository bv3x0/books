"""
Glyph management for chapter dividers.
Maps BISAC categories to glyph image folders and provides random selection.
"""

import random
import shutil
from pathlib import Path
from typing import Optional

from app.logger import log

PROJECT_ROOT = Path(__file__).parent.parent.parent
GLYPH_SOURCE_DIR = PROJECT_ROOT / "glyphs"
STATIC_GLYPH_DIR = PROJECT_ROOT / "blog" / "static" / "glyphs"

# Map categories without their own glyph folder to an existing one
CATEGORY_ALIASES = {
    "poetry": "philosophy",
}

# Cache folder mapping per publish run
_glyph_folders: Optional[dict[str, Path]] = None


def get_glyph_folders() -> dict[str, Path]:
    """
    Scan glyphs/ directory and return mapping of lowercase category names to folder paths.

    Returns:
        Dict mapping lowercase category names to their glyph folder paths.
        Example: {"philosophy": Path(".../glyphs/Philosophy")}
    """
    global _glyph_folders
    if _glyph_folders is not None:
        return _glyph_folders

    if not GLYPH_SOURCE_DIR.exists():
        log.warning(f"Glyph source directory not found: {GLYPH_SOURCE_DIR}")
        _glyph_folders = {}
        return _glyph_folders

    folders = {}
    for folder in GLYPH_SOURCE_DIR.iterdir():
        if folder.is_dir() and not folder.name.startswith("."):
            folders[folder.name.lower()] = folder

    _glyph_folders = folders
    return _glyph_folders


def get_random_glyph(categories: list[str]) -> Optional[str]:
    """
    Select a random glyph image from the pooled categories.

    Args:
        categories: List of lowercase BISAC category names

    Returns:
        URL path to glyph image (e.g., "/glyphs/Philosophy/image.png"),
        or None if no glyphs found.
    """
    if not categories:
        return None

    glyph_folders = get_glyph_folders()

    available_glyphs = []
    missing = []
    for category in categories:
        resolved = CATEGORY_ALIASES.get(category, category)
        folder = glyph_folders.get(resolved)
        if folder and folder.exists():
            available_glyphs.extend(folder.glob("*.png"))
        else:
            missing.append(category)

    if missing:
        log.warning(f"No glyph folder for categories: {missing}")

    if not available_glyphs:
        return None

    selected = random.choice(available_glyphs)
    relative_path = selected.relative_to(GLYPH_SOURCE_DIR)
    return f"/glyphs/{relative_path.as_posix()}"


def sync_glyphs_to_static() -> int:
    """
    Copy glyph images from glyphs/ to blog/static/glyphs/.
    Only copies files that are new or modified.

    Returns:
        Number of files copied.
    """
    if not GLYPH_SOURCE_DIR.exists():
        log.warning(f"Glyph source directory not found: {GLYPH_SOURCE_DIR}")
        return 0

    STATIC_GLYPH_DIR.mkdir(parents=True, exist_ok=True)

    copied = 0
    for category_folder in GLYPH_SOURCE_DIR.iterdir():
        if not category_folder.is_dir() or category_folder.name.startswith("."):
            continue

        dest_folder = STATIC_GLYPH_DIR / category_folder.name
        dest_folder.mkdir(exist_ok=True)

        for glyph_file in category_folder.glob("*.png"):
            dest_file = dest_folder / glyph_file.name
            if not dest_file.exists() or glyph_file.stat().st_mtime > dest_file.stat().st_mtime:
                shutil.copy2(glyph_file, dest_file)
                copied += 1

    log.info(f"Synced glyphs to static: {copied} copied")
    return copied
