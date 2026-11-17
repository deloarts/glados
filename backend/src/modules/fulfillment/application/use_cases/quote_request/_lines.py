"""
Builds the lines a quote request asks suppliers to quote, from the request's
input, checked the way an order line is: a bought or source item new work
may name, an active project, whole pieces in a counted unit, and demand
shares that name a live demand of the line's own item and together fit the
line. A MADE line names a lot position of a live lot and takes the lot's
project. A share reserves nothing; the award allocates what the demand
still needs then. A substitute item is checked the same way, and must be of
the line's own kind.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from src.modules.catalogue.domain.errors import BoughtItemNotFoundError
from src.modules.catalogue.domain.errors import SourceItemNotFoundError
from src.modules.catalogue.domain.policies.bought_item_rules import BoughtItemCatalogueRules
from src.modules.catalogue.domain.policies.source_item_rules import SourceItemCatalogueRules
from src.modules.catalogue.ports.outbound.catalogue_queries import IBoughtItemQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ISourceItemQueries
from src.modules.fulfillment.application.dto.quote_request_dto import QuoteRequestLineInput
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestLine
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestLineDemand
from src.modules.fulfillment.domain.errors import DemandItemNotFoundError
from src.modules.fulfillment.domain.errors import LotPositionNotFoundError
from src.modules.fulfillment.domain.errors import QuoteRequestInvalidError
from src.modules.fulfillment.domain.errors import SourceItemDemandNotFoundError
from src.modules.fulfillment.domain.services.allocation_service import BoughtItemAllocationRules
from src.modules.fulfillment.domain.services.quote_request_rules import assert_line_substitutable
from src.modules.fulfillment.domain.services.quote_request_rules import assert_shares_fit
from src.modules.fulfillment.domain.services.quote_request_rules import substitute_of_line_kind
from src.modules.fulfillment.domain.services.source_item_allocation_service import (
    SourceItemAllocationRules,
)
from src.modules.fulfillment.domain.value_objects.lot_status import TERMINAL_LOT_STATUSES
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.quote_request_status import (
    QuoteRequestDemandFamily,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.services.quantities import assert_whole_pieces
from src.modules.workspace.domain.errors import ProjectNotFoundError
from src.modules.workspace.domain.policies.project_activity import assert_project_active
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries


@dataclass(frozen=True)
class LineRepositories:
    bought_items: IBoughtItemQueries
    source_items: ISourceItemQueries
    bought_demands: IBoughtItemDemandItemRepository
    source_demands: ISourceItemDemandRepository
    lots: IProductionLotRepository
    projects: IProjectQueries


async def line_project_ids(
    repos: LineRepositories, lines: Iterable[QuoteRequestLineInput]
) -> list[int]:
    """The projects the lines put work on, read without a lock: the named
    project, or for a MADE line the project of its lot, which a lot never
    changes. The caller share-locks them before it locks the request, as
    every use case that creates work on a project does, so a project being
    completed, archived or deleted counts the line or refuses it, and
    build_line checks them active under that lock."""
    ids: set[int] = set()
    for data in lines:
        if data.line_type is OrderLineType.MADE and data.lot_position_id is not None:
            position = await repos.lots.get_position_by_id(data.lot_position_id)
            lot = await repos.lots.get_by_id(position.lot_id) if position else None
            if lot is not None:
                ids.add(lot.project_id)
        elif data.project_id is not None:
            ids.add(data.project_id)
    return sorted(ids)


async def build_line(
    repos: LineRepositories,
    data: QuoteRequestLineInput,
    *,
    request_id: int,
    position: int,
    now_at: datetime,
) -> QuoteRequestLine:
    """The line `data` asks for, checked, not yet saved."""
    line_type = data.line_type
    project_id = data.project_id
    unit = data.unit.strip().upper()
    if line_type is OrderLineType.BOUGHT and data.bought_item_id is not None:
        BoughtItemCatalogueRules.assert_item_demandable(
            found_or_raise(
                await repos.bought_items.get_by_id(data.bought_item_id),
                BoughtItemNotFoundError,
                f"Catalogue item #{data.bought_item_id} not found.",
            )
        )
    elif line_type is OrderLineType.SOURCE and data.source_item_id is not None:
        SourceItemCatalogueRules.assert_item_demandable(
            found_or_raise(
                await repos.source_items.get_by_id(data.source_item_id),
                SourceItemNotFoundError,
                f"Source item #{data.source_item_id} not found.",
            )
        )
    elif line_type is OrderLineType.MADE and data.lot_position_id is not None:
        position_row = found_or_raise(
            await repos.lots.get_position_by_id(data.lot_position_id),
            LotPositionNotFoundError,
            f"Lot position #{data.lot_position_id} not found.",
        )
        lot = found_or_raise(
            await repos.lots.get_by_id(position_row.lot_id),
            LotPositionNotFoundError,
            f"Lot #{position_row.lot_id} not found.",
        )
        if lot.status in TERMINAL_LOT_STATUSES:
            raise QuoteRequestInvalidError(
                f"Lot {lot.lot_number} is {lot.status.value}; its positions take no quote request."
            )
        project_id = lot.project_id

    if project_id is None:
        raise QuoteRequestInvalidError("A quote request line needs a project.")
    assert_project_active(
        found_or_raise(
            await repos.projects.get_by_id(project_id),
            ProjectNotFoundError,
            f"Project #{project_id} not found.",
        ),
        work="new quote request lines",
    )
    counted = None if line_type is OrderLineType.MADE else unit
    assert_whole_pieces(data.quantity, what="The quote request line quantity", unit=counted)
    for share in data.demands:
        assert_whole_pieces(share.quantity, what="A demand share", unit=counted)
    assert_shares_fit(data.quantity, (share.quantity for share in data.demands))
    for share in data.demands:
        await _check_share(repos, data, share.family, share.demand_item_id)

    return QuoteRequestLine(
        id=0,
        quote_request_id=request_id,
        position=position,
        line_type=line_type,
        quantity=data.quantity,
        unit="PCS" if line_type is OrderLineType.MADE else unit,
        created=now_at,
        project_id=project_id,
        bought_item_id=data.bought_item_id,
        source_item_id=data.source_item_id,
        lot_position_id=data.lot_position_id,
        virtual_name=(data.virtual_name or "").strip() or None,
        note=(data.note or "").strip() or None,
        demands=[
            QuoteRequestLineDemand(
                id=0,
                line_id=0,
                family=share.family,
                demand_item_id=share.demand_item_id,
                quantity=share.quantity,
            )
            for share in data.demands
        ],
    )


async def _check_share(
    repos: LineRepositories,
    data: QuoteRequestLineInput,
    family: QuoteRequestDemandFamily,
    demand_item_id: int,
) -> None:
    """A share names a demand that is neither fulfilled nor canceled, of
    the item the line asks for."""
    if family is QuoteRequestDemandFamily.BOUGHT:
        bought = found_or_raise(
            await repos.bought_demands.get_by_id(demand_item_id),
            DemandItemNotFoundError,
            f"Demand item #{demand_item_id} not found.",
        )
        BoughtItemAllocationRules.assert_not_terminal(bought)
        if data.bought_item_id is None or bought.item_id != data.bought_item_id:
            raise QuoteRequestInvalidError(
                f"Demand #{demand_item_id} is for another item than the line."
            )
        return
    source = found_or_raise(
        await repos.source_demands.get_by_id(demand_item_id),
        SourceItemDemandNotFoundError,
        f"Source item demand #{demand_item_id} not found.",
    )
    SourceItemAllocationRules.assert_not_terminal(source)
    same_item = (
        data.bought_item_id is not None and source.bought_item_id == data.bought_item_id
    ) or (data.source_item_id is not None and source.source_item_id == data.source_item_id)
    if not same_item:
        raise QuoteRequestInvalidError(
            f"Source item demand #{demand_item_id} is for another material than the line."
        )


async def check_substitute_item(
    repos: LineRepositories,
    line: QuoteRequestLine,
    bought_item_id: int | None,
    source_item_id: int | None,
) -> int:
    """The substitute item named for `line`, checked: the line can take
    another item, the item is of the line's own kind, and new work may name
    it, as for any line."""
    assert_line_substitutable(line)
    item_id = substitute_of_line_kind(line, bought_item_id, source_item_id)
    if bought_item_id is not None:
        BoughtItemCatalogueRules.assert_item_demandable(
            found_or_raise(
                await repos.bought_items.get_by_id(item_id),
                BoughtItemNotFoundError,
                f"Catalogue item #{item_id} not found.",
            )
        )
    else:
        SourceItemCatalogueRules.assert_item_demandable(
            found_or_raise(
                await repos.source_items.get_by_id(item_id),
                SourceItemNotFoundError,
                f"Source item #{item_id} not found.",
            )
        )
    return item_id


def next_position(lines: list[QuoteRequestLine]) -> int:
    return max((line.position for line in lines), default=0) + 1
