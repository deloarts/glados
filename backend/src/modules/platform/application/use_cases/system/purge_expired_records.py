"""
Enforces the retention policy from the admin settings: application and
request logs older than log_retention_days, and credential usage and
settings audit rows older than audit_retention_days, are deleted. A value
of 0 keeps that category forever. Idempotency keys go once their lifetime
(services/idempotency.py) is over, whatever the settings say. Runs hourly
from the system scheduler.
"""

from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta

from src.modules.platform.application.services.idempotency import KEY_LIFETIME
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.retention_purger_port import IRetentionPurger
from src.shared_kernel.domain.services.clock import now_utc


@dataclass(frozen=True)
class PurgeResult:
    logs_removed: int
    audit_removed: int
    idempotency_keys_removed: int = 0


class PurgeExpiredRecords:
    def __init__(
        self, settings_repo: IPlatformSettingsRepository, purger: IRetentionPurger
    ) -> None:
        self._settings_repo = settings_repo
        self._purger = purger

    async def execute(self, now: datetime | None = None) -> PurgeResult:
        now = now or now_utc()
        retention = await self._settings_repo.get_retention()

        logs_removed = 0
        if retention.log_retention_days > 0:
            logs_removed = await self._purger.purge_logs_before(
                now - timedelta(days=retention.log_retention_days)
            )
        audit_removed = 0
        if retention.audit_retention_days > 0:
            audit_removed = await self._purger.purge_audit_before(
                now - timedelta(days=retention.audit_retention_days)
            )

        keys_removed = await self._purger.purge_idempotency_keys_before(now - KEY_LIFETIME)

        if logs_removed or audit_removed or keys_removed:
            log.info(
                "Retention purge removed %d log, %d audit and %d idempotency key record(s).",
                logs_removed,
                audit_removed,
                keys_removed,
            )
        return PurgeResult(
            logs_removed=logs_removed,
            audit_removed=audit_removed,
            idempotency_keys_removed=keys_removed,
        )
