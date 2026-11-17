"""
Backs the trigger endpoints (POST {API_KEY}/pdm/files/changed and the
batch forms on the API-key and PAT surfaces): the vault add-in (or any
other caller holding USE_PDM_ADDIN) says "this file changed", and this
use case only
stages a PdmFileChangeRequested event for the pdm_sync worker to act on;
it never reads from PDM itself and never trusts the caller's payload
beyond the vault name and the file's identity, so the actual variables,
version and state are always re-read from the Web API downstream (see
RefreshPdmFile). Glados knows the caller only as the actor its credential
signs in as, the key's own service account for an API key and the owner
for a PAT, so the rate limiter below, kept per actor, is what keeps a
misbehaving or compromised token from flooding the event stream.

The batch forms (POST {API_KEY}/pdm/files/changed/batch and POST
/api/v1/pat/pdm/files/changed/batch) stage one event per file of a single
call, see execute_batch. Their entries may also say why the file changed
(reason and destination state); that, and the actor's full name, travel on
the event only so the sync run can record them for the file history.
"""

from src.modules.external_data.application.dto.pdm_dto import RequestPdmFileRefreshBatchCommand
from src.modules.external_data.application.dto.pdm_dto import RequestPdmFileRefreshCommand
from src.modules.external_data.application.services.pdm_integration import is_pdm_enabled
from src.modules.external_data.application.services.pdm_trigger_rate_limiter import (
    PdmTriggerRateLimiter,
)
from src.modules.external_data.application.services.pdm_vault import vault_name_matches
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.errors import PdmNotEnabledError
from src.modules.external_data.domain.errors import PdmVaultMismatchError
from src.modules.external_data.domain.events.pdm_events import PdmFileChangeRequested
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class RequestPdmFileRefresh:
    def __init__(
        self,
        admin_settings_repo: IExternalDataSettingsRepository,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        rate_limiter: PdmTriggerRateLimiter,
    ) -> None:
        self._admin_settings = admin_settings_repo
        self._bus = event_bus
        self._uow = uow
        self._rate_limiter = rate_limiter

    async def execute(self, actor: User, cmd: RequestPdmFileRefreshCommand) -> None:
        """Raises InsufficientPermissionsError (403) without
        use:pdm_addin, PdmNotEnabledError (409) while the integration
        is off or unconfigured, PdmVaultMismatchError (400) for an unknown
        vault name, and PdmTriggerRateLimitedError (429) once the actor
        has exceeded its trigger budget. Nothing about `cmd.file_id`/
        `cmd.path`/`cmd.version` is validated here beyond being present;
        the worker re-reads and validates the real file from PDM."""
        settings = await self._authorize(actor, cmd.vault_name)
        self._rate_limiter.check(actor.id)

        await self._bus.publish(
            self._event(settings, actor, cmd.file_id, cmd.path, cmd.version, None, None)
        )
        await self._uow.commit()

        log.info("PDM file-changed trigger: file_id=%r path=%r.", cmd.file_id, cmd.path)

    async def execute_batch(self, actor: User, cmd: RequestPdmFileRefreshBatchCommand) -> int:
        """The batch form of execute: one event per distinct file id (the
        last entry for an id wins), committed together. Raises the same
        errors as execute; the rate limit counts every file, so the whole
        batch is rejected when it does not fit the remaining budget.
        Returns the number of files accepted."""
        settings = await self._authorize(actor, cmd.vault_name)
        files = list({ref.file_id: ref for ref in cmd.files}.values())
        self._rate_limiter.check(actor.id, cost=len(files))

        for ref in files:
            await self._bus.publish(
                self._event(
                    settings, actor, ref.file_id, ref.path, ref.version, ref.reason, ref.state
                )
            )
        await self._uow.commit()

        log.info("PDM file-changed batch trigger: %d files.", len(files))
        return len(files)

    async def _authorize(self, actor: User, vault_name: str) -> AdminPdmSettings:
        if not actor.has_permission(Permission.USE_PDM_ADDIN):
            raise InsufficientPermissionsError(
                f"User #{actor.id} ({actor.full_name}) cannot trigger a PDM sync."
            )

        settings = await self._admin_settings.get_pdm()
        if not is_pdm_enabled(settings):
            raise PdmNotEnabledError(
                "The PDM integration is not enabled and configured; there is nothing to refresh."
            )

        if not vault_name_matches(vault_name, settings.vault_name):
            raise PdmVaultMismatchError(f"Unknown vault {vault_name!r}.")
        return settings

    @staticmethod
    def _event(
        settings: AdminPdmSettings,
        actor: User,
        file_id: int | None,
        path: str | None,
        version: int | None,
        reason: str | None,
        state: str | None,
    ) -> PdmFileChangeRequested:
        return PdmFileChangeRequested(
            vault_name=settings.vault_name,
            file_id=file_id,
            path=path,
            version=version,
            requested_by_id=actor.id,
            source="file_trigger",
            reason=reason,
            state=state,
            requested_by_name=actor.full_name,
        )
