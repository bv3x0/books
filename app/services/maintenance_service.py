"""
Maintenance service: integrity checks, reconcile, backlog reporting, and vector sync.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from app.bootstrap import project_python_executable
from app.core.publisher import PROJECT_ROOT, report_semantic_backlog
from app.logger import log
from app.services.step_result import StepResult


PYTHON = project_python_executable()
RECONCILE_PARTIAL_EXIT_CODE = 3


def _stream_command(
    cmd: list[str], cwd: Path, warning_returncodes: set[int] | None = None
) -> StepResult:
    try:
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        log.error(f"Command not found: {cmd[0]}")
        return StepResult.failed(f"Command not found: {cmd[0]}")

    assert process.stdout is not None
    try:
        for line in process.stdout:
            line = line.rstrip()
            if line:
                log.info(f"  {line}")
    finally:
        process.stdout.close()

    process.wait()
    if warning_returncodes and process.returncode in warning_returncodes:
        log.warning(
            f"Command completed with warning exit code {process.returncode}: {' '.join(cmd)}"
        )
        return StepResult.warning(
            f"Command completed with warning exit code {process.returncode}: {' '.join(cmd)}"
        )
    if process.returncode != 0:
        log.error(f"Command failed with exit code {process.returncode}: {' '.join(cmd)}")
        return StepResult.failed(
            f"Command failed with exit code {process.returncode}: {' '.join(cmd)}"
        )
    return StepResult.success()


def run_integrity_check(allow_vector_drift: bool = True) -> StepResult:
    """Run structural integrity checks for index/vectors/concepts consistency."""
    script_path = PROJECT_ROOT / "scripts" / "check_integrity.py"
    if not script_path.exists():
        log.warning("Integrity script not found, skipping")
        return StepResult.skipped("Integrity script not found")

    cmd = [PYTHON, str(script_path)]
    if allow_vector_drift:
        cmd.append("--allow-vector-drift")
    return _stream_command(cmd, cwd=PROJECT_ROOT)


def run_reconcile(mode: str) -> StepResult:
    """Reconcile vectors/index consistency before publish."""
    normalized_mode = (mode or "none").lower()
    if normalized_mode == "none":
        return StepResult.skipped("Reconcile disabled")

    script_path = PROJECT_ROOT / "scripts" / "reconcile_vectors.py"
    if not script_path.exists():
        log.error("Reconcile script not found.")
        return StepResult.failed("Reconcile script not found")

    cmd = [PYTHON, str(script_path)]
    if normalized_mode == "full":
        cmd.append("--apply-all")
    elif normalized_mode == "reuse":
        cmd.append("--apply")
    else:
        log.error(f"Unknown reconcile mode: {mode}")
        return StepResult.failed(f"Unknown reconcile mode: {mode}")

    return _stream_command(
        cmd,
        cwd=PROJECT_ROOT,
        warning_returncodes={RECONCILE_PARTIAL_EXIT_CODE},
    )


def report_vector_backlog() -> StepResult:
    """Report index/vectors drift without failing the publish."""
    ok = report_semantic_backlog()
    return StepResult.success() if ok else StepResult.warning("Backlog report had warnings")


def sync_vectors_to_postgres() -> StepResult:
    """Sync local SQLite vectors to Postgres for semantic search."""
    script_path = PROJECT_ROOT / "scripts" / "migrate-vectors.py"
    if not script_path.exists():
        log.warning("Vector migration script not found, skipping")
        return StepResult.skipped("Vector migration script not found")

    if not os.environ.get("DATABASE_URL_UNPOOLED") and not os.environ.get(
        "POSTGRES_URL_NON_POOLING"
    ):
        log.warning("DATABASE_URL_UNPOOLED not set, skipping vector sync")
        log.warning("  (Semantic search will use stale data until vectors are synced)")
        return StepResult.skipped("Vector sync skipped: Postgres env not set")

    return _stream_command([PYTHON, str(script_path)], cwd=PROJECT_ROOT)
