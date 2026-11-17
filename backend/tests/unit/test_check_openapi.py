"""
Step B of scripts/check_openapi.py, the freeze of the `pat` snapshot once its
minor is released. Under `--strict`, which CI turns on, a freeze check that
cannot run fails; locally it only warns. git is replaced by a fake that
answers each command the step runs, so no test touches the real repository.
"""

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from scripts import check_openapi

_FROZEN = '{"paths": {}}\n'


class _FakeGit:
    """Answers `git fetch --tags`, `git tag --list` and `git show` the way a
    test configures it."""

    def __init__(
        self,
        *,
        fetch_ok: bool = True,
        tags: tuple[str, ...] = ("v1.2.0", "v1.2.1"),
        snapshot_at_tag: str | None = _FROZEN,
    ) -> None:
        self.fetch_ok = fetch_ok
        self.tags = tags
        self.snapshot_at_tag = snapshot_at_tag
        self.shown: list[str] = []

    def __call__(self, cmd: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        if cmd[:2] == ["git", "fetch"]:
            if self.fetch_ok:
                return subprocess.CompletedProcess(cmd, 0, "", "")
            return subprocess.CompletedProcess(cmd, 128, "", "could not read from remote")
        if cmd[:2] == ["git", "tag"]:
            return subprocess.CompletedProcess(cmd, 0, "\n".join(self.tags) + "\n", "")
        if cmd[:2] == ["git", "show"]:
            self.shown.append(cmd[2])
            if self.snapshot_at_tag is None:
                return subprocess.CompletedProcess(cmd, 128, "", "path does not exist")
            return subprocess.CompletedProcess(cmd, 0, self.snapshot_at_tag, "")
        raise AssertionError(f"unexpected command {cmd}")


@pytest.fixture
def snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A `pat` snapshot for minor 1.2 under a throwaway repository root."""
    monkeypatch.setattr(check_openapi, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_openapi, "current_minor", lambda: "1.2")
    target = tmp_path / "openapi" / "pat-v1.2.json"
    target.parent.mkdir()
    target.write_text(_FROZEN)
    monkeypatch.setattr(check_openapi, "snapshot_path", lambda surface: target)
    return target


@pytest.fixture
def use_git(monkeypatch: pytest.MonkeyPatch) -> Callable[[_FakeGit], _FakeGit]:
    def _use(fake: _FakeGit) -> _FakeGit:
        monkeypatch.setattr(check_openapi.subprocess, "run", fake)
        return fake

    return _use


@pytest.mark.parametrize("strict", [True, False])
def test_unchanged_snapshot_passes(
    snapshot: Path, use_git: Callable[[_FakeGit], _FakeGit], strict: bool
) -> None:
    fake = use_git(_FakeGit())

    assert check_openapi._step_b(strict=strict)
    # The lowest tag of the minor is the frozen one.
    assert fake.shown == ["v1.2.0:openapi/pat-v1.2.json"]


@pytest.mark.parametrize("strict", [True, False])
def test_unreleased_minor_passes(
    snapshot: Path, use_git: Callable[[_FakeGit], _FakeGit], strict: bool
) -> None:
    use_git(_FakeGit(tags=("v1.1.0", "v1.2.0-rc1")))

    assert check_openapi._step_b(strict=strict)


def test_failed_tag_fetch_fails_under_strict(
    snapshot: Path,
    use_git: Callable[[_FakeGit], _FakeGit],
    capsys: pytest.CaptureFixture[str],
) -> None:
    use_git(_FakeGit(fetch_ok=False))

    assert not check_openapi._step_b(strict=True)
    assert "could not read from remote" in capsys.readouterr().out


def test_failed_tag_fetch_only_warns_locally(
    snapshot: Path,
    use_git: Callable[[_FakeGit], _FakeGit],
    capsys: pytest.CaptureFixture[str],
) -> None:
    use_git(_FakeGit(fetch_ok=False))

    assert check_openapi._step_b(strict=False)
    assert capsys.readouterr().out.startswith("Warning: `git fetch --tags` failed")


def test_snapshot_missing_at_tag_fails_under_strict(
    snapshot: Path, use_git: Callable[[_FakeGit], _FakeGit]
) -> None:
    use_git(_FakeGit(snapshot_at_tag=None))

    assert not check_openapi._step_b(strict=True)


def test_snapshot_missing_at_tag_only_warns_locally(
    snapshot: Path,
    use_git: Callable[[_FakeGit], _FakeGit],
    capsys: pytest.CaptureFixture[str],
) -> None:
    use_git(_FakeGit(snapshot_at_tag=None))

    assert check_openapi._step_b(strict=False)
    assert "not found at tag v1.2.0" in capsys.readouterr().out


@pytest.mark.parametrize("strict", [True, False])
def test_changed_contract_fails_and_names_the_bump_script(
    snapshot: Path,
    use_git: Callable[[_FakeGit], _FakeGit],
    capsys: pytest.CaptureFixture[str],
    strict: bool,
) -> None:
    use_git(_FakeGit())
    snapshot.write_text('{"paths": {"/api/v1/pat/new": {}}}\n')

    assert not check_openapi._step_b(strict=strict)
    out = capsys.readouterr().out
    assert "scripts/bump_version.sh 1.3.0" in out
    assert "poetry version" not in out


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({}, False),
        ({"CI": "true"}, True),
        ({"GITHUB_ACTIONS": "true"}, True),
        ({"CI": "false"}, False),
    ],
)
def test_strict_by_default_on_ci(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str], expected: bool
) -> None:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    assert check_openapi.strict_by_default() is expected


@pytest.mark.parametrize(
    ("argv", "env", "exit_code"),
    [(["--strict"], {}, 1), ([], {"CI": "true"}, 1), ([], {}, 0)],
)
def test_main_fails_closed_when_strict(
    snapshot: Path,
    use_git: Callable[[_FakeGit], _FakeGit],
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    env: dict[str, str],
    exit_code: int,
) -> None:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(check_openapi, "_step_a", lambda: True)
    use_git(_FakeGit(fetch_ok=False))

    assert check_openapi.main(argv) == exit_code
