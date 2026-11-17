"""
ORM <-> domain mapping of the quote request aggregate. A line resolves its
display identity from the live catalogue row as an order line does, so a
rename shows on requests already open.
"""

from functools import lru_cache
from typing import Any

from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
    BoughtItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.source_item_model import (
    SourceItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
    LotPositionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteExtraCostOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteRequestLineDemandOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteRequestLineOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteRequestOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteRequestSupplierOrmModel,
)
from src.modules.fulfillment.domain.entities.quote_request import Quote
from src.modules.fulfillment.domain.entities.quote_request import QuoteExtraCost
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequest
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestLine
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestLineDemand
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestSupplier
from src.modules.fulfillment.domain.value_objects.extra_cost_kind import ExtraCostKind
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.quote_request_status import (
    QuoteRequestDemandFamily,
)
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestStatus
from src.modules.platform.adapters.outbound.persistence.mapping_common import changed_by_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import creator_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user
from src.modules.platform.infrastructure.label_languages import resolve_label

# Built on first use, as in the order repository's mappers: constructing a
# loader option configures the mappers, which must wait until every model
# module is imported.


@lru_cache(maxsize=1)
def quote_request_load_options() -> tuple[ORMOption, ...]:
    """Everything quote_request_orm_to_entity() dereferences."""
    lines = selectinload(QuoteRequestOrmModel.lines)
    suppliers = selectinload(QuoteRequestOrmModel.suppliers)
    return (
        load_user(QuoteRequestOrmModel.creator),
        load_user(QuoteRequestOrmModel.changed_by),
        lines.selectinload(QuoteRequestLineOrmModel.demands),
        lines.selectinload(QuoteRequestLineOrmModel.bought_item),
        lines.selectinload(QuoteRequestLineOrmModel.source_item).selectinload(
            SourceItemOrmModel.type
        ),
        lines.selectinload(QuoteRequestLineOrmModel.lot_position)
        .selectinload(LotPositionOrmModel.lot)
        .selectinload(ProductionLotOrmModel.made_item),
        lines.selectinload(QuoteRequestLineOrmModel.project),
        lines.selectinload(QuoteRequestLineOrmModel.order_items).selectinload(
            OrderItemOrmModel.order
        ),
        suppliers.selectinload(QuoteRequestSupplierOrmModel.supplier),
        suppliers.selectinload(QuoteRequestSupplierOrmModel.quotes).selectinload(
            QuoteOrmModel.substitute_bought_item
        ),
        suppliers.selectinload(QuoteRequestSupplierOrmModel.quotes)
        .selectinload(QuoteOrmModel.substitute_source_item)
        .selectinload(SourceItemOrmModel.type),
        suppliers.selectinload(QuoteRequestSupplierOrmModel.extra_costs),
    )


@lru_cache(maxsize=1)
def supplier_row_load_options() -> tuple[ORMOption, ...]:
    """Everything supplier_orm_to_entity() dereferences, for a supplier row
    read on its own rather than through its request."""
    quotes = selectinload(QuoteRequestSupplierOrmModel.quotes)
    return (
        selectinload(QuoteRequestSupplierOrmModel.supplier),
        quotes.selectinload(QuoteOrmModel.substitute_bought_item),
        quotes.selectinload(QuoteOrmModel.substitute_source_item).selectinload(
            SourceItemOrmModel.type
        ),
        selectinload(QuoteRequestSupplierOrmModel.extra_costs),
    )


def _item_identity(
    bought: BoughtItemOrmModel | None, source: SourceItemOrmModel | None
) -> tuple[str, str] | None:
    """The article name and order code of a bought item, or the dimension
    and order code or "material | type" of a source item."""
    if bought is not None:
        return bought.article_name, bought.order_code_1
    if source is not None:
        descriptor = " | ".join(
            part
            for part in (source.material, resolve_label(source.type.name) if source.type else None)
            if part
        )
        return source.dimension or f"Source item #{source.id}", source.order_code_1 or descriptor
    return None


def _identity(orm: QuoteRequestLineOrmModel) -> tuple[str, str]:
    """The line's name and code: those of its bought or source item, the
    made item's name and part number for a lot position, or the free
    text."""
    item = _item_identity(orm.bought_item, orm.source_item)
    if item is not None:
        return item
    lot = orm.lot_position.lot if orm.lot_position is not None else None
    if lot is not None and lot.made_item is not None:
        return lot.made_item.article_name, lot.made_item.part_number or ""
    return orm.virtual_name or "", ""


