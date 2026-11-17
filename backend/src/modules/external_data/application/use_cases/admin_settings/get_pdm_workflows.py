"""
Proxies GET api/{vaultName}/workflows for the admin settings page's
released/obsolete state pickers (GET /admin/settings/pdm/workflows), under
the saved connection and its shared session, same as the other PDM
proxies in this package.
"""

from src.modules.external_data.application.dto.admin_settings_dto.pdm_vault import PdmWorkflowResult
from src.modules.external_data.application.dto.admin_settings_dto.pdm_vault import (
    PdmWorkflowStateResult,
)
from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.external_data.ports.outbound.pdm_gateway_port import IPdmGateway
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmWorkflow
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules


class GetPdmWorkflows:
    def __init__(self, session: PdmSessionService) -> None:
        self._session = session

    async def execute(self, actor: User) -> list[PdmWorkflowResult]:
        SettingsRules.assert_can_read(actor)

        async def _call(gateway: IPdmGateway, token: str) -> list[PdmWorkflow]:
            return await gateway.workflows(token)

        workflows = await self._session.call(_call)
        return [
            PdmWorkflowResult(
                workflow_id=w.workflow_id,
                workflow_name=w.workflow_name,
                states=[
                    PdmWorkflowStateResult(state_id=s.state_id, state_name=s.state_name)
                    for s in w.states
                ],
            )
            for w in workflows
        ]
