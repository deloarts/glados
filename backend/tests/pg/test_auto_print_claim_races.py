"""
Two deliveries of one event to the auto_print group, as the reclaim scan or
`admin republish-outbox` can cause: each claims the template's job row with
an insert that does nothing on a conflict of the unique
(classifier, source_event_id) index. The later insert waits for the earlier
transaction, writes nothing once it commits, and its delivery sends no
print; a delivery that comes while the first one is still printing finds
the committed claim and sends nothing either.
"""

import asyncio

import pytest
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.domain.events.lot_events import LotCreated
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.quality.adapters.outbound.persistence.models.print_job_model import (
    PrintJobOrmModel,
)
from src.modules.quality.adapters.outbound.persistence.repositories.print_job_repository import (
    SqlAlchemyPrintJobRepository,
)
from src.modules.quality.adapters.outbound.persistence.repositories.print_template_repository import (
    SqlAlchemyPrintTemplateRepository,
)
from src.modules.quality.adapters.outbound.persistence.repositories.printer_repository import (
    SqlAlchemyPrinterRepository,
)
from src.modules.quality.application.use_cases.print_document.handle_event_auto_print import (
    HandleEventAutoPrint,
)
from src.modules.quality.application.use_cases.print_document.print_document import PrintDocument
from src.modules.quality.domain.value_objects.print_classifier import PrintSides
from src.modules.quality.ports.outbound.printer_gateway_port import PrintDelivery
from tests.pg._floor import Floor
from tests.pg._race import SIDE
from tests.pg._race import WAIT_SECONDS
from tests.pg._race import Gate
from tests.pg._race import sessions
from tests.pg._race import wait_for_lock
from tests.pg.conftest import RACE_B
from tests.unit.test_print_document_use_case import FakeDocketRenderer

EVENT_ID = "1700000000000-0"


class _LotRoot(BaseModel):
    id: int
    lot_number: str = "LOT-1"


class _Roots:
    async def resolve(self, root_type: str, root_id: int) -> _LotRoot:
        return _LotRoot(id=root_id)


class _Gateway:
    """Records every send with the side that made it, and holds side A's
    send until the test lets it go."""

    def __init__(self, hold_a: asyncio.Event | None = None) -> None:
        self.sent: list[str | None] = []
        self.a_sending = asyncio.Event()
        self._hold_a = hold_a

    async def send(
        self, printer, payload, content_type, copies, *, sides: PrintSides = PrintSides.ONE_SIDED
    ) -> PrintDelivery:
        side = SIDE.get()
        if side == "a" and self._hold_a is not None:
            self.a_sending.set()
            await self._hold_a.wait()
        self.sent.append(side)
        return PrintDelivery()


def _handler(db: AsyncSession, gateway: _Gateway) -> HandleEventAutoPrint:
    templates = SqlAlchemyPrintTemplateRepository(db)
    jobs = SqlAlchemyPrintJobRepository(db)
    roots = _Roots()
    return HandleEventAutoPrint(
        template_repo=templates,
        job_repo=jobs,
        user_repo=SqlAlchemyUserRepository(db),
        root_resolver=roots,
        print_document=PrintDocument(
            template_repo=templates,
            printer_repo=SqlAlchemyPrinterRepository(db),
            job_repo=jobs,
            root_resolver=roots,
            gateway=gateway,
            docket_renderer=FakeDocketRenderer(),  # type: ignore[arg-type]
            asset_resolver=None,
            domain_url="https://glados.example",
            uow=SqlAlchemyUnitOfWork(db),
        ),
        uow=SqlAlchemyUnitOfWork(db),
    )


async def _deliver(side: str, engine: AsyncEngine, gateway: _Gateway, event: LotCreated) -> None:
    SIDE.set(side)
    async with sessions(engine)() as db:
        await _handler(db, gateway).execute(event, EVENT_ID)


async def _armed_lot_label(floor: Floor) -> LotCreated:
    """The graph's lot_label template, armed for lot_created, printing to a
    label printer, and the event of its lot."""
    template = await floor.graph.print_template()
    await floor.db.execute(
        text("UPDATE print_template_table SET source = '^XA^XZ' WHERE id = :id"),
        {"id": template.id},
    )
    await floor.db.execute(
        text("UPDATE printer_table SET kind = 'zpl_label' WHERE id = :id"),
        {"id": template.printer_id},
    )
    await floor.db.commit()
    lot = await floor.graph.lot()
    return LotCreated(lot_id=lot.id, made_item_id=lot.made_item_id, creator_id=floor.actor.id)


async def _jobs(engine: AsyncEngine) -> list[tuple[str, str | None]]:
    async with sessions(engine)() as db:
        rows = await db.execute(select(PrintJobOrmModel.status, PrintJobOrmModel.source_event_id))
        return [(status, source) for status, source in rows.all()]


async def test_a_delivery_racing_an_uncommitted_claim_waits_and_prints_nothing(
    floor: Floor,
    engine_a: AsyncEngine,
    engine_b: AsyncEngine,
    watcher: AsyncEngine,
    monkeypatch,
) -> None:
    event = await _armed_lot_label(floor)
    gateway = _Gateway()

    # Side A stops right after its insert, before the claim commits.
    gate = Gate("a")
    monkeypatch.setattr(
        SqlAlchemyPrintJobRepository,
        "claim_for_event",
        gate.wrap(SqlAlchemyPrintJobRepository.claim_for_event, after=True),
    )

    first = asyncio.ensure_future(_deliver("a", engine_a, gateway, event))
    await gate.wait_reached()
    second = asyncio.ensure_future(_deliver("b", engine_b, gateway, event))
    await wait_for_lock(watcher, RACE_B)
    gate.release()
    await asyncio.wait_for(asyncio.gather(first, second), WAIT_SECONDS * 2)

    assert gateway.sent == ["a"]
    assert await _jobs(engine_a) == [("sent", EVENT_ID)]


async def test_a_delivery_during_the_first_ones_print_sends_nothing(
    floor: Floor, engine_a: AsyncEngine, engine_b: AsyncEngine
) -> None:
    event = await _armed_lot_label(floor)
    hold = asyncio.Event()
    gateway = _Gateway(hold_a=hold)

    first = asyncio.ensure_future(_deliver("a", engine_a, gateway, event))
    await asyncio.wait_for(gateway.a_sending.wait(), WAIT_SECONDS)
    assert await _jobs(engine_b) == [("printing", EVENT_ID)]

    await asyncio.wait_for(_deliver("b", engine_b, gateway, event), WAIT_SECONDS)
    hold.set()
    await asyncio.wait_for(first, WAIT_SECONDS)

    assert gateway.sent == ["a"]
    assert await _jobs(engine_a) == [("sent", EVENT_ID)]


async def test_a_released_claim_lets_the_redelivery_print(
    floor: Floor, engine_a: AsyncEngine, engine_b: AsyncEngine
) -> None:
    event = await _armed_lot_label(floor)
    gateway = _Gateway()

    class _BrokenRoots(_Roots):
        async def resolve(self, root_type: str, root_id: int) -> _LotRoot:
            raise RuntimeError("lost the connection")

    SIDE.set("a")
    async with sessions(engine_a)() as db:
        handler = _handler(db, gateway)
        handler._print._resolver = _BrokenRoots()
        with pytest.raises(RuntimeError):
            await handler.execute(event, EVENT_ID)
    assert await _jobs(engine_a) == []

    await _deliver("b", engine_b, gateway, event)
    assert gateway.sent == ["b"]
    assert await _jobs(engine_a) == [("sent", EVENT_ID)]
