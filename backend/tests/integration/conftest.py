"""
Fixtures for the API integration layer, whose tests drive real HTTP
requests through the actual FastAPI app rather than calling use cases
directly.

What this exercises that unit tests cannot:
  - routing and per-surface router mounting
  - FastAPI's dependency graph (every `Depends` chain in the modules'
    deps packages actually resolving at request time)
  - request/response schema validation
  - the domain-exception -> HTTP status mapping in exception_handlers.py
  - the real SQLAlchemy repositories against a live database

The app's lifespan is deliberately NOT run: requests go through
`httpx.AsyncClient` over `ASGITransport`, which never sends the lifespan
startup event, which is what keeps the suite hermetic, no Alembic
migrations, no event-bus workers. The schema is created directly from the
ORM metadata instead, through a separate synchronous engine on the same
SQLite file (`_ddl_engine`) that also seeds and truncates tables, so those
session-scoped and per-test chores never touch the event loop. Everything
a test does itself (`db`, `create_user`, `auth_headers`, requests) runs on
the app's async engine in the test's own loop.

Requests still resolve the real dependency graph, so use cases would stage
their domain events in the outbox table. `_no_event_bus` below overrides the
bus with an in-process recorder instead, so a test can assert on what was
published and nothing is staged at all.

The database is the throwaway SQLite file configured in tests/conftest.py.
Every test starts from an empty schema (see `_clean_tables`), so tests
cannot leak state into each other regardless of execution order.
`_guard_throwaway_database` refuses to run at all if that indirection has
been defeated, setting ENV_FILE makes tests/conftest.py back off, which
would otherwise point `create_all` and the per-test truncation at a real
Postgres database.
"""

import importlib
from collections.abc import AsyncIterator
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Iterator
from contextlib import AbstractContextManager
from contextlib import contextmanager
from datetime import UTC
from datetime import datetime

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.bootstrap.main import app
from src.modules.platform.adapters.inbound.api.deps.database import get_transactional_event_bus
from src.modules.platform.adapters.inbound.api.deps.services import get_backup_jobs_factory
from src.modules.platform.adapters.inbound.api.deps.services import get_login_attempt_tracker
from src.modules.platform.adapters.inbound.api.deps.services import get_replay_guard
from src.modules.platform.adapters.outbound.persistence.alembic_imports import model_module_names
from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_session_repository import (
    SqlAlchemyUserSessionRepository,
)
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.adapters.outbound.persistence.session import engine
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.entities.user_session import make_user_session
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.infrastructure.security.token import create_access_token
from tests.factories import TEST_PASSWORD
from tests.factories import make_user
from tests.integration._lifecycle_drift import assert_no_lifecycle_drift
from tests.integration._lifecycle_drift import checked_aggregates
from tests.integration._sqlite_similarity import similarity as _sqlite_similarity
from tests.integration.fakes import FakeBackupJobs
from tests.integration.fakes import FakeLoginAttemptTracker
from tests.integration.fakes import FakeReplayGuard

# DDL, seeding and truncation only: a plain synchronous engine on the same
# SQLite file the app's async engine uses (see the module docstring).
_ddl_engine = create_engine(cfg.database.url)

# Requests carry the same client address and host TestClient used, which
# session rows, trusted devices and the maintenance-mode IP allowlist read.
_TEST_CLIENT_ADDRESS = ("testclient", 50000)
_TEST_BASE_URL = "http://testserver"


def _new_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=_TEST_CLIENT_ADDRESS),
        base_url=_TEST_BASE_URL,
        follow_redirects=True,
    )


@event.listens_for(engine.sync_engine, "connect")
def _register_sqlite_similarity(dbapi_connection: object, connection_record: object) -> None:
    """The fuzzy fallback query calls
    `func.similarity(col, term) >= 0.3`, pg_trgm's function. Postgres has
    it natively; SQLite (this suite's engine, enforced by
    `_guard_throwaway_database` below) does not, so it needs registering
    per DBAPI connection as a scalar function. A no-op for any other
    dialect: this is defensive, since this suite's engine is always SQLite,
    not a claim that some other test module could safely point `engine` at
    Postgres and still get this covered.

    `tests.integration._sqlite_similarity.similarity` is a pure-Python
    approximation of pg_trgm's algorithm (see that module's docstring),
    not a byte-exact port, which is documented there as test-only
    infrastructure.
    """
    if engine.dialect.name != "sqlite":
        return
    dbapi_connection.create_function("similarity", 2, _sqlite_similarity)  # type: ignore[attr-defined]


