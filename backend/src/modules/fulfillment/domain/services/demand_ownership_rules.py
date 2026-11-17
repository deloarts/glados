"""
Who may edit or cancel a bought or made item demand. Without
manage:demand_items an actor may change only a demand they created, and a
fulfilled or canceled demand is refused first. Both families share their
status values, so the made enum names them for both.
"""

from typing import Protocol

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.domain.errors import DemandItemAlreadyCanceledError
from src.modules.fulfillment.domain.errors import DemandItemAlreadyFulfilledError
from src.modules.fulfillment.domain.errors import DemandItemOfAnotherUserError
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.permission import Permission


class OwnedDemand(Protocol):
    @property
    def id(self) -> int: ...

    @property
    def status(self) -> str: ...

    @property
    def creator_id(self) -> int: ...


def assert_can_update_demand(actor: User, demand: OwnedDemand) -> None:
    """Raises unless `actor` may edit `demand`. A holder of
    manage:demand_items may edit any demand in any status."""
    assert_has_permission(actor, Permission.WRITE_DEMAND_ITEMS, "update", "demand items")
    if actor.has_permission(Permission.MANAGE_DEMAND_ITEMS):
        return
    if demand.status == MadeItemDemandStatus.FULFILLED:
        raise DemandItemAlreadyFulfilledError(
            f"Demand item #{demand.id} is already fulfilled and cannot be modified."
        )
    if demand.status == MadeItemDemandStatus.CANCELED:
        raise DemandItemAlreadyCanceledError(
            f"Demand item #{demand.id} is canceled and cannot be modified."
        )
    if demand.creator_id != actor.id:
        raise DemandItemOfAnotherUserError(
            f"User #{actor.id} ({actor.full_name}) tried to update demand item "
            f"#{demand.id} which belongs to another user."
        )


def assert_can_cancel_demand(actor: User, demand: OwnedDemand) -> None:
    """Raises unless `actor` may cancel `demand`. A fulfilled or canceled
    demand is refused for everyone."""
    if demand.status == MadeItemDemandStatus.FULFILLED:
        raise DemandItemAlreadyFulfilledError(
            f"Demand item #{demand.id} is already fulfilled and cannot be canceled."
        )
    if demand.status == MadeItemDemandStatus.CANCELED:
        raise DemandItemAlreadyCanceledError(f"Demand item #{demand.id} is already canceled.")
    if not actor.has_permission(Permission.MANAGE_DEMAND_ITEMS) and demand.creator_id != actor.id:
        raise DemandItemOfAnotherUserError(
            f"User #{actor.id} ({actor.full_name}) cannot cancel demand item "
            f"#{demand.id}, it belongs to another user."
        )
