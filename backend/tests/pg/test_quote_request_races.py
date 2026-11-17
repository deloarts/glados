"""
Race tests of the quote request award. Two awards of the same open line
come one after the other on the lifecycle locks they share, the request's
row lock last among them: the second waits for the first, reads the line as
awarded under its locks and is refused, so the line goes onto exactly one
order and its demand is allocated once.
"""

from typing import Any

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from src.modules.fulfillment.adapters.inbound.api.deps import quote_requests as quote_request_deps
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.allocation import (
    SqlAlchemyBoughtItemAllocationRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.quote_request_repository import (
    SqlAlchemyQuoteRequestRepository,
)
from src.modules.fulfillment.application.dto.quote_request_dto import AwardLineInput
from src.modules.fulfillment.application.dto.quote_request_dto import AwardQuoteRequestCommand
from src.modules.fulfillment.domain.entities.quote_request import Quote
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequest
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestLine
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestLineDemand
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestSupplier
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.quote_request_status import (
    QuoteRequestDemandFamily,
)
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestStatus
from src.modules.platform.domain.exceptions import DomainError
from tests.integration.repository_reads._graph import NOW
from tests.pg._floor import Floor
from tests.pg._race import Gate
from tests.pg._race import outcomes
from tests.pg._race import request
from tests.pg._race import sessions
from tests.pg._race import start
from tests.pg._race import wait_for_lock
from tests.pg.conftest import RACE_B


async def _sent_request(floor: Floor, demand_id: int) -> tuple[int, int, int]:
    """A sent request with one bought line for the demand and one supplier
    that priced it; the request, line and supplier row ids."""
    graph = floor.graph
    supplier = await graph.supplier()
    item = await graph.bought_item()
    project = await graph.project()
    repo = SqlAlchemyQuoteRequestRepository(floor.db)
    saved = await repo.save(
        QuoteRequest(
            id=0,
            request_number="RFQ-RACE-1",
            created=NOW,
            changed=NOW,
            changes=[],
            status=QuoteRequestStatus.SENT,
            creator_id=graph.uid,
        )
    )
    row = await repo.save_supplier(
        QuoteRequestSupplier(
            id=0, quote_request_id=saved.id, supplier_id=supplier.id, position=1, sent_at=NOW
        )
    )
    line = await repo.save_line(
        QuoteRequestLine(
            id=0,
            quote_request_id=saved.id,
            position=1,
            line_type=OrderLineType.BOUGHT,
            quantity=4.0,
            unit="PCS",
            created=NOW,
            project_id=project.id,
            bought_item_id=item.id,
            demands=[
                QuoteRequestLineDemand(
                    id=0,
                    line_id=0,
                    family=QuoteRequestDemandFamily.BOUGHT,
                    demand_item_id=demand_id,
                    quantity=4.0,
                )
            ],
        )
    )
    await repo.set_offer(
        row.id, [Quote(id=0, supplier_row_id=row.id, line_id=line.id, unit_price=250)], []
    )
    await floor.db.commit()
    return saved.id, line.id, row.id


async def test_two_awards_of_one_line_put_it_on_one_order(
    floor: Floor,
    engine_a: AsyncEngine,
    engine_b: AsyncEngine,
    watcher: AsyncEngine,
    monkeypatch: Any,
) -> None:
    demand = await floor.bought_demand(4.0)
    request_id, line_id, row_id = await _sent_request(floor, demand.id)
    gate = Gate("a")
    repository = SqlAlchemyQuoteRequestRepository
    monkeypatch.setattr(
        repository,
        "get_by_id_for_update",
        gate.wrap(repository.get_by_id_for_update, after=True),
    )
    award = quote_request_deps.get_award_quote_request_use_case

    def award_line(use_case: Any) -> Any:
        return use_case.execute(
            floor.actor,
            request_id,
            AwardQuoteRequestCommand(
                awards=[AwardLineInput(line_id=line_id, supplier_row_id=row_id)]
            ),
        )

    first = start(request("a", engine_a, award, award_line))
    await gate.wait_reached()
    second = start(request("b", engine_b, award, award_line))
    await wait_for_lock(watcher, RACE_B)
    gate.release()
    done, refused = await outcomes(first, second)

    assert not isinstance(done, BaseException)
    assert isinstance(refused, DomainError)
    async with sessions(engine_a)() as db:
        lines = await db.scalar(
            select(func.count())
            .select_from(OrderItemOrmModel)
            .where(OrderItemOrmModel.quote_request_line_id == line_id)
        )
        allocated = await SqlAlchemyBoughtItemAllocationRepository(db).get_allocated_quantity(
            demand.id
        )
    assert lines == 1
    assert allocated == 4.0