def line_orm_to_entity(orm: QuoteRequestLineOrmModel) -> QuoteRequestLine:
    name, code = _identity(orm)
    lot = orm.lot_position.lot if orm.lot_position is not None else None
    # A line leads to several order lines when an award was voided, because
    # its order line was canceled, and the line was awarded again; the newest
    # one counts, and the award holds while any of them is live.
    order_item = max(orm.order_items, key=lambda i: i.id, default=None)
    return QuoteRequestLine(
        id=orm.id,
        public_id=orm.public_id,
        quote_request_id=orm.quote_request_id,
        position=orm.position,
        line_type=OrderLineType(orm.line_type),
        quantity=orm.quantity,
        unit=orm.unit,
        created=utc_aware(orm.created),
        project_id=orm.project_id,
        bought_item_id=orm.bought_item_id,
        source_item_id=orm.source_item_id,
        lot_position_id=orm.lot_position_id,
        virtual_name=orm.virtual_name,
        note=orm.note,
        awarded_supplier_id=orm.awarded_supplier_id,
        awarded_price=orm.awarded_price,
        awarded_at=utc_aware(orm.awarded_at),
        awarded_by_id=orm.awarded_by_id,
        dropped_at=utc_aware(orm.dropped_at),
        substitute_reason=orm.substitute_reason,
        substituted_by_line_id=orm.substituted_by_line_id,
        demands=[_demand_orm_to_entity(d) for d in orm.demands],
        item_name=name,
        item_code=code,
        project_number=orm.project.project_number if orm.project else "",
        lot_id=lot.id if lot is not None else None,
        lot_number=lot.lot_number if lot is not None else "",
        order_item_id=order_item.id if order_item is not None else None,
        order_id=order_item.order_id if order_item is not None else None,
        order_number=(
            order_item.order.order_number
            if order_item is not None and order_item.order is not None
            else ""
        ),
        award_live=any(i.canceled_at is None for i in orm.order_items),
    )


def _demand_orm_to_entity(orm: QuoteRequestLineDemandOrmModel) -> QuoteRequestLineDemand:
    bought = orm.bought_demand_item_id is not None
    return QuoteRequestLineDemand(
        id=orm.id,
        line_id=orm.line_id,
        family=QuoteRequestDemandFamily.BOUGHT if bought else QuoteRequestDemandFamily.SOURCE,
        demand_item_id=(orm.bought_demand_item_id if bought else orm.source_demand_item_id) or 0,
        quantity=orm.quantity,
    )


def demand_entity_to_orm(d: QuoteRequestLineDemand) -> QuoteRequestLineDemandOrmModel:
    bought = d.family == QuoteRequestDemandFamily.BOUGHT
    return QuoteRequestLineDemandOrmModel(
        bought_demand_item_id=d.demand_item_id if bought else None,
        source_demand_item_id=None if bought else d.demand_item_id,
        quantity=d.quantity,
    )


def _quote_orm_to_entity(orm: QuoteOrmModel) -> Quote:
    name, code = _item_identity(orm.substitute_bought_item, orm.substitute_source_item) or ("", "")
    return Quote(
        id=orm.id,
        supplier_row_id=orm.supplier_row_id,
        line_id=orm.line_id,
        unit_price=orm.unit_price,
        no_offer=orm.no_offer,
        lead_time_days=orm.lead_time_days,
        min_quantity=orm.min_quantity,
        note=orm.note,
        substitute_bought_item_id=orm.substitute_bought_item_id,
        substitute_source_item_id=orm.substitute_source_item_id,
        substitute_reason=orm.substitute_reason,
        substitute_item_name=name,
        substitute_item_code=code,
    )


def _cost_orm_to_entity(orm: QuoteExtraCostOrmModel) -> QuoteExtraCost:
    return QuoteExtraCost(
        id=orm.id,
        supplier_row_id=orm.supplier_row_id,
        kind=ExtraCostKind(orm.kind),
        amount=orm.amount,
        position=orm.position,
        label=orm.label,
        note=orm.note,
        line_id=orm.line_id,
    )


