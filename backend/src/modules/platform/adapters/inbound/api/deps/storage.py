"""Use case factory: MigrateStorage for the plain migrate endpoint and for the
streaming one's background task. The task opens its own database session
after the request's session is closed, so both build the use case from a
session through build_migrate_storage_use_case and can never drift apart.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.inbound.api.deps.database import get_db
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.repositories import get_platform_settings_repo
from src.modules.platform.adapters.inbound.api.deps.services import get_storage_adapter_factory
from src.modules.platform.application.use_cases.admin_settings.migrate_storage import MigrateStorage


def build_migrate_storage_use_case(db: AsyncSession) -> MigrateStorage:
    """MigrateStorage built from one session, with the same providers the
    request-scoped dependency graph uses."""
    return MigrateStorage(
        get_platform_settings_repo(db),
        get_storage_adapter_factory(),
        uow=get_unit_of_work(db),
    )


def get_migrate_storage_use_case(
    db: AsyncSession = Depends(get_db, scope="function"),
) -> MigrateStorage:
    return build_migrate_storage_use_case(db)
