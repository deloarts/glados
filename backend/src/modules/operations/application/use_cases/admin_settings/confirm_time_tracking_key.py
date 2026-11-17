"""Confirms the credential key of the saved time tracking service, the key
users' credentials are sealed for from then on. The admin names the key id
the connection test showed, and the key is stored only when the service
still serves exactly that key, so a key that changed in between is never
confirmed unseen. The provider label is stored with it, for the
capabilities answer.

Credentials sealed for a previous key stop being usable at once, since
their key id no longer matches; their users enter the password again. The
audit entry names the old and the new key id.
"""

from src.modules.operations.application.dto.admin_settings_dto.time_tracking import (
    AdminTimeTrackingSettingsResult,
)
from src.modules.operations.application.dto.admin_settings_dto.time_tracking import (
    ConfirmTimeTrackingKeyCommand,
)
from src.modules.operations.application.mappers.admin_settings_mapper.time_tracking import (
    TimeTrackingSettingsMapper,
)
from src.modules.operations.application.services.time_tracking_service import service_connection
from src.modules.operations.application.use_cases.admin_settings.get_time_tracking_settings import (
    credential_holders,
)
from src.modules.operations.domain.errors import TimeTrackingKeyChangedError
from src.modules.operations.domain.errors import TimeTrackingNotConfiguredError
from src.modules.operations.domain.errors import TimeTrackingProviderError
from src.modules.operations.infrastructure.security.time_tracking_sealer import (
    InvalidCredentialKeyError,
)
from src.modules.operations.infrastructure.security.time_tracking_sealer import load_public_key
from src.modules.operations.ports.outbound.operations_settings_repository import (
    IOperationsSettingsRepository,
)
from src.modules.operations.ports.outbound.repositories.user_time_tracking_credentials_repository import (
    IUserTimeTrackingCredentialsRepository,
)
from src.modules.operations.ports.outbound.time_tracking_provider_port import (
    ITimeTrackingProviderFactory,
)
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class ConfirmTimeTrackingKey:
    def __init__(
        self,
        provider_factory: ITimeTrackingProviderFactory,
        repo: IOperationsSettingsRepository,
        credentials_repo: IUserTimeTrackingCredentialsRepository,
        user_repo: IUserRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._provider_factory = provider_factory
        self._repo = repo
        self._credentials = credentials_repo
        self._users = user_repo
        self._uow = uow

    async def execute(
        self, actor: User, cmd: ConfirmTimeTrackingKeyCommand
    ) -> AdminTimeTrackingSettingsResult:
        SettingsRules.assert_can_write(actor)

        current = await self._repo.get_time_tracking()
        if not current.is_configured:
            raise TimeTrackingNotConfiguredError(
                "Save the service URL and the API key before confirming a key."
            )
        await self._uow.commit()
        info = await self._provider_factory(service_connection(current)).info()
        if info.credential_key_id != cmd.credential_key_id:
            raise TimeTrackingKeyChangedError(
                "The service now serves another credential key. Test the connection again."
            )
        try:
            load_public_key(info.credential_public_key)
        except InvalidCredentialKeyError as exc:
            raise TimeTrackingProviderError(
                "The time tracking service serves an invalid credential key."
            ) from exc

        current.credential_public_key = info.credential_public_key
        previous_key_id = current.credential_key_id
        current.credential_key_id = info.credential_key_id
        current.provider_label = info.provider_label
        saved = await self._repo.save_time_tracking(current)
        await self._repo.append_audit(
            AdminSettingsAuditEntry.by_actor(
                actor,
                settings_domain="time_tracking",
                summary=(
                    f"Time tracking credential key {info.credential_key_id} confirmed by "
                    f"{actor.username} (previously {previous_key_id or 'none'})."
                ),
            )
        )
        await self._uow.commit()

        log.info("Confirmed the time tracking credential key %s.", info.credential_key_id)
        return TimeTrackingSettingsMapper.time_tracking_to_result(
            saved,
            credential_holders=await credential_holders(saved, self._credentials, self._users),
        )
