"""
Proxies GET api/{vaultName}/folders/{folderId}/browse for the admin
settings page's watched-folder picker (GET
/admin/settings/pdm/folders?parent_id=), under the saved connection and
its shared session. Folders only: `browse_folder` also returns files and
BOMs at that level, which the picker has no use for (it names folders,
never individual files).
"""

from src.modules.external_data.application.dto.admin_settings_dto.pdm_vault import PdmFolderResult
from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.external_data.ports.outbound.pdm_gateway_port import IPdmGateway
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmObjectInfo
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules

# PDM's ObjectType: 0 folder, 1 file, 3 BOM.
_FOLDER_OBJECT_TYPE = 0


class BrowsePdmFolders:
    def __init__(self, session: PdmSessionService) -> None:
        self._session = session

    async def execute(self, actor: User, parent_id: int) -> list[PdmFolderResult]:
        SettingsRules.assert_can_read(actor)

        async def _call(gateway: IPdmGateway, token: str) -> list[PdmObjectInfo]:
            return await gateway.browse_folder(token, parent_id)

        objects = await self._session.call(_call)
        return [
            PdmFolderResult(id=o.id, name=o.name, path=o.path)
            for o in objects
            if o.object_type == _FOLDER_OBJECT_TYPE
        ]
