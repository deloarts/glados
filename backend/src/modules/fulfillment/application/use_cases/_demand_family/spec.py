"""
Declares what differs between the bought, made and source item demand
families as one `DemandFamilySpec` per family, so the use cases in this
package are written once. The family's allocation rules class decides the
allocation guards and carries the family's domain terms (noun, terminal
statuses, errors); the spec adds what the application layer needs on top:
the lifecycle aggregate the reconciler knows the demands by, the result
mapper, the noun of the family's log lines and the source value of a stock
allocation.

The repositories are request-scoped, so they are not part of the spec. The
protocols below name the part of each family's repository port and entities
the shared use cases call, and the demand rules class that bought and made
item demands, which users create and edit, bind beside the spec. The
reconciler reasons the families' demand actions share are declared here too.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from typing import Generic
from typing import Protocol
from typing import TypeVar

from src.modules.fulfillment.domain.services.allocation_coverage import DemandAllocationRules
from src.modules.fulfillment.domain.services.demand_terms import DemandTerms
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.platform.domain.entities.user import User

# Close the changelog lines of the statuses the reconciler derives after a
# demand's cancel, manual fulfil, fulfilment from stock, allocation write or
# edit, in all three families.
CANCEL_REASON = "demand canceled"
FULFIL_REASON = "marked fulfilled"
STOCK_REASON = "fulfilled from stock"
ALLOCATION_REASON = "allocation recalculated"
QUANTITY_REASON = "quantity changed"


class FamilyDemand(Protocol):
    """The fields of a demand the shared use cases read and write, which
    every family's demand entity has."""

    id: int
    quantity: float
    unit: str
    creator_id: int
    changed: datetime | None
    changes: list[str]
    fulfilled_manually_at: datetime | None

    @property
    def status(self) -> str:
        """Each family types it with its own status enum, which the shared
        use cases only read."""
        ...


class CatalogueDemand(FamilyDemand, Protocol):
    """A demand for a catalogue item that a user creates and edits, which
    bought and made item demands are."""

    project_id: int
    items_per_unit: float
    high_priority: bool
    notify_on_delivery: bool
    note: str | None
    desired_delivery_date: date | None


class FamilyAllocation(Protocol):
    quantity: float
    # Who created the row; the writer that knows the actor sets it.
    created_by_id: int | None

    @property
    def source(self) -> str:
        """Each family types it with its own allocation source enum."""
        ...


D = TypeVar("D", bound=FamilyDemand)
CD = TypeVar("CD", bound=CatalogueDemand)
CD_contra = TypeVar("CD_contra", bound=CatalogueDemand, contravariant=True)
A = TypeVar("A", bound=FamilyAllocation)
R = TypeVar("R")


class DemandRepo(Protocol[D]):
    """The part of every family's demand repository port these use cases call."""

    async def get_by_id(self, id: int, /) -> D | None: ...

    async def get_by_id_for_update(self, id: int, /) -> D | None: ...

    async def save(self, demand: D, /) -> D: ...


class DeletableDemandRepo(DemandRepo[D], Protocol[D]):
    """A demand repository of a family whose demands can be deleted."""

    async def delete(self, demand: D, /) -> None: ...


class AllocationRepo(Protocol[A]):
    """The part of every family's allocation repository port these use cases call."""

    async def get_by_demand_item_id(self, demand_item_id: int, /) -> list[A]: ...

    async def save(self, allocation: A, /) -> A: ...


class WritableAllocationRepo(AllocationRepo[A], Protocol[A]):
    """An allocation repository the allocation writers also delete through."""

    async def delete(self, allocation: A, /) -> None: ...


class CatalogueDemandRules(Protocol[CD_contra]):
    """The demand rules class of a family whose demands users create and
    edit, used as the class object itself."""

    def assert_can_create(self, actor: User, /) -> None: ...

    def assert_can_update(self, actor: User, demand: CD_contra, /) -> None: ...

    def assert_valid_quantity(self, quantity: float, /) -> None: ...


@dataclass(frozen=True)
class DemandFamilySpec(Generic[D, R]):
    """One family's declared shape. `rules` is the family's allocation rules
    class, whose `terms` name the family in every message. `log_noun` names
    a demand in the family's log lines, which do not always use the message
    noun. `stock_source` is the `source` value of the family's stock
    allocation, `fill_rank` its place in the fill of a line or lot."""

    rules: type[DemandAllocationRules]
    aggregate: LifecycleAggregate
    to_result: Callable[[D], R]
    log_noun: str
    stock_source: str
    # The family's rank in the fill of a line or lot (lifecycle/demand.py).
    fill_rank: int

    @property
    def terms(self) -> DemandTerms:
        return self.rules.terms

    def not_found_message(self, demand_id: int) -> str:
        """Such as "Demand item #12 not found."."""
        return f"{self.terms.noun} #{demand_id} not found."
