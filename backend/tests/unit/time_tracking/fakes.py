"""
In-memory stand-ins for the ports the time tracking use cases depend on:
admin settings (time tracking and the default time zone), stored
credentials, users, the attempt tracker and the time tracking provider. The
provider records every call, so a test can assert that no request reached
the time tracking service.
"""

import calendar
from dataclasses import replace
from datetime import date
from datetime import datetime
from types import SimpleNamespace
from typing import Any

from src.modules.operations.domain.entities.admin_settings.time_tracking import (
    AdminTimeTrackingSettings,
)
from src.modules.operations.domain.entities.user_time_tracking_credentials import (
    UserTimeTrackingCredentials,
)
from src.modules.operations.domain.errors import TimeTrackingAuthenticationFailedError
from src.modules.operations.domain.errors import TimeTrackingPermissionDeniedError
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingReadRights
from src.modules.operations.ports.outbound.time_tracking_provider_port import (
    TimeTrackingCredentialField,
)
from src.modules.operations.ports.outbound.time_tracking_provider_port import TimeTrackingMonthRead
from src.modules.operations.ports.outbound.time_tracking_provider_port import (
    TimeTrackingServiceConnection,
)
from src.modules.operations.ports.outbound.time_tracking_provider_port import (
    TimeTrackingServiceInfo,
)
from src.modules.operations.ports.outbound.time_tracking_provider_port import (
    TimeTrackingServiceStatus,
)
from src.modules.operations.ports.outbound.time_tracking_provider_port import (
    TimeTrackingVerification,
)
from src.modules.operations.ports.outbound.time_tracking_provider_port import TimeTrackingYearRead
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.user import User
from tests.unit.time_tracking._helpers import BINDING
from tests.unit.time_tracking._helpers import KEY_ID
from tests.unit.time_tracking._helpers import NOW
from tests.unit.time_tracking._helpers import PUBLIC_KEY
from tests.unit.time_tracking._helpers import make_month
from tests.unit.time_tracking._helpers import make_settings


class FakeSettingsRepo:
    def __init__(self, time_tracking: AdminTimeTrackingSettings | None = None) -> None:
        self.time_tracking = time_tracking or make_settings()
        self.timezone = "Europe/Vienna"
        self.audit: list[AdminSettingsAuditEntry] = []

    async def get_time_tracking(self) -> AdminTimeTrackingSettings:
        return self.time_tracking

    async def save_time_tracking(
        self, settings: AdminTimeTrackingSettings
    ) -> AdminTimeTrackingSettings:
        self.time_tracking = settings
        return settings

    async def get_general(self) -> Any:
        return SimpleNamespace(default_timezone=self.timezone)

    async def append_audit(self, entry: AdminSettingsAuditEntry) -> AdminSettingsAuditEntry:
        self.audit.append(entry)
        return entry


class FakeCredentialsRepo:
    def __init__(self, *rows: UserTimeTrackingCredentials) -> None:
        self.rows = {row.user_id: row for row in rows}
        self.saves: list[UserTimeTrackingCredentials] = []
        self.auth_failed: list[tuple[int, datetime]] = []
        self.cleared: list[int] = []
        self.deleted: list[int] = []

    async def get_by_user(self, user_id: int) -> UserTimeTrackingCredentials | None:
        return self.rows.get(user_id)

    async def list_all(self) -> list[UserTimeTrackingCredentials]:
        return [self.rows[key] for key in sorted(self.rows)]

    async def exists_for_user(self, user_id: int) -> bool:
        return user_id in self.rows

    async def is_fingerprint_taken_by_other_user(self, fingerprint: str, user_id: int) -> bool:
        return any(
            row.time_tracking_user_fingerprint == fingerprint and row.user_id != user_id
            for row in self.rows.values()
        )

    async def save(self, credentials: UserTimeTrackingCredentials) -> UserTimeTrackingCredentials:
        saved = replace(credentials, id=credentials.id or len(self.rows) + 100)
        self.rows[credentials.user_id] = saved
        self.saves.append(saved)
        return saved

    async def mark_auth_failed(self, user_id: int, at: datetime) -> None:
        self.auth_failed.append((user_id, at))
        if user_id in self.rows:
            self.rows[user_id] = replace(self.rows[user_id], time_tracking_auth_failed_at=at)

    async def clear_sealed(self, user_id: int) -> None:
        self.cleared.append(user_id)
        if user_id in self.rows:
            self.rows[user_id] = replace(self.rows[user_id], time_tracking_sealed_credentials=None)

    async def delete_for_user(self, user_id: int) -> bool:
        self.deleted.append(user_id)
        return self.rows.pop(user_id, None) is not None

    async def delete_all(self) -> int:
        count = len(self.rows)
        self.rows.clear()
        return count

    async def get_count(self) -> int:
        return len(self.rows)


