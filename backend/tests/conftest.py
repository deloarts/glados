"""
Settings environment and suite-wide fixtures for the whole test suite.

`src/modules/platform/infrastructure/config/settings.py` builds its `cfg` singleton at
import time and requires security/database/redis/init values, so any
module that does `from ...settings import cfg` at module level, notably
`src/modules/platform/infrastructure/security/token.py`, imports under pytest only
because this file sets those values first.

The database URL points at a throwaway SQLite file, created fresh per
pytest session and deleted on exit. A *file* rather than `sqlite://`
(in-memory) on purpose: an in-memory SQLite database is scoped to its
connection, and the integration suite has several (the request-scoped
`get_db` dependency, plus `DatabaseLoggingMiddleware`, which opens its
own `SessionLocal()`), so an in-memory URL would give each one a
separate empty database.

Nothing here *reads* from Redis, the integration client never runs the
app's lifespan, so the event-bus workers that would need it are never
started. Writes are a different story: publishing goes through the normal
DI graph, so the URL still points at a dedicated database (see below) and
the integration suite additionally stubs the bus out entirely.

If ENV_FILE is set, this backs off entirely and lets the real config
load, since environment variables take precedence over an env file in
pydantic-settings and would otherwise silently override a developer's
actual configuration, including pointing the test suite at their real
development database. That back-off is why tests/integration/conftest.py
asserts on the resolved URL before it creates or truncates anything.
"""

import atexit
import logging
import os
import shutil
import tempfile
from collections.abc import Iterator

import pytest
from _pytest.logging import LogCaptureFixture
from hypothesis import HealthCheck
from hypothesis import settings

# The schedule walk runs in the request under test, so a test reads the
# planned dates a write moved right after it.
os.environ.setdefault("SCHEDULING__RECOMPUTE_IN_BACKGROUND", "false")

if not os.getenv("ENV_FILE"):
    _tmp_dir = tempfile.mkdtemp(prefix="glados-test-db-")
    atexit.register(shutil.rmtree, _tmp_dir, True)

    os.environ.setdefault("DEBUG", "false")
    os.environ.setdefault("SECURITY__SECRET_KEY_PERSISTENT", "test-persistent-key")
    os.environ.setdefault("SECURITY__SECRET_KEY_NON_PERSISTENT", "test-non-persistent-key")
    os.environ.setdefault("SECURITY__ENCRYPTION_KEY", "test-encryption-key")
    # The two per-process values below are set by this file unless the
    # developer exported them. An xdist worker inherits the controller's
    # environment, values this file set there included, so the keys it set
    # are recorded and a worker replaces them with its own instead of
    # sharing the controller's SQLite file and Redis database.
    _set_here = set(filter(None, os.environ.get("GLADOS_TEST_SET_HERE", "").split(",")))
    for _key in ("DATABASE__URL", "REDIS__URL"):
        if _key in _set_here or _key not in os.environ:
            _set_here.add(_key)
    os.environ["GLADOS_TEST_SET_HERE"] = ",".join(sorted(_set_here))

    if "DATABASE__URL" in _set_here:
        os.environ["DATABASE__URL"] = f"sqlite:///{_tmp_dir}/test.db"
    # Database 15, never 0: the integration suite publishes real domain
    # events through the normal DI graph, and a developer's running dev
    # backend has event-bus consumer groups on the `glados:events` stream
    # of whichever database it is pointed at. Sharing database 0 would let
    # the live app consume test events and write notifications into the
    # development database addressed to whichever user happens to hold the
    # test-local user id. Under pytest-xdist each worker gets its own
    # database, counting down from 15 (gw0 to 15, gw1 to 14, ...), which caps
    # a run at 15 workers; more are refused rather than letting two workers
    # share a database.
    _worker = os.environ.get("PYTEST_XDIST_WORKER", "gw0")
    _redis_db = 15 - int(_worker.removeprefix("gw"))
    if _redis_db < 1:
        raise pytest.UsageError(
            f"xdist worker {_worker} has no free Redis database; run with --maxprocesses 15"
        )
    if "REDIS__URL" in _set_here:
        os.environ["REDIS__URL"] = f"redis://localhost:6379/{_redis_db}"
    os.environ.setdefault("INIT__FULL_NAME", "Test Admin")
    os.environ.setdefault("INIT__MAIL", "admin@example.com")
    os.environ.setdefault("INIT__PASSWORD", "test-password")


def pytest_configure(config: pytest.Config) -> None:
    """Fills the Platform registries before collection, as every process
    entry point does (src/bootstrap/registrations.py), so a test that encodes
    an event or parametrizes over a registry sees every module's entries."""
    from src.bootstrap.registrations import register_all

    register_all()


