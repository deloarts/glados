"""
Whether a lot needs our raw material, decided by its first position. A
supplier who does position 1 brings the material, so the lot then needs no
source demand and has nothing to approve. Position 1 made in house needs the
material for every piece, and a MIXED position 1 only for the pieces made in
house, the rest coming from its supplier lines.

While position 1 is unassigned, its routing predicts the answer: a position
whose every step is a fabrication step with a method that is required
external is expected to go to a supplier. The prediction is only used where
nothing is committed yet, at lot creation and when position 1 becomes
unassigned again; an assignment always wins over it.

The rules are pure. CreateLot, ApproveLotSource, SwitchLotMaterialSource and
the material follow-up of the lifecycle reconciler read the lot, call them
and write what they decide. No I/O.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.services.lifecycle.facts import LotPositionFacts
from src.modules.fulfillment.domain.services.lifecycle.lot_position import live_lines
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.source_approval_status import (
    SUPPLIER_MATERIAL_STATUSES,
)
from src.modules.fulfillment.domain.value_objects.source_approval_status import SourceApprovalStatus
from src.modules.platform.domain.services.quantities import quantity_eq
from src.modules.platform.domain.services.quantities import quantity_gt


class _RoutingStep(Protocol):
    """A lot step or a made item process: its role and whether its
    fabrication method is required external."""

    @property
    def role(self) -> StepRole: ...

    @property
    def fabrication_method_required_external(self) -> bool: ...


class MaterialSupply(Enum):
    """Who brings the material of a lot's first position."""

    # INTERNAL, or unassigned without the supplier prediction.
    OURS = "ours"
    # MIXED: ours for the pieces made in house, the supplier's for the rest.
    SHARED = "shared"
    # EXTERNAL.
    SUPPLIER = "supplier"
    # Unassigned, and the routing says a supplier does it.
    SUPPLIER_EXPECTED = "supplier_expected"


class DemandAction(Enum):
    """What happens to the lot's raw material demand."""

    NONE = "none"
    # A new demand for `MaterialDecision.quantity`.
    CREATE = "create"
    # The live demand's quantity becomes `MaterialDecision.quantity`.
    RESIZE = "resize"
    # The live demand ends the way a source switch ends it: canceled when
    # nothing reached it, else fulfilled with what arrived.
    SETTLE = "settle"


@dataclass(frozen=True)
class MaterialDecision:
    """The lot's new source approval status and what its demand does."""

    status: SourceApprovalStatus
    action: DemandAction = DemandAction.NONE
    quantity: float = 0.0


def predicts_supplier_material(steps: Iterable[_RoutingStep]) -> bool:
    """Whether a first position with these steps is expected to go to a
    supplier: it has steps, and every one is a fabrication step whose method
    is required external. An inspection is always done in house."""
    steps = list(steps)
    return bool(steps) and all(
        step.role == StepRole.FABRICATION and step.fabrication_method_required_external
        for step in steps
    )


def tracks_material(lot: ProductionLot) -> bool:
    """Whether the lot's material follows its first position: it has a
    bought or source item as its material source. A rework lot's material
    is the made item it reworks, which these rules leave alone."""
    return lot.source_made_item_id is None and (
        lot.source_item_id is not None or lot.source_bought_item_id is not None
    )


def first_position_supply(kind: LotPositionKind, *, predicted: bool) -> MaterialSupply:
    """Who brings position 1's material, from its derived kind and, while it
    is unassigned, the routing's prediction."""
    if kind == LotPositionKind.EXTERNAL:
        return MaterialSupply.SUPPLIER
    if kind == LotPositionKind.MIXED:
        return MaterialSupply.SHARED
    if kind == LotPositionKind.UNASSIGNED and predicted:
        return MaterialSupply.SUPPLIER_EXPECTED
    return MaterialSupply.OURS


def supplier_share(facts: LotPositionFacts) -> float:
    """The pieces of a position its live supplier lines hold. A line closed
    short holds what arrived, so the pieces it never brought count as ours
    again."""
    return sum((line.quantity for line in live_lines(facts)), 0.0)


