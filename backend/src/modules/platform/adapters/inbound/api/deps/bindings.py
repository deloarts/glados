"""
The dependencies of Platform's routes whose implementations live in the
modules above it or in the composition root, which binds them at startup
(`src/bootstrap/bindings.py`).
"""

from collections.abc import Awaitable
from collections.abc import Callable
from typing import Any

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.inbound.api.deps.binding import Binding
from src.modules.platform.adapters.inbound.api.deps.database import get_db
from src.modules.platform.application.services.file_attachments.base import ILinkedFiles
from src.modules.platform.application.services.schedule_recompute_port import ScheduleRecompute
from src.modules.platform.ports.outbound.repositories.tenant_holiday_repository import (
    ITenantHolidayRepository,
)
from src.modules.platform.ports.outbound.service_health_port import IServiceHealthChecker
from src.modules.platform.ports.outbound.user_held_credentials_port import IUserHeldCredentials

tenant_holidays: Binding[Callable[[AsyncSession], ITenantHolidayRepository]] = Binding(
    "The tenant holiday store"
)
schedule_generation_counter: Binding[Callable[[], Any]] = Binding(
    "The schedule walk's generation counter"
)
schedule_recompute: Binding[Callable[[AsyncSession, Any], ScheduleRecompute]] = Binding(
    "The schedule walk"
)
service_health_checker: Binding[Callable[[AsyncSession], Awaitable[IServiceHealthChecker]]] = (
    Binding("The service health checker")
)
user_held_credentials: Binding[Callable[[AsyncSession], IUserHeldCredentials]] = Binding(
    "The credentials a user holds in other systems"
)
linked_files: Binding[Callable[[AsyncSession], ILinkedFiles]] = Binding(
    "The item files a CAD document links"
)


def get_tenant_holiday_repo(
    db: AsyncSession = Depends(get_db, scope="function"),
) -> ITenantHolidayRepository:
    return tenant_holidays.get()(db)


def get_schedule_recompute_generation_counter() -> Any:
    """The generation counter the schedule walk coalesces requests with. It
    is a dependency of its own, shared by the walk every module requests,
    so a request builds one counter and a test replaces it in one place."""
    return schedule_generation_counter.get()()


def get_schedule_recompute(
    db: AsyncSession = Depends(get_db, scope="function"),
    generation_counter: Any = Depends(get_schedule_recompute_generation_counter),
) -> ScheduleRecompute:
    """The schedule walk a write below Planning & fulfillment requests after
    its commit (schedule_recompute_port.py)."""
    return schedule_recompute.get()(db, generation_counter)


async def get_service_health_checker(
    db: AsyncSession = Depends(get_db, scope="function"),
) -> IServiceHealthChecker:
    return await service_health_checker.get()(db)


def get_user_held_credentials(
    db: AsyncSession = Depends(get_db, scope="function"),
) -> IUserHeldCredentials:
    return user_held_credentials.get()(db)


def get_linked_files(db: AsyncSession = Depends(get_db, scope="function")) -> ILinkedFiles:
    return linked_files.get()(db)
