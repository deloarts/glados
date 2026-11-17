"""
src.modules.platform.const.VERSION is read out of pyproject.toml at *import* time, and
src.modules.platform.const is imported transitively by every ORM model, so a missing
pyproject.toml does not degrade the version string, it kills every runtime
entrypoint (gunicorn, `alembic upgrade head`, the CLI) before it starts.
That is deliberate: /health, the host endpoint and the glados_app_info
metric feed the frontend/backend skew check, so reporting a made-up
version is worse than refusing to boot.

The cost of that strictness is that the prod image MUST ship the file. It
did not, and the staging deploy crash-looped in the entrypoint's migration
step (the dev stage does `COPY . .`, which is why it only ever failed in
prod). These tests pin both halves: the loader stays strict, and the prod
stage keeps copying what the loader needs.
"""

import re
from pathlib import Path

import pytest

from src.modules.platform import const

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO_ROOT / "docker" / "backend.Dockerfile"


def _prod_stage() -> str:
    """The `FROM ... AS prod` stage only: the dev stage's blanket
    `COPY . .` would otherwise satisfy every assertion below."""
    text = DOCKERFILE.read_text()
    match = re.search(r"^FROM .+ AS prod$", text, re.MULTILINE)
    assert match is not None, "prod stage not found in backend.Dockerfile"
    rest = text[match.end() :]
    next_stage = re.search(r"^FROM .+ AS \w+$", rest, re.MULTILINE)
    return rest[: next_stage.start()] if next_stage else rest


def _prod_copy_sources() -> list[str]:
    return [
        source
        for line in _prod_stage().splitlines()
        if (stripped := line.strip()).startswith("COPY ")
        # `COPY --from=builder ...` pulls from another stage, not the build
        # context, so it says nothing about which repo files are shipped.
        and not stripped.startswith("COPY --from=")
        for source in stripped.split()[1:-1]
    ]


def test_version_matches_the_pyproject_the_loader_reads():
    import tomllib

    with (REPO_ROOT / "pyproject.toml").open("rb") as f:
        assert tomllib.load(f)["project"]["version"] == const.VERSION


def test_load_version_raises_when_pyproject_is_missing(tmp_path, monkeypatch):
    # _load_version() resolves pyproject.toml relative to the module's
    # __file__, looked up at call time, so relocating it is enough to
    # reproduce the prod image's layout without touching the real repo.
    orphan = tmp_path / "src" / "modules" / "platform" / "const.py"
    orphan.parent.mkdir(parents=True)
    orphan.touch()
    monkeypatch.setattr(const, "__file__", str(orphan))

    with pytest.raises(FileNotFoundError):
        const._load_version()


def test_load_version_reads_the_adjacent_pyproject(tmp_path, monkeypatch):
    orphan = tmp_path / "src" / "modules" / "platform" / "const.py"
    orphan.parent.mkdir(parents=True)
    orphan.touch()
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "9.9.9"\n')
    monkeypatch.setattr(const, "__file__", str(orphan))

    assert const._load_version() == "9.9.9"


def test_prod_image_copies_pyproject_so_the_version_loader_can_boot():
    assert "pyproject.toml" in _prod_copy_sources()


def test_prod_image_copies_the_rest_of_the_runtime_tree():
    sources = _prod_copy_sources()
    for required in ("src/", "alembic/", "alembic.ini"):
        assert required in sources
