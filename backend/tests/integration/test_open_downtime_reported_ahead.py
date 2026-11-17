"""
An open downtime reported ahead of its start does not mark the machine down
before then: the machine reads, the walk and Auto-Plan ask only for open
downtimes that have begun, while the one-open-downtime check still sees it.
"""

from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.repositories.machine_downtime_repository import (
    SqlAlchemyMachineDowntimeRepository,
)
from src.modules.fulfillment.domain.entities.machine_downtime import MachineDowntime
from src.modules.fulfillment.domain.value_objects.machine_downtime_reason import (
    MachineDowntimeReason,
)
from src.shared_kernel.domain.services.clock import now_utc
from tests.integration.repository_reads._graph import Graph
from tests.integration.repository_reads._graph import make


async def test_an_open_downtime_counts_once_it_has_begun(
    db: AsyncSession, create_user: Any
) -> None:
    owner = await create_user(username="owner", email="owner@example.com")
    graph = Graph(db, owner, owner)
    machine = await graph.machine()
    repo = SqlAlchemyMachineDowntimeRepository(db)
    now = now_utc()
    await repo.save(
        make(
            MachineDowntime,
            machine_id=machine.id,
            started_at=now + timedelta(hours=3),
            ended_at=None,
            reason=MachineDowntimeReason.MAINTENANCE,
            reported_by_id=owner.id,
        )
    )
    await db.commit()

    assert await repo.get_open_by_machine_ids([machine.id], started_by=now) == {}
    assert machine.id in await repo.get_open_by_machine_ids([machine.id])
    assert machine.id in await repo.get_open_by_machine_ids(
        [machine.id], started_by=now + timedelta(hours=4)
    )