# Hypothesis profiles. `dev` is loaded by default and keeps Hypothesis' own
# defaults with 100 examples, so a local run explores new examples each time
# and replays failures from the example database in `.hypothesis/`. CI runs
# with `--hypothesis-profile ci`, which the Hypothesis pytest plugin loads
# after this file: four times the examples, derandomized so every run checks
# the same examples, without an example database, without a deadline (coverage
# tracing slows each example down), and with the blob that reproduces a
# failure printed. The stateful models scale these counts by a weight, see
# tests/unit/lifecycle/_profiles.py. The dev profile is built on Hypothesis'
# plain defaults, because a new profile otherwise inherits whatever profile is
# active, and Hypothesis loads its own derandomized profile when it detects CI.
settings.register_profile("dev", parent=settings.get_profile("default"), max_examples=100)
settings.register_profile(
    "ci",
    max_examples=400,
    derandomize=True,
    database=None,
    deadline=None,
    print_blob=True,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile("dev")


@pytest.fixture(autouse=True)
def _clear_maintenance_cache() -> None:
    """admin_settings_repository.py caches get_maintenance()'s result in a
    process-global, module-level variable for MAINTENANCE_CACHE_TTL_S seconds
    (see that module's docstring). That cache outlives any one test's database
    session or engine, so without this a value cached by one test could still
    be returned, stale, by a later test running within the same TTL window,
    across the whole suite, not just within tests/integration, since the unit
    tests that exercise the repository directly use their own throwaway
    engines. Imported inside the fixture body, not at module scope, for the
    same reason this file sets DATABASE__URL etc. above before anything reads
    them: the repository module pulls in the ORM/settings import chain, and
    this file must finish configuring the environment first.
    """
    from src.modules.platform.adapters.outbound.persistence.repositories.platform_settings_repository import (
        clear_maintenance_cache,
    )

    clear_maintenance_cache()


@pytest.fixture(autouse=True)
def _reset_loop_bound_clients() -> None:
    """The async Redis client and the cached PDM gateways (httpx.AsyncClient)
    are created lazily and cached per process, and each is bound to the
    event loop it first ran on. pytest-asyncio gives every test its own
    loop, so a client cached by one test would fail in the next one; drop
    the caches before each test so every test builds its own. Imported
    inside the body for the same reason as _clear_maintenance_cache above."""
    from src.modules.external_data.adapters.outbound.external.pdm import factory as pdm_factory
    from src.modules.platform.infrastructure.redis_client import get_async_redis_client

    get_async_redis_client.cache_clear()
    pdm_factory._gateways.clear()


@pytest.fixture(autouse=True)
def _pin_totp_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pins pyotp's notion of "now" to the middle of the current 30 second
    step for the whole test. A test generates a code with TOTP.now() and the
    app verifies it a moment later with TOTP.verify(), which accepts only the
    current step; a test that happened to straddle a step boundary failed
    with an InvalidTOTPCodeError for a perfectly valid code. Pinning both
    calls to one instant removes that race without widening the app's
    verification window."""
    import datetime

    import pyotp

    step = 30
    now = datetime.datetime.now().timestamp()
    pinned = datetime.datetime.fromtimestamp(now - now % step + step / 2)
    original_verify = pyotp.TOTP.verify

    def now_pinned(self: pyotp.TOTP) -> str:
        return self.at(pinned)

    def verify_pinned(
        self: pyotp.TOTP,
        otp: str,
        for_time: datetime.datetime | None = None,
        valid_window: int = 0,
    ) -> bool:
        return original_verify(self, otp, for_time or pinned, valid_window)

    monkeypatch.setattr(pyotp.TOTP, "now", now_pinned)
    monkeypatch.setattr(pyotp.TOTP, "verify", verify_pinned)


@pytest.fixture
def glados_caplog(caplog: LogCaptureFixture) -> Iterator[LogCaptureFixture]:
    """`caplog`, scoped to the app's own logger.

    `src/modules/platform/infrastructure/logging/logger.py` sets `log.propagate = False` on
    `logging.getLogger("glados")` deliberately, so its records never reach
    the root logger and never double-print via uvicorn's own root handler,
    which also means plain `caplog` (root-only) never sees them. This
    attaches caplog's own capture handler directly to the "glados" logger
    for the duration of the test (removed in teardown), so `.records`
    behaves exactly like `caplog.records` otherwise would. It lives here
    rather than in a package conftest so unit and integration tests share it.
    """
    caplog.set_level(logging.DEBUG, logger="glados")
    glados_logger = logging.getLogger("glados")
    glados_logger.addHandler(caplog.handler)
    try:
        yield caplog
    finally:
        glados_logger.removeHandler(caplog.handler)
