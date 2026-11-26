"""
ORM <-> domain entity mapping helpers for the ProductionLot / LotStep /
LotPosition aggregate. Not part of the public API of this package.
"""

from functools import lru_cache
from typing import Any
from typing import cast

from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.catalogue.adapters.outbound.persistence.models.source_item_model import (
    SourceItemOrmModel,
)
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_event_model import (
    LotEventOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
    LotPositionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_provision_model import (
    LotPositionProvisionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_step_model import (
    LotStepOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.domain.entities.lot_event import LotEvent
from src.modules.fulfillment.domain.entities.lot_event import LotEventEntity
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_position_provision import LotPositionProvision
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.lot_origin_disposition import LotOriginDisposition
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.source_approval_status import SourceApprovalStatus
from src.modules.platform.adapters.outbound.persistence.mapping_common import changed_by_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import creator_kwargs
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.platform.infrastructure.label_languages import resolve_label
from src.modules.workspace.adapters.outbound.persistence.models.project_model import ProjectOrmModel

# ── LotStep ──────────────────────────────────────────────────────────


# Loader options per mapper, built lazily and cached: constructing them
# configures the mappers, which fails at import time if a model referenced by
# string is not registered yet. Each set lists every relationship its mapper
# dereferences, because the models are lazy="raise_on_sql". user_orm_to_entity
# reads UserOrmModel.members, which is lazy="selectin" itself.
@lru_cache(maxsize=1)
def step_load_options() -> tuple[ORMOption, ...]:
    """Everything step_orm_to_entity dereferences."""
    return (
        selectinload(LotStepOrmModel.fabrication_method),
        selectinload(LotStepOrmModel.inspection_method),
    )


def _method_wait_after_minutes(orm: LotStepOrmModel, is_inspection: bool) -> int | None:
    """The wait of the method that does the step: the inspection method's
    for an inspection step, the fabrication method's otherwise."""
    method = orm.inspection_method if is_inspection else orm.fabrication_method
    return method.wait_after_minutes if method is not None else None


def step_orm_to_entity(orm: LotStepOrmModel) -> LotStep:
    is_inspection = orm.role == StepRole.INSPECTION.value
    return LotStep(
        id=orm.id,
        public_id=orm.public_id,
        created=orm.created,
        note=orm.note,
        estimated_setup_minutes=orm.estimated_setup_minutes,
        estimated_minutes_per_piece=orm.estimated_minutes_per_piece,
        sequence=orm.sequence,
        creator_id=orm.creator_id,
        fabrication_method_id=orm.fabrication_method_id,
        lot_id=orm.lot_id,
        position_id=orm.position_id,
        source_process_id=orm.source_process_id,
        role=StepRole(orm.role),
        inspection_method_id=orm.inspection_method_id,
        fabrication_method_name=(
            LocalizedText(values=dict(orm.fabrication_method.name or {}))
            if orm.fabrication_method
            else LocalizedText()
        ),
        fabrication_method_requires_machine=(
            False
            if is_inspection
            else (orm.fabrication_method.requires_machine if orm.fabrication_method else True)
        ),
        fabrication_method_required_external=(
            orm.fabrication_method.required_external if orm.fabrication_method else False
        ),
        fabrication_method_default_supplier_id=(
            orm.fabrication_method.default_supplier_id if orm.fabrication_method else None
        ),
        fabrication_method_lead_time_days=(
            orm.fabrication_method.lead_time_days if orm.fabrication_method else None
        ),
        inspection_method_name=(
            LocalizedText(values=dict(orm.inspection_method.name or {}))
            if orm.inspection_method
            else None
        ),
        inspection_method_requires_evidence=(
            orm.inspection_method.requires_evidence if orm.inspection_method else None
        ),
        method_wait_after_minutes=_method_wait_after_minutes(orm, is_inspection),
        time_budget_per_piece=orm.time_budget_per_piece,
    )


def step_entity_to_dict(step: LotStep) -> dict[str, Any]:
    return {
        "created": step.created,
        "note": step.note,
        "estimated_setup_minutes": step.estimated_setup_minutes,
        "estimated_minutes_per_piece": step.estimated_minutes_per_piece,
        "sequence": step.sequence,
        "creator_id": step.creator_id,
        "fabrication_method_id": step.fabrication_method_id,
        "lot_id": step.lot_id,
        "position_id": step.position_id,
        "source_process_id": step.source_process_id,
        "role": step.role.value,
        "inspection_method_id": step.inspection_method_id,
        "time_budget_per_piece": step.time_budget_per_piece,
    }


# ── LotPosition ──────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def position_load_options() -> tuple[ORMOption, ...]:
    """Everything position_orm_to_entity dereferences."""
    return (
        load_user(LotPositionOrmModel.creator),
        load_user(LotPositionOrmModel.changed_by),
        selectinload(LotPositionOrmModel.steps).selectinload(LotStepOrmModel.fabrication_method),
        selectinload(LotPositionOrmModel.steps).selectinload(LotStepOrmModel.inspection_method),
    )


def position_orm_to_entity(orm: LotPositionOrmModel) -> LotPosition:
    return LotPosition(
        id=orm.id,
        public_id=orm.public_id,
        created=orm.created,
        changed=orm.changed,
        changes=list(orm.changes or []),
        sequence=orm.sequence,
        kind=LotPositionKind(orm.kind),
        status=LotPositionStatus(orm.status),
        quantity=orm.quantity,
        quantity_completed=orm.quantity_completed,
        note=orm.note,
        **creator_kwargs(orm.creator_id, orm.creator),
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
        lot_id=orm.lot_id,
        steps=[step_orm_to_entity(s) for s in sorted(orm.steps, key=lambda s: s.sequence)],
        planned_pickup_date=orm.planned_pickup_date,
        planned_delivery_date=orm.planned_delivery_date,
        latest_pickup_date=orm.latest_pickup_date,
        latest_delivery_date=orm.latest_delivery_date,
    )


def position_entity_to_dict(position: LotPosition) -> dict[str, Any]:
    return {
        "created": position.created,
        "changed": position.changed,
        "changes": position.changes,
        "sequence": position.sequence,
        "kind": position.kind.value,
        "status": position.status.value,
        "quantity": position.quantity,
        "quantity_completed": position.quantity_completed,
        "note": position.note,
        "creator_id": position.creator_id,
        "lot_id": position.lot_id,
        "planned_pickup_date": position.planned_pickup_date,
        "planned_delivery_date": position.planned_delivery_date,
        "latest_pickup_date": position.latest_pickup_date,
        "latest_delivery_date": position.latest_delivery_date,
    }


# ── LotPositionProvision ─────────────────────────────────────────────


@lru_cache(maxsize=1)
def provision_load_options() -> tuple[ORMOption, ...]:
    """Everything provision_orm_to_entity dereferences."""
    return (load_user(LotPositionProvisionOrmModel.creator),)


def provision_orm_to_entity(orm: LotPositionProvisionOrmModel) -> LotPositionProvision:
    return LotPositionProvision(
        id=orm.id,
        public_id=orm.public_id,
        lot_position_id=orm.lot_position_id,
        quantity=orm.quantity,
        provision_date=orm.provision_date,
        note=orm.note,
        **creator_kwargs(orm.creator_id, orm.creator),
        created=orm.created,
    )


def provision_entity_to_dict(p: LotPositionProvision) -> dict[str, Any]:
    return {
        "lot_position_id": p.lot_position_id,
        "quantity": p.quantity,
        "provision_date": p.provision_date,
        "note": p.note,
        "creator_id": p.creator_id,
        "created": p.created,
    }


# ── LotEvent ─────────────────────────────────────────────────────────


_EVENT_ENTITIES: frozenset[str] = frozenset({"lot", "position", "step", "order"})


def _event_entity(stored: str) -> LotEventEntity:
    if stored in _EVENT_ENTITIES:
        return cast(LotEventEntity, stored)
    raise ValueError(f"Unknown lot event entity {stored!r}.")


def event_orm_to_entity(orm: LotEventOrmModel) -> LotEvent:
    return LotEvent(
        id=orm.id,
        public_id=orm.public_id,
        lot_id=orm.lot_id,
        occurred_at=orm.occurred_at,
        actor_id=orm.actor_id,
        actor_username=orm.actor_username,
        actor_full_name=orm.actor_full_name,
        event_type=LotEventType(orm.event_type),
        entity=_event_entity(orm.entity),
        entity_id=orm.entity_id,
        summary=orm.summary,
        payload=orm.payload,
    )


def event_entity_to_dict(e: LotEvent) -> dict[str, Any]:
    return {
        "lot_id": e.lot_id,
        "occurred_at": e.occurred_at,
        "actor_id": e.actor_id,
        "actor_username": e.actor_username,
        "actor_full_name": e.actor_full_name,
        "event_type": e.event_type.value,
        "entity": e.entity,
        "entity_id": e.entity_id,
        "summary": e.summary,
        "payload": e.payload,
    }


# ── ProductionLot ────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def lot_load_options() -> tuple[ORMOption, ...]:
    """Everything lot_orm_to_entity dereferences."""
    return (
        selectinload(ProductionLotOrmModel.positions)
        .selectinload(LotPositionOrmModel.steps)
        .selectinload(LotStepOrmModel.fabrication_method),
        selectinload(ProductionLotOrmModel.positions)
        .selectinload(LotPositionOrmModel.steps)
        .selectinload(LotStepOrmModel.inspection_method),
        load_user(ProductionLotOrmModel.positions, LotPositionOrmModel.creator),
        load_user(ProductionLotOrmModel.positions, LotPositionOrmModel.changed_by),
        load_user(ProductionLotOrmModel.creator),
        load_user(ProductionLotOrmModel.changed_by),
        selectinload(ProductionLotOrmModel.made_item),
        selectinload(ProductionLotOrmModel.project).selectinload(ProjectOrmModel.customer),
        selectinload(ProductionLotOrmModel.project).selectinload(ProjectOrmModel.product),
        selectinload(ProductionLotOrmModel.source_bought_item),
        selectinload(ProductionLotOrmModel.source_item).selectinload(SourceItemOrmModel.type),
        selectinload(ProductionLotOrmModel.source_made_item),
    )


def _lot_source_label(orm: ProductionLotOrmModel) -> str:
    if orm.source_bought_item:
        return orm.source_bought_item.article_name
    if orm.source_item:
        return orm.source_item.dimension or f"Source item #{orm.source_item.id}"
    if orm.source_made_item:
        return orm.source_made_item.part_number or orm.source_made_item.article_name
    return ""


def _lot_source_sublabel(orm: ProductionLotOrmModel) -> str:
    if orm.source_bought_item:
        return orm.source_bought_item.order_code_1
    if orm.source_item:
        type_name = resolve_label(orm.source_item.type.name) if orm.source_item.type else None
        return " | ".join(part for part in (orm.source_item.material, type_name) if part)
    if orm.source_made_item:
        return orm.source_made_item.article_name
    return ""


def _lot_source_material(orm: ProductionLotOrmModel) -> str:
    if orm.source_item:
        return orm.source_item.material or ""
    return ""


def lot_orm_to_entity(orm: ProductionLotOrmModel) -> ProductionLot:
    positions = [position_orm_to_entity(p) for p in sorted(orm.positions, key=lambda p: p.sequence)]
    flat_steps = sorted(
        (step for position in positions for step in position.steps),
        key=lambda s: s.sequence,
    )
    return ProductionLot(
        id=orm.id,
        public_id=orm.public_id,
        created=orm.created,
        changed=orm.changed,
        changes=list(orm.changes or []),
        lot_number=orm.lot_number,
        quantity=orm.quantity,
        status=LotStatus(orm.status),
        priority=UrgencyClass(orm.priority),
        note=orm.note,
        required_delivery_date=orm.required_delivery_date,
        completed_at=orm.completed_at,
        quantity_scrapped=orm.quantity_scrapped,
        **creator_kwargs(orm.creator_id, orm.creator),
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
        made_item_id=orm.made_item_id,
        project_id=orm.project_id,
        input_demand_id=orm.input_demand_id,
        source_bought_item_id=orm.source_bought_item_id,
        source_item_id=orm.source_item_id,
        source_made_item_id=orm.source_made_item_id,
        origin_lot_id=orm.origin_lot_id,
        origin_disposition=(
            LotOriginDisposition(orm.origin_disposition)
            if orm.origin_disposition is not None
            else None
        ),
        source_approval_status=SourceApprovalStatus(orm.source_approval_status),
        source_approved_by_id=orm.source_approved_by_id,
        source_approved_date=orm.source_approved_date,
        source_rejected_by_id=orm.source_rejected_by_id,
        source_rejected_date=orm.source_rejected_date,
        source_rejection_reason=orm.source_rejection_reason,
        held_at=orm.held_at,
        canceled_at=orm.canceled_at,
        edit_version=orm.edit_version,
        force_completed_at=orm.force_completed_at,
        made_item_part_number=(orm.made_item.part_number or "") if orm.made_item else "",
        made_item_article_name=orm.made_item.article_name if orm.made_item else "",
        made_item_revision=orm.made_item.revision if orm.made_item else "",
        made_item_material=(orm.made_item.material or "") if orm.made_item else "",
        made_item_public_id=orm.made_item.public_id if orm.made_item else None,
        source_label=_lot_source_label(orm),
        source_sublabel=_lot_source_sublabel(orm),
        source_material=_lot_source_material(orm),
        project_number=orm.project.project_number if orm.project else "",
        project_customer=orm.project.customer.name if orm.project and orm.project.customer else "",
        product_id=orm.project.product_id if orm.project else None,
        product_number=(
            orm.project.product.product_number if orm.project and orm.project.product else None
        ),
        positions=positions,
        steps=flat_steps,
    )


def lot_entity_to_dict(lot: ProductionLot) -> dict[str, Any]:
    return {
        "created": lot.created,
        "changed": lot.changed,
        "changes": lot.changes,
        "lot_number": lot.lot_number,
        "quantity": lot.quantity,
        "status": lot.status.value,
        "priority": lot.priority.value,
        "note": lot.note,
        "required_delivery_date": lot.required_delivery_date,
        "completed_at": lot.completed_at,
        "quantity_scrapped": lot.quantity_scrapped,
        "creator_id": lot.creator_id,
        "made_item_id": lot.made_item_id,
        "project_id": lot.project_id,
        "input_demand_id": lot.input_demand_id,
        "source_bought_item_id": lot.source_bought_item_id,
        "source_item_id": lot.source_item_id,
        "source_made_item_id": lot.source_made_item_id,
        "origin_lot_id": lot.origin_lot_id,
        "origin_disposition": (
            lot.origin_disposition.value if lot.origin_disposition is not None else None
        ),
        "source_approval_status": lot.source_approval_status.value,
        "source_approved_by_id": lot.source_approved_by_id,
        "source_approved_date": lot.source_approved_date,
        "source_rejected_by_id": lot.source_rejected_by_id,
        "source_rejected_date": lot.source_rejected_date,
        "source_rejection_reason": lot.source_rejection_reason,
        "held_at": lot.held_at,
        "canceled_at": lot.canceled_at,
        "edit_version": lot.edit_version,
        "force_completed_at": lot.force_completed_at,
    }
