"""The explicit "Check access" action in My Account: the time tracking
service signs in with the actor's stored, sealed credentials, checks the
rights and signs out. The result is returned, never stored.

The same guards as every other call run first, including the lockout after
failed checks. A rejection counts towards that lockout and marks the stored
credentials as rejected, so no further call is made with them until the
user saves again; a changed binding drops the sealed value.
"""

from collections.abc import Callable
from datetime import datetime

from src.modules.operations.application.dto.time_tracking_dto import TimeTrackingAccountResult
from src.modules.operations.application.mappers.time_tracking_mapper import TimeTrackingMapper
from src.modules.operations.application.services.time_tracking_access import (
    assert_verify_not_locked,
)
from src.modules.operations.application.services.time_tracking_access import (
    load_time_tracking_setup,
)
from src.modules.operations.application.services.time_tracking_access import record_verify_failure
from src.modules.operations.application.services.time_tracking_access import recording_rejections
from src.modules.operations.domain.errors import TimeTrackingAuthenticationFailedError
from src.modules.operations.domain.services.time_tracking_rules import assert_credentials_usable
from src.modules.operations.ports.outbound.operations_settings_repository import (
    IOperationsSettingsRepository,
)
from src.modules.operations.ports.outbound.repositories.user_time_tracking_credentials_repository import (
    IUserTimeTrackingCredentialsRepository,
)
from src.modules.operations.ports.outbound.time_tracking_provider_port import (
    ITimeTrackingProviderFactory,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.login_attempt_tracker_port import ILoginAttemptTracker
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


class CheckMyTimeTrackingAccess:
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

    async def execute(self, actor: User) -> TimeTrackingAccountResult:
        setup = await load_time_tracking_setup(actor, self._settings)
        credentials = assert_credentials_usable(
            await self._credentials.get_by_user(actor.id),
            current_key_id=setup.settings.credential_key_id,
        )
        assert credentials.time_tracking_sealed_credentials
        await assert_verify_not_locked(self._rate_tracker, actor.id)

        await self._uow.commit()
        provider = self._provider_factory(setup.connection)
        try:
            async with recording_rejections(self._credentials, self._uow, actor.id, self._clock()):
                verification = await provider.verify(credentials.time_tracking_sealed_credentials)
        except TimeTrackingAuthenticationFailedError:
            await record_verify_failure(self._rate_tracker, actor.id)
            raise

        return TimeTrackingMapper.account_to_result(
            setup.settings,
            credentials,
            employee_name=verification.employee_name,
            rights=verification.rights,
        )
