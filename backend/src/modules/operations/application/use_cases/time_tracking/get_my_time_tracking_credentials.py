"""Returns the actor's own stored time tracking credentials and whether they
can be used, from Glados data only. Never contacts the time tracking
system, so opening My Account or loading the app costs it nothing. The user
name is returned to its owner only; the password never leaves the server."""

from src.modules.operations.application.dto.time_tracking_dto import TimeTrackingAccountResult
from src.modules.operations.application.mappers.time_tracking_mapper import TimeTrackingMapper
from src.modules.operations.application.services.time_tracking_access import load_enabled_settings
from src.modules.operations.ports.outbound.operations_settings_repository import (
    IOperationsSettingsRepository,
)
from src.modules.operations.ports.outbound.repositories.user_time_tracking_credentials_repository import (
    IUserTimeTrackingCredentialsRepository,
)
from src.modules.platform.domain.entities.user import User


class GetMyTimeTrackingCredentials:
    def __init__(
        self,
        settings_repo: IOperationsSettingsRepository,
        credentials_repo: IUserTimeTrackingCredentialsRepository,
    ) -> None:
        self._settings = settings_repo
        self._credentials = credentials_repo

    async def execute(self, actor: User) -> TimeTrackingAccountResult:
        settings = await load_enabled_settings(actor, self._settings)
        credentials = await self._credentials.get_by_user(actor.id)
        return TimeTrackingMapper.account_to_result(settings, credentials)
