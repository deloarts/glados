"""
RFID lookup for the key surface, which hardware readers call to learn who
tapped a tag.

**RFID identifies, it does not authenticate.** A tag is cloneable and
readable at a distance, so the answer is a name, never a session or the
account's details: the id, username and full name, nothing more. The admin
security setting `allow_rfid_login` switches the lookup off here exactly as
it does for operator identification on the web surface.
"""

from src.modules.platform.application.dto.user_dto import RfidIdentityResult
from src.modules.platform.application.mappers.user_mapper import UserMapper
from src.modules.platform.domain.exceptions import RfidDisabledError
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository


class IdentifyUserByRfid:
    def __init__(
        self, user_repo: IUserRepository, settings_repo: IPlatformSettingsRepository
    ) -> None:
        self._users = user_repo
        self._settings = settings_repo

    async def execute(self, rfid: str) -> RfidIdentityResult:
        if not (await self._settings.get_security()).allow_rfid_login:
            raise RfidDisabledError("RFID identification is disabled.")

        # The repository finds active accounts only. A service account never
        # carries a tag, so finding one would mean a corrupt row; it gets the
        # same answer as an unknown tag.
        user = await self._users.get_by_rfid(rfid)
        if user is None or user.is_service_account:
            log.warning("RFID lookup failed, no matching user.")
            raise UserNotFoundError("No user found for this RFID.")

        log.info("User %r (id=%s) identified by RFID.", user.username, user.id)
        return UserMapper.to_rfid_identity_result(user)