class RecordingEventBus:
    """In-process stand-in for `OutboxEventBus`. Satisfies IEventBus,
    reaches no broker, and keeps what was published so a test can assert
    on it via the `published_events` fixture."""

    def __init__(self) -> None:
        self.events: list[object] = []

    async def publish(self, event: object) -> None:
        self.events.append(event)


_event_bus = RecordingEventBus()


_backup_jobs = FakeBackupJobs()


@pytest.fixture(scope="session", autouse=True)
def _no_real_backup_jobs() -> Iterator[None]:
    """No test may run a real backup. The run-now endpoint's background task
    otherwise shells out to pg_dump, which, handed this suite's SQLite URL,
    aims at localhost:5432 with no password and blocks forever on the
    terminal password prompt, hanging the whole run. The file job would copy
    real storage objects around for just as little reason."""
    app.dependency_overrides[get_backup_jobs_factory] = lambda: (
        lambda settings, db_url: _backup_jobs
    )
    yield
    app.dependency_overrides.pop(get_backup_jobs_factory, None)


@pytest.fixture(scope="session", autouse=True)
def _no_event_bus() -> Iterator[None]:
    """Records every event published during the suite in process instead of
    staging it in the outbox, see the module docstring."""
    # Leaving the bus live would both write event_outbox_table rows and hide
    # those events from the published_events fixture.
    app.dependency_overrides[get_transactional_event_bus] = lambda: _event_bus
    yield
    app.dependency_overrides.pop(get_transactional_event_bus, None)


@pytest.fixture
def published_events() -> Iterator[list[object]]:
    """The events published during a single test, oldest first."""
    _event_bus.events.clear()
    yield _event_bus.events
    _event_bus.events.clear()


@pytest.fixture(autouse=True)
def replay_guard() -> Iterator[FakeReplayGuard]:
    """Every test gets its own isolated, in-memory IReplayGuard.

    Function-scoped (unlike `_no_event_bus` above, which shares one
    instance for the whole session): a real RedisReplayGuard would work
    against actual Redis, whose claimed keys persist for their TTL across
    the whole test run, unlike the throwaway SQLite file, which resets
    per test. Two unrelated tests reusing the same low user id (routine
    here, since each test starts from an empty user_table) within the
    same 30-second TOTP step would then spuriously fail each other's
    verification. A fresh fake per test removes that cross-test coupling
    entirely; a test that wants to assert on claims (e.g. "the same code
    is rejected the second time") requests this fixture by name to get
    the instance in use.
    """
    fake = FakeReplayGuard()
    app.dependency_overrides[get_replay_guard] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_replay_guard, None)


@pytest.fixture(autouse=True)
def login_attempts() -> Iterator[FakeLoginAttemptTracker]:
    """Every test gets its own isolated, in-memory ILoginAttemptTracker, for
    the same reason as `replay_guard` above: the real tracker keeps
    failure counters and lockouts in Redis for minutes, so a test that
    locks out a low user id would make an unrelated later test (with the
    same id, routine since every test starts from an empty user_table) see
    a 429. Test modules that need their own instance still override the
    dependency themselves; this is only the default."""
    fake = FakeLoginAttemptTracker()
    app.dependency_overrides[get_login_attempt_tracker] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_login_attempt_tracker, None)


@pytest.fixture
async def seeded_security(db: AsyncSession) -> AdminSecuritySettings:
    """The security settings row InitDatabase would seed, for routes that
    confirm the caller's password: the confirmation goes through the login
    throttle, which reads it. Without a token lifetime cap, so a test may
    create a token without an expiry."""
    settings = AdminSecuritySettings(
        id=1,
        enforce_totp=False,
        allow_rfid_login=True,
        allow_local_login=True,
        enable_api_key_auth=False,
        min_password_length=8,
        session_timeout_minutes=1440,
        totp_trusted_device_days=0,
        max_login_attempts=5,
        lockout_duration_minutes=15,
        token_max_lifetime_days=0,
    )
    await SqlAlchemyAdminSettingsRepository(db).save_security(settings)
    await db.commit()
    return settings