def supplier_orm_to_entity(orm: QuoteRequestSupplierOrmModel) -> QuoteRequestSupplier:
    return QuoteRequestSupplier(
        id=orm.id,
        public_id=orm.public_id,
        quote_request_id=orm.quote_request_id,
        supplier_id=orm.supplier_id,
        position=orm.position,
        sent_at=utc_aware(orm.sent_at),
        responded_at=utc_aware(orm.responded_at),
        declined_at=utc_aware(orm.declined_at),
        valid_until=orm.valid_until,
        note=orm.note,
        quotes=[_quote_orm_to_entity(q) for q in orm.quotes],
        extra_costs=[_cost_orm_to_entity(c) for c in orm.extra_costs],
        supplier_name=orm.supplier.name if orm.supplier else "",
        supplier_archived=bool(orm.supplier.archived) if orm.supplier else False,
    )


def quote_request_orm_to_entity(orm: QuoteRequestOrmModel) -> QuoteRequest:
    return QuoteRequest(
        id=orm.id,
        public_id=orm.public_id,
        request_number=orm.request_number,
        created=utc_aware(orm.created),
        changed=utc_aware(orm.changed),
        changes=list(orm.changes or []),
        status=QuoteRequestStatus(orm.status),
        note=orm.note,
        deadline=orm.deadline,
        closed_at=utc_aware(orm.closed_at),
        canceled_at=utc_aware(orm.canceled_at),
        edit_version=orm.edit_version,
        **creator_kwargs(orm.creator_id, orm.creator),
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
        lines=[line_orm_to_entity(line) for line in orm.lines],
        suppliers=[supplier_orm_to_entity(row) for row in orm.suppliers],
    )


def quote_request_entity_to_dict(r: QuoteRequest) -> dict[str, Any]:
    return {
        "request_number": r.request_number,
        "created": r.created,
        "changed": r.changed,
        "changes": r.changes,
        "status": r.status.value,
        "note": r.note,
        "deadline": r.deadline,
        "closed_at": r.closed_at,
        "canceled_at": r.canceled_at,
        "edit_version": r.edit_version,
        "creator_id": r.creator_id,
    }


def line_entity_to_dict(line: QuoteRequestLine) -> dict[str, Any]:
    return {
        "quote_request_id": line.quote_request_id,
        "position": line.position,
        "line_type": line.line_type.value,
        "quantity": line.quantity,
        "unit": line.unit,
        "created": line.created,
        "note": line.note,
        "virtual_name": line.virtual_name,
        "project_id": line.project_id,
        "bought_item_id": line.bought_item_id,
        "source_item_id": line.source_item_id,
        "lot_position_id": line.lot_position_id,
        "awarded_supplier_id": line.awarded_supplier_id,
        "awarded_price": line.awarded_price,
        "awarded_at": line.awarded_at,
        "awarded_by_id": line.awarded_by_id,
        "dropped_at": line.dropped_at,
        "substitute_reason": line.substitute_reason,
        "substituted_by_line_id": line.substituted_by_line_id,
    }


def supplier_entity_to_dict(row: QuoteRequestSupplier) -> dict[str, Any]:
    return {
        "quote_request_id": row.quote_request_id,
        "supplier_id": row.supplier_id,
        "position": row.position,
        "sent_at": row.sent_at,
        "responded_at": row.responded_at,
        "declined_at": row.declined_at,
        "valid_until": row.valid_until,
        "note": row.note,
    }


def quote_entity_to_orm(q: Quote) -> QuoteOrmModel:
    return QuoteOrmModel(
        line_id=q.line_id,
        unit_price=q.unit_price,
        no_offer=q.no_offer,
        lead_time_days=q.lead_time_days,
        min_quantity=q.min_quantity,
        note=q.note,
        substitute_bought_item_id=q.substitute_bought_item_id,
        substitute_source_item_id=q.substitute_source_item_id,
        substitute_reason=q.substitute_reason,
    )


def cost_entity_to_orm(c: QuoteExtraCost) -> QuoteExtraCostOrmModel:
    return QuoteExtraCostOrmModel(
        kind=c.kind.value,
        label=c.label,
        amount=c.amount,
        note=c.note,
        position=c.position,
        line_id=c.line_id,
    )
