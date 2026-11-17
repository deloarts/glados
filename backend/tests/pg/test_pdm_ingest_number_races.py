"""
Two PDM files that carry the same new part number, ingested at once on a real
Postgres, as two poll workers or a poll and the trigger worker do. Both find
no item with the number, so both create one. The first holds its registry
claim uncommitted at the commit, and the second's claim of the same number
waits for it. Once the first commits, the second hits the registry's primary
key, and commit_with_number_retry rolls it back. The ingest then decides the
second file again against what the first committed and parks it as a
conflict with the item the first file created, the outcome the next poll
gives it too. No second item and no second registry entry is written.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from src.bootstrap.adapters.outbound.persistence.init_db import InitDatabase
from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.bootstrap.workers.pdm_schedule import build_ingest_pdm_file
from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
    MadeItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.part_number_registry_model import (
    PartNumberRegistryOrmModel,
)
from src.modules.external_data.adapters.outbound.persistence.models.pdm_file_snapshot_model import (
    PdmFileSnapshotOrmModel,
)
from src.modules.external_data.application.dto.pdm_dto import IngestOutcome
from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.quality.adapters.outbound.persistence.repositories.print_template_repository import (
    SqlAlchemyPrintTemplateRepository,
)
from tests.pg._race import SIDE
from tests.pg._race import Gate
from tests.pg._race import outcomes
from tests.pg._race import sessions
from tests.pg._race import start
from tests.pg._race import wait_for_lock
from tests.pg.conftest import RACE_A
from tests.pg.conftest import RACE_B
from tests.unit.ingest_pdm_file._helpers import MADE_VARIABLES
from tests.unit.ingest_pdm_file._helpers import make_made_item_settings
from tests.unit.ingest_pdm_file._helpers import make_payload
from tests.unit.ingest_pdm_file._helpers import make_pdm_settings
from tests.unit.ingest_pdm_file.fakes import FakeAdminSettingsRepository
from tests.unit.ingest_pdm_file.fakes import FakePdmGateway

_NUMBER = MADE_VARIABLES["PDM.PartNumber"]
_FIRST_FILE = 100
_SECOND_FILE = 101


@pytest.fixture
async def seeded(engine_a: AsyncEngine) -> None:
    """The seed every deployment starts from (settings rows, the system
    user ingest writes as), with PDM switched on and made items numbered
    from PDM."""
    async with sessions(engine_a)() as db:
        settings = SqlAlchemyAdminSettingsRepository(db)
        await InitDatabase(
            user_repo=SqlAlchemyUserRepository(db),
            admin_settings_repo=settings,
            print_template_repo=SqlAlchemyPrintTemplateRepository(db),
            db=db,
        ).run()
        await settings.save_pdm(make_pdm_settings())
        await settings.save_made_items(make_made_item_settings())
        await db.commit()


@pytest.fixture
def gate(monkeypatch: pytest.MonkeyPatch) -> Iterator[Gate]:
    """Stops side A at its commit, after its write has flushed the item and
    the registry claim."""
    gate = Gate(RACE_A)
    monkeypatch.setattr(SqlAlchemyUnitOfWork, "commit", gate.wrap(SqlAlchemyUnitOfWork.commit))
    yield gate
    gate.release()


def _pdm_session() -> PdmSessionService:
    """PDM itself is never reached: the gateway answers the releaser lookup
    with no transitions, and the session keeps its token in memory."""
    gateway = FakePdmGateway()
    return PdmSessionService(
        repo=FakeAdminSettingsRepository(pdm=make_pdm_settings()),
        gateway_factory=lambda connection: gateway,
    )


async def _ingest(side: str, engine: AsyncEngine, file_id: int) -> IngestOutcome:
    """Ingests the released made file `file_id`, carrying the shared part
    number, as the poller does: on its own session, rolled back on error."""
    SIDE.set(side)
    async with sessions(engine)() as db:
        ingest = build_ingest_pdm_file(db, _pdm_session())
        payload = make_payload(kind="made", file_id=file_id, variables=dict(MADE_VARIABLES))
        try:
            return await ingest.execute(payload)
        except BaseException:
            await db.rollback()
            raise


async def _holders(engine: AsyncEngine) -> tuple[int, int]:
    """How many made items carry the shared number, and how many registry
    entries it has."""
    async with sessions(engine)() as db:
        items = await db.scalar(select(func.count()).where(MadeItemOrmModel.part_number == _NUMBER))
        entries = await db.scalar(
            select(func.count()).where(PartNumberRegistryOrmModel.part_number == _NUMBER)
        )
        return items or 0, entries or 0


async def _snapshot_states(engine: AsyncEngine) -> dict[int, str]:
    async with sessions(engine)() as db:
        rows = await db.execute(
            select(PdmFileSnapshotOrmModel.file_id, PdmFileSnapshotOrmModel.sync_state)
        )
        return {file_id: state for file_id, state in rows.all()}


async def test_the_second_file_with_the_same_new_number_is_parked_as_a_conflict(
    seeded: None,
    gate: Gate,
    engine_a: AsyncEngine,
    engine_b: AsyncEngine,
    watcher: AsyncEngine,
) -> None:
    first = start(_ingest(RACE_A, engine_a, _FIRST_FILE))
    second = None
    try:
        await gate.wait_reached()
        second = start(_ingest(RACE_B, engine_b, _SECOND_FILE))
        await wait_for_lock(watcher, RACE_B)
    finally:
        gate.release()
    created, lost = await outcomes(first, second)

    assert isinstance(created, IngestOutcome)
    assert created.action == "created"
    assert isinstance(lost, IngestOutcome)
    assert lost.action == "conflict"
    assert await _holders(engine_a) == (1, 1)
    assert await _snapshot_states(engine_a) == {_FIRST_FILE: "ingested", _SECOND_FILE: "conflict"}

    # The next poll comes to the same conclusion.
    retried = await _ingest(RACE_B, engine_b, _SECOND_FILE)

    assert retried.action == "conflict"
    assert retried.message == lost.message
    assert await _holders(engine_a) == (1, 1)
