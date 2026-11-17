"""
DB-backed round-trip coverage for the substitute_source_item_id /
substitute_reason columns added to source_item_allocation_table (mirrors
bought_item_allocation_table's existing substitute_item_id /
substitute_reason). Exercises SqlAlchemySourceItemAllocationRepository
directly: what is under test is that the ORM model, the migration's
columns, and the repository's entity<->row mapping (both on insert and on
the existing-row update branch) round-trip the two new fields, following
the arrangement pattern of tests/integration/test_demand_allocation_filters.py
(same `db` / `create_user` fixtures, project + demand created through the
real repositories, allocation quantities inserted directly).
"""

from datetime import UTC
from datetime import date
from datetime import datetime

from sqlalchemy.orm import Session

from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_allocation_repository import (
    SqlAlchemySourceItemAllocationRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_demand_repository import (
    SqlAlchemySourceItemDemandRepository,
)
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemAllocationSource,
)
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from tests.integration._demand_facts import give_demand_facts


async def _project(db: Session, creator_id: int, number: str) -> int:
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=creator_id, project_number=number)
    )
    return project.id


async def _source_demand(
    db: Session, creator_id: int, project_id: int, *, quantity: float = 10.0
) -> int:
    demand = await SqlAlchemySourceItemDemandRepository(db).save(
        SourceItemDemandItem(
            id=0,
            created=date.today(),
            changed=None,
            changes=[],
            status=SourceItemDemandStatus.OPEN,
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


class TestSourceItemAllocationSubstitutionPersistence:
    async def test_substitute_fields_round_trip_on_insert(self, db, create_user):
        user = await create_user()
        project_id = await _project(db, user.id, "P-SUB-1")
        demand_id = await _source_demand(db, user.id, project_id)
        repo = SqlAlchemySourceItemAllocationRepository(db)

        await repo.save(
            SourceItemDemandAllocation(
                demand_item_id=demand_id,
                order_item_id=1,
                quantity=4.0,
                substitute_source_item_id=2,
                substitute_reason="preferred supplier out of stock",
            )
        )

        [saved] = await repo.get_by_demand_item_id(demand_id)
        assert saved.substitute_source_item_id == 2
        assert saved.substitute_reason == "preferred supplier out of stock"

    async def test_substitute_fields_survive_a_quantity_update(self, db, create_user):
        """save()'s existing-row branch must not drop the substitute
        columns when only the quantity changes."""
        user = await create_user()
        project_id = await _project(db, user.id, "P-SUB-2")
        demand_id = await _source_demand(db, user.id, project_id)
        repo = SqlAlchemySourceItemAllocationRepository(db)
        await repo.save(
            SourceItemDemandAllocation(
                demand_item_id=demand_id,
                order_item_id=1,
                quantity=4.0,
                substitute_source_item_id=2,
                substitute_reason="preferred supplier out of stock",
            )
        )

        await repo.save(
            SourceItemDemandAllocation(
                demand_item_id=demand_id,
                order_item_id=1,
                quantity=6.0,
                substitute_source_item_id=2,
                substitute_reason="preferred supplier out of stock",
            )
        )

        [saved] = await repo.get_by_demand_item_id(demand_id)
        assert saved.quantity == 6.0
        assert saved.substitute_source_item_id == 2
        assert saved.substitute_reason == "preferred supplier out of stock"

    async def test_no_substitution_leaves_fields_null(self, db, create_user):
        user = await create_user()
        project_id = await _project(db, user.id, "P-SUB-3")
        demand_id = await _source_demand(db, user.id, project_id)
        repo = SqlAlchemySourceItemAllocationRepository(db)

        await repo.save(
            SourceItemDemandAllocation(demand_item_id=demand_id, order_item_id=1, quantity=10.0)
        )

        [saved] = await repo.get_by_demand_item_id(demand_id)
        assert saved.substitute_source_item_id is None
        assert saved.substitute_reason is None

    async def test_save_round_trips_substitute_fields_without_committing(self, db, create_user):
        user = await create_user()
        project_id = await _project(db, user.id, "P-SUB-4")
        demand_id = await _source_demand(db, user.id, project_id)
        repo = SqlAlchemySourceItemAllocationRepository(db)

        await repo.save(
            SourceItemDemandAllocation(
                demand_item_id=demand_id,
                order_item_id=1,
                quantity=4.0,
                substitute_source_item_id=3,
                substitute_reason="reason via flush path",
            )
        )
        await db.commit()
        # The demand takes the status its allocation derives, as the
        # allocation use case would have stored it.
        await give_demand_facts(
            db, LifecycleAggregate.SOURCE_DEMANDS, demand_id, expected="allocated"
        )
        await db.commit()

        [saved] = await repo.get_by_demand_item_id(demand_id)
        assert saved.substitute_source_item_id == 3
        assert saved.substitute_reason == "reason via flush path"


class TestAllocationAuditColumns:
    async def test_the_creator_stays_and_the_change_time_moves_on_update(self, db, create_user):
        user = await create_user()
        project_id = await _project(db, user.id, "P-AUDIT-1")
        demand_id = await _source_demand(db, user.id, project_id)
        repo = SqlAlchemySourceItemAllocationRepository(db)

        await repo.save(
            SourceItemDemandAllocation(
                demand_item_id=demand_id,
                order_item_id=None,
                quantity=2.0,
                source=SourceItemAllocationSource.STOCK,
                created_by_id=user.id,
            )
        )
        await db.commit()
        [created] = await repo.get_by_demand_item_id(demand_id)
        await repo.save(
            SourceItemDemandAllocation(
                demand_item_id=demand_id,
                order_item_id=None,
                quantity=3.0,
                source=SourceItemAllocationSource.STOCK,
            )
        )
        await db.commit()
        # The demand takes the status its allocation derives, as the
        # allocation use case would have stored it.
        await give_demand_facts(
            db, LifecycleAggregate.SOURCE_DEMANDS, demand_id, expected="allocated"
        )
        await db.commit()
        db.expire_all()
        [updated] = await repo.get_by_demand_item_id(demand_id)

        assert created.created_by_id == user.id
        assert created.created_at is not None and created.changed_at is not None
        assert updated.created_by_id == user.id
        assert updated.created_at == created.created_at
        assert updated.changed_at is not None and updated.changed_at >= created.changed_at
