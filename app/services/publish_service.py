"""
Publish service: orchestrates blog build and deployment-adjacent maintenance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.core.publisher import PUBLIC_DIR
from app.logger import log
from app.services.content_service import (
    compute_related,
    refresh_stats,
    sync_glyphs,
    sync_notes,
)
from app.services.maintenance_service import (
    report_vector_backlog,
    run_integrity_check,
    run_reconcile,
    sync_vectors_to_postgres,
)
from app.services.site_service import build_search_index, build_site, serve_locally
from app.services.step_result import StepResult, StepStatus


@dataclass(frozen=True)
class PublishOptions:
    reconcile_mode: str = "none"
    sync_vectors: bool = False
    run_integrity: bool = True


@dataclass(frozen=True)
class PublishStep:
    label: str
    run: Callable[[], StepResult]
    fatal: bool


@dataclass(frozen=True)
class PublishRunResult:
    ok: bool
    fatal_step: str | None
    steps: list[tuple[str, StepResult]]

    @property
    def had_warnings(self) -> bool:
        return any(result.status in {StepStatus.WARNING, StepStatus.SKIPPED} for _, result in self.steps)


def publish_run(options: PublishOptions) -> PublishRunResult:
    """Run the end-to-end publish workflow and return structured step results."""
    log.info("=" * 50)
    log.info("Publishing notes to blog...")
    log.info("=" * 50)
    log.info(
        "Publish options: integrity=%s, reconcile=%s, sync_vectors=%s"
        % (
            "on" if options.run_integrity else "off",
            options.reconcile_mode,
            "on" if options.sync_vectors else "off",
        )
    )

    steps: list[PublishStep] = [
        PublishStep("Syncing glyph images", sync_glyphs, True),
        PublishStep("Converting notes to posts", sync_notes, True),
        PublishStep("Computing related books", compute_related, False),
        PublishStep("Updating stats", refresh_stats, True),
        PublishStep("Reporting semantic backlog", report_vector_backlog, False),
    ]

    if options.run_integrity:
        steps.append(
            PublishStep(
                "Running integrity check",
                lambda: run_integrity_check(allow_vector_drift=True),
                True,
            )
        )
    if options.reconcile_mode != "none":
        steps.append(
            PublishStep(
                f"Reconciling vectors ({options.reconcile_mode})",
                lambda: run_reconcile(options.reconcile_mode),
                True,
            )
        )

    steps.extend(
        [
            PublishStep("Building Hugo site", build_site, True),
            PublishStep("Generating Pagefind search index", build_search_index, False),
        ]
    )

    if options.sync_vectors:
        steps.append(PublishStep("Syncing vectors to Postgres", sync_vectors_to_postgres, False))

    total_steps = len(steps)
    results: list[tuple[str, StepResult]] = []
    had_non_fatal_issues = False

    for idx, step in enumerate(steps, start=1):
        log.info(f"\n[{idx}/{total_steps}] {step.label}...")
        result = step.run()
        results.append((step.label, result))
        if result.message and result.status is not StepStatus.SUCCESS:
            log.info(f"  {result.status.value}: {result.message}")
        if not result.ok:
            if step.fatal:
                return PublishRunResult(ok=False, fatal_step=step.label, steps=results)
            had_non_fatal_issues = True
            continue
        if result.status in {StepStatus.WARNING, StepStatus.SKIPPED}:
            had_non_fatal_issues = True

    log.info("\n" + "=" * 50)
    if had_non_fatal_issues:
        log.warning("Blog build completed with warnings (see logs above).")
    else:
        log.info("Blog built successfully!")
    log.info(f"Output: {PUBLIC_DIR}")
    log.info("=" * 50)
    return PublishRunResult(ok=True, fatal_step=None, steps=results)


def publish(options: PublishOptions) -> bool:
    """Compatibility wrapper for callers that only need success/failure."""
    return publish_run(options).ok
