"""
Read scenarios for supplier orders, their items, deliveries and files.
See the package docstring for how the scenarios work.
"""

from datetime import timedelta
from typing import Any
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_file_repository import (
    SqlAlchemyOrderFileRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.delivery import (
    SqlAlchemyOrderItemDeliveryRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order import (
    SqlAlchemyOrderRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order_item import (
    SqlAlchemyOrderItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.quote_request_file_repository import (
    SqlAlchemyQuoteRequestFileRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.quote_request_file_repository import (
    SqlAlchemyQuoteRequestSupplierRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.quote_request_repository import (
    SqlAlchemyQuoteRequestRepository,
)
from src.modules.fulfillment.domain.entities.order_file import OrderFile
from src.modules.fulfillment.domain.entities.quote_request import Quote
from src.modules.fulfillment.domain.entities.quote_request import QuoteExtraCost
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequest
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestLine
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestLineDemand
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestSupplier
from src.modules.fulfillment.domain.entities.quote_request_file import QuoteRequestFile
from src.modules.fulfillment.domain.value_objects.extra_cost_kind import ExtraCostKind
from src.modules.fulfillment.domain.value_objects.order_file_category import OrderFileCategory
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.quote_file_category import QuoteFileCategory
from src.modules.fulfillment.domain.value_objects.quote_request_status import (
    QuoteRequestDemandFamily,
)
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestStatus
from src.modules.fulfillment.ports.outbound.repositories.order_repository import OrderFilterDto
from src.modules.fulfillment.ports.outbound.repositories.quote_request_repository import (
    QuoteRequestFilterDto,
)
from tests.integration.repository_reads._graph import NOW
from tests.integration.repository_reads._graph import Graph
from tests.integration.repository_reads._graph import file_fields
from tests.integration.repository_reads._graph import make
from tests.integration.repository_reads._harness import Scenarios

SCENARIOS = Scenarios()


@SCENARIOS.register(SqlAlchemyOrderRepository)
async def _orders(g: Graph, r: Any) -> None:
    await g.bought_allocation()
    await g.source_allocation()
    await g.made_order_item()
    await g.delivery()
    order = await g.order()
    project = await g.project()
    await r.get_by_id(order.id)
    await r.get_by_id_for_update(order.id)
    await r.get_by_ids([order.id])
    await r.get_ids_after(0, 10)
    await r.get_by_order_number(order.order_number)
    await r.get_multi(OrderFilterDto())
    await r.maybe_empty.get_multi(OrderFilterDto(todo_horizon=NOW.date()))
    await r.get_spend_facts(NOW - timedelta(days=1), NOW + timedelta(days=1))
    await r.get_project_summary(project.id)
    await r.get_product_summary(cast(int, project.product_id))
    await r.next_order_number("O-{seq}")


@SCENARIOS.register(SqlAlchemyOrderItemRepository)
async def _order_items(g: Graph, r: Any) -> None:
    await g.bought_allocation()
    await g.delivery()
    bought = await g.bought_order_item()
    source = await g.source_order_item()
    made = await g.made_order_item()
    assert bought.bought_item_id and source.source_item_id and made.lot_position_id
    await r.get_by_bought_item_id(bought.bought_item_id)
    await r.get_by_id(bought.id)
    await r.get_by_id_for_update(bought.id)
    await r.get_by_ids([bought.id, source.id, made.id])
    await r.get_by_lot_position_id(made.lot_position_id)
    await r.get_by_lot_position_ids([made.lot_position_id])
    await r.get_by_order_id(bought.order_id)
    await r.get_by_order_ids([bought.order_id])
    bought.quantity_rejected_lost = 1.0
    await r.save(bought)
    await r.get_settled_short(10)
    await r.get_by_source_item_id(source.source_item_id)
    await r.next_position(bought.order_id)


@SCENARIOS.register(SqlAlchemyOrderItemDeliveryRepository)
async def _deliveries(g: Graph, r: Any) -> None:
    delivery = await g.delivery()
    await r.get_by_id(delivery.id)
    await r.get_by_order_item_id(delivery.order_item_id)
    await r.get_by_order_item_ids([delivery.order_item_id])
    await r.get_totals_by_order_item_ids([delivery.order_item_id])


@SCENARIOS.register(SqlAlchemyOrderFileRepository)
async def _order_files(g: Graph, r: Any) -> None:
    order = await g.order()
    file = await SqlAlchemyOrderFileRepository(g.db).save(
        make(
            OrderFile,
            order_id=order.id,
            category=OrderFileCategory.INVOICE,
            uploaded_by_user_id=g.uid,
            **file_fields("order"),
        )
    )
    await g.db.commit()
    await r.get_by_id(file.id)
    await r.get_by_item_id(order.id)
    await r.get_by_item_id_and_category(order.id, OrderFileCategory.INVOICE)
    await r.get_by_item_ids([order.id])


@SCENARIOS.register(SqlAlchemyQuoteRequestRepository)
async def _quote_requests(g: Graph, r: Any) -> None:
    supplier = await g.supplier()
    item = await g.bought_item()
    project = await g.project()
    demand = await g.bought_demand()
    position = await g.internal_position()
    await g.order()
    writer = SqlAlchemyQuoteRequestRepository(g.db)
    request = await writer.save(
        make(
            QuoteRequest,
            request_number="RFQ-1",
            status=QuoteRequestStatus.DRAFT,
            created=NOW,
            changed=NOW,
            changes=[],
            creator_id=g.uid,
        )
    )
    row = await writer.save_supplier(
        make(QuoteRequestSupplier, quote_request_id=request.id, supplier_id=supplier.id, position=1)
    )
    line = await writer.save_line(
        make(
            QuoteRequestLine,
            quote_request_id=request.id,
            position=1,
            line_type=OrderLineType.BOUGHT,
            quantity=2.0,
            unit="PCS",
            created=NOW,
            project_id=project.id,
            bought_item_id=item.id,
            demands=[
                QuoteRequestLineDemand(
                    id=0,
                    line_id=0,
                    family=QuoteRequestDemandFamily.BOUGHT,
                    demand_item_id=demand.id,
                    quantity=1.0,
                )
            ],
        )
    )
    await writer.save_line(
        make(
            QuoteRequestLine,
            quote_request_id=request.id,
            position=2,
            line_type=OrderLineType.MADE,
            quantity=1.0,
            unit="PCS",
            created=NOW,
            project_id=project.id,
            lot_position_id=position.id,
        )
    )
    await writer.set_offer(
        row.id,
        [Quote(id=0, supplier_row_id=row.id, line_id=line.id, unit_price=100)],
        [
            QuoteExtraCost(
                id=0, supplier_row_id=row.id, kind=ExtraCostKind.SHIPPING, amount=500, position=1
            )
        ],
    )
    await g.db.commit()
    await r.get_by_id(request.id)
    await r.get_by_id_for_update(request.id)
    await r.get_by_ids([request.id])
    await r.get_ids_after(0, 10)
    await r.get_multi(QuoteRequestFilterDto(search="RFQ", supplier_id=supplier.id))
    await r.get_open_links(
        bought_demand_ids=[demand.id], source_demand_ids=[1], lot_position_ids=[position.id]
    )
    await r.next_request_number("RFQ-{seq}")


@SCENARIOS.register(SqlAlchemyQuoteRequestSupplierRepository)
async def _quote_request_suppliers(g: Graph, r: Any) -> None:
    row_id = await _quote_supplier_row(g)
    await r.get_by_id(row_id)


@SCENARIOS.register(SqlAlchemyQuoteRequestFileRepository)
async def _quote_request_files(g: Graph, r: Any) -> None:
    row_id = await _quote_supplier_row(g)
    file = await SqlAlchemyQuoteRequestFileRepository(g.db).save(
        make(
            QuoteRequestFile,
            supplier_row_id=row_id,
            category=QuoteFileCategory.OFFER,
            uploaded_by_user_id=g.uid,
            **file_fields("offer"),
        )
    )
    await g.db.commit()
    await r.get_by_id(file.id)
    await r.get_by_item_id(row_id)
    await r.get_by_item_id_and_category(row_id, QuoteFileCategory.OFFER)
    await r.get_by_item_ids([row_id])


async def _quote_supplier_row(g: Graph) -> int:
    supplier = await g.supplier()
    writer = SqlAlchemyQuoteRequestRepository(g.db)
    request = await writer.save(
        make(
            QuoteRequest,
            request_number="RFQ-F1",
            status=QuoteRequestStatus.DRAFT,
            created=NOW,
            changed=NOW,
            changes=[],
            creator_id=g.uid,
        )
    )
    row = await writer.save_supplier(
        make(QuoteRequestSupplier, quote_request_id=request.id, supplier_id=supplier.id, position=1)
    )
    await g.db.commit()
    return row.id


@SCENARIOS.parametrize
async def test_read_methods_map_without_lazy_loads(repo_cls: type, db: AsyncSession) -> None:
    await SCENARIOS.run(repo_cls, db)
