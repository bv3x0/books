#!/usr/bin/env python3
"""
Unified daily workflow wrapper.

Commands:
  add      -> run app/main.py for one book
  publish  -> run app/cli/publish.py publish
  ship     -> run publish, then git push
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

    return run_cmd(["git", "push"])


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
        help="Run publish, then git push",
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
