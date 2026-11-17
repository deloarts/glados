"""Adapter and service factories, and the services one process shares
between requests."""

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.catalogue.ports.outbound.bought_item_usage_port import IBoughtItemUsages
from src.modules.catalogue.ports.outbound.made_item_usage_port import IMadeItemUsages
from src.modules.fulfillment.adapters.outbound.external.schedule_recompute.redis_generation_counter import (
    RedisScheduleRecomputeGenerationCounter,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_usage_repository import (
    SqlAlchemyBoughtItemUsages,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_usage_repository import (
    SqlAlchemyMadeItemUsages,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.project_work_repository import (
    SqlAlchemyProjectWork,
)
from src.modules.fulfillment.adapters.outbound.persistence.schedule_recompute_lock import (
    SqlAlchemyScheduleRecomputeLock,
)
from src.modules.fulfillment.ports.outbound.schedule_recompute_generation_port import (
    IScheduleRecomputeGenerationCounter,
)
from src.modules.fulfillment.ports.outbound.schedule_recompute_lock_port import (
    IScheduleRecomputeLock,
)
from src.modules.platform.adapters.inbound.api.deps.database import repo_factory
from src.modules.platform.adapters.outbound.persistence.session import engine
from src.modules.platform.infrastructure.redis_client import get_async_redis_client
from src.modules.workspace.ports.outbound.project_work_port import IProjectWork


def build_schedule_recompute_generation_counter() -> IScheduleRecomputeGenerationCounter:
    """The Redis generation counter the composition root binds to Platform's
    get_schedule_recompute_generation_counter."""
    return RedisScheduleRecomputeGenerationCounter(get_async_redis_client())


def get_schedule_recompute_lock() -> IScheduleRecomputeLock:
    # The engine, not a session, so the lock is independent of the walk's
    # transaction (see advisory_lock.py).
    return SqlAlchemyScheduleRecomputeLock(engine)


get_project_work: Callable[[AsyncSession], IProjectWork] = repo_factory(SqlAlchemyProjectWork)
get_bought_item_usages: Callable[[AsyncSession], IBoughtItemUsages] = repo_factory(
    SqlAlchemyBoughtItemUsages
)
get_made_item_usages: Callable[[AsyncSession], IMadeItemUsages] = repo_factory(
    SqlAlchemyMadeItemUsages
)
