"""
DB-backed coverage for the `not_fully_allocated` demand filter on all three
demand repositories (bought-item, source-item, made-item).

The filter cannot be expressed as a status comparison, which is the whole
reason it exists: the lifecycle derivation
(src/modules/fulfillment/domain/services/lifecycle/demand.py) moves a demand to ALLOCATED as
soon as *any* quantity is covered, so a demand covered 1-of-10 and one
covered 9-of-10 carry the identical stored status. These tests pin the
quantity maths in
src/modules/fulfillment/adapters/outbound/persistence/allocation_filters.py, a status-based
"fix" to that predicate fails here immediately.

Allocation rows are inserted through the ORM directly rather than through
the allocation use cases: what is under test is a SQL predicate over
`SUM(quantity)`, and the use cases would drag order items, orders,
suppliers and production lots in without changing a single number the
predicate reads.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

from sqlalchemy.orm import Session

from src.modules.catalogue.domain.value_objects.bought_item_status import AllocationSource
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemAllocationSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_allocation_model import (
    BoughtItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_allocation_model import (
    MadeItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_allocation_model import (
    SourceItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.demand_item import (
    SqlAlchemyBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_repository.demand_item import (
    SqlAlchemyMadeItemDemandItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_demand_repository import (
    SqlAlchemySourceItemDemandRepository,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemAllocationSource,
)
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    DemandItemFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    MadeItemDemandFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    SourceItemDemandFilterDto,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project

# ── Arrangement helpers ───────────────────────────────────────────────


async def _project(db: Session, creator_id: int, number: str) -> int:
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=creator_id, project_number=number)
    )
    return project.id


async def _bought_demand(
    db: Session,
    creator_id: int,
    project_id: int,
    *,
    quantity: float,
    status: BoughtItemDemandStatus = BoughtItemDemandStatus.OPEN,
) -> int:
    demand = await SqlAlchemyBoughtItemDemandItemRepository(db).save(
        BoughtItemDemandItem(
            id=0,
            created=date.today(),
            changed=None,
            changes=[],
            status=status,
            quantity=quantity,
            unit="pcs",
            items_per_unit=1.0,
            high_priority=False,
            notify_on_delivery=False,
            note=None,
            desired_delivery_date=None,
            creator_id=creator_id,
            item_id=1,
            project_id=project_id,
        )
    )
    return demand.id


async def _bought_allocation(
    db: Session,
    demand_id: int,
    quantity: float,
    *,
    order_item_id: int | None = None,
    source: str = AllocationSource.ORDER.value,
) -> None:
    db.add(
        BoughtItemAllocationOrmModel(
            demand_item_id=demand_id,
            order_item_id=order_item_id,
            source=source,
            quantity=quantity,
        )
    )
    await db.commit()


async def _source_demand(
    db: Session,
    creator_id: int,
    project_id: int,
    *,
    quantity: float,
    status: SourceItemDemandStatus = SourceItemDemandStatus.OPEN,
) -> int:
    demand = await SqlAlchemySourceItemDemandRepository(db).save(
        SourceItemDemandItem(
            id=0,
            created=date.today(),
            changed=None,
            changes=[],
            status=status,
            quantity=quantity,
            unit="pcs",
            items_per_unit=1.0,
            high_priority=False,
            notify_on_delivery=False,
            note=None,
            desired_delivery_date=None,
            creator_id=creator_id,
            bought_item_id=None,
            source_item_id=None,
            lot_id=0,
            project_id=project_id,
        )
    )
    return demand.id


async def _source_allocation(
    db: Session,
    demand_id: int,
    quantity: float,
    *,
    order_item_id: int | None = None,
    source: str = SourceItemAllocationSource.ORDER.value,
) -> None:
    db.add(
        SourceItemAllocationOrmModel(
            demand_item_id=demand_id,
            order_item_id=order_item_id,
            source=source,
            quantity=quantity,
        )
    )
    await db.commit()


async def _made_demand(
    db: Session,
    creator_id: int,
    project_id: int,
    *,
    quantity: float,
    status: MadeItemDemandStatus = MadeItemDemandStatus.OPEN,
) -> int:
    demand = await SqlAlchemyMadeItemDemandItemRepository(db).save(
        MadeItemDemandItem(
            id=0,
            created=date.today(),
            changed=None,
            changes=[],
            status=status,
            quantity=quantity,
            unit="pcs",
            items_per_unit=1.0,
            high_priority=False,
            notify_on_delivery=False,
            note=None,
            desired_delivery_date=None,
            creator_id=creator_id,
            made_item_id=1,
            project_id=project_id,
        )
    )
    return demand.id


async def _made_allocation(
    db: Session,
    demand_id: int,
    quantity: float,
    *,
    lot_id: int | None = None,
    source: str = MadeItemAllocationSource.LOT.value,
) -> None:
    db.add(
        MadeItemAllocationOrmModel(
            demand_item_id=demand_id,
            lot_id=lot_id,
            source=source,
            quantity=quantity,
        )
    )
    await db.commit()


async def _bought_ids(db: Session) -> list[int]:
    _, demands = await SqlAlchemyBoughtItemDemandItemRepository(db).get_multi(
        DemandItemFilterDto(not_fully_allocated=True)
    )
    return [d.id for d in demands]


async def _source_ids(db: Session) -> list[int]:
    _, demands = await SqlAlchemySourceItemDemandRepository(db).get_multi(
        SourceItemDemandFilterDto(not_fully_allocated=True)
    )
    return [d.id for d in demands]


async def _made_ids(db: Session) -> list[int]:
    _, demands = await SqlAlchemyMadeItemDemandItemRepository(db).get_multi(
        MadeItemDemandFilterDto(not_fully_allocated=True)
    )
    return [d.id for d in demands]


# ── Bought-item demands ───────────────────────────────────────────────


class TestBoughtItemNotFullyAllocated:
    async def test_demand_without_allocations_is_included(self, db, create_user):
        user = await create_user()
        project_id = await _project(db, user.id, "P-NFA-1")
        demand_id = await _bought_demand(db, user.id, project_id, quantity=10.0)

        assert demand_id in await _bought_ids(db)

    async def test_partially_allocated_demand_is_included(self, db, create_user):
        """The case the stored status cannot express: 4 of 10 covered still
        reads as ALLOCATED, exactly like a fully covered demand does."""
        user = await create_user()
        project_id = await _project(db, user.id, "P-NFA-2")
        demand_id = await _bought_demand(
            db,
            user.id,
            project_id,
            quantity=10.0,
            status=BoughtItemDemandStatus.ALLOCATED,
        )
        await _bought_allocation(db, demand_id, 4.0, order_item_id=1)

        assert demand_id in await _bought_ids(db)

    async def test_fully_allocated_demand_is_excluded(self, db, create_user):
        user = await create_user()
        project_id = await _project(db, user.id, "P-NFA-3")
        demand_id = await _bought_demand(
            db,
            user.id,
            project_id,
            quantity=10.0,
            status=BoughtItemDemandStatus.ALLOCATED,
        )
        await _bought_allocation(db, demand_id, 10.0, order_item_id=1)

        assert demand_id not in await _bought_ids(db)

    async def test_coverage_sums_across_allocations(self, db, create_user):
        """Two partial allocations that together reach the demand quantity
        leave nothing to order, neither one does on its own."""
        user = await create_user()
        project_id = await _project(db, user.id, "P-NFA-4")
        demand_id = await _bought_demand(
            db,
            user.id,
            project_id,
            quantity=10.0,
            status=BoughtItemDemandStatus.ALLOCATED,
        )
        await _bought_allocation(db, demand_id, 6.0, order_item_id=1)
        await _bought_allocation(db, demand_id, 4.0, order_item_id=2)

        assert demand_id not in await _bought_ids(db)

    async def test_stock_sourced_allocation_counts_as_coverage(
        self, db, create_user, allow_lifecycle_drift
    ):
        """Stock allocations carry no order_item_id but still cover the
        demand (compute_coverage_totals counts them as
        `fulfilled_from_stock`), so they must not be summed away."""
        # Stored ALLOCATED on purpose: stock covering the whole quantity
        # derives FULFILLED, which the filter would exclude by its status
        # alone, and the test is about the coverage sum.
        user = await create_user()
        project_id = await _project(db, user.id, "P-NFA-5")
        demand_id = await _bought_demand(
            db,
            user.id,
            project_id,
            quantity=10.0,
            status=BoughtItemDemandStatus.ALLOCATED,
        )
        await _bought_allocation(db, demand_id, 10.0, source=AllocationSource.STOCK.value)

        assert demand_id not in await _bought_ids(db)

    async def test_canceled_demand_is_excluded_despite_open_quantity(self, db, create_user):
        """A canceled demand sits below full coverage forever; it is not
        something the Manage Orders panel can act on."""
        user = await create_user()
        project_id = await _project(db, user.id, "P-NFA-6")
        demand_id = await _bought_demand(
            db,
            user.id,
            project_id,
            quantity=10.0,
            status=BoughtItemDemandStatus.CANCELED,
        )

        assert demand_id not in await _bought_ids(db)

    async def test_fulfilled_demand_is_excluded(self, db, create_user):
        user = await create_user()
        project_id = await _project(db, user.id, "P-NFA-7")
        demand_id = await _bought_demand(
            db,
            user.id,
            project_id,
            quantity=10.0,
            status=BoughtItemDemandStatus.FULFILLED,
        )

        assert demand_id not in await _bought_ids(db)

    async def test_filter_is_off_by_default(self, db, create_user):
        """Omitting the flag must not silently narrow the unfiltered list."""
        user = await create_user()
        project_id = await _project(db, user.id, "P-NFA-8")
        covered_id = await _bought_demand(
            db,
            user.id,
            project_id,
            quantity=10.0,
            status=BoughtItemDemandStatus.ALLOCATED,
        )
        await _bought_allocation(db, covered_id, 10.0, order_item_id=1)

        _, demands = await SqlAlchemyBoughtItemDemandItemRepository(db).get_multi(
            DemandItemFilterDto()
        )

        assert covered_id in [d.id for d in demands]


# ── Source-item demands ───────────────────────────────────────────────


class TestSourceItemNotFullyAllocated:
    """Same predicate, second aggregate, SourceItemDemandStatus mirrors
    BoughtItemDemandStatus exactly, so the behaviour must match."""

    async def test_demand_without_allocations_is_included(self, db, create_user):
        user = await create_user()
        project_id = await _project(db, user.id, "P-SNFA-1")
        demand_id = await _source_demand(db, user.id, project_id, quantity=5.0)

        assert demand_id in await _source_ids(db)

    async def test_partially_allocated_demand_is_included(self, db, create_user):
        user = await create_user()
        project_id = await _project(db, user.id, "P-SNFA-2")
        demand_id = await _source_demand(
            db,
            user.id,
            project_id,
            quantity=5.0,
            status=SourceItemDemandStatus.ALLOCATED,
        )
        await _source_allocation(db, demand_id, 2.0, order_item_id=1)

        assert demand_id in await _source_ids(db)

    async def test_fully_allocated_demand_is_excluded(self, db, create_user):
        user = await create_user()
        project_id = await _project(db, user.id, "P-SNFA-3")
        demand_id = await _source_demand(
            db,
            user.id,
            project_id,
            quantity=5.0,
            status=SourceItemDemandStatus.ALLOCATED,
        )
        await _source_allocation(db, demand_id, 5.0, order_item_id=1)

        assert demand_id not in await _source_ids(db)

    async def test_canceled_demand_is_excluded_despite_open_quantity(self, db, create_user):
        user = await create_user()
        project_id = await _project(db, user.id, "P-SNFA-4")
        demand_id = await _source_demand(
            db,
            user.id,
            project_id,
            quantity=5.0,
            status=SourceItemDemandStatus.CANCELED,
        )

        assert demand_id not in await _source_ids(db)


# ── Made-item demands ─────────────────────────────────────────────────


class TestMadeItemNotFullyAllocated:
    """Third aggregate. Made-item allocations are backed by production lots
    rather than order items, but coverage is the same SUM(quantity), the
    predicate never looks at what an allocation points to."""

    async def test_demand_without_allocations_is_included(self, db, create_user):
        user = await create_user()
        project_id = await _project(db, user.id, "P-MNFA-1")
        demand_id = await _made_demand(db, user.id, project_id, quantity=8.0)

        assert demand_id in await _made_ids(db)

    async def test_partially_allocated_demand_is_included(self, db, create_user):
        user = await create_user()
        project_id = await _project(db, user.id, "P-MNFA-2")
        demand_id = await _made_demand(
            db,
            user.id,
            project_id,
            quantity=8.0,
            status=MadeItemDemandStatus.ALLOCATED,
        )
        await _made_allocation(db, demand_id, 3.0, lot_id=1)

        assert demand_id in await _made_ids(db)

    async def test_fully_allocated_demand_is_excluded(self, db, create_user):
        user = await create_user()
        project_id = await _project(db, user.id, "P-MNFA-3")
        demand_id = await _made_demand(
            db,
            user.id,
            project_id,
            quantity=8.0,
            status=MadeItemDemandStatus.ALLOCATED,
        )
        await _made_allocation(db, demand_id, 8.0, lot_id=1)

        assert demand_id not in await _made_ids(db)

    async def test_partially_covered_ordered_demand_is_included(
        self, db, create_user, allow_lifecycle_drift
    ):
        """A made-item demand stored before the lifecycle derivation can sit
        at ORDERED with most of its quantity still uncovered, since such a
        row reached ORDERED the moment its covering lot left DRAFT. A
        `statuses=['open', 'allocated']` preselect would hide exactly these
        rows; the quantity predicate must not."""
        # A status stored before the lifecycle derivation, which derives
        # ALLOCATED today; the row stays as stored on purpose.
        user = await create_user()
        project_id = await _project(db, user.id, "P-MNFA-4")
        demand_id = await _made_demand(
            db,
            user.id,
            project_id,
            quantity=8.0,
            status=MadeItemDemandStatus.ORDERED,
        )
        await _made_allocation(db, demand_id, 2.0, lot_id=1)

        assert demand_id in await _made_ids(db)

    async def test_stock_sourced_allocation_counts_as_coverage(
        self, db, create_user, allow_lifecycle_drift
    ):
        # Stored ALLOCATED on purpose: stock covering the whole quantity
        # derives FULFILLED, which the filter would exclude by its status
        # alone, and the test is about the coverage sum.
        user = await create_user()
        project_id = await _project(db, user.id, "P-MNFA-5")
        demand_id = await _made_demand(
            db,
            user.id,
            project_id,
            quantity=8.0,
            status=MadeItemDemandStatus.ALLOCATED,
        )
        await _made_allocation(db, demand_id, 8.0, source=MadeItemAllocationSource.STOCK.value)

        assert demand_id not in await _made_ids(db)

    async def test_canceled_demand_is_excluded_despite_open_quantity(self, db, create_user):
        user = await create_user()
        project_id = await _project(db, user.id, "P-MNFA-6")
        demand_id = await _made_demand(
            db,
            user.id,
            project_id,
            quantity=8.0,
            status=MadeItemDemandStatus.CANCELED,
        )

        assert demand_id not in await _made_ids(db)
