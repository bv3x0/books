"""
Content publishing service: prepares derived Hugo content from canonical notes/index.
"""

from __future__ import annotations

from app.core.glyph_manager import sync_glyphs_to_static
from app.core.publisher import (
    compute_related_books,
    sync_notes_to_posts,
    update_stats,
    write_related_books_data,
)
from app.logger import log
from app.services.step_result import StepResult


def sync_glyphs() -> StepResult:
    """Sync generated glyph assets into the Hugo static directory."""
    try:
        sync_glyphs_to_static()
        return StepResult.success("Glyph assets synced")
    except Exception as e:
        log.error(f"Glyph sync failed: {e}")
        return StepResult.failed(str(e))


def sync_notes() -> StepResult:
    """Convert canonical notes into Hugo book posts."""
    try:
        converted = sync_notes_to_posts()
        log.info(f"Converted {len(converted)} notes.")
        return StepResult.success(f"Converted {len(converted)} notes")
    except Exception as e:
        log.error(f"Notes sync failed: {e}")
        return StepResult.failed(str(e))


def compute_related() -> StepResult:
    """Refresh derived related-books data for the site."""
    try:
        related = compute_related_books()
        if not write_related_books_data(related):
            log.warning("Related books data write failed - continuing with stale data")
            return StepResult.warning("Related books write failed; stale data kept")
        return StepResult.success("Related books refreshed")
    except Exception as e:
        log.error(f"Related books refresh failed: {e}")
        return StepResult.failed(str(e))


def refresh_stats() -> StepResult:
    """Refresh derived site stats from canonical notes/index data."""
    try:
        update_stats()
        return StepResult.success("Stats refreshed")
    except Exception as e:
        log.error(f"Stats refresh failed: {e}")
        return StepResult.failed(str(e))
