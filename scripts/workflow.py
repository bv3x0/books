#!/usr/bin/env python3
"""
Unified daily workflow wrapper.

Commands:
  add      -> run app/main.py for one book
  publish  -> run app/cli/publish.py publish
  ship     -> run publish, then commit/push with an explicit preview or production target
  smoke    -> run local smoke checks for publish/build/search surfaces
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.bootstrap import project_python_executable


PYTHON = project_python_executable()
PRODUCTION_BRANCH = os.environ.get("SUMMARIZER_PRODUCTION_BRANCH", "main")


def run_cmd(cmd: list[str]) -> int:
    """Run a command in project root, streaming output."""
    process = subprocess.run(cmd, cwd=PROJECT_ROOT)
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


def add_command(args: argparse.Namespace) -> int:
    cmd = [PYTHON, "app/main.py", args.book]
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
    return run_cmd(cmd)


def publish_command(args: argparse.Namespace) -> int:
    cmd = [PYTHON, "app/cli/publish.py", "publish"]
    if args.reconcile != "none":
        cmd.extend(["--reconcile", args.reconcile])
    if args.sync_vectors:
        cmd.append("--sync-vectors")
    if args.skip_integrity:
        cmd.append("--skip-integrity")
    return run_cmd(cmd)


def ship_command(args: argparse.Namespace) -> int:
    branch = get_current_branch_name()
    branch_display = branch or "<detached-head>"
    preview_only_push = branch != PRODUCTION_BRANCH

    if preview_only_push and not args.allow_preview and not args.deploy_production:
        print(
            (
                f"Refusing to ship from '{branch_display}' without an explicit deploy target.\n"
                f"Pushing '{branch_display}' only updates a Vercel preview deployment.\n"
                f"Use `python3 scripts/workflow.py ship --allow-preview` for a preview-only push,\n"
                f"or `python3 scripts/workflow.py ship --deploy-production` to push and deploy this worktree to production."
            ),
            file=sys.stderr,
        )
        return 2

    if preview_only_push and args.allow_preview:
        print(
            f"Preview ship: branch '{branch_display}' will push a preview deployment only.",
            file=sys.stderr,
        )

    publish_args = argparse.Namespace(
        reconcile=args.reconcile,
        sync_vectors=args.sync_vectors,
        skip_integrity=args.skip_integrity,
    )
    rc = publish_command(publish_args)
    if rc != 0:
        return rc

    # Stage all tracked/new files relevant to publishing
    paths = ["notes/", "index/", "blog/content/", "blog/data/"]
    rc = run_cmd(["git", "add"] + paths)
    if rc != 0:
        return rc

    # Check if there's anything to commit
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=PROJECT_ROOT
    )
    if result.returncode == 0:
        print("Nothing to commit.")
        return 0

    commit_cmd = ["git"]
    if args.no_gpg_sign:
        commit_cmd.extend(["-c", "commit.gpgsign=false"])
    commit_cmd.extend(["commit", "-m", "new books"])

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

    rc = run_cmd(["git", "push"])
    if rc != 0:
        return rc

    if args.deploy_production:
        if branch == PRODUCTION_BRANCH:
            print(
                f"Skipped explicit Vercel production deploy: pushing '{PRODUCTION_BRANCH}' already triggers production.",
                file=sys.stderr,
            )
            return 0
        print(
            f"Deploying current worktree from '{branch_display}' to Vercel production...",
            file=sys.stderr,
        )
        return run_cmd(["npx", "vercel", "deploy", "--prod", "--yes"])

    return 0


def smoke_command(_args: argparse.Namespace) -> int:
    return run_cmd([PYTHON, "scripts/smoke_test.py"])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Daily workflow wrapper for add/publish/ship.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add = subparsers.add_parser("add", help="Add/update one book via app/main.py")
    add.add_argument("book", help="Book name used for notes/index output")
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
        action="store_true",
        help="Sync vectors to Postgres after build",
    )
    publish.add_argument(
        "--skip-integrity",
        action="store_true",
        help="Skip integrity check before build",
    )
    publish.set_defaults(handler=publish_command)

    ship = subparsers.add_parser(
        "ship",
        help="Run publish, then commit/push; feature branches require an explicit preview or production target",
    )
    ship.add_argument(
        "--reconcile",
        choices=["none", "reuse", "full"],
        default="none",
        help="Reconcile vectors before build (default: none)",
    )
    ship.add_argument(
        "--sync-vectors",
        action="store_true",
        help="Sync vectors to Postgres after build",
    )
    ship.add_argument(
        "--skip-integrity",
        action="store_true",
        help="Skip integrity check before build",
    )
    ship.add_argument(
        "--no-gpg-sign",
        action="store_true",
        help="Create the ship commit without GPG signing",
    )
    ship.add_argument(
        "--allow-preview",
        action="store_true",
        help="Allow shipping from a non-production branch when you only want a preview deployment",
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
    smoke.set_defaults(handler=smoke_command)

    return parser


def main() -> int:
    os.chdir(PROJECT_ROOT)
    parser = build_parser()
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
