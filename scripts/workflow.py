#!/usr/bin/env python3
"""
Unified daily workflow wrapper.

Commands:
  add      -> run app/main.py for one book or a batch manifest
  publish  -> run app/cli/publish.py publish
  ship     -> run publish, then commit/push the current worktree; non-production branches create preview deploys by default
  smoke    -> run local smoke checks for publish/build/search surfaces
"""

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.bootstrap import project_python_executable
from app.services.publish_service import PublishOptions, publish_run


PYTHON = project_python_executable()
PRODUCTION_BRANCH = os.environ.get("SUMMARIZER_PRODUCTION_BRANCH", "main")
COMPARISON_NOTE_SUFFIXES = (".test", ".gem", ".gpt")


@dataclass(frozen=True)
class PublishSettings:
    reconcile: str
    sync_vectors: bool
    skip_integrity: bool
    book_filters: list[str] | None
    force_search_index: bool


def run_cmd(cmd: list[str], env: dict[str, str] | None = None) -> int:
    """Run a command in project root, streaming output."""
    started_at = time.perf_counter()
    process = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env)
    elapsed = time.perf_counter() - started_at
    print(f"[workflow] completed in {elapsed:.2f}s: {' '.join(cmd)}", file=sys.stderr)
    return process.returncode


def run_captured_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a command in project root while capturing output for diagnostics."""
    return subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )


def print_completed_process_output(result: subprocess.CompletedProcess[str]) -> None:
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)


def get_current_branch_name() -> str | None:
    """Return the current git branch name, if available."""
    result = run_captured_cmd(["git", "branch", "--show-current"])
    if result.returncode != 0:
        return None
    branch = result.stdout.strip()
    return branch or None


def _book_slug_from_canonical_path(raw_path: str) -> str | None:
    """Return a book slug for changed canonical note/index paths."""
    path = Path(raw_path)
    if len(path.parts) != 2:
        return None

    parent, filename = path.parts
    stem = Path(filename).stem
    if parent == "notes" and filename.endswith(".md"):
        if stem.endswith(COMPARISON_NOTE_SUFFIXES):
            return None
        return stem
    if parent == "index" and filename.endswith(".json") and not filename.startswith("_"):
        return stem
    return None


def get_changed_book_filters() -> list[str]:
    """Detect canonical book slugs changed in the current git worktree."""
    result = run_captured_cmd(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"]
    )
    if result.returncode != 0:
        print_completed_process_output(result)
        return []

    books = set()
    for entry in result.stdout.split("\0"):
        if len(entry) < 4:
            continue
        path = entry[3:] if entry[2] == " " else entry
        slug = _book_slug_from_canonical_path(path)
        if slug:
            books.add(slug)
    return sorted(books)


def resolve_book_filters(args: argparse.Namespace) -> list[str] | None:
    """Resolve explicit or changed-only book filters for publish-like commands."""
    explicit_books = [book for book in (getattr(args, "book", None) or []) if book]
    if explicit_books:
        return sorted(dict.fromkeys(explicit_books))
    if getattr(args, "changed_only", False):
        return get_changed_book_filters()
    return None


def resolve_publish_settings(args: argparse.Namespace) -> PublishSettings:
    """Resolve publish preset flags and scoped book filters."""
    reconcile = args.reconcile
    sync_vectors = args.sync_vectors
    changed_only = getattr(args, "changed_only", False)

    if getattr(args, "daily", False):
        reconcile = "full"
        sync_vectors = True
        changed_only = True

    settings_args = argparse.Namespace(
        book=getattr(args, "book", None),
        changed_only=changed_only,
    )
    book_filters = resolve_book_filters(settings_args)

    if book_filters is not None:
        if book_filters:
            print(
                "Book scope: " + ", ".join(book_filters),
                file=sys.stderr,
            )
        else:
            if reconcile != "none" or sync_vectors:
                print(
                    "Changed-only scope found no canonical book changes; "
                    "skipping reconcile/vector sync.",
                    file=sys.stderr,
                )
            reconcile = "none"
            sync_vectors = False

    return PublishSettings(
        reconcile=reconcile,
        sync_vectors=sync_vectors,
        skip_integrity=args.skip_integrity,
        book_filters=book_filters,
        force_search_index=getattr(args, "force_search_index", False),
    )


def default_commit_message(args: argparse.Namespace) -> str:
    """Return a useful default commit message for wrapper-created commits."""
    explicit_books = [book for book in (getattr(args, "book", None) or []) if book]
    if explicit_books:
        unique_books = list(dict.fromkeys(explicit_books))
        if len(unique_books) == 1:
            return f"publish {unique_books[0]}"
        return f"publish {len(unique_books)} book updates"
    if getattr(args, "daily", False):
        return "publish daily book updates"
    if getattr(args, "changed_only", False):
        return "publish changed book updates"
    return "publish book updates"


def commit_message(args: argparse.Namespace) -> str:
    return getattr(args, "message", None) or default_commit_message(args)


def build_ingest_env(args: argparse.Namespace) -> dict[str, str] | None:
    """Build an optional environment override for ingest tuning flags."""
    env_updates = {}
    if getattr(args, "concurrency", None) is not None:
        env_updates["INGEST_CONCURRENCY"] = str(args.concurrency)
    if getattr(args, "chunk_min_tokens", None) is not None:
        env_updates["SMART_CHUNK_MIN_TOKENS"] = str(args.chunk_min_tokens)
    if getattr(args, "chunk_max_tokens", None) is not None:
        env_updates["SMART_CHUNK_MAX_TOKENS"] = str(args.chunk_max_tokens)
    if getattr(args, "chunk_target_output_tokens", None) is not None:
        env_updates["SMART_CHUNK_TARGET_OUTPUT_TOKENS"] = str(
            args.chunk_target_output_tokens
        )

    if not env_updates:
        return None

    print(
        "Ingest tuning: "
        + ", ".join(f"{key}={value}" for key, value in sorted(env_updates.items())),
        file=sys.stderr,
    )
    env = os.environ.copy()
    env.update(env_updates)
    return env


def print_ship_result(summary: str) -> None:
    """Print a blunt end-of-run ship summary."""
    print(f"SHIP RESULT: {summary}", file=sys.stderr)


def add_command(args: argparse.Namespace) -> int:
    cmd = [PYTHON, "app/main.py"]
    if args.batch_manifest:
        cmd.extend(["--batch-manifest", args.batch_manifest])
    else:
        cmd.append(args.book)
    if args.toc:
        cmd.append("--toc")
    if args.retry:
        cmd.append("--retry")
    if args.ocr:
        cmd.append("--ocr")
    if args.split:
        cmd.append("--split")
    if args.gem:
        cmd.append("--gem")
    if args.gpt:
        cmd.append("--gpt")
    if args.test:
        cmd.append("--test")
    if args.enrich:
        cmd.append("--enrich")
    if args.no_semantic_merge:
        cmd.append("--no-semantic-merge")
    if args.yes:
        cmd.append("--yes")
    if args.non_interactive:
        cmd.append("--non-interactive")
    env = build_ingest_env(args)
    if env is not None:
        return run_cmd(cmd, env=env)
    return run_cmd(cmd)


def publish_command(args: argparse.Namespace) -> int:
    settings = resolve_publish_settings(args)
    started_at = time.perf_counter()
    result = publish_run(
        PublishOptions(
            reconcile_mode=settings.reconcile,
            sync_vectors=settings.sync_vectors,
            run_integrity=not settings.skip_integrity,
            book_filters=(
                tuple(settings.book_filters)
                if settings.book_filters is not None
                else None
            ),
            force_search_index=settings.force_search_index,
        )
    )
    elapsed = time.perf_counter() - started_at
    print(f"[workflow] publish completed in {elapsed:.2f}s", file=sys.stderr)
    return 0 if result.ok else 1


def print_ship_plan(args: argparse.Namespace, branch: str | None, branch_display: str) -> None:
    """Print what ship would do without mutating the worktree."""
    commit = commit_message(args)
    if branch == PRODUCTION_BRANCH:
        deploy_summary = f"push '{PRODUCTION_BRANCH}' for production deployment"
    elif getattr(args, "deploy_production", False):
        deploy_summary = (
            f"push '{branch_display}', then deploy current worktree to Vercel production"
        )
    else:
        deploy_summary = f"push '{branch_display}' for preview deployment only"

    print(f"Plan: publish, stage all changes, commit '{commit}', then {deploy_summary}.", file=sys.stderr)


def ship_command(args: argparse.Namespace) -> int:
    branch = get_current_branch_name()
    branch_display = branch or "<detached-head>"
    preview_only_push = branch != PRODUCTION_BRANCH

    if getattr(args, "plan_only", False):
        print_ship_plan(args, branch, branch_display)
        print_ship_result("Plan only. No publish, git, push, or deploy actions ran.")
        return 0

    if preview_only_push and not args.deploy_production:
        print(
            f"Preview ship: branch '{branch_display}' will push a preview deployment only.",
            file=sys.stderr,
        )

    if getattr(args, "skip_publish", False):
        if not args.dry_run:
            print("--skip-publish is only allowed with --dry-run.", file=sys.stderr)
            return 2
        print("Dry run: skipping publish preflight by request.", file=sys.stderr)
    else:
        publish_args = argparse.Namespace(
            reconcile=args.reconcile,
            sync_vectors=args.sync_vectors,
            skip_integrity=args.skip_integrity,
            changed_only=getattr(args, "changed_only", False),
            book=getattr(args, "book", None),
            daily=getattr(args, "daily", False),
            force_search_index=getattr(args, "force_search_index", False),
        )
        rc = publish_command(publish_args)
        if rc != 0:
            return rc

    if args.dry_run:
        print(
            f"Dry run: would stage the current worktree and push '{branch_display}'.",
            file=sys.stderr,
        )
        print(f"Dry run: would commit with message: {commit_message(args)}", file=sys.stderr)
        if args.deploy_production:
            if branch == PRODUCTION_BRANCH:
                print(
                    f"Dry run: pushing '{PRODUCTION_BRANCH}' would trigger production automatically.",
                    file=sys.stderr,
                )
            else:
                print(
                    f"Dry run: would deploy current worktree from '{branch_display}' to Vercel production.",
                    file=sys.stderr,
                )
        else:
            print_ship_result("Dry run only. Production unchanged.")
        return 0

    # Stage the full worktree so wrapper-driven code/config changes are not silently skipped.
    rc = run_cmd(["git", "add", "-A"])
    if rc != 0:
        return rc

    # Check if there's anything to commit
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=PROJECT_ROOT
    )
    if result.returncode != 0:
        commit_cmd = ["git"]
        if args.no_gpg_sign:
            commit_cmd.extend(["-c", "commit.gpgsign=false"])
        commit_cmd.extend(["commit", "-m", commit_message(args)])

        commit_result = run_captured_cmd(commit_cmd)
        print_completed_process_output(commit_result)
        if commit_result.returncode != 0:
            combined_output = "\n".join(
                part for part in [commit_result.stdout, commit_result.stderr] if part
            ).lower()
            if not args.no_gpg_sign and (
                "gpg failed to sign the data" in combined_output
                or "signing failed: no pinentry" in combined_output
                or "fatal: failed to write commit object" in combined_output
            ):
                print(
                    "Git commit signing failed because pinentry was unavailable.",
                    file=sys.stderr,
                )
                print(
                    "Retry with: python3 scripts/workflow.py ship --no-gpg-sign",
                    file=sys.stderr,
                )
                print(
                    "Or fix your GPG/pinentry setup and rerun the same ship command.",
                    file=sys.stderr,
                )
            return commit_result.returncode
    else:
        print("Nothing new to commit.", file=sys.stderr)

    rc = run_cmd(["git", "push"])
    if rc != 0:
        return rc

    if args.deploy_production:
        if branch == PRODUCTION_BRANCH:
            print(
                f"Skipped explicit Vercel production deploy: pushing '{PRODUCTION_BRANCH}' already triggers production.",
                file=sys.stderr,
            )
            print_ship_result(f"Production updated via '{PRODUCTION_BRANCH}' push.")
            return 0
        print(
            f"Deploying current worktree from '{branch_display}' to Vercel production...",
            file=sys.stderr,
        )
        rc = run_cmd(["npx", "vercel", "deploy", "--prod", "--yes"])
        if rc != 0:
            return rc
        print_ship_result(f"Production updated from branch '{branch_display}'.")
        return 0

    if preview_only_push:
        print_ship_result(
            f"Preview updated only from branch '{branch_display}'. Production unchanged."
        )
    else:
        print_ship_result(f"Production updated via '{PRODUCTION_BRANCH}' push.")

    return 0


def smoke_command(_args: argparse.Namespace) -> int:
    cmd = [PYTHON, "scripts/smoke_test.py"]
    for flag in ("quick", "publish", "deploy_contract", "full"):
        if getattr(_args, flag, False):
            cmd.append("--" + flag.replace("_", "-"))
    return run_cmd(cmd)


def positive_int(raw: str) -> int:
    value = int(raw)
    if value <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Daily workflow wrapper for add/publish/ship.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add = subparsers.add_parser("add", help="Add/update one book or batch via app/main.py")
    add.add_argument("book", nargs="?", help="Book name used for notes/index output")
    add.add_argument(
        "--batch-manifest",
        help="Path to JSON manifest describing multiple books and source folders",
    )
    add.add_argument(
        "--toc",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use manual TOC from books/toc.txt (default: on)",
    )
    add.add_argument("--retry", action="store_true", help="Retry failed chunks only")
    add.add_argument("--ocr", action="store_true", help="Use VLM OCR for scanned PDFs")
    add.add_argument("--split", action="store_true", help="Split two-page spreads")
    add.add_argument("--gem", action="store_true", help="Use Gemini provider")
    add.add_argument("--gpt", action="store_true", help="Use OpenAI provider")
    add.add_argument(
        "--test",
        action="store_true",
        help="Benchmark/QA mode only (notes-only; skips canonical index/concept updates)",
    )
    add.add_argument(
        "--enrich",
        action="store_true",
        help="Enable embeddings/vector enrichment during this run",
    )
    add.add_argument(
        "--no-semantic-merge",
        action="store_true",
        help="Disable embedding-based semantic concept merge",
    )
    add.add_argument(
        "--yes",
        action="store_true",
        help="Auto-accept ingest prompts after you've already reviewed the input",
    )
    add.add_argument(
        "--non-interactive",
        action="store_true",
        help="Never prompt; proceed on safe confirmations and abort when judgment is required",
    )
    add.add_argument(
        "--concurrency",
        type=positive_int,
        help="Set INGEST_CONCURRENCY for this ingest run",
    )
    add.add_argument(
        "--chunk-min-tokens",
        type=positive_int,
        help="Set SMART_CHUNK_MIN_TOKENS for this ingest run",
    )
    add.add_argument(
        "--chunk-max-tokens",
        type=positive_int,
        help="Set SMART_CHUNK_MAX_TOKENS for this ingest run",
    )
    add.add_argument(
        "--chunk-target-output-tokens",
        type=positive_int,
        help="Set SMART_CHUNK_TARGET_OUTPUT_TOKENS for this ingest run",
    )
    add.set_defaults(handler=add_command)

    publish = subparsers.add_parser("publish", help="Run app/cli/publish.py publish")
    publish.add_argument(
        "--reconcile",
        choices=["none", "reuse", "full"],
        default="none",
        help="Reconcile vectors before build (default: none)",
    )
    publish.add_argument(
        "--sync-vectors",
        "--sync",
        action="store_true",
        dest="sync_vectors",
        help="Sync vectors to Postgres after build",
    )
    publish.add_argument(
        "--book",
        action="append",
        help="Scope reconcile/vector sync to a book slug/filter (repeatable)",
    )
    publish.add_argument(
        "--changed-only",
        action="store_true",
        help="Scope reconcile/vector sync to changed canonical notes/index books",
    )
    publish.add_argument(
        "--skip-integrity",
        action="store_true",
        help="Skip integrity check before build",
    )
    publish.add_argument(
        "--force-search-index",
        action="store_true",
        help="Regenerate Pagefind even when local search inputs look unchanged",
    )
    publish.add_argument(
        "--daily",
        action="store_true",
        help="Preset: --changed-only --reconcile full --sync-vectors",
    )
    publish.set_defaults(handler=publish_command)

    ship = subparsers.add_parser(
        "ship",
        help="Run publish, then commit/push the current worktree; non-production branches default to preview deployments",
    )
    ship.add_argument(
        "--reconcile",
        choices=["none", "reuse", "full"],
        default="none",
        help="Reconcile vectors before build (default: none)",
    )
    ship.add_argument(
        "--sync-vectors",
        "--sync",
        action="store_true",
        dest="sync_vectors",
        help="Sync vectors to Postgres after build",
    )
    ship.add_argument(
        "--book",
        action="append",
        help="Scope reconcile/vector sync to a book slug/filter (repeatable)",
    )
    ship.add_argument(
        "--changed-only",
        action="store_true",
        help="Scope reconcile/vector sync to changed canonical notes/index books",
    )
    ship.add_argument(
        "--skip-integrity",
        action="store_true",
        help="Skip integrity check before build",
    )
    ship.add_argument(
        "--force-search-index",
        action="store_true",
        help="Regenerate Pagefind even when local search inputs look unchanged",
    )
    ship.add_argument(
        "--daily",
        action="store_true",
        help="Preset: --changed-only --reconcile full --sync-vectors",
    )
    ship.add_argument(
        "-m",
        "--message",
        help="Commit message for wrapper-created ship commits",
    )
    ship.add_argument(
        "--no-gpg-sign",
        action="store_true",
        help="Create the ship commit without GPG signing",
    )
    ship.add_argument(
        "--dry-run",
        action="store_true",
        help="Run publish and report what ship would do without staging, committing, pushing, or deploying",
    )
    ship.add_argument(
        "--skip-publish",
        action="store_true",
        help="With --dry-run only, skip the publish preflight",
    )
    ship.add_argument(
        "--plan-only",
        action="store_true",
        help="Print the ship plan without publishing, staging, committing, pushing, or deploying",
    )
    ship.add_argument(
        "--allow-preview",
        action="store_true",
        help="Compatibility flag: non-production branches already push preview deployments by default",
    )
    ship.add_argument(
        "--deploy-production",
        action="store_true",
        help="After push, deploy the current worktree to Vercel production (useful from non-main branches)",
    )
    ship.set_defaults(handler=ship_command)

    smoke = subparsers.add_parser(
        "smoke",
        help="Run local smoke checks for publish/build/search surfaces",
    )
    smoke_mode = smoke.add_mutually_exclusive_group()
    smoke_mode.add_argument(
        "--quick",
        action="store_true",
        help="Only run fast CLI/API parse checks",
    )
    smoke_mode.add_argument(
        "--publish",
        action="store_true",
        help="Run quick checks plus one local publish and output verification",
    )
    smoke_mode.add_argument(
        "--deploy-contract",
        action="store_true",
        help="Run quick checks plus the Vercel root build contract",
    )
    smoke_mode.add_argument(
        "--full",
        action="store_true",
        help="Run all smoke checks (default)",
    )
    smoke.set_defaults(handler=smoke_command)

    return parser


def main() -> int:
    os.chdir(PROJECT_ROOT)
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "add" and bool(getattr(args, "book", None)) == bool(
        getattr(args, "batch_manifest", None)
    ):
        parser.error("workflow add requires either a book name or --batch-manifest")
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