def in_house_need(supply: MaterialSupply, position_quantity: float, supplier: float) -> float:
    """The pieces position 1 makes from our material."""
    if supply == MaterialSupply.OURS:
        return position_quantity
    if supply == MaterialSupply.SHARED:
        return max(position_quantity - supplier, 0.0)
    return 0.0


def initial_status(
    supply: MaterialSupply, *, approval_required: bool, source_is_item: bool
) -> SourceApprovalStatus:
    """The status of a lot that gets its material source now, at creation or
    on a source switch. Only a source item is approved, and only while the
    setting asks for it."""
    if supply == MaterialSupply.SUPPLIER:
        return SourceApprovalStatus.SUPPLIER_SOURCED
    if supply == MaterialSupply.SUPPLIER_EXPECTED:
        return SourceApprovalStatus.AWAITING_FIRST_STEP
    if approval_required and source_is_item:
        return SourceApprovalStatus.PENDING
    return SourceApprovalStatus.NOT_REQUIRED


def decide_material(
    supply: MaterialSupply,
    *,
    current: SourceApprovalStatus,
    live_demand_quantity: float | None,
    need: float,
    approval_required: bool,
    source_is_item: bool,
) -> MaterialDecision:
    """What a change of position 1 does to the lot's status and demand.
    `live_demand_quantity` is the quantity of the lot's open, allocated or
    ordered demand, None without one.

    A supplier's position 1 settles the demand. Ours, or a share of it,
    leaves a recorded decision as it is and sizes the live demand to the
    pieces made in house; a lot that needed no material until now is treated
    like a new one, which is pending approval or demands its material at
    once. A lot without a live demand that needed material before keeps
    without one, because a user ended that demand."""
    if supply in (MaterialSupply.SUPPLIER, MaterialSupply.SUPPLIER_EXPECTED):
        status = initial_status(
            supply, approval_required=approval_required, source_is_item=source_is_item
        )
        if live_demand_quantity is not None:
            return MaterialDecision(status, DemandAction.SETTLE)
        return MaterialDecision(status)

    if current in SUPPLIER_MATERIAL_STATUSES:
        status = initial_status(
            supply, approval_required=approval_required, source_is_item=source_is_item
        )
        if live_demand_quantity is None:
            if status == SourceApprovalStatus.PENDING or not quantity_gt(need, 0.0):
                return MaterialDecision(status)
            return MaterialDecision(status, DemandAction.CREATE, need)
    else:
        status = current
    if live_demand_quantity is None:
        return MaterialDecision(status)
    if not quantity_gt(need, 0.0):
        return MaterialDecision(status, DemandAction.SETTLE)
    if quantity_eq(live_demand_quantity, need):
        return MaterialDecision(status)
    return MaterialDecision(status, DemandAction.RESIZE, need)


def first_position(lot: ProductionLot) -> LotPosition | None:
    """The lot's position with the lowest sequence, None without positions."""
    return min(lot.positions, key=lambda p: p.sequence, default=None)


def position_supplier_share(position: LotPosition) -> float:
    """supplier_share for a loaded position, from the live line and the
    lines closed short that the repository joins onto it."""
    live = position.order_item_status not in (None, OrderItemStatus.CANCELED)
    on_live_line = (position.order_item_quantity or 0.0) if live else 0.0
    return on_live_line + position.closed_lines_quantity


def lot_supply(lot: ProductionLot, *, enabled: bool) -> MaterialSupply:
    """Who brings the material of the lot's first position, from its stored
    kind and steps. With the setting off, or for a lot whose material these
    rules leave alone, it is always ours."""
    position = first_position(lot)
    if not enabled or position is None or not tracks_material(lot):
        return MaterialSupply.OURS
    return first_position_supply(
        position.kind, predicted=predicts_supplier_material(position.steps)
    )


def capped_to_in_house(lot: ProductionLot, supply: MaterialSupply, quantity: float) -> float:
    """`quantity` of material, cut down to what a MIXED first position makes
    in house. Any other supply leaves it as it is, so a lot made in house
    keeps demanding what it always did."""
    position = first_position(lot)
    if supply != MaterialSupply.SHARED or position is None:
        return quantity
    need = in_house_need(supply, position.quantity, position_supplier_share(position))
    return min(quantity, need)