@pytest.fixture(scope="session", autouse=True)
def _guard_throwaway_database() -> None:
    """Fail loudly rather than operate on a real database.

    `_schema` runs `create_all` and `_clean_tables` truncates every table
    after every test, so a URL pointing anywhere real would quietly empty
    a developer's development database. tests/conftest.py backs off
    whenever ENV_FILE is set, which makes that a single stray environment
    variable away.
    """
    url = str(_ddl_engine.url)
    if not url.startswith("sqlite"):
        pytest.exit(
            f"Integration tests refuse to run against {url!r}, they create and "
            "truncate every table. Unset ENV_FILE and DATABASE__URL so "
            "tests/conftest.py can point the suite at its throwaway SQLite file.",
            returncode=1,
        )


def _import_all_models() -> None:
    """Model modules are not imported by the package's __init__, so
    Base.metadata is empty until each one is loaded, without this,
    create_all() would silently create zero tables."""
    for name in model_module_names():
        importlib.import_module(name)


@pytest.fixture(scope="session", autouse=True)
def _schema(_guard_throwaway_database: None) -> None:
    """The database file is created fresh per pytest session and deleted
    on exit (tests/conftest.py), so there is nothing to drop first and
    nothing to clean up afterwards. Depends on the guard explicitly rather
    than relying on autouse ordering, create_all is the first thing that
    would touch a wrongly-configured database."""
    _import_all_models()
    Base.metadata.create_all(_ddl_engine)


@pytest.fixture(autouse=True)
def _clean_tables(_schema: None) -> Iterator[None]:
    """Empty every table between tests so execution order can never
    matter. Deletion order is irrelevant here: SQLite leaves foreign-key
    enforcement off by default, and the schema has a known mutually
    dependent pair (source_item_demand_item <-> production_lot) that has no
    valid topological order anyway."""
    yield
    with _ddl_engine.begin() as conn:
        for table in Base.metadata.tables.values():
            conn.execute(text(f'DELETE FROM "{table.name}"'))  # names from metadata


@pytest.fixture(autouse=True)
async def _no_lifecycle_drift(
    request: pytest.FixtureRequest, _clean_tables: None
) -> AsyncIterator[None]:
    """After every test and before the tables are emptied, the stored
    lifecycle fields of every aggregate the lifecycle reconciler writes must
    equal their derivation (tests/integration/_lifecycle_drift.py). The set
    is read when the check runs and is empty until the first aggregate moves
    onto the reconciler, so the check costs nothing before then."""
    yield
    if "allow_lifecycle_drift" not in request.fixturenames:
        await assert_no_lifecycle_drift(checked_aggregates())


@pytest.fixture
def allow_lifecycle_drift() -> None:
    """Requested by a test that leaves inconsistent lifecycle rows on
    purpose, such as a test of the drift report, so the drift check after it
    is skipped."""


