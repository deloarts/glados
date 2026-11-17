"""
Auto-allocate allocates across a unit mismatch, as a manual allocation may,
since nothing converts between units yet; its answer counts the lines it
used whose unit differs from the demand's, so the client can warn as the
manual allocation dialog does.
"""

from datetime import UTC
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from tests.integration import _lifecycle_seed as seed

ALLOCATIONS = "/api/v1/web/bought-items-allocations"


async def test_auto_allocate_counts_the_lines_in_another_unit(
    db: AsyncSession, auth_client: Any
) -> None:
    client = await auth_client(permissions=[Permission.WRITE_ALLOCATIONS, Permission.WRITE_ORDERS])
    # The demand's project exists, or auto-allocate leaves the demand alone.
    await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=1, project_number="P-UNIT")
    )
    order = await seed.order(db, "ordered", ordered_date=seed.NOW)
    line = await seed.line(db, order, "ordered", ordered_date=seed.NOW)
    line.unit = "m"
    demand = await seed.bought_demand(db, "open", None, 5.0)
    await db.commit()
    await seed.settle(db)

    allocated = await client.post(f"{ALLOCATIONS}/demand/{demand.id}/auto-allocate")

    assert allocated.status_code == 200, allocated.text
    body = allocated.json()
    assert body["allocations_created"] == 1
    assert body["unit_mismatches"] == 1
