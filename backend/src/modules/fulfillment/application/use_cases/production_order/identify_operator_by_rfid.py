"""
RFID operator identification, the tap-your-chip alternative to picking a
name from the GetOperators dropdown when a shared-account session records
who actually did the work.

**RFID identifies, it does not authenticate.** This use case deliberately
returns a *user identity*, never a session token: an RFID chip is cloneable
and readable at a distance, so it is not a credential. Authentication has
already happened, the caller must hold a real session, and this only
answers "which of the eligible operators is standing here".

Eligibility mirrors GetOperators exactly, including the shared-account
membership boundary, so a chip can only ever resolve to someone who could
have been chosen from the dropdown instead.
"""

from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.platform.application.dto.user_dto import PublicUserResult
from src.modules.platform.application.mappers.user_mapper import UserMapper
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import RfidDisabledError
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository


class IdentifyOperatorByRfid:
    def __init__(
        self,
        user_repo: IUserRepository,
        settings_repo: IFulfillmentSettingsRepository,
    ) -> None:
        self._users = user_repo
        self._settings = settings_repo

    async def execute(self, actor: User, rfid: str) -> PublicUserResult:
        if not (await self._settings.get_security()).allow_rfid_login:
            raise RfidDisabledError("RFID identification is disabled.")

        user = await self._users.get_by_rfid(rfid)

        # One error for every rejection reason, unknown chip, inactive
        # user, service/shared account, or not a member of this shared
        # account. Distinguishing them would let an unknown chip be told
        # apart from a known-but-ineligible one, turning this into a
        # membership oracle.
        eligible = (
            user is not None
            and user.is_active
            and not user.is_service_account
            and not user.is_shared_account
            and not (actor.is_shared_account and user.id not in actor.member_ids)
        )
        if not eligible or user is None:
            log.warning("RFID identification failed.")
            raise UserNotFoundError("No selectable operator found for this RFID.")

        log.info(
            "Operator %r (id=%s) identified by RFID.",
            user.username,
            user.id,
        )
        return UserMapper.to_public_result(user)
