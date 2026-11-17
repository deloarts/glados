"""The actor's own year view, read live through the time tracking service
and only when the user opens the year section. The service returns the
months of the year up to the current one, read in one session on its side;
the year lines and the end balance are computed here. Future years are
refused before the service is asked, and fetches are spaced per user.
Nothing is written, except the bookkeeping after the service rejected the
stored credentials.
"""

from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

from src.modules.operations.application.dto.time_tracking_dto import TimeTrackingYearResult
from src.modules.operations.application.mappers.time_tracking_mapper import TimeTrackingMapper
from src.modules.operations.application.services.time_tracking_access import claim_fetch
from src.modules.operations.application.services.time_tracking_access import (
    load_time_tracking_setup,
)
from src.modules.operations.application.services.time_tracking_access import recording_rejections
from src.modules.operations.domain.errors import TimeTrackingPeriodInvalidError
from src.modules.operations.domain.errors import TimeTrackingPermissionDeniedError
from src.modules.operations.domain.services.time_tracking_rules import assert_credentials_usable
from src.modules.operations.domain.services.time_tracking_summary import year_month
from src.modules.operations.domain.services.time_tracking_summary import year_summary
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
from src.modules.operations.ports.outbound.time_tracking_provider_port import TimeTrackingYearRead
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.login_attempt_tracker_port import ILoginAttemptTracker
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


class GetMyTimeTrackingYear:
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

    async def execute(self, actor: User, year: int) -> TimeTrackingYearResult:
        setup = await load_time_tracking_setup(actor, self._settings)
        now = self._clock()
        today = now.astimezone(ZoneInfo(setup.timezone)).date()
        if year > today.year:
            raise TimeTrackingPeriodInvalidError("Future years cannot be shown.")
        credentials = assert_credentials_usable(
            await self._credentials.get_by_user(actor.id),
            current_key_id=setup.settings.credential_key_id,
        )
        assert credentials.time_tracking_sealed_credentials
        await claim_fetch(self._rate_tracker, "year", actor.id)

        await self._uow.commit()
        provider = self._provider_factory(setup.connection)
        read: TimeTrackingYearRead | None = None
        async with recording_rejections(self._credentials, self._uow, actor.id, now):
            try:
                read = await provider.year(
                    credentials.time_tracking_sealed_credentials,
                    credentials.time_tracking_binding,
                    year,
                )
            except TimeTrackingPermissionDeniedError:
                read = None

        summary = (
            year_summary(year, [year_month(m, today=today, now=now) for m in read.months])
            if read is not None
            else None
        )
        return TimeTrackingMapper.year_to_result(
            year=year,
            summary=summary,
            rights=TimeTrackingReadRights(days=None, month=None, year=read is not None),
            employee_name=read.employee_name if read is not None else "",
            now=now,
        )