@pytest.fixture(autouse=True)
def _seed_admin_settings(_clean_tables: None) -> None:
    """Seed the admin settings singletons the request path reads.

    In production InitDatabase seeds every settings table at startup, and the
    repository's get_* methods rely on that, they raise rather than invent a
    default. `_clean_tables` truncates everything between tests, so without
    this any endpoint that reads settings (product/project create, which
    enforce the admin-configured number patterns) would 500.

    Only the domains the request path actually reads are seeded; add more here
    as endpoints start depending on them.
    """
    from src.modules.catalogue.adapters.outbound.persistence.models.admin_settings_model.made_items import (
        AdminMadeItemSettingsOrmModel,
    )
    from src.modules.catalogue.adapters.outbound.persistence.models.admin_settings_model.orders import (
        AdminOrderSettingsOrmModel,
    )
    from src.modules.external_data.adapters.outbound.persistence.models.admin_settings_model.pdm import (
        AdminPdmSettingsOrmModel,
    )
    from src.modules.fulfillment.adapters.outbound.persistence.models.admin_settings_model.production import (
        AdminProductionSettingsOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.banner import (
        AdminBannerSettingsOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.general import (
        AdminGeneralSettingsOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.maintenance import (
        AdminMaintenanceSettingsOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.storage import (
        AdminStorageSettingsOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.repositories.platform_settings_repository import (
        clear_maintenance_cache,
    )

    session = Session(_ddl_engine)
    try:
        if not session.scalar(select(AdminGeneralSettingsOrmModel).filter_by(id=1).limit(1)):
            session.add(
                AdminGeneralSettingsOrmModel(
                    id=1,
                    product_number_pattern="",
                    project_number_pattern="",
                    allow_headless_projects=True,
                    empty_value_placeholder="-",
                )
            )
        # Read by every file endpoint, via get_optional_storage_adapter.
        # Seeded disabled: the file routes then return metadata with
        # url=None instead of needing a live object store.
        if not session.scalar(select(AdminStorageSettingsOrmModel).filter_by(id=1).limit(1)):
            session.add(AdminStorageSettingsOrmModel(id=1, provider="local", enabled=False))
        # Read by every one of auth_deps.py's authenticated dependencies,
        # since maintenance mode is enforced there (_enforce_maintenance).
        # Without this, every
        # `auth_client`/`auth_headers` request in the whole suite would 500
        # instead of the 401/403/2xx it actually means to test. Seeded
        # disabled, same reasoning as storage above: the baseline behaviour
        # for a test that doesn't care about maintenance mode is "off".
        if not session.scalar(select(AdminMaintenanceSettingsOrmModel).filter_by(id=1).limit(1)):
            session.add(
                AdminMaintenanceSettingsOrmModel(id=1, enabled=False, message=None, allowed_ips=[])
            )
            # Written through the ORM directly, not save_maintenance(), so it
            # cannot invalidate admin_settings_repository.py's own cache the
            # way a real write would. tests/conftest.py's autouse fixture
            # already clears that cache before every test, but this row is
            # inserted mid-setup by a fixture the whole suite depends on, so
            # invalidate again here rather than rely on cross-conftest fixture
            # ordering to keep this insert correct on its own.
            clear_maintenance_cache()
        # Read by /announcements/me (every active user) and the admin
        # banner endpoints, same "seeded disabled" baseline as maintenance
        # and storage above.
        if not session.scalar(select(AdminBannerSettingsOrmModel).filter_by(id=1).limit(1)):
            session.add(
                AdminBannerSettingsOrmModel(
                    id=1, enabled=False, text="", severity="info", updated_at=datetime.now(UTC)
                )
            )
        # Read by GET /pat/settings/field-mapping (owner + custom_property +
        # update_in_place). Both rows rely entirely on their ORM column
        # defaults (docs/FIELD_OWNERSHIP.md's default variable maps and
        # revision policy respectively), same "bare row" seeding as the
        # others above.
        if not session.scalar(select(AdminMadeItemSettingsOrmModel).filter_by(id=1).limit(1)):
            session.add(AdminMadeItemSettingsOrmModel(id=1))
        # Read by order creation (the order number format) and by every
        # delivery (the delivery tolerances); a bare row takes the column
        # defaults, which number orders and take no tolerance.
        if not session.scalar(select(AdminOrderSettingsOrmModel).filter_by(id=1).limit(1)):
            session.add(AdminOrderSettingsOrmModel(id=1))
        # enabled=False explicit, same "seeded disabled" reasoning as
        # storage/maintenance/banner above: SQLite's generic (non-native-
        # boolean) result processor reads a Boolean server_default column
        # back truthy when no INSERT ever wrote it explicitly (see
        # test_admin_pdm_settings_persistence.py's matching note), and
        # UpdatePdmSettings branches on `enabled`, so a bare row here
        # would make an unrelated PUT trip the "enabled requires
        # configuration" rule.
        if not session.scalar(select(AdminPdmSettingsOrmModel).filter_by(id=1).limit(1)):
            session.add(AdminPdmSettingsOrmModel(id=1, enabled=False))
        # Read by the lifecycle reconciler of every request whose run moves
        # who does a lot's first position (lot_material_followup.py). The
        # number format has only a server default, so it is written, and the
        # rule it reads is written explicitly for the SQLite reason above.
        if not session.scalar(select(AdminProductionSettingsOrmModel).filter_by(id=1).limit(1)):
            session.add(
                AdminProductionSettingsOrmModel(
                    id=1,
                    production_order_number_format="PO-{seq:04d}",
                    external_first_step_needs_no_material=True,
                )
            )
        session.commit()
    finally:
        session.close()


@pytest.fixture
async def db() -> AsyncIterator[AsyncSession]:
    """A session for arranging fixtures/asserting final state directly,
    independent of the sessions the app opens per request."""
    async with SessionLocal() as session:
        yield session


@contextmanager
def count_queries(session: AsyncSession) -> Iterator[list[str]]:
    """A regression net for repository query-shape changes (eager loading,
    N+1 fixes) that have no observable output difference, only the number
    of round trips changes, so ordinary field assertions can't catch a
    regression.

    Listens on `session.get_bind()` for `before_cursor_execute` and
    appends every statement's raw SQL text to the yielded list, so a
    failing count assertion can dump exactly what ran. Unconditionally
    removes the listener in `finally`, so a failure mid-block never leaks
    it onto later queries in the same test (or session, since sessions
    are function-scoped but the engine/bind is shared across the suite).

    The metric is *round-trip count*, not statement shape: dialect
    differences between this SQLite file and production Postgres change
    how a given query is worded, not how many round trips a given loader
    strategy costs, so a count measured here is meaningful on Postgres
    too, even though SQLite ORM-side statistics diverge (`db` fixture note
    above / `_guard_throwaway_database`).
    """
    statements: list[str] = []

    def _listener(
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        statements.append(statement)

    bind = session.sync_session.get_bind()
    event.listen(bind, "before_cursor_execute", _listener)
    try:
        yield statements
    finally:
        event.remove(bind, "before_cursor_execute", _listener)


@pytest.fixture
def query_counter(db: AsyncSession) -> Callable[[], AbstractContextManager[list[str]]]:
    """`with query_counter() as statements:` counts round trips issued
    through the `db` fixture's session during the block. A factory rather
    than the contextmanager directly, so a test can enter/exit it more
    than once against the same session."""

    def _counter() -> AbstractContextManager[list[str]]:
        return count_queries(db)

    return _counter


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """Unauthenticated client; never runs the lifespan, see module docstring."""
    async with _new_client() as c:
        yield c


def make_user_entity(
    username: str = "tester",
    email: str = "tester@example.com",
    permissions: list[str] | None = None,
    *,
    password: str = TEST_PASSWORD,
    is_active: bool = True,
    is_systemuser: bool = False,
    is_service_account: bool = False,
    auth_provider: str = "local",
) -> User:
    """An unsaved user for the repository to assign an id to."""
    return make_user(
        id=0,
        username=username,
        email=email,
        permissions=permissions,
        password=password,
        is_active=is_active,
        is_systemuser=is_systemuser,
        is_service_account=is_service_account,
        auth_provider=auth_provider,
    )


@pytest.fixture
def create_user(db: AsyncSession) -> Callable[..., Awaitable[User]]:
    """Persists a user through the real repository and returns the saved
    entity (with its assigned id)."""

    async def _create(
        username: str = "tester",
        email: str = "tester@example.com",
        permissions: list[str] | None = None,
        *,
        password: str = TEST_PASSWORD,
        is_active: bool = True,
        is_systemuser: bool = False,
        is_service_account: bool = False,
        auth_provider: str = "local",
    ) -> User:
        entity = make_user_entity(
            username,
            email,
            permissions,
            password=password,
            is_active=is_active,
            is_systemuser=is_systemuser,
            is_service_account=is_service_account,
            auth_provider=auth_provider,
        )
        saved = await SqlAlchemyUserRepository(db).save(entity)
        await db.commit()
        return saved

    return _create


async def auth_headers(user: User) -> dict[str, str]:
    """A Bearer header for `user`. Web tokens are the non-persistent kind
    and carry the user's token_version, which ValidateWebToken checks,
    a stale version is treated as an invalidated session.

    A server-side session row is created alongside, because the token's
    `sid` claim must name a live row: session tokens carry no exp claim
    and the row is the entire liveness story (idle timeout + revocation)."""
    async with SessionLocal() as session_db:
        session = await SqlAlchemyUserSessionRepository(session_db).save(
            make_user_session(user_id=user.id, user_agent="pytest", ip="testclient")
        )
        await session_db.commit()
    token = create_access_token(
        subject=user.id,
        persistent=False,
        expires_delta=None,
        token_version=user.token_version,
        sid=str(session.public_id),
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def auth_client(
    create_user: Callable[..., Awaitable[User]],
) -> AsyncIterator[Callable[..., Awaitable[httpx.AsyncClient]]]:
    """A client authenticated as a user with the given permissions. Every
    client handed out is closed when the test ends."""
    clients: list[httpx.AsyncClient] = []

    async def _client(
        permissions: list[str] | None = None, **user_kwargs: object
    ) -> httpx.AsyncClient:
        user = await create_user(permissions=permissions, **user_kwargs)
        c = _new_client()
        c.headers.update(await auth_headers(user))
        clients.append(c)
        return c

    yield _client
    for c in clients:
        await c.aclose()
