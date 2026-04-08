#!/usr/bin/env python3
"""
CLI entry point for blog publishing.
"""

import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.publish_service import PublishOptions, publish, serve_locally
from app.logger import setup_logger

log = setup_logger("publisher")


def main():
    parser = argparse.ArgumentParser(
        description="Blog publisher - Convert notes to blog posts and build Hugo site"
    )
    parser.add_argument(
        "command",
        choices=["publish", "serve"],
        help="publish: build blog, serve: start local dev server"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=1313,
        help="Port for dev server (default: 1313)"
    )
    parser.add_argument(
        "--reconcile",
        choices=["none", "reuse", "full"],
        default="none",
        help="Run vector/index reconcile before build (none=default, reuse=--apply, full=--apply-all)"
    )
    parser.add_argument(
        "--sync-vectors",
        action="store_true",
        help="Sync local vectors to Postgres after build"
    )
    parser.add_argument(
        "--skip-integrity",
        action="store_true",
        help="Skip scripts/check_integrity.py before build (not recommended)"
    )
    
    args = parser.parse_args()
    
    if args.command == "publish":
        success = publish(
            PublishOptions(
                reconcile_mode=args.reconcile,
                sync_vectors=args.sync_vectors,
                run_integrity=not args.skip_integrity,
            )
        )
        sys.exit(0 if success else 1)
    elif args.command == "serve":
        serve_locally(args.port)


if __name__ == "__main__":
    main()
