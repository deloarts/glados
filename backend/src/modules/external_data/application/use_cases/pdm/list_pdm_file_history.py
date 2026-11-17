"""
Backs the PAT surface's file history read (POST
/api/v1/pat/pdm/files/history): the vault add-in shows, for the files a user
selects in the vault view, what Glados did with them and why, newest first
and merged across the files. It reads the sync log only, so it shows what
the worker has processed: a trigger still waiting in the queue, or one
rejected before it was queued, has no entry yet, and the log keeps runs for
SYNC_RUN_RETENTION. Gated by use:pdm_addin, which the PDM add-in token
preset carries, since the existing sync log reads sit behind read:settings,
which a token can never hold. The vault name is checked exactly as the
trigger checks it, so a caller cannot read another vault's ids by mistake.
"""

from src.modules.external_data.application.dto.pdm_dto import ListPdmFileHistoryCommand
from src.modules.external_data.application.dto.pdm_dto import PdmFileHistoryEntryResult
from src.modules.external_data.application.services.pdm_integration import is_pdm_enabled
from src.modules.external_data.application.services.pdm_vault import vault_name_matches
from src.modules.external_data.domain.errors import PdmNotEnabledError
from src.modules.external_data.domain.errors import PdmVaultMismatchError
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.external_data.ports.outbound.repositories.pdm_sync_run_repository import (
    IPdmSyncRunRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission


class ListPdmFileHistory:
    def __init__(
        self, admin_settings_repo: IExternalDataSettingsRepository, run_repo: IPdmSyncRunRepository
    ) -> None:
        self._admin_settings = admin_settings_repo
        self._runs = run_repo

    async def execute(
        self, actor: User, cmd: ListPdmFileHistoryCommand
    ) -> list[PdmFileHistoryEntryResult]:
        """Raises InsufficientPermissionsError (403) without use:pdm_addin,
        PdmNotEnabledError (409) while the integration is off or
        unconfigured and PdmVaultMismatchError (400) for an unknown vault
        name. Returns an empty list before the vault id is first resolved,
        since no entry can exist then."""
        if not actor.has_permission(Permission.USE_PDM_ADDIN):
            raise InsufficientPermissionsError(
                f"User #{actor.id} ({actor.full_name}) cannot read the PDM sync history."
            )

        settings = await self._admin_settings.get_pdm()
        if not is_pdm_enabled(settings):
            raise PdmNotEnabledError(
                "The PDM integration is not enabled and configured; there is no history to read."
            )
        if not vault_name_matches(cmd.vault_name, settings.vault_name):
            raise PdmVaultMismatchError(f"Unknown vault {cmd.vault_name!r}.")
        if not settings.vault_id:
            return []

        rows = await self._runs.list_file_history(
            settings.vault_id, sorted(set(cmd.file_ids)), cmd.limit
        )
        return [
            PdmFileHistoryEntryResult(
                file_id=entry.file_id,
                name=entry.name,
                path=entry.path,
                kind=entry.kind,
                action=entry.action,
                message=entry.message,
                created_at=entry.created_at,
                run_id=run.id,
                trigger=run.trigger.value,
                run_started_at=run.started_at,
                run_finished_at=run.finished_at,
                run_error=run.error,
                change_reason=run.change_reason,
                change_state=run.change_state,
                requested_by_name=run.requested_by_name,
            )
            for entry, run in rows
        ]
