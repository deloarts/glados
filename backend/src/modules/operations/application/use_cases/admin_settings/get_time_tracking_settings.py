"""Routes GET /admin/settings/time-tracking through the use-case layer. Adds
the users with stored time tracking credentials and whether those can be
used, so the admin sees who opted in and what the purge would remove. The
list never carries a time tracking user name or anything sealed."""

from src.modules.operations.application.dto.admin_settings_dto.time_tracking import (
    AdminTimeTrackingSettingsResult,
)
from src.modules.operations.application.dto.admin_settings_dto.time_tracking import (
    TimeTrackingCredentialHolderResult,
)
from src.modules.operations.application.mappers.admin_settings_mapper.time_tracking import (
    TimeTrackingSettingsMapper,
)
from src.modules.operations.domain.entities.admin_settings.time_tracking import (
    AdminTimeTrackingSettings,
)
from src.modules.operations.domain.services.time_tracking_rules import credentials_invalid_reason
from src.modules.operations.ports.outbound.operations_settings_repository import (
    IOperationsSettingsRepository,
)
from src.modules.operations.ports.outbound.repositories.user_time_tracking_credentials_repository import (
    IUserTimeTrackingCredentialsRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository


async def credential_holders(
    settings: AdminTimeTrackingSettings,
    credentials_repo: IUserTimeTrackingCredentialsRepository,
    user_repo: IUserRepository,
) -> list[TimeTrackingCredentialHolderResult]:
    """Every user with stored credentials, by user name."""
    holders: list[TimeTrackingCredentialHolderResult] = []
    for credentials in await credentials_repo.list_all():
        user = await user_repo.get_by_id(credentials.user_id)
        if user is None:
            continue
        reason = credentials_invalid_reason(credentials, current_key_id=settings.credential_key_id)
        holders.append(
            TimeTrackingCredentialHolderResult(
                user_id=user.id,
                username=user.username,
                full_name=user.full_name,
                saved_at=credentials.updated_at,
                credentials_valid=reason is None,
                credentials_invalid_reason=reason.value if reason else None,
            )
        )
    return sorted(holders, key=lambda h: h.username.casefold())


class GetTimeTrackingSettings:
    def __init__(
        self,
        repo: IOperationsSettingsRepository,
        credentials_repo: IUserTimeTrackingCredentialsRepository,
        user_repo: IUserRepository,
    ) -> None:
        self._repo = repo
        self._credentials = credentials_repo
        self._users = user_repo

    async def execute(self, actor: User) -> AdminTimeTrackingSettingsResult:
        SettingsRules.assert_can_read(actor)
        settings = await self._repo.get_time_tracking()
        return TimeTrackingSettingsMapper.time_tracking_to_result(
            settings,
            credential_holders=await credential_holders(settings, self._credentials, self._users),
        )
