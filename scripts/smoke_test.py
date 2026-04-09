#!/usr/bin/env python3
"""
Operational smoke test for the repo's local build and publish surfaces.

This is intentionally broad and integration-oriented. It does not hit external
LLM APIs or run a full ingest. It verifies the core operator invariants:

- Python CLIs still load
- workflow wrapper subcommands still parse and run
- publish still succeeds on current data
- Vercel build still succeeds from repo root
- semantic search API file still parses
- expected build outputs still exist
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.bootstrap import project_python_executable


PYTHON = project_python_executable()


@dataclass(frozen=True)
class SmokeStep:
    name: str
    cmd: list[str]


def run_step(step: SmokeStep) -> bool:
    print(f"\n==> {step.name}", flush=True)
    print(f"    $ {' '.join(step.cmd)}", flush=True)
    completed = subprocess.run(step.cmd, cwd=PROJECT_ROOT)
    if completed.returncode != 0:
        print(f"    FAIL ({completed.returncode})", flush=True)
        return False
    print("    PASS", flush=True)
    return True


def verify_outputs() -> bool:
    print("\n==> Verifying build outputs", flush=True)
    required_paths = [
        PROJECT_ROOT / "blog" / "public",
        PROJECT_ROOT / "blog" / "public" / "pagefind",
        PROJECT_ROOT / "api" / "search.js",
    ]
    missing = [path for path in required_paths if not path.exists()]
    if missing:
        for path in missing:
            print(f"    MISSING: {path}", flush=True)
        return False
    for path in required_paths:
        print(f"    OK: {path}", flush=True)
    return True


def main() -> int:
    os.chdir(PROJECT_ROOT)
    steps = [
        SmokeStep("CLI help: ingest", [PYTHON, "app/main.py", "--help"]),
        SmokeStep("CLI help: publish", [PYTHON, "app/cli/publish.py", "--help"]),
        SmokeStep("CLI help: workflow add", [PYTHON, "scripts/workflow.py", "add", "--help"]),
        SmokeStep("CLI help: workflow ship", [PYTHON, "scripts/workflow.py", "ship", "--help"]),
        SmokeStep("API syntax: search", ["node", "--check", "api/search.js"]),
        SmokeStep("Workflow publish current data", [PYTHON, "scripts/workflow.py", "publish"]),
        SmokeStep("Workflow ship dry run", [PYTHON, "scripts/workflow.py", "ship", "--dry-run"]),
        SmokeStep("Vercel root build", ["npm", "run", "vercel-build"]),
    ]

    for step in steps:
        if not run_step(step):
            return 1

    if not verify_outputs():
        print("\nSmoke test failed during output verification.", flush=True)
        return 1

    print("\nSmoke test passed.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
