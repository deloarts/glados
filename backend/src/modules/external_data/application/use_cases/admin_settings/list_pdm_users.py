"""
GET /admin/settings/pdm/users: every vault user (GET api/{vaultName}/users)
cross-referenced against Glados users, for the "Match PDM Users"
dialog on the SolidWorks PDM settings tab. A vault user already linked
(UserPdmLink) reports that link; an unlinked one gets a same-identity
guess (proposed_user_id) so the dialog can preselect a sensible default
instead of forcing an admin to hunt through the user list by hand: a
case-insensitive username match first, and only when that fails, one more
Web API call (GET .../Extended) to try the vault user's email. The
configured service account, the login PdmSessionService authenticates as,
is flagged and never proposed. Several vault users may report the same
linked_user_id or proposed_user_id, since one Glados user may hold more
than one PDM link. See docs/PDM_INTEGRATION.md's user mapping section.
"""

from src.modules.external_data.application.dto.admin_settings_dto.pdm_vault import PdmUserResult
from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.external_data.ports.outbound.pdm_gateway_port import IPdmGateway
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmUser
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import DomainError
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.repositories.user_pdm_link_repository import (
    IUserPdmLinkRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository


class ListPdmUsers:
    def __init__(
        self,
        session: PdmSessionService,
        settings_repo: IExternalDataSettingsRepository,
        user_repo: IUserRepository,
        link_repo: IUserPdmLinkRepository,
    ) -> None:
        self._session = session
        self._settings = settings_repo
        self._users = user_repo
        self._links = link_repo

    async def execute(self, actor: User) -> list[PdmUserResult]:
        SettingsRules.assert_can_write(actor)

        settings = await self._settings.get_pdm()
        service_account = settings.username.strip().lower()

        async def _list(gateway: IPdmGateway, token: str) -> list[PdmUser]:
            return await gateway.list_users(token)

        vault_users = await self._session.call(_list)
        linked_user_ids = {link.pdm_user_id: link.user_id for link in await self._links.list_all()}

        results: list[PdmUserResult] = []
        for vault_user in vault_users:
            is_service_account = (
                bool(service_account) and vault_user.username.strip().lower() == service_account
            )
            linked_user_id = linked_user_ids.get(vault_user.id)
            proposed_id = (
                None
                if linked_user_id is not None or is_service_account
                else await self._propose(vault_user)
            )
            results.append(
                PdmUserResult(
                    pdm_user_id=vault_user.id,
                    username=vault_user.username,
                    full_name=vault_user.full_name,
                    is_service_account=is_service_account,
                    linked_user_id=linked_user_id,
                    proposed_user_id=proposed_id,
                )
            )
        return results

    async def _propose(self, vault_user: PdmUser) -> int | None:
        by_username = await self._users.get_by_username_ci(vault_user.username)
        if by_username is not None:
            return by_username.id

        async def _extended(gateway: IPdmGateway, token: str) -> str:
            return (await gateway.user_extended(token, vault_user.id)).email

        try:
            email = await self._session.call(_extended)
        except DomainError as exc:
            # A single vault user's extended lookup failing (a private
            # user record, a transient vault hiccup) must not blank out
            # every other row's proposal: log and treat as "no guess".
            log.warning(
                f"PDM user matching: could not read extended info for vault user "
                f"{vault_user.id}: {exc}"
            )
            return None
        if not email:
            return None
        by_email = await self._users.get_by_email_ci(email)
        return by_email.id if by_email is not None else None
