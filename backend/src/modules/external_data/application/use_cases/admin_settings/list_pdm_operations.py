"""
Lists the SOLIDWORKS PDM Web API operation catalogue for the admin API
console (GET /admin/settings/pdm/operations). Purely a read of the
in-process catalogue, no call to the vault is made and no permission
beyond read:settings is required.
"""

from src.modules.external_data.application.dto.admin_settings_dto.pdm_vault import (
    PdmOperationResult,
)
from src.modules.external_data.application.dto.admin_settings_dto.pdm_vault import PdmParamResult
from src.modules.external_data.application.services.pdm_console_policy import console_operations
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmOperationSpec
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules


class ListPdmOperations:
    def __init__(self, catalogue: tuple[PdmOperationSpec, ...]) -> None:
        self._catalogue = console_operations(catalogue)

    async def execute(self, actor: User) -> list[PdmOperationResult]:
        SettingsRules.assert_can_read(actor)
        return [self._to_result(spec) for spec in self._catalogue]

    @staticmethod
    def _to_result(spec: PdmOperationSpec) -> PdmOperationResult:
        # vaultName is dropped from the param list the console renders: the
        # invoke endpoint fills it from the saved connection, and showing it
        # as an editable field would let an admin pass an out-of-vault name
        # that the server ignores anyway.
        return PdmOperationResult(
            id=spec.id,
            method=spec.method,
            path=spec.path,
            group=spec.group,
            description=spec.description,
            params=[
                PdmParamResult(
                    name=p.name,
                    location=p.location,
                    type=p.type,
                    required=p.required,
                    description=p.description,
                )
                for p in spec.params
                if p.name != "vaultName"
            ],
            has_body=spec.has_body,
            body_example=spec.body_example,
            mutating=spec.mutating,
        )
