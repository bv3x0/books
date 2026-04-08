from __future__ import annotations

import site
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = PROJECT_ROOT / ".venv"


def _venv_site_packages() -> list[Path]:
    version_dir = f"python{sys.version_info.major}.{sys.version_info.minor}"
    candidates = [
        VENV_DIR / "lib" / version_dir / "site-packages",
        VENV_DIR / "Lib" / "site-packages",
    ]
    return [path for path in candidates if path.exists()]


def bootstrap_project_site_packages() -> Path | None:
    for site_packages in _venv_site_packages():
        site_packages_str = str(site_packages)
        if site_packages_str not in sys.path:
            site.addsitedir(site_packages_str)
        return site_packages
    return None


def project_python_executable() -> str:
    executable = Path(sys.executable).resolve()
    if executable.exists() and VENV_DIR in executable.parents:
        return str(executable)

    candidates = [
        VENV_DIR / "bin" / "python",
        VENV_DIR / "Scripts" / "python.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    return sys.executable or "python3"
