"""
Site service: Hugo build, local serve, and search-index generation.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.core.publisher import BLOG_DIR, PROJECT_ROOT, PUBLIC_DIR
from app.logger import log
from app.services.step_result import StepResult


PAGEFIND_DIR = PUBLIC_DIR / "pagefind"
SEARCH_FINGERPRINT_CACHE = PROJECT_ROOT / ".cache" / "pagefind-fingerprint.json"
PRESERVED_PAGEFIND_DIR = PROJECT_ROOT / ".cache" / "pagefind-preserved"
SEARCH_FINGERPRINT_VERSION = 1


def _fingerprint_file(hasher: "hashlib._Hash", path: Path) -> None:
    hasher.update(path.relative_to(PROJECT_ROOT).as_posix().encode("utf-8"))
    hasher.update(b"\0")
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    hasher.update(b"\0")


def compute_search_index_fingerprint() -> str:
    """Hash the inputs that determine the generated Pagefind custom records."""
    hasher = hashlib.sha256()
    hasher.update(f"pagefind-inputs-v{SEARCH_FINGERPRINT_VERSION}".encode("utf-8"))

    input_paths = [
        PROJECT_ROOT / "package.json",
        PROJECT_ROOT / "package-lock.json",
        PROJECT_ROOT / "scripts" / "build-search-index.mjs",
    ]
    input_paths.extend(sorted((PROJECT_ROOT / "index").glob("*.json")))
    input_paths.extend(sorted((BLOG_DIR / "content" / "books").glob("*.md")))

    for path in input_paths:
        if path.exists() and path.is_file():
            _fingerprint_file(hasher, path)

    return hasher.hexdigest()


def _read_cached_search_fingerprint() -> str | None:
    try:
        payload = json.loads(SEARCH_FINGERPRINT_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return None
    if payload.get("version") != SEARCH_FINGERPRINT_VERSION:
        return None
    fingerprint = payload.get("fingerprint")
    return fingerprint if isinstance(fingerprint, str) else None


def _write_cached_search_fingerprint(fingerprint: str) -> None:
    SEARCH_FINGERPRINT_CACHE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": SEARCH_FINGERPRINT_VERSION,
        "fingerprint": fingerprint,
    }
    SEARCH_FINGERPRINT_CACHE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def search_index_cache_enabled() -> bool:
    """Return whether local publish may reuse an unchanged Pagefind index."""
    return not os.environ.get("SUMMARIZER_DISABLE_PAGEFIND_CACHE")


def is_search_index_cache_valid(fingerprint: str | None = None) -> bool:
    """Return true when Pagefind output exists and matches current inputs."""
    if not search_index_cache_enabled():
        return False
    if not PAGEFIND_DIR.exists() or not any(PAGEFIND_DIR.iterdir()):
        return False
    current = fingerprint or compute_search_index_fingerprint()
    return _read_cached_search_fingerprint() == current


def _move_cached_search_index() -> Path | None:
    if not is_search_index_cache_valid():
        return None
    if PRESERVED_PAGEFIND_DIR.exists():
        shutil.rmtree(PRESERVED_PAGEFIND_DIR, ignore_errors=True)
    PRESERVED_PAGEFIND_DIR.parent.mkdir(parents=True, exist_ok=True)
    PAGEFIND_DIR.rename(PRESERVED_PAGEFIND_DIR)
    log.info("Preserving unchanged Pagefind index through Hugo rebuild.")
    return PRESERVED_PAGEFIND_DIR


def build_site() -> StepResult:
    """Build the Hugo site into blog/public."""
    if not BLOG_DIR.exists():
        log.error(f"Blog directory not found: {BLOG_DIR}")
        return StepResult.failed(f"Blog directory not found: {BLOG_DIR}")

    try:
        with tempfile.TemporaryDirectory() as work_dir:
            work_path = Path(work_dir)
            hugo_output = work_path / "public"
            preserved_pagefind = None
            result = subprocess.run(
                ["hugo", "--source", str(BLOG_DIR), "--destination", str(hugo_output)],
                capture_output=True,
                text=True,
                check=True,
            )
            try:
                preserved_pagefind = _move_cached_search_index()
                if PUBLIC_DIR.exists():
                    shutil.rmtree(PUBLIC_DIR, ignore_errors=True)
                shutil.copytree(hugo_output, PUBLIC_DIR, dirs_exist_ok=True)
                if preserved_pagefind is not None:
                    PAGEFIND_DIR.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(preserved_pagefind), str(PAGEFIND_DIR))
            finally:
                if preserved_pagefind is not None and preserved_pagefind.exists() and not PAGEFIND_DIR.exists():
                    PAGEFIND_DIR.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(preserved_pagefind), str(PAGEFIND_DIR))
        log.info("Site built successfully!")
        if result.stdout:
            log.debug(result.stdout)
        return StepResult.success("Site built successfully")
    except subprocess.CalledProcessError as e:
        log.error(f"Build failed: {e.stderr}")
        return StepResult.failed(e.stderr or str(e))
    except FileNotFoundError:
        log.error("Hugo is not installed. Install with: brew install hugo")
        return StepResult.failed("Hugo is not installed")


def serve_locally(port: int = 1313) -> None:
    """Start Hugo development server."""
    if not BLOG_DIR.exists():
        log.error(f"Blog directory not found: {BLOG_DIR}")
        return

    try:
        log.info(f"Starting Hugo server on port {port}...")
        log.info("Press Ctrl+C to stop the server.")
        log.info(f"Server will be available at: http://localhost:{port}/")
        subprocess.run(
            [
                "hugo",
                "server",
                "--source",
                str(BLOG_DIR),
                "--port",
                str(port),
                "--baseURL",
                f"http://localhost:{port}/",
            ],
            check=True,
        )
    except KeyboardInterrupt:
        log.info("\nServer stopped.")
    except FileNotFoundError:
        log.error("Hugo is not installed. Install with: brew install hugo")
    except subprocess.CalledProcessError as e:
        log.error(f"Server failed to start: {e}")


def build_search_index(force: bool = False) -> StepResult:
    """Generate the Pagefind search index from claim data."""
    script_path = PROJECT_ROOT / "scripts" / "build-search-index.mjs"
    if not script_path.exists():
        log.warning("Search index script not found, skipping")
        return StepResult.skipped("Search index script not found")

    try:
        fingerprint = compute_search_index_fingerprint()
        if not force and is_search_index_cache_valid(fingerprint):
            log.info("Pagefind search index unchanged; using cached output.")
            return StepResult.success("Search index unchanged")

        result = subprocess.run(
            ["node", str(script_path)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        for line in result.stdout.strip().split("\n"):
            if line.startswith("Total claims") or line.startswith("Index size"):
                log.info(f"  {line}")
        _write_cached_search_fingerprint(fingerprint)
        return StepResult.success("Search index generated")
    except subprocess.CalledProcessError as e:
        log.error(f"Search index generation failed: {e}")
        log.error(e.stderr if e.stderr else "No error output")
        return StepResult.failed(e.stderr or str(e))
    except FileNotFoundError:
        log.warning("Node.js not found, skipping search index generation")
        return StepResult.skipped("Node.js not found")
