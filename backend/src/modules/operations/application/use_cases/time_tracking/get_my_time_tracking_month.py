"""The actor's own month, read live through the time tracking service and
never stored. Future months are refused before the service is asked, and
fetches are spaced per user. When the account may not read the month, the
answer carries the rights and no data. Nothing is written, except the
bookkeeping after the service rejected the stored credentials.
"""

import calendar
from collections.abc import Callable
from datetime import date
from datetime import datetime
from zoneinfo import ZoneInfo

from src.modules.operations.application.dto.time_tracking_dto import TimeTrackingMonthResult
from src.modules.operations.application.mappers.time_tracking_mapper import TimeTrackingMapper
from src.modules.operations.application.services.time_tracking_access import claim_fetch
from src.modules.operations.application.services.time_tracking_access import (
    load_time_tracking_setup,
)
from src.modules.operations.application.services.time_tracking_access import recording_rejections
from src.modules.operations.domain.errors import TimeTrackingPeriodInvalidError
from src.modules.operations.domain.errors import TimeTrackingPermissionDeniedError
from src.modules.operations.domain.services.time_tracking_rules import assert_credentials_usable
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingReadRights
from src.modules.operations.ports.outbound.operations_settings_repository import (
    IOperationsSettingsRepository,
)
from src.modules.operations.ports.outbound.repositories.user_time_tracking_credentials_repository import (
    IUserTimeTrackingCredentialsRepository,
)
from src.modules.operations.ports.outbound.time_tracking_provider_port import (
    ITimeTrackingProviderFactory,
)
from src.modules.operations.ports.outbound.time_tracking_provider_port import TimeTrackingMonthRead
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.login_attempt_tracker_port import ILoginAttemptTracker
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


def month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


class GetMyTimeTrackingMonth:
    def __init__(
        self,
        settings_repo: IOperationsSettingsRepository,
        credentials_repo: IUserTimeTrackingCredentialsRepository,
        provider_factory: ITimeTrackingProviderFactory,
        rate_tracker: ILoginAttemptTracker,
        *,
        uow: IUnitOfWork,
        clock: Callable[[], datetime] = now_utc,
    ) -> None:
        self._settings = settings_repo
        self._credentials = credentials_repo
        self._provider_factory = provider_factory
        self._rate_tracker = rate_tracker
        self._uow = uow
        self._clock = clock

    async def execute(self, actor: User, year: int, month: int) -> TimeTrackingMonthResult:
        setup = await load_time_tracking_setup(actor, self._settings)
        now = self._clock()
        today = now.astimezone(ZoneInfo(setup.timezone)).date()
        try:
            first_day, last_day = month_bounds(year, month)
        except ValueError as exc:
            raise TimeTrackingPeriodInvalidError(f"{year}-{month:02d} is not a month.") from exc
        if first_day > today:
            raise TimeTrackingPeriodInvalidError("Future months cannot be shown.")
        credentials = assert_credentials_usable(
            await self._credentials.get_by_user(actor.id),
            current_key_id=setup.settings.credential_key_id,
        )
        assert credentials.time_tracking_sealed_credentials
        await claim_fetch(self._rate_tracker, "month", actor.id)

        await self._uow.commit()
        provider = self._provider_factory(setup.connection)
        read: TimeTrackingMonthRead | None = None
        async with recording_rejections(self._credentials, self._uow, actor.id, now):
            try:
                read = await provider.month(
                    credentials.time_tracking_sealed_credentials,
                    credentials.time_tracking_binding,
                    year,
                    month,
                )
            except TimeTrackingPermissionDeniedError:
                read = None

        return TimeTrackingMapper.month_to_result(
            first_day=first_day,
            last_day=last_day,
            month=read.month if read is not None else None,
            rights=TimeTrackingReadRights(days=None, month=read is not None, year=None),
            employee_name=read.employee_name if read is not None else "",
            today=today,
            now=now,
        )
