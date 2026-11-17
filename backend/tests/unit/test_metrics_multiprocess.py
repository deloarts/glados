"""
Multiprocess-mode coverage for src/read/adapters/inbound/api/metrics.py and
src/modules/platform/infrastructure/gunicorn_conf.py.

prometheus_client picks single- vs multi-process value storage at IMPORT
time from PROMETHEUS_MULTIPROC_DIR (prometheus_client/values.py's
get_value_class(), read once into a module-level `ValueClass`). Once this
test process has imported prometheus_client (which every other test module
in this suite does, transitively, well before this file ever runs),
multiprocess mode can no longer be toggled on for it. Both scenarios below
therefore run in a fresh subprocess, launched with PROMETHEUS_MULTIPROC_DIR
already set in its environment before its Python interpreter starts.
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TIMEOUT_SECONDS = 9  # keep the whole test well under the 10s budget


def _run(script: str, *, prometheus_multiproc_dir: str) -> subprocess.CompletedProcess[str]:
    """Runs `script` in a fresh interpreter with PROMETHEUS_MULTIPROC_DIR
    set from the start; see the module docstring for why that has to
    happen before Python imports prometheus_client, not after.

    Starts from a full copy of this process' own environment (PATH,
    locale, and the SECURITY__/DATABASE__/REDIS__/INIT__ settings
    Settings() requires, already set by tests/conftest.py's
    os.environ.setdefault calls before any test in this session executes),
    overriding only what this test actually cares about.
    """
    # The database file lives in a subdirectory: prometheus_client reads every
    # *.db file directly inside PROMETHEUS_MULTIPROC_DIR as a metrics file, and
    # the state collector opens the database before the registry is read.
    db_dir = Path(prometheus_multiproc_dir) / "database"
    db_dir.mkdir(exist_ok=True)
    env = {
        **os.environ,
        "DATABASE__URL": f"sqlite:///{db_dir}/metrics_test.db",
        "PROMETHEUS_MULTIPROC_DIR": prometheus_multiproc_dir,
    }
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_SECONDS,
    )


class TestMultiprocessScrapeSumsAcrossProcesses:
    def test_livesum_gauge_is_summed_across_a_forked_process(self, tmp_path):
        """Sets glados_live_connections to 2 in this (the subprocess'
        "child") process and to 1 in a forked grandchild. It uses fork(), not
        multiprocessing's default spawn/forkserver, because the whole
        point is exercising prometheus_client's real per-pid file split
        under a shared PROMETHEUS_MULTIPROC_DIR, which only a real fork()
        (COW memory, distinct pid) reproduces the way gunicorn's workers
        do. metrics_response() is our own production code path (not a
        hand-rolled MultiProcessCollector call), so this also proves
        GladosStateCollector coexists with the multiprocess registry
        without raising.
        """
        script = """
            import asyncio
            import multiprocessing
            import sys

            from prometheus_client.parser import text_string_to_metric_families

            from src.modules.platform.adapters.inbound.api.http_metrics import LIVE_CONNECTIONS
            from src.read.adapters.inbound.api.metrics import metrics_response

            def _set_in_grandchild():
                LIVE_CONNECTIONS.set(1)

            ctx = multiprocessing.get_context("fork")
            grandchild = ctx.Process(target=_set_in_grandchild)
            grandchild.start()
            grandchild.join(timeout=5)
            assert grandchild.exitcode == 0, grandchild.exitcode

            LIVE_CONNECTIONS.set(2)  # this process' own contribution

            response = asyncio.run(metrics_response())
            body = response.body.decode()

            families = {f.name: f for f in text_string_to_metric_families(body)}
            live = families["glados_live_connections"]
            assert len(live.samples) == 1, live.samples
            value = live.samples[0].value
            assert value == 3.0, f"expected 2 (self) + 1 (grandchild) == 3, got {value}"

            print("OK", grandchild.pid)
        """
        result = _run(script, prometheus_multiproc_dir=str(tmp_path))

        assert result.returncode == 0, result.stdout + result.stderr
        assert "OK" in result.stdout


class TestChildExitCleansUpDeadProcessFiles:
    def test_child_exit_removes_the_dead_pids_livesum_file(self, tmp_path):
        script = """
            import glob
            import multiprocessing
            import os

            from src.modules.platform.adapters.inbound.api.http_metrics import LIVE_CONNECTIONS
            from src.modules.platform.infrastructure.gunicorn_conf import child_exit

            def _set_in_grandchild():
                LIVE_CONNECTIONS.set(1)

            ctx = multiprocessing.get_context("fork")
            grandchild = ctx.Process(target=_set_in_grandchild)
            grandchild.start()
            grandchild.join(timeout=5)
            assert grandchild.exitcode == 0, grandchild.exitcode

            pattern = os.path.join(
                os.environ["PROMETHEUS_MULTIPROC_DIR"], f"gauge_livesum_{grandchild.pid}.db"
            )
            assert glob.glob(pattern), "grandchild's file should exist right after it exits"

            class FakeWorker:
                pid = grandchild.pid

            child_exit(None, FakeWorker())

            assert not glob.glob(pattern), "child_exit should have removed the dead pid's file"
            print("OK")
        """
        result = _run(script, prometheus_multiproc_dir=str(tmp_path))

        assert result.returncode == 0, result.stdout + result.stderr
        assert "OK" in result.stdout

    def test_child_exit_is_a_no_op_without_the_env_var(self, tmp_path):
        """gunicorn_conf.py is loaded by every gunicorn invocation,
        including a hypothetical future one that never sets
        PROMETHEUS_MULTIPROC_DIR: child_exit must not blow up looking
        for a directory that was never configured."""
        script = """
            import os

            os.environ.pop("PROMETHEUS_MULTIPROC_DIR", None)

            from src.modules.platform.infrastructure.gunicorn_conf import child_exit

            class FakeWorker:
                pid = 999999

            child_exit(None, FakeWorker())  # must not raise
            print("OK")
        """
        result = _run(script, prometheus_multiproc_dir=str(tmp_path))

        assert result.returncode == 0, result.stdout + result.stderr
        assert "OK" in result.stdout
