"""
docker/entrypoint.sh is a shell script, not Python, so it cannot be
imported or exercised by the rest of the suite. `sh -n` (parse-only, no
execution) catches syntax errors without docker; the case-arm assertions
are plain text checks that the allowlisted dispatch (recovery commands +
the maintenance sidecar) is actually present, so a future edit that
silently drops one of them fails a test instead of only surfacing at
deploy time. See docs/OPERATIONS.md sections 5 and 6 for what each case runs.
"""

import os
import subprocess
from pathlib import Path

ENTRYPOINT = Path(__file__).resolve().parents[2] / "docker" / "entrypoint.sh"


def test_entrypoint_is_present():
    assert ENTRYPOINT.is_file()


def test_entrypoint_parses_without_syntax_errors():
    result = subprocess.run(
        ["sh", "-n", str(ENTRYPOINT)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_entrypoint_dispatches_restore_and_admin_before_migrations():
    text = ENTRYPOINT.read_text()
    dispatch_index = text.index("restore|admin")
    migration_index = text.index("alembic upgrade head")
    assert dispatch_index < migration_index
    assert 'exec python -m "src.bootstrap.cli.${cmd}" "$@"' in text


def test_entrypoint_dispatches_the_maintenance_sidecar_command():
    text = ENTRYPOINT.read_text()
    assert "maintenance)" in text
    assert "exec sleep infinity" in text
    # Same allowlisted case block as restore|admin, not a bolted-on branch.
    case_start = text.index('case "$1" in')
    case_end = text.index("esac")
    assert case_start < text.index("maintenance)") < case_end


def test_prometheus_multiproc_dir_is_created_before_migrations_and_wiped_after():
    text = ENTRYPOINT.read_text()
    mkdir_index = text.index('mkdir -p "$PROMETHEUS_MULTIPROC_DIR"')
    migration_index = text.index("alembic upgrade head")
    rm_index = text.index('rm -rf "$PROMETHEUS_MULTIPROC_DIR"/*')
    exec_index = text.rindex('exec "$@"')
    assert mkdir_index < migration_index < rm_index < exec_index


def _run_entrypoint(tmp_path, *, dump_exit: int, skip: str | None = None):
    """Runs the entrypoint with `python` and `alembic` replaced by stubs that
    record their calls, the dump stub exiting with `dump_exit`."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls"
    (bin_dir / "python").write_text(f'#!/bin/sh\necho "python $*" >> {calls}\nexit {dump_exit}\n')
    (bin_dir / "alembic").write_text(f'#!/bin/sh\necho "alembic $*" >> {calls}\n')
    for stub in bin_dir.iterdir():
        stub.chmod(0o755)
    env = {key: value for key, value in os.environ.items() if key != "PROMETHEUS_MULTIPROC_DIR"}
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env.pop("GLADOS_SKIP_PRE_MIGRATION_DUMP", None)
    if skip is not None:
        env["GLADOS_SKIP_PRE_MIGRATION_DUMP"] = skip
    result = subprocess.run(
        ["sh", str(ENTRYPOINT), "true"], capture_output=True, text=True, env=env
    )
    recorded = calls.read_text().splitlines() if calls.exists() else []
    return result, recorded


def test_the_pre_migration_dump_runs_before_the_migrations(tmp_path):
    result, calls = _run_entrypoint(tmp_path, dump_exit=0)

    assert result.returncode == 0, result.stderr
    assert calls == [
        "python -m src.bootstrap.cli.admin pre-migration-dump",
        "alembic upgrade head",
    ]


def test_a_failed_dump_stops_the_start_without_migrating(tmp_path):
    result, calls = _run_entrypoint(tmp_path, dump_exit=1)

    assert result.returncode == 1
    assert calls == ["python -m src.bootstrap.cli.admin pre-migration-dump"]
    assert "GLADOS_SKIP_PRE_MIGRATION_DUMP=true" in result.stderr


def test_the_skip_variable_migrates_without_a_dump(tmp_path):
    result, calls = _run_entrypoint(tmp_path, dump_exit=1, skip="true")

    assert result.returncode == 0, result.stderr
    assert calls == ["alembic upgrade head"]
    assert "without a pre-migration dump" in result.stderr


def test_any_other_skip_value_still_takes_the_dump(tmp_path):
    result, calls = _run_entrypoint(tmp_path, dump_exit=0, skip="yes")

    assert result.returncode == 0, result.stderr
    assert calls[0] == "python -m src.bootstrap.cli.admin pre-migration-dump"


def test_a_one_off_command_runs_without_the_multiprocess_metrics_dir(tmp_path):
    """`docker compose run backend restore` inherits the backend's
    PROMETHEUS_MULTIPROC_DIR, whose directory only the server start creates;
    the command must not see it, or loading the app fails."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    seen = tmp_path / "seen"
    (bin_dir / "python").write_text(
        f'#!/bin/sh\necho "dir=${{PROMETHEUS_MULTIPROC_DIR:-unset}} args=$*" > {seen}\n'
    )
    (bin_dir / "python").chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["PROMETHEUS_MULTIPROC_DIR"] = str(tmp_path / "missing")
    result = subprocess.run(
        ["sh", str(ENTRYPOINT), "restore", "--backup", "key"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert seen.read_text().strip() == "dir=unset args=-m src.bootstrap.cli.restore --backup key"
