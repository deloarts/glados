"""
Backs the admin API console's "Execute" action: calls any catalogued PDM
Web API operation generically through PdmSessionService, under the saved
connection and its shared session token.

Mutating operations (checkin, delete, changestate, and 25 others per the
catalogue) need two switches. The deployment must allow them at all
(PDM__ALLOW_MUTATING_OPERATIONS, off by default), and the caller must opt
in with `allow_mutating` on this specific call, per the console's "Allow
Critical Endpoints" switch. A successful mutating call is recorded in the settings audit log
because PDM's own history does not always attribute the Web API user
clearly. Never logs the request or response body, and never logs the
bearer token, only the operation id and the resulting HTTP status.
"""

from src.modules.external_data.application.dto.admin_settings_dto.pdm_vault import (
    InvokePdmOperationCommand,
)
from src.modules.external_data.application.dto.admin_settings_dto.pdm_vault import (
    PdmInvokeResultDto,
)
from src.modules.external_data.application.services.pdm_console_policy import console_operations
from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.external_data.domain.errors import PdmMutatingOperationsDisabledError
from src.modules.external_data.domain.errors import PdmOperationNotAllowedError
from src.modules.external_data.domain.errors import PdmOperationParametersInvalidError
from src.modules.external_data.domain.errors import PdmUnknownOperationError
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.external_data.ports.outbound.pdm_gateway_port import IPdmGateway
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmInvokeResult
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmOperationSpec
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class InvokePdmOperation:
    def __init__(
        self,
        session: PdmSessionService,
        catalogue: tuple[PdmOperationSpec, ...],
        repo: IExternalDataSettingsRepository,
        *,
        uow: IUnitOfWork,
        mutating_operations_enabled: bool = False,
    ) -> None:
        self._uow = uow
        self._session = session
        self._catalogue = console_operations(catalogue)
        self._repo = repo
        self._mutating_operations_enabled = mutating_operations_enabled

    async def execute(self, actor: User, cmd: InvokePdmOperationCommand) -> PdmInvokeResultDto:
        SettingsRules.assert_can_write(actor)

        spec = next((s for s in self._catalogue if s.id == cmd.operation_id), None)
        if spec is None:
            raise PdmUnknownOperationError(f"Unknown PDM operation id {cmd.operation_id!r}.")

        if "vaultName" in cmd.path_params:
            raise PdmOperationParametersInvalidError(
                "vaultName is filled in from the saved connection and must not be supplied."
            )

        required_path_params = {
            p.name for p in spec.params if p.location == "path" and p.required
        } - {"vaultName"}
        missing = required_path_params - set(cmd.path_params)
        if missing:
            raise PdmOperationParametersInvalidError(
                f"Missing required path parameter(s): {sorted(missing)}."
            )

        if spec.mutating and not self._mutating_operations_enabled:
            raise PdmMutatingOperationsDisabledError(
                f"{cmd.operation_id!r} is a mutating operation, and this deployment leaves "
                "them off. Set PDM__ALLOW_MUTATING_OPERATIONS=true to allow them."
            )
        if spec.mutating and not cmd.allow_mutating:
            raise PdmOperationNotAllowedError(
                f"{cmd.operation_id!r} is a mutating operation; "
                "allow_mutating must be true to invoke it."
            )

        async def _invoke(gateway: IPdmGateway, token: str) -> PdmInvokeResult:
            return await gateway.invoke(token, spec, cmd.path_params, cmd.query, cmd.body)

        result = await self._session.call(_invoke)

        log.info(
            "PDM operation %r invoked: HTTP %s.",
            cmd.operation_id,
            result.status_code,
        )

        if spec.mutating and 200 <= result.status_code < 300:
            await self._repo.append_audit(
                AdminSettingsAuditEntry.by_actor(
                    actor,
                    settings_domain="pdm",
                    summary=(
                        f"PDM mutating operation {cmd.operation_id!r} invoked by "
                        f"{actor.username} (HTTP {result.status_code})."
                    ),
                )
            )
            await self._uow.commit()

        return PdmInvokeResultDto(
            method=result.method,
            url=result.url,
            status_code=result.status_code,
            elapsed_ms=result.elapsed_ms,
            content_type=result.content_type,
            response_json=result.response_json,
            response_text=result.response_text,
        )
