"""
Site service: Hugo build, local serve, and search-index generation.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile

from app.core.publisher import BLOG_DIR, PROJECT_ROOT, PUBLIC_DIR
from app.logger import log
from app.services.step_result import StepResult


def build_site() -> StepResult:
    """Build the Hugo site into blog/public."""
    if not BLOG_DIR.exists():
        log.error(f"Blog directory not found: {BLOG_DIR}")
        return StepResult.failed(f"Blog directory not found: {BLOG_DIR}")

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = subprocess.run(
                ["hugo", "--source", str(BLOG_DIR), "--destination", tmp_dir],
                capture_output=True,
                text=True,
                check=True,
            )
            if PUBLIC_DIR.exists():
                shutil.rmtree(PUBLIC_DIR, ignore_errors=True)
            shutil.copytree(tmp_dir, PUBLIC_DIR, dirs_exist_ok=True)
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


def build_search_index() -> StepResult:
    """Generate the Pagefind search index from claim data."""
    script_path = PROJECT_ROOT / "scripts" / "build-search-index.mjs"
    if not script_path.exists():
        log.warning("Search index script not found, skipping")
        return StepResult.skipped("Search index script not found")

    try:
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
        return StepResult.success("Search index generated")
    except subprocess.CalledProcessError as e:
        log.error(f"Search index generation failed: {e}")
        log.error(e.stderr if e.stderr else "No error output")
        return StepResult.failed(e.stderr or str(e))
    except FileNotFoundError:
        log.warning("Node.js not found, skipping search index generation")
        return StepResult.skipped("Node.js not found")
