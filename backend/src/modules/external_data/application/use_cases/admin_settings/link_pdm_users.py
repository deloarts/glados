"""
POST /admin/settings/pdm/users/link: saves the PDM-user-to-Glados-user
links an admin confirmed in the Match PDM Users dialog. Each
entry sets (`user_id`) or clears (`user_id: null`) one vault user's link.

Several vault users may link to the same Glados user (a person can
release under more than one PDM account), so, unlike a single-valued
column, setting one entry never disturbs another target's existing
links. Relinking a PDM user id that already links to a different Glados
user is allowed and moves it: the caller picked this PDM user for this
Glados user deliberately, and UserPdmLink.upsert reassigns rather than
rejecting, since pdm_user_id's unique constraint would otherwise reject a
second row for it anyway.

The request only ever carries `pdm_user_id`/`user_id`, never the vault
username, so a linking entry (user_id not null) needs one Web API call
(GET api/{vaultName}/users, the same call ListPdmUsers makes) to resolve
`pdm_username` for the row being stored; an unlink never touches the
vault at all. That call failing (vault unreachable between the admin
loading the dialog and hitting save) must not lose the admin's already-
confirmed selections: it is logged and treated as "no usernames
resolved", the same fail-open shape ListPdmUsers' own extended-lookup
uses, so every entry still links, with an empty display username.
"""

from src.modules.external_data.application.dto.admin_settings_dto.pdm_vault import (
    LinkPdmUsersCommand,
)
from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.external_data.ports.outbound.pdm_gateway_port import IPdmGateway
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmUser
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import DomainError
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.repositories.user_pdm_link_repository import (
    IUserPdmLinkRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class LinkPdmUsers:
    def __init__(
        self,
        user_repo: IUserRepository,
        link_repo: IUserPdmLinkRepository,
        session: PdmSessionService,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._users = user_repo
        self._links = link_repo
        self._session = session
        self._uow = uow

    async def execute(self, actor: User, cmd: LinkPdmUsersCommand) -> None:
        SettingsRules.assert_can_write(actor)

        usernames: dict[int, str] = {}
        if any(entry.user_id is not None for entry in cmd.links):

            async def _list(gateway: IPdmGateway, token: str) -> list[PdmUser]:
                return await gateway.list_users(token)

            try:
                vault_users = await self._session.call(_list)
                usernames = {u.id: u.username for u in vault_users}
            except DomainError as exc:
                log.warning(
                    f"PDM user linking: could not read the vault's user list, "
                    f"linking without display usernames: {exc}"
                )

        for entry in cmd.links:
            if entry.user_id is None:
                await self._links.delete_by_pdm_user_id(entry.pdm_user_id)
                await self._uow.commit()
                continue

            user = found_or_raise(
                await self._users.get_by_id(entry.user_id),
                UserNotFoundError,
                f"User #{entry.user_id} not found.",
            )

            # A vault user id the current listing no longer reports (removed
            # from the vault between listing and saving) still links, with
            # an empty display username rather than failing the whole batch.
            pdm_username = usernames.get(entry.pdm_user_id, "")
            await self._links.upsert(
                pdm_user_id=entry.pdm_user_id, user_id=user.id, pdm_username=pdm_username
            )
            # Each entry commits on its own, so an unknown user id later in
            # the batch leaves the entries before it saved.
            await self._uow.commit()

        log.info(f"Updated PDM user links ({len(cmd.links)} entrie(s)).")
