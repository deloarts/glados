"""
Backs the API-key surface's trigger config read (GET {API_KEY}/pdm/config):
gives an API-key caller that checks releases itself one place to read the
release-state names it should treat as "released", so it never hardcodes
them. The vault add-in does not call it, since PDM transition conditions
guard its releases. Resolves AdminPdmSettings.made_released_state_ids/
bought_released_state_ids to workflow state names fresh from the Web API,
the same PdmSessionService discipline ValidatePdmFile uses, and lets
whatever the session raises (an unconfigured/unreachable vault, an
authentication failure) propagate unchanged. Read-only throughout: no
snapshot is written, no sync run is logged.
"""

from src.modules.external_data.application.dto.pdm_dto import PdmTriggerConfigResult
from src.modules.external_data.application.services.pdm_integration import is_pdm_enabled
from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.external_data.domain.errors import PdmNotEnabledError
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.external_data.ports.outbound.pdm_gateway_port import IPdmGateway
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmWorkflow
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission


class GetPdmTriggerConfig:
    def __init__(
        self, session: PdmSessionService, admin_settings_repo: IExternalDataSettingsRepository
    ) -> None:
        self._session = session
        self._admin_settings = admin_settings_repo

    async def execute(self, actor: User) -> PdmTriggerConfigResult:
        if not actor.has_permission(Permission.USE_PDM_ADDIN):
            raise InsufficientPermissionsError(
                f"User #{actor.id} ({actor.full_name}) cannot read the PDM trigger config."
            )

        settings = await self._admin_settings.get_pdm()
        if not is_pdm_enabled(settings):
            raise PdmNotEnabledError(
                "The PDM integration is not enabled and configured; there is no config to read."
            )

        # Both kinds' released-state ids, not released_state_ids_for(kind);
        # that accessor is for a caller that already knows its own kind; the
        # add-in wants the union across made and bought.
        released_ids = set(settings.made_released_state_ids) | set(
            settings.bought_released_state_ids
        )

        async def _workflows(gw: IPdmGateway, token: str) -> list[PdmWorkflow]:
            return await gw.workflows(token)

        workflows = await self._session.call(_workflows)
        names = {
            state.state_name
            for workflow in workflows
            for state in workflow.states
            if state.state_id in released_ids
        }

        return PdmTriggerConfigResult(
            vault_name=settings.vault_name, release_state_names=sorted(names)
        )
