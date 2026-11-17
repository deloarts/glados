"""
The procurement pipelines of bought and made item demands leave out the
demands of a deleted project, whatever their status.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_demand_item_model import (
    BoughtItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_demand_item_model import (
    MadeItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.demand_item import (
    SqlAlchemyBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_repository.demand_item import (
    SqlAlchemyMadeItemDemandItemRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus

TODAY = date(2026, 10, 1)


async def _projects(db: AsyncSession) -> tuple[int, int]:
    """A live project and a deleted one, as DeleteProject leaves it."""
    repo = SqlAlchemyProjectRepository(db)
    live = await repo.save(
        Project(
            id=0, created=datetime(2026, 9, 1, tzinfo=UTC), creator_id=1, project_number="P-LIVE"
        )
    )
    deleted = await repo.save(
        Project(
            id=0,
            created=datetime(2026, 9, 1, tzinfo=UTC),
            creator_id=1,
            project_number="P-GONE",
            status=ProjectStatus.ARCHIVED,
            deleted=True,
        )
    )
    await db.commit()
    return live.id, deleted.id


async def test_the_bought_item_pipeline_leaves_out_a_deleted_projects_demands(
    db: AsyncSession,
) -> None:
    live, deleted = await _projects(db)
    for project_id in (live, deleted):
        db.add(
            BoughtItemDemandItemOrmModel(
                created=TODAY,
                status="open",
                quantity=2.0,
                unit="pcs",
                creator_id=1,
                item_id=1,
                project_id=project_id,
            )
        )
    await db.commit()

    pipeline = await SqlAlchemyBoughtItemDemandItemRepository(db).get_pipeline(
        TODAY - timedelta(days=30)
    )

    assert [demand.project_id for demand in pipeline] == [live]


async def test_the_made_item_pipeline_leaves_out_a_deleted_projects_demands(
    db: AsyncSession,
) -> None:
    live, deleted = await _projects(db)
    for project_id in (live, deleted):
        db.add(
            MadeItemDemandItemOrmModel(
                created=TODAY,
                status="open",
                quantity=2.0,
                unit="pcs",
                creator_id=1,
                made_item_id=1,
                project_id=project_id,
            )
        )
    await db.commit()

    pipeline = await SqlAlchemyMadeItemDemandItemRepository(db).get_pipeline(
        TODAY - timedelta(days=30)
    )

    assert [demand.project_id for demand in pipeline] == [live]
