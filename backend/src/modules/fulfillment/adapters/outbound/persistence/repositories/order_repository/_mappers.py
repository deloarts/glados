"""
ORM <-> domain entity mapping helpers shared by the order aggregate
repositories in this package. Not part of the public API of this package,
each repository module imports only the mappers it needs.
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
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_step_model import (
    LotStepOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_extra_cost_model import (
    OrderExtraCostOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_delivery_model import (
    OrderItemDeliveryOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_model import OrderOrmModel
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteRequestLineOrmModel,
)
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order import OrderQuoteRequestRef
from src.modules.fulfillment.domain.entities.order_extra_cost import OrderExtraCost
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.order_item_delivery import OrderItemDelivery
from src.modules.fulfillment.domain.value_objects.extra_cost_kind import ExtraCostKind
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.rejection_outcome import RejectionOutcome
from src.modules.platform.adapters.outbound.persistence.mapping_common import changed_by_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import creator_kwargs
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user
from src.modules.platform.adapters.outbound.persistence.user_loading import user_orm_to_entity
from src.modules.platform.infrastructure.label_languages import resolve_label
from src.modules.workspace.adapters.outbound.persistence.models.project_model import ProjectOrmModel
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus

# The load-option sets below are built on first use and cached, not held in
# module-level tuples: constructing a loader option inspects the mapper, which
# forces registry configuration, and at import time not every model module is
# registered yet, so building them at module scope breaks unrelated mappers.
# Each set lists every relationship its mapper dereferences, because all
# relationships are lazy="raise_on_sql" and a missing one fails at mapping time.
# UserOrmModel.members, read by user_orm_to_entity, is lazy="selectin" itself.

# ── Order ─────────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def order_load_options() -> tuple[ORMOption, ...]:
    """Everything order_orm_to_entity() dereferences."""
    return (
        load_user(OrderOrmModel.creator),
        load_user(OrderOrmModel.changed_by),
        selectinload(OrderOrmModel.supplier),
        selectinload(OrderOrmModel.extra_costs),
        selectinload(OrderOrmModel.quote_requests),
    )


def order_orm_to_entity(orm: OrderOrmModel) -> Order:
    return Order(
        id=orm.id,
        public_id=orm.public_id,
        order_number=orm.order_number,
        created=orm.created,
        changed=orm.changed,
        changes=list(orm.changes or []),
        status=OrderStatus(orm.status),
        note=orm.note,
        ordered_date=orm.ordered_date,
        expected_delivery_date=orm.expected_delivery_date,
        delivery_date=orm.delivery_date,
        storage_place=orm.storage_place,
        **creator_kwargs(orm.creator_id, orm.creator),
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
        supplier_id=orm.supplier_id,
        requested_at=orm.requested_at,
        canceled_at=orm.canceled_at,
        edit_version=orm.edit_version,
        supplier_name=orm.supplier.name if orm.supplier else "",
        supplier_vat_id=(orm.supplier.vat_id or "") if orm.supplier else "",
        supplier_archived=bool(orm.supplier.archived) if orm.supplier else False,
        extra_costs=[order_extra_cost_orm_to_entity(c) for c in orm.extra_costs],
        # Several lines from one request reach it once each through the join.
        quote_requests=list(
            {
                r.id: OrderQuoteRequestRef(id=r.id, request_number=r.request_number)
                for r in orm.quote_requests
            }.values()
        ),
    )


def order_extra_cost_orm_to_entity(orm: OrderExtraCostOrmModel) -> OrderExtraCost:
    return OrderExtraCost(
        id=orm.id,
        public_id=orm.public_id,
        order_id=orm.order_id,
        kind=ExtraCostKind(orm.kind),
        amount=orm.amount,
        position=orm.position,
        label=orm.label,
        note=orm.note,
        order_item_id=orm.order_item_id,
    )


def order_extra_cost_entity_to_dict(c: OrderExtraCost) -> dict[str, Any]:
    return {
        "order_id": c.order_id,
        "kind": c.kind.value,
        "amount": c.amount,
        "position": c.position,
        "label": c.label,
        "note": c.note,
        "order_item_id": c.order_item_id,
    }


def order_entity_to_dict(o: Order) -> dict[str, Any]:
    return {
        "order_number": o.order_number,
        "created": o.created,
        "changed": o.changed,
        "changes": o.changes,
        "status": o.status.value,
        "note": o.note,
        "ordered_date": o.ordered_date,
        "expected_delivery_date": o.expected_delivery_date,
        "delivery_date": o.delivery_date,
        "storage_place": o.storage_place,
        "creator_id": o.creator_id,
        "supplier_id": o.supplier_id,
        "requested_at": o.requested_at,
        "canceled_at": o.canceled_at,
        "edit_version": o.edit_version,
    }


# ── OrderItem ─────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def order_item_load_options() -> tuple[ORMOption, ...]:
    """Everything order_item_orm_to_entity() dereferences.

    The mapper resolves the display identity of every line from its live
    catalogue row, and a MADE line reaches its made item and fabrication
    methods indirectly through lot_position, so a page of order items needs
    the whole tree loaded up front.
    """
    return (
        load_user(OrderItemOrmModel.creator),
        load_user(OrderItemOrmModel.changed_by),
        load_user(OrderItemOrmModel.orderer),
        load_user(OrderItemOrmModel.receiver),
        selectinload(OrderItemOrmModel.supplier),
        selectinload(OrderItemOrmModel.bought_item).selectinload(BoughtItemOrmModel.manufacturer),
        selectinload(OrderItemOrmModel.source_item).selectinload(SourceItemOrmModel.type),
        selectinload(OrderItemOrmModel.source_item).selectinload(SourceItemOrmModel.manufacturer),
        selectinload(OrderItemOrmModel.project).selectinload(ProjectOrmModel.customer),
        selectinload(OrderItemOrmModel.project).selectinload(ProjectOrmModel.product),
        selectinload(OrderItemOrmModel.lot_position)
        .selectinload(LotPositionOrmModel.lot)
        .selectinload(ProductionLotOrmModel.made_item),
        selectinload(OrderItemOrmModel.lot_position)
        .selectinload(LotPositionOrmModel.steps)
        .selectinload(LotStepOrmModel.fabrication_method),
        selectinload(OrderItemOrmModel.quote_request_line).selectinload(
            QuoteRequestLineOrmModel.quote_request
        ),
    )


def order_item_orm_to_entity(orm: OrderItemOrmModel) -> OrderItem:
    # Display identity is resolved per line type, always from the live
    # catalogue row so a rename propagates to lines already on an order:
    #   BOUGHT  → orm.bought_item
    #   SOURCE  → orm.source_item (dimension/material/type, mirroring the
    #             lots list's own source-item label/sublabel)
    #   MADE    → made_item, reached through the lot position
    #   VIRTUAL → orm.virtual_name, the only line type with no catalogue row
    made_item = (
        orm.lot_position.lot.made_item if orm.lot_position and orm.lot_position.lot else None
    )
    bought_item = orm.bought_item
    source_item = orm.source_item

    # item_order_code_1/2 mean strictly "this line's real supplier order
    # code": filled for BOUGHT and SOURCE (both have their own catalogue
    # order codes), empty for MADE/VIRTUAL (neither has one). The
    # "material | type" descriptor a SOURCE line shows in place of a code
    # when it has none lives in item_specification instead, so a code field
    # never carries a descriptor.
    if bought_item:
        item_order_code_1 = bought_item.order_code_1
        item_order_code_2 = bought_item.order_code_2
    elif source_item:
        item_order_code_1 = source_item.order_code_1 or ""
        item_order_code_2 = source_item.order_code_2
    else:
        item_order_code_1 = ""
        item_order_code_2 = None

    item_specification = (
        " | ".join(
            part for part in (source_item.material, resolve_label(source_item.type.name)) if part
        )
        if source_item and source_item.type
        else ""
    )

    # The individually addressable counterparts of the descriptors above.
    # item_article_name/item_specification keep their current meaning: the
    # order table renders a SOURCE line as "dimension" over "material | type",
    # but a consumer that needs the parts separately (a supplier order-mail
    # table with its own Material and Dimension columns) cannot split those
    # strings back apart. Each field stays None wherever the line type has no
    # such concept, so it renders as an empty cell rather than a wrong value.
    item_material: str | None = None
    item_dimension: str | None = None
    item_type_name: str | None = None
    item_revision: str | None = None
    item_base_size: str | None = None
    item_mass: int | None = None
    item_manufacturer: str | None = None
    if source_item:
        item_material = source_item.material or None
        item_dimension = source_item.dimension
        item_type_name = resolve_label(source_item.type.name) if source_item.type else None
        item_mass = source_item.mass
        item_manufacturer = source_item.manufacturer.name if source_item.manufacturer else None
    elif made_item:
        item_material = made_item.material
        item_revision = made_item.revision or None
        item_base_size = made_item.base_size
        item_mass = made_item.mass
    elif bought_item:
        item_mass = bought_item.mass
        item_manufacturer = bought_item.manufacturer.name if bought_item.manufacturer else None

    return OrderItem(
        id=orm.id,
        public_id=orm.public_id,
        created=orm.created,
        changed=orm.changed,
        changes=list(orm.changes or []),
        status=OrderItemStatus(orm.status),
        position=orm.position,
        quantity=orm.quantity,
        quantity_delivered=orm.quantity_delivered,
        quantity_rejected=orm.quantity_rejected,
        quantity_rejected_lost=orm.quantity_rejected_lost,
        unit=orm.unit,
        items_per_unit=orm.items_per_unit,
        price=orm.price,
        note=orm.note,
        ordered_date=orm.ordered_date,
        expected_delivery_date=orm.expected_delivery_date,
        delivery_date=orm.delivery_date,
        storage_place=orm.storage_place,
        expected_pickup_date=orm.expected_pickup_date,
        ready_for_pickup_date=orm.ready_for_pickup_date,
        **creator_kwargs(orm.creator_id, orm.creator),
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
        orderer_id=orm.orderer_id,
        receiver_id=orm.receiver_id,
        bought_item_id=orm.bought_item_id,
        order_id=orm.order_id,
        supplier_id=orm.supplier_id,
        project_id=orm.project_id,
        line_type=OrderLineType(orm.line_type),
        lot_position_id=orm.lot_position_id,
        source_item_id=orm.source_item_id,
        quote_request_line_id=orm.quote_request_line_id,
        quote_request_id=(
            orm.quote_request_line.quote_request_id if orm.quote_request_line else None
        ),
        quote_request_number=(
            orm.quote_request_line.quote_request.request_number
            if orm.quote_request_line and orm.quote_request_line.quote_request
            else ""
        ),
        virtual_name=orm.virtual_name,
        requested_at=orm.requested_at,
        canceled_at=orm.canceled_at,
        edit_version=orm.edit_version,
        closed_short_at=orm.closed_short_at,
        closed_short_from=orm.closed_short_from,
        orderer=user_orm_to_entity(orm.orderer) if orm.orderer else None,
        receiver=user_orm_to_entity(orm.receiver) if orm.receiver else None,
        # A MadeItem has no order code of its own; its part number is
        # carried by item_part_number below.
        item_order_code_1=item_order_code_1,
        item_order_code_2=item_order_code_2,
        item_specification=item_specification,
        item_article_name=(
            bought_item.article_name
            if bought_item
            else (source_item.dimension or f"Source item #{source_item.id}")
            if source_item
            else made_item.article_name
            if made_item
            else (orm.virtual_name or "")
        ),
        item_part_number=bought_item.part_number
        if bought_item
        else (made_item.part_number if made_item else None),
        item_material=item_material,
        item_dimension=item_dimension,
        item_type_name=item_type_name,
        item_revision=item_revision,
        item_base_size=item_base_size,
        item_mass=item_mass,
        item_manufacturer=item_manufacturer,
        made_item_id=made_item.id if made_item else None,
        supplier_name=orm.supplier.name if orm.supplier else "",
        supplier_external_lead_time_days=(
            orm.supplier.external_lead_time_days if orm.supplier else None
        ),
        project_number=orm.project.project_number if orm.project else "",
        product_number=(
            orm.project.product.product_number if orm.project and orm.project.product else None
        ),
        project_customer=orm.project.customer.name
        if (orm.project and orm.project.customer)
        else "",
        project_description=(orm.project.description or "") if orm.project else "",
        project_status=ProjectStatus(orm.project.status) if orm.project else ProjectStatus.ARCHIVED,
        lot_id=orm.lot_position.lot_id if orm.lot_position else None,
        lot_number=orm.lot_position.lot.lot_number
        if orm.lot_position and orm.lot_position.lot
        else "",
        fabrication_method=", ".join(
            dict.fromkeys(
                resolve_label(s.fabrication_method.name)
                for s in orm.lot_position.steps
                if s.fabrication_method
            )
        )
        if orm.lot_position
        else "",
    )


def order_item_entity_to_dict(i: OrderItem) -> dict[str, Any]:
    return {
        "created": i.created,
        "changed": i.changed,
        "changes": i.changes,
        "status": i.status.value,
        "position": i.position,
        "quantity": i.quantity,
        "quantity_delivered": i.quantity_delivered,
        "quantity_rejected": i.quantity_rejected,
        "quantity_rejected_lost": i.quantity_rejected_lost,
        "unit": i.unit,
        "items_per_unit": i.items_per_unit,
        "price": i.price,
        "note": i.note,
        "ordered_date": i.ordered_date,
        "expected_delivery_date": i.expected_delivery_date,
        "delivery_date": i.delivery_date,
        "storage_place": i.storage_place,
        "expected_pickup_date": i.expected_pickup_date,
        "ready_for_pickup_date": i.ready_for_pickup_date,
        "creator_id": i.creator_id,
        "orderer_id": i.orderer_id,
        "receiver_id": i.receiver_id,
        "bought_item_id": i.bought_item_id,
        "order_id": i.order_id,
        "supplier_id": i.supplier_id,
        "project_id": i.project_id,
        "line_type": i.line_type.value,
        "lot_position_id": i.lot_position_id,
        "source_item_id": i.source_item_id,
        "quote_request_line_id": i.quote_request_line_id,
        "virtual_name": i.virtual_name,
        "requested_at": i.requested_at,
        "canceled_at": i.canceled_at,
        "edit_version": i.edit_version,
        "closed_short_at": i.closed_short_at,
        "closed_short_from": i.closed_short_from,
    }


# ── OrderItemDelivery ────────────────────────────────────────────────


@lru_cache(maxsize=1)
def delivery_load_options() -> tuple[ORMOption, ...]:
    """Everything delivery_orm_to_entity() dereferences."""
    return (load_user(OrderItemDeliveryOrmModel.receiver),)


def delivery_orm_to_entity(orm: OrderItemDeliveryOrmModel) -> OrderItemDelivery:
    return OrderItemDelivery(
        id=orm.id,
        public_id=orm.public_id,
        order_item_id=orm.order_item_id,
        quantity=orm.quantity,
        delivery_date=orm.delivery_date,
        storage_place=orm.storage_place,
        receiver_id=orm.receiver_id,
        created=orm.created,
        quantity_rejected=orm.quantity_rejected,
        rejection_reason=orm.rejection_reason,
        rejection_note=orm.rejection_note,
        rejection_outcome=(
            RejectionOutcome(orm.rejection_outcome) if orm.rejection_outcome is not None else None
        ),
        corrects_delivery_id=orm.corrects_delivery_id,
        correction_reason=orm.correction_reason,
        supplier_batch=orm.supplier_batch,
        delivery_note_number=orm.delivery_note_number,
        certificate_reference=orm.certificate_reference,
        damage_noted_on_delivery_note=orm.damage_noted_on_delivery_note,
        receiver=user_orm_to_entity(orm.receiver) if orm.receiver else None,
    )
