"""
SqlAlchemyRetentionPurger against the real schema: deletes only rows older
than the cutoff, across several batches, and reports how many it removed.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.audit import (
    AdminSettingsAuditOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.log_model import LogOrmModel
from src.modules.platform.adapters.outbound.persistence.retention_purger import (
    SqlAlchemyRetentionPurger,
)

_CUTOFF = datetime(2026, 7, 1, tzinfo=UTC)


async def _count(db: AsyncSession, model: type) -> int:
    return await db.scalar(select(func.count()).select_from(model)) or 0


async def test_logs_older_than_the_cutoff_are_removed_in_batches(db: AsyncSession) -> None:
    for i in range(7):
        db.add(LogOrmModel(timestamp=_CUTOFF - timedelta(days=1, minutes=i), level="INFO"))
    for i in range(3):
        db.add(LogOrmModel(timestamp=_CUTOFF + timedelta(minutes=i), level="INFO"))
    await db.commit()

    removed = await SqlAlchemyRetentionPurger(db, batch_size=2).purge_logs_before(_CUTOFF)

    assert removed == 7
    assert await _count(db, LogOrmModel) == 3


async def test_settings_audit_older_than_the_cutoff_is_removed(db: AsyncSession) -> None:
    for when in (_CUTOFF - timedelta(days=400), _CUTOFF + timedelta(days=1)):
        db.add(AdminSettingsAuditOrmModel(changed_at=when, settings_domain="mail", summary="x"))
    await db.commit()

    removed = await SqlAlchemyRetentionPurger(db).purge_audit_before(_CUTOFF)

    assert removed == 1
    assert await _count(db, AdminSettingsAuditOrmModel) == 1