class FakeUserRepo:
    def __init__(self, *users: User) -> None:
        self.users = {user.id: user for user in users}

    async def get_by_id(self, id: int) -> User | None:
        return self.users.get(id)


class FakeTracker:
    def __init__(self) -> None:
        self.failures: dict[str, int] = {}
        self.locks: dict[str, int] = {}

    async def record_failure(self, key: str) -> int:
        self.failures[key] = self.failures.get(key, 0) + 1
        return self.failures[key]

    async def reset(self, key: str) -> None:
        self.failures.pop(key, None)
        self.locks.pop(key, None)

    async def lock(self, key: str, seconds: int) -> None:
        self.locks[key] = seconds
        self.failures.pop(key, None)

    async def lock_ttl(self, key: str) -> int:
        return self.locks.get(key, 0)

    async def claim(self, key: str, seconds: int) -> bool:
        if key in self.locks:
            return False
        self.locks[key] = seconds
        return True

    async def release_prefix(self, prefix: str) -> int:
        keys = [k for k in (*self.failures, *self.locks) if k.startswith(prefix)]
        for key in keys:
            self.failures.pop(key, None)
            self.locks.pop(key, None)
        return len(keys)

    async def clear_all(self) -> int:
        removed = len(self.failures) + len(self.locks)
        self.failures.clear()
        self.locks.clear()
        return removed


class FakeProvider:
    """Records every call as (name, args). `reject_credentials` makes the
    credential calls raise TimeTrackingAuthenticationFailedError; reads
    named in `denied` ("month", "year") raise
    TimeTrackingPermissionDeniedError; `fail_on` maps a call name to an
    exception to raise."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.reject_credentials = False
        self.denied: set[str] = set()
        self.fail_on: dict[str, Exception] = {}
        self.connections: list[TimeTrackingServiceConnection] = []
        self.key_id = KEY_ID
        self.public_key = PUBLIC_KEY
        self.contract_version = "0.1"
        self.rights = TimeTrackingReadRights(days=False, month=True, year=True)

    def factory(self, connection: TimeTrackingServiceConnection) -> "FakeProvider":
        self.connections.append(connection)
        return self

    def names(self) -> list[str]:
        return [name for name, _ in self.calls]

    def _record(self, name: str, *args: object) -> None:
        self.calls.append((name, args))
        if name in self.fail_on:
            raise self.fail_on[name]

    def _check_credentials(self) -> None:
        if self.reject_credentials:
            raise TimeTrackingAuthenticationFailedError("The system rejected the credentials.")

    async def health(self) -> str:
        self._record("health")
        return "0.1.0"

    async def info(self) -> TimeTrackingServiceInfo:
        self._record("info")
        return TimeTrackingServiceInfo(
            service="example-time-service",
            version="0.1.0",
            contract_version=self.contract_version,
            provider_label="Example Time",
            credential_fields=(
                TimeTrackingCredentialField(
                    name="user", kind="text", required=True, max_length=128
                ),
                TimeTrackingCredentialField(
                    name="password", kind="secret", required=True, max_length=256
                ),
            ),
            credential_public_key=self.public_key,
            credential_key_id=self.key_id,
            binding=BINDING,
        )

    async def status(self) -> TimeTrackingServiceStatus:
        self._record("status")
        return TimeTrackingServiceStatus(server_version="1.200.0.1", default_project="DEMO")

    async def verify(self, sealed_credentials: str) -> TimeTrackingVerification:
        self._record("verify", sealed_credentials)
        self._check_credentials()
        return TimeTrackingVerification(
            binding=BINDING, employee_name="Doe, Jane", rights=self.rights
        )

    async def month(
        self, sealed_credentials: str, binding: str, year: int, month: int
    ) -> TimeTrackingMonthRead:
        self._record("month", sealed_credentials, binding, year, month)
        self._check_credentials()
        if "month" in self.denied:
            raise TimeTrackingPermissionDeniedError("denied")
        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])
        return TimeTrackingMonthRead(
            employee_name="Doe, Jane", month=make_month(first_day, last_day), fetched_at=NOW
        )

    async def year(self, sealed_credentials: str, binding: str, year: int) -> TimeTrackingYearRead:
        self._record("year", sealed_credentials, binding, year)
        self._check_credentials()
        if "year" in self.denied:
            raise TimeTrackingPermissionDeniedError("denied")
        last_month = 9 if year == 2026 else 12
        months = tuple(
            make_month(date(year, m, 1), date(year, m, calendar.monthrange(year, m)[1]))
            for m in range(1, last_month + 1)
        )
        return TimeTrackingYearRead(employee_name="Doe, Jane", months=months, fetched_at=NOW)
