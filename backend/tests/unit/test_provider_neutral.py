"""
Glados talks to time tracking and to the stock system only through the
provider-neutral contracts of the time tracking service and the stock
service, so no code, test, doc, migration or locale in the repository
names the systems those services were written for.

The searched names are assembled at run time, so this file does not match
itself. The stock system's name is a prefix of "logistics" and of the
German "Logistik", which stay allowed.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
_NAME = "".join(("ti", "mas"))
_PATTERN = re.compile("|".join((_NAME, "".join(("lo", "gis")) + "(?!ti[ck])")))

_ROOTS = (
    "backend/src",
    "backend/tests",
    "backend/scripts",
    "backend/alembic",
    "backend/openapi",
    "frontend/src",
    "docs",
)
_ROOT_FILES = (
    "README.md",
    "CLAUDE.md",
    "backend/CLAUDE.md",
    "backend/pyproject.toml",
    "docker-compose.yml",
    "docker-compose.dev.yml",
    ".env.example",
    ".env.dev.example",
)
_SUFFIXES = {".py", ".ts", ".vue", ".md", ".json", ".toml", ".yml", ".yaml", ".scss", ".css"}
_SKIPPED_PARTS = {"node_modules", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"}


def _candidates() -> list[Path]:
    files = [REPO_ROOT / name for name in _ROOT_FILES if (REPO_ROOT / name).is_file()]
    for root in _ROOTS:
        files.extend(
            path
            for path in (REPO_ROOT / root).rglob("*")
            if path.is_file()
            and path.suffix in _SUFFIXES
            and not _SKIPPED_PARTS.intersection(path.parts)
        )
    return files


def test_no_file_names_a_provider_system() -> None:
    offenders = []
    for path in _candidates():
        relative = path.relative_to(REPO_ROOT).as_posix()
        if _PATTERN.search(relative.lower()) or _PATTERN.search(
            path.read_text(errors="ignore").lower()
        ):
            offenders.append(relative)

    assert offenders == [], f"provider-specific names found in: {offenders}"
