"""
Every pair of lifecycle writers that can meet on one row races on Postgres,
over HTTP through the whole app, with the lost race retry middleware in
front. The writers and the data shapes are the ones of the SQLite writer
matrix (tests/integration/lifecycle_matrix). Every row of a shape lies in
one lock closure of the reconciler: the demand, its lines and their orders,
its lots with their positions and production orders, and the neighbour
demand sharing a line or a lot, which every writer locks with its target.
So two writers share a lock target exactly when one shape gives both of
them their rows, and a pair races on the first shape of `_PREFERENCE` that
does; a pair no shape serves is skipped.

Both requests wait at a barrier and then run concurrently, each on its own
connection. Each must answer a success or a documented refusal (409 for a
version or a state the other request changed, 422, and the shape's own
refusals), never a 500 such as a LockOrderError and never a 503: a
deadlock the middleware retried must be resolved by the retry. Afterwards
every quantity invariant holds and every stored lifecycle field equals its
derivation.
"""

import asyncio
import dataclasses
from collections.abc import AsyncIterator
from datetime import UTC
from datetime import datetime
from typing import Any

import httpx
import pytest
from sqlalchemy import Engine
from sqlalchemy import inspect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.bootstrap.main import app
from src.modules.catalogue.adapters.outbound.persistence.models.admin_settings_model.made_items import (
    AdminMadeItemSettingsOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.admin_settings_model.orders import (
    AdminOrderSettingsOrmModel,
)
from src.modules.external_data.adapters.outbound.persistence.models.admin_settings_model.pdm import (
    AdminPdmSettingsOrmModel,
)
from src.modules.fulfillment.adapters.inbound.api.deps import services as fulfillment_services
from src.modules.fulfillment.adapters.inbound.api.deps.services import get_schedule_recompute_lock
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._lifecycle_rows import (
    lock_rows,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.schedule_recompute_lock import (
    SqlAlchemyScheduleRecomputeLock,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.platform.adapters.inbound.api.deps.bindings import (
    get_schedule_recompute_generation_counter,
)
from src.modules.platform.adapters.inbound.api.deps.database import get_transactional_event_bus
from src.modules.platform.adapters.inbound.api.deps.services import get_backup_jobs_factory
from src.modules.platform.adapters.inbound.api.deps.services import get_login_attempt_tracker
from src.modules.platform.adapters.inbound.api.deps.services import get_replay_guard
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
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_session_repository import (
    SqlAlchemyUserSessionRepository,
)
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.entities.user_session import make_user_session
from src.modules.platform.infrastructure.security.token import create_access_token
from tests.factories import make_user
from tests.integration._lifecycle_drift import assert_no_lifecycle_drift
from tests.integration._lifecycle_drift import checked_aggregates
from tests.integration.fakes import FakeBackupJobs
from tests.integration.fakes import FakeLoginAttemptTracker
from tests.integration.fakes import FakeReplayGuard
from tests.integration.lifecycle_matrix._invariants import assert_quantities_conserved
from tests.integration.lifecycle_matrix._shapes import SHAPES
from tests.integration.lifecycle_matrix._shapes import World
from tests.integration.lifecycle_matrix._shapes import build_world
from tests.integration.lifecycle_matrix._shapes import catalogue
from tests.integration.lifecycle_matrix._writers import EVERY_WRITE_PERMISSION
from tests.integration.lifecycle_matrix._writers import WRITERS
from tests.integration.lifecycle_matrix._writers import Writer
from tests.integration.lifecycle_matrix._writers import skip_reason
from tests.pg._race import LocalGenerationCounter
from tests.pg._race import outcomes
from tests.pg._race import sessions
from tests.pg._race import start

# The shapes a pair races on, the busiest first: a demand split over two
# lines or two lots with a neighbour, then the line, lot and production
# order states, then the edge shapes.
_PREFERENCE = (
    "lines_bought",
    "lines_source",
    "lots_made",
    "running_lot",
    "pool_order",
    "bought_beside_source",
    "made_line_beside_bought",
    "partially_delivered_line",
    "raw_material_partly_delivered",
    "tolerance_line",
    "held_lot",
    "lost_pieces_line",
    "closed_short_line",
    "moved_line",
    "completed_lot",
    "canceled_lot",
    "smallest_quantity",
)
assert sorted(_PREFERENCE) == sorted(SHAPES)

PAIRS = [(first, second) for i, first in enumerate(WRITERS) for second in WRITERS[i:]]

_RETRIED = "lost a race in the database and runs once more"
# Writers that take the row they name away from where the other writer
# names it: a moved line is no longer under its old order, and a removed
# line or a released allocation no longer exists, so the other writer of the
# pair may find it gone (404) when it comes second.
_TAKES_THE_ROW_AWAY = frozenset({"move_line", "remove_line", "release_allocation"})
_ADDRESS = ("testclient", 50000)

# What each shape gives a writer, learned the first time a test seeds it.
_profiles: dict[str, World] = {}


class _RecordingEventBus:
    async def publish(self, event: object) -> None:
        return None


# The engine of the running test. FastAPI keeps every dependency callable it
# has seen in a cache, so an override that closed over a test's engine would
# keep that engine and its compiled statements alive for the whole session;
# the overrides below are the same functions in every test and read it here.
_current_engine: list[AsyncEngine] = []


def _recompute_lock() -> SqlAlchemyScheduleRecomputeLock:
    return SqlAlchemyScheduleRecomputeLock(_current_engine[0])


def _fake_backup_jobs(settings: object, db_url: str) -> FakeBackupJobs:
    return FakeBackupJobs()


def _backup_jobs_factory() -> Any:
    return _fake_backup_jobs


def _truncate(schema_engine: Engine) -> None:
    with schema_engine.begin() as connection:
        connection.execute(text("SET LOCAL lock_timeout = '5s'"))
        names = inspect(connection).get_table_names(schema="public")
        quoted = ", ".join(f'"{name}"' for name in names)
        connection.execute(text(f"TRUNCATE {quoted} RESTART IDENTITY CASCADE"))


async def _seed_settings(db: AsyncSession) -> None:
    """The settings singletons the request path reads, as the integration
    suite seeds them."""
    db.add_all(
        [
            AdminGeneralSettingsOrmModel(
                id=1,
                product_number_pattern="",
                project_number_pattern="",
                allow_headless_projects=True,
                empty_value_placeholder="-",
            ),
            AdminStorageSettingsOrmModel(id=1, provider="local", enabled=False),
            AdminMaintenanceSettingsOrmModel(id=1, enabled=False, message=None, allowed_ips=[]),
            AdminBannerSettingsOrmModel(
                id=1, enabled=False, text="", severity="info", updated_at=datetime.now(UTC)
            ),
            AdminMadeItemSettingsOrmModel(id=1),
            AdminOrderSettingsOrmModel(id=1),
            AdminPdmSettingsOrmModel(id=1, enabled=False),
        ]
    )
    await db.commit()
    await SqlAlchemyAdminSettingsRepository(db).save_production(
        AdminProductionSettings(
            id=1,
            production_order_number_format="PON-{yy}-{seq:05d}",
            default_weekly_hours={0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0},
            default_external_lead_days=0,
            response_time_days=1,
            require_qa=False,
        )
    )
    await db.commit()
    clear_maintenance_cache()


async def _user(db: AsyncSession, username: str, permissions: list[str]) -> User:
    saved = await SqlAlchemyUserRepository(db).save(
        make_user(id=0, username=username, email=f"{username}@example.com", permissions=permissions)
    )
    await db.commit()
    return saved


async def _client(db: AsyncSession, user: User) -> httpx.AsyncClient:
    """A client signed in as `user` with a web session of its own."""
    session = await SqlAlchemyUserSessionRepository(db).save(
        make_user_session(user_id=user.id, user_agent="pytest", ip="testclient")
    )
    await db.commit()
    token = create_access_token(
        subject=user.id,
        persistent=False,
        expires_delta=None,
        token_version=user.token_version,
        sid=str(session.public_id),
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=_ADDRESS),
        base_url="http://testserver",
        headers={"Authorization": f"Bearer {token}"},
    )


@dataclasses.dataclass
class _Stage:
    db: AsyncSession
    schema_engine: Engine
    clients: list[httpx.AsyncClient]

    async def reset(self) -> None:
        """Empties the database and seeds the settings, the catalogue and
        the two signed-in clients again."""
        for client in self.clients:
            await client.aclose()
        await self.db.rollback()
        _truncate(self.schema_engine)
        await self.prepare()

    async def prepare(self) -> None:
        await _seed_settings(self.db)
        owner = await _user(self.db, "owner", [])
        await catalogue(self.db, owner)
        actor = await _user(self.db, "racer", EVERY_WRITE_PERMISSION)
        self.owner = owner
        self.clients = [await _client(self.db, actor), await _client(self.db, actor)]


@pytest.fixture
async def stage(engine_a: AsyncEngine, schema_engine: Engine) -> AsyncIterator[_Stage]:
    """The app's sessions bound to the throwaway database, the services that
    would reach Redis or a broker replaced in memory, and the seeded
    settings and catalogue."""
    bound = SessionLocal.kw.get("bind")
    SessionLocal.configure(bind=engine_a)
    original_engine = fulfillment_services.engine
    fulfillment_services.engine = engine_a
    _current_engine[:] = [engine_a]
    overrides: dict[Any, Any] = {
        get_schedule_recompute_generation_counter: LocalGenerationCounter,
        get_schedule_recompute_lock: _recompute_lock,
        get_transactional_event_bus: _RecordingEventBus,
        get_replay_guard: FakeReplayGuard,
        get_login_attempt_tracker: FakeLoginAttemptTracker,
        get_backup_jobs_factory: _backup_jobs_factory,
    }
    saved = {key: app.dependency_overrides.get(key) for key in overrides}
    app.dependency_overrides.update(overrides)
    try:
        async with sessions(engine_a)() as db:
            staged = _Stage(db=db, schema_engine=schema_engine, clients=[])
            await staged.prepare()
            try:
                yield staged
            finally:
                for client in staged.clients:
                    await client.aclose()
    finally:
        for key, value in saved.items():
            if value is None:
                app.dependency_overrides.pop(key, None)
            else:
                app.dependency_overrides[key] = value
        fulfillment_services.engine = original_engine
        _current_engine.clear()
        SessionLocal.configure(bind=bound)


def _serves(shape: str, first: Writer, second: Writer) -> bool | None:
    """Whether `shape` gives both writers their rows, None until it is seeded."""
    profile = _profiles.get(shape)
    if profile is None:
        return None
    return skip_reason(first, profile) is None and skip_reason(second, profile) is None


async def _world_for(stage: _Stage, first: Writer, second: Writer) -> World | None:
    """The World of the first preferred shape serving both writers, seeded
    on the stage, or None when no shape does. A shape seen for the first
    time is seeded to learn what it gives, and the stage is reset when it
    serves the pair no rows."""
    seeded = False
    for shape in _PREFERENCE:
        if _serves(shape, first, second) is False:
            continue
        if seeded:
            await stage.reset()
        world = await build_world(stage.db, stage.clients[0], stage.owner, shape)
        seeded = True
        _profiles.setdefault(shape, dataclasses.replace(world, client=None))
        if _serves(shape, first, second):
            world.notes["shape"] = shape
            return world
    return None


@pytest.mark.parametrize(("first", "second"), PAIRS, ids=[f"{a.name}+{b.name}" for a, b in PAIRS])
async def test_two_writers_on_one_lock_closure_both_finish_consistently(
    stage: _Stage,
    engine_b: AsyncEngine,
    glados_caplog: pytest.LogCaptureFixture,
    record_property: Any,
    first: Writer,
    second: Writer,
) -> None:
    world = await _world_for(stage, first, second)
    if world is None:
        pytest.skip(f"no shape gives both {first.name} and {second.name} their rows")
    worlds = [world, dataclasses.replace(world, client=stage.clients[1])]
    barrier = asyncio.Barrier(2)

    async def side(writer: Writer, on: World) -> httpx.Response:
        await barrier.wait()
        return await writer.call(on)

    answers = await outcomes(start(side(first, worlds[0])), start(side(second, worlds[1])))

    allowed = {409, 422, *world.also_refused}
    if _TAKES_THE_ROW_AWAY & {first.name, second.name}:
        allowed.add(404)
    for writer, answer in zip((first, second), answers, strict=True):
        assert isinstance(answer, httpx.Response), (writer.name, repr(answer))
        assert answer.status_code < 300 or answer.status_code in allowed, (
            world.notes["shape"],
            writer.name,
            answer.status_code,
            answer.text[:500],
        )
    async with sessions(engine_b)() as fresh:
        await assert_quantities_conserved(fresh)
    await assert_no_lifecycle_drift(checked_aggregates())
    # Reported in the JUnit XML, so a run can be summarised by its outcomes.
    record_property("shape", world.notes["shape"])
    record_property("statuses", ",".join(str(answer.status_code) for answer in answers))
    record_property(
        "retried", sum(_RETRIED in record.getMessage() for record in glados_caplog.records)
    )


async def _lock_by_plan(db: AsyncSession, lot_id: int) -> None:
    await lock_rows(db, ProductionLotOrmModel, ProductionLotOrmModel.id, [lot_id])


async def _lock_by_read(db: AsyncSession, lot_id: int) -> None:
    await SqlAlchemyProductionLotRepository(db).get_by_id_for_update(lot_id)


@pytest.mark.parametrize("lock", [_lock_by_plan, _lock_by_read], ids=["plan", "read"])
async def test_a_locked_lot_lets_a_demand_drawn_for_it_be_written_twice(
    stage: _Stage, engine_b: AsyncEngine, lock: Any
) -> None:
    """A row lock on a lot serializes the lifecycle writers of the lot, but
    must not block the foreign key check of a row that references the lot.
    Postgres checks that key again when a transaction updates a row a second
    time, as an allocation writer does with the source demand it notes and
    then derives; a lot lock that blocked the check would deadlock that
    writer against a lot writer waiting for the demand."""
    world = await build_world(stage.db, stage.clients[0], stage.owner, "bought_beside_source")
    assert world.demand is not None and world.lot is not None
    demand_id = world.demand[1]
    async with sessions(stage.db.bind)() as holder:  # type: ignore[arg-type]
        await lock(holder, world.lot)
        async with sessions(engine_b)() as writer:
            await writer.execute(text("SET LOCAL lock_timeout = '2s'"))
            for note in ("first", "second"):
                await writer.execute(
                    text("UPDATE source_item_demand_item_table SET note = :note WHERE id = :id"),
                    {"note": note, "id": demand_id},
                )
            await writer.commit()
        await holder.rollback()
