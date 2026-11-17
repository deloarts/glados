"""
Who may set the status of a demand by hand, and which statuses can be set
at all. One rule serves the bought, made and source item demand families, so
their three status endpoints cannot drift apart.

A demand's status is derived from its quantity, its allocations and two
intents (lifecycle/demand.py). The only statuses a user sets are those two
intents: CANCELED, recorded as canceled_at, and FULFILLED, recorded as
fulfilled_manually_at. OPEN, ALLOCATED and ORDERED follow from the
allocations and cannot be set. Changing a status needs write:demand_items.
Without manage:demand_items an actor may change only the demands they
created, and never to FULFILLED or CANCELED, because both are irreversible,
so in practice both need manage:demand_items.

The permission rule reads the requested status as the caller sent it, before
the use case parses it, so a caller without permission is refused even for
an unknown or unchanged status. Whether the demand may take the intent now
is decided by the demand intent table (lifecycle/intents.py DEMAND_INTENTS)
through assert_demand_intent. No I/O.
"""

from typing import Protocol

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.domain.errors import DemandItemHasAllocationsError
from src.modules.fulfillment.domain.errors import DemandItemInvalidStatusTransitionError
from src.modules.fulfillment.domain.errors import DemandItemOfAnotherUserError
from src.modules.fulfillment.domain.errors import SourceItemDemandLotStartedError
from src.modules.fulfillment.domain.services.lifecycle.intents import DEMAND_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import DemandContext
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import DomainError
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction

# Bought, made and source demands share their status values, so the made
# enum names the irreversible targets for all three families.
_IRREVERSIBLE_TARGETS = (
    MadeItemDemandStatus.FULFILLED,
    MadeItemDemandStatus.CANCELED,
)


# The statuses a user can set, as the intent each records.
MANUAL_DEMAND_STATUSES = {
    MadeItemDemandStatus.CANCELED.value: LifecycleAction.CANCEL,
    MadeItemDemandStatus.FULFILLED.value: LifecycleAction.FULFIL,
}


class _Demand(Protocol):
    @property
    def id(self) -> int: ...

    @property
    def creator_id(self) -> int: ...


class _DemandWithStatus(_Demand, Protocol):
    @property
    def status(self) -> str: ...


def assert_can_change_demand_status(actor: User, demand: _Demand, target: str) -> None:
    """Raise unless `actor` may move `demand` to the requested status `target`.

    The creator check runs before the target check, so another user's demand
    is reported as such whatever the target."""
    if not actor.has_permission(Permission.WRITE_DEMAND_ITEMS):
        raise InsufficientPermissionsError(
            f"User #{actor.id} ({actor.full_name}) cannot update demand items."
        )
    if actor.has_permission(Permission.MANAGE_DEMAND_ITEMS):
        return
    if demand.creator_id != actor.id:
        raise DemandItemOfAnotherUserError(
            f"User #{actor.id} ({actor.full_name}) tried to change the status of "
            f"demand item #{demand.id} which belongs to another user."
        )
    if target in _IRREVERSIBLE_TARGETS:
        raise InsufficientPermissionsError(
            f"Moving demand item #{demand.id} to {target!r} is irreversible and "
            f"requires the manage:demand_items permission."
        )


def manual_demand_action(demand_id: int, target: str) -> LifecycleAction:
    """The intent a requested status records: CANCEL for `canceled`,
    FULFIL for `fulfilled`. Any other value, a derived status included, is
    refused (422), since OPEN, ALLOCATED and ORDERED follow from the
    allocations."""
    action = MANUAL_DEMAND_STATUSES.get(target)
    if action is None:
        raise DemandItemInvalidStatusTransitionError(
            f"Demand item #{demand_id} cannot be set to {target!r} by hand. Only "
            f"{sorted(MANUAL_DEMAND_STATUSES)} can be set; open, allocated and ordered "
            f"follow from the demand's allocations."
        )
    return action


def assert_demand_intent(
    actor: User,
    action: LifecycleAction,
    demand: _DemandWithStatus,
    *,
    has_allocations: bool,
    already_fulfilled_error: type[DomainError],
    already_canceled_error: type[DomainError],
    noun: str,
    lot_started: bool = False,
) -> None:
    """Raises unless the demand intent table allows `action` on the demand
    now: a fulfilled or canceled demand takes no intent (409 with the
    family's error), a demand that holds allocations is not deleted (409),
    and the raw material demand of a lot that started production is not
    canceled (409). `lot_started` is only ever set for raw material
    demands."""
    refusal = DEMAND_INTENTS.check(
        action,
        demand,
        DemandContext(has_allocations=has_allocations, lot_started=lot_started),
        actor,
    )
    if refusal is None:
        return
    if action is LifecycleAction.REMOVE:
        raise DemandItemHasAllocationsError(
            f"{noun} #{demand.id} still holds allocations; cancel it instead, which releases them."
        )
    if not refusal.by_status:
        raise SourceItemDemandLotStartedError(
            f"{noun} #{demand.id} feeds a lot that has started production, so it is not "
            f"canceled. Switch the lot's material source, or force-complete the lot."
        )
    if demand.status == MadeItemDemandStatus.FULFILLED:
        raise already_fulfilled_error(f"{noun} #{demand.id} is already fulfilled.")
    raise already_canceled_error(f"{noun} #{demand.id} is already canceled.")
