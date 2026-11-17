"""Application-wide constants: API endpoints, pagination limits, upload
constraints, and defaults seeded from environment."""

import tomllib
from pathlib import Path


def _load_version() -> str:
    """Single source of truth for the app version: [project].version in
    pyproject.toml. That file is COPY'd into /app alongside src/ in the
    prod image (see docker/backend.Dockerfile), so this resolves the same
    way in-container as it does locally."""
    pyproject_path = Path(__file__).resolve().parents[3] / "pyproject.toml"
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)
    return str(data["project"]["version"])


def contract_minor(version: str) -> str:
    """The `major.minor` part of a version, e.g. "1.2" for "1.2.3". The `pat`
    contract only changes with the minor, so this names the contract a
    backend serves."""
    parts = version.split(".")
    if len(parts) < 2:
        raise ValueError(f"Cannot parse major.minor from version {version!r}")
    return f"{int(parts[0])}.{int(parts[1])}"


VERSION: str = _load_version()
PAT_CONTRACT: str = contract_minor(VERSION)
NAME = "glados"

# Sent on every `pat` response, so a client learns the backend version from
# whichever call it makes first.
VERSION_HEADER = "X-Glados-Version"

SYSTEM_USER = "system"


SERVER_DEFAULT_AUTH_PROVIDER = "local"
SERVER_DEFAULT_LANGUAGE = "enGB"
SERVER_DEFAULT_TIMEZONE = "Europe/Vienna"
SERVER_DEFAULT_DATE_FORMAT = "iso"
SERVER_DEFAULT_THEME_PRESET = "Aura"
SERVER_DEFAULT_THEME_SURFACE = "slate"
SERVER_DEFAULT_THEME_PRIMARY = "emerald"
SERVER_DEFAULT_THEME_DARK_MODE = True
SERVER_DEFAULT_BUTTON_FLAT_STYLE = True
SERVER_DEFAULT_TABLE_GRIDLINES = False
SERVER_DEFAULT_TABLE_STRIPED_ROWS = True
SERVER_DEFAULT_START_PAGE = "dashboard"
# Presentation-only display currency (ISO 4217 alphabetic code); prices are
# always stored and transported as plain integer cents, see
# AdminGeneralSettings.currency.
SERVER_DEFAULT_CURRENCY = "EUR"


API_WEB = "/api/v1/web"
API_PAT = "/api/v1/pat"
API_KEY = "/api/v1/key"
API_AUTH = "/api/v1/auth"
API_PUBLIC = "/api/v1/public"
# The MCP surface for AI agents (adapters/inbound/mcp/).
API_MCP = "/api/v1/mcp"


# Caps list requests so a bare request (limit omitted) never returns the
# entire table as data grows. DEFAULT_PAGE_SIZE is what an omitted limit
# resolves to; MAX_PAGE_SIZE is the hard ceiling
# even an explicit request can't exceed. See
# src/modules/platform/adapters/outbound/persistence/pagination.py (clamp_page) and each
# list endpoint's `limit: int | None = Query(..., le=MAX_PAGE_SIZE)`.
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 500

# Hard ceiling for any single uploaded request body, checked from the
# Content-Length header BEFORE the body is buffered into memory (see
# api/upload_limits.py). Above the largest per-category limit (100 MB
# STEP/STL) with headroom, so it never rejects a legitimate upload, it
# only stops an oversized body from being read into RAM in the first
# place. The bundled nginx (frontend/docker/nginx.conf) caps bodies at the
# same 110M so the body never reaches the app; keep the two in step.
MAX_UPLOAD_BYTES = 110 * 1024 * 1024
