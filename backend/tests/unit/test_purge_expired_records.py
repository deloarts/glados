"""
PurgeExpiredRecords turns the retention settings into cutoffs: N days
before now per category, and nothing at all for a value of 0.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

from src.modules.platform.application.use_cases.system.purge_expired_records import (
    PurgeExpiredRecords,
)
from src.modules.platform.domain.entities.admin_settings.retention import AdminRetentionSettings

_NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


class _Settings:
    def __init__(self, log_days: int, audit_days: int) -> None:
        self._retention = AdminRetentionSettings(
            id=1,
            log_retention_days=log_days,
            audit_retention_days=audit_days,
            soft_delete_cleanup_days=0,
        )

    async def get_retention(self) -> AdminRetentionSettings:
        return self._retention


class _Purger:
    def __init__(self) -> None:
        self.log_cutoffs: list[datetime] = []
        self.audit_cutoffs: list[datetime] = []
        self.key_cutoffs: list[datetime] = []

    async def purge_logs_before(self, cutoff: datetime) -> int:
        self.log_cutoffs.append(cutoff)
        return 7

    async def purge_audit_before(self, cutoff: datetime) -> int:
        self.audit_cutoffs.append(cutoff)
        return 3

    async def purge_idempotency_keys_before(self, cutoff: datetime) -> int:
        self.key_cutoffs.append(cutoff)
        return 2


async def test_cutoffs_follow_the_configured_days(glados_caplog) -> None:
    purger = _Purger()

    result = await PurgeExpiredRecords(_Settings(90, 365), purger).execute(now=_NOW)  # type: ignore[arg-type]

    assert purger.log_cutoffs == [_NOW - timedelta(days=90)]
    assert purger.audit_cutoffs == [_NOW - timedelta(days=365)]
    assert (result.logs_removed, result.audit_removed) == (7, 3)


async def test_zero_keeps_a_category_forever() -> None:
    purger = _Purger()

    result = await PurgeExpiredRecords(_Settings(0, 0), purger).execute(now=_NOW)  # type: ignore[arg-type]

    assert purger.log_cutoffs == []
    assert purger.audit_cutoffs == []
    assert (result.logs_removed, result.audit_removed) == (0, 0)


async def test_idempotency_keys_go_after_their_lifetime_whatever_the_settings() -> None:
    purger = _Purger()

    result = await PurgeExpiredRecords(_Settings(0, 0), purger).execute(now=_NOW)  # type: ignore[arg-type]

    assert purger.key_cutoffs == [_NOW - timedelta(hours=24)]
    assert result.idempotency_keys_removed == 2
