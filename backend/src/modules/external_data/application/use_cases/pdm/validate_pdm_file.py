"""
Backs the API-key surface's pre-release validation endpoint (POST
{API_KEY}/pdm/files/{file_id}/validate, docs/reference/pdm-ingest.md section
8): resolves one file fresh from the Web API (the same discipline as
RefreshPdmFile, Glados never trusts anything about the file beyond its id),
works out its kind the same way RefreshPdmFile does (watched folder,
falling back to the datacard's kind variable for a `by_kind` folder), and
hands the result to ValidatePdmPayload for the actual dry run. Read-only
throughout: no snapshot is written, no sync run is logged, unlike a real
refresh. This call is meant to be cheap enough to run from a vault hook
before every attempted release, although the vault add-in does not call
it, since PDM transition conditions guard its releases.

A file outside every watched folder, or inside a `documents` folder (which
never holds catalogue items, see PdmWatchedFolder's own docstring), is not
an error: it is reported as an unresolvable validation (`kind: null`,
`would: "unknown"`) the same way an unresolved `by_kind` kind is, so the
caller always gets a 200 with an explanation rather than being told the
file itself is missing. PdmFileNotFoundError (404) is reserved for the
file genuinely not resolving, or the vault reporting it in the private
state / a state this session's grants can't read: RefreshPdmFile treats
that as a quiet skip because it runs unattended, but here the caller is
usually a human waiting for feedback, so it is surfaced as a clear error
instead of a silently empty-looking "unknown" result.

The batch endpoint (POST {API_KEY}/pdm/files/validate/batch) runs the same
check for several files under one time budget and reports each file's
outcome separately instead of failing the whole call, see execute_batch.
"""

import time

from src.modules.external_data.application.dto.pdm_dto import PdmBatchValidationOutcome
from src.modules.external_data.application.dto.pdm_dto import PdmValidationResult
from src.modules.external_data.application.dto.pdm_dto import ValidatePdmPayloadCommand
from src.modules.external_data.application.services.pdm_integration import is_pdm_enabled
from src.modules.external_data.application.services.pdm_integration import is_private_state
from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.external_data.application.services.pdm_variables import NO_FILE_LEVEL_CONFIGURATION
from src.modules.external_data.application.services.pdm_variables import resolve_file_kind
from src.modules.external_data.application.services.pdm_variables import select_configuration
from src.modules.external_data.application.services.pdm_vault import fetch_vault_id
from src.modules.external_data.application.use_cases.pdm.validate_pdm_payload import (
    ValidatePdmPayload,
)
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.errors import PdmApiError
from src.modules.external_data.domain.errors import PdmFileNotFoundError
from src.modules.external_data.domain.errors import PdmNotEnabledError
from src.modules.external_data.domain.value_objects.pdm_watched_folder import match_watched_folder
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.external_data.ports.outbound.pdm_gateway_port import IPdmGateway
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmConfigVariables
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmObjectInfo
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission

# Same 403 PDM answers for a file this vault user may list but not read
# (private state or missing grant): see refresh_pdm_file.py's identical
# constant and reasoning.
_UNREADABLE_STATUS_CODE = 403

# A batch validation stops starting new files after this many seconds and
# reports the rest "not_validated", so the add-in's release hook, which waits
# for the answer, is never held longer than its own budget.
_BATCH_BUDGET_SECONDS = 12.0


def _unresolved(reason: str) -> PdmValidationResult:
    # The API-key surface always has a real vault-issued file id (or
    # bails out before ValidatePdmPayload.execute ever runs, as here):
    # file_identity is "not_applicable" the same way it is for a full
    # execute() call on this surface, never "unresolved".
    return PdmValidationResult(
        ok=False,
        reasons=[reason],
        pending_pdm=[],
        kind=None,
        part_number=None,
        revision=None,
        would="unknown",
        file_identity="not_applicable",
        notes=[],
    )


class ValidatePdmFile:
    def __init__(
        self,
        session: PdmSessionService,
        admin_settings_repo: IExternalDataSettingsRepository,
        validate: ValidatePdmPayload,
    ) -> None:
        self._session = session
        self._admin_settings = admin_settings_repo
        self._validate = validate

    async def execute(self, actor: User, file_id: int) -> PdmValidationResult:
        settings = await self._authorize(actor)

        async def _lookup(gw: IPdmGateway, token: str) -> PdmObjectInfo | None:
            results = await gw.files_info(token, [file_id])
            return results[0] if results else None

        obj = await self._session.call(_lookup)
        if obj is None:
            raise PdmFileNotFoundError(f"PDM file #{file_id} was not found in the vault.")
        return await self._validate_object(settings, obj)

    async def execute_batch(
        self, actor: User, file_ids: list[int]
    ) -> list[PdmBatchValidationOutcome]:
        """Validates several files in one call, for a release of many files
        at once. The files are resolved with a single Web API read, then
        validated one by one until _BATCH_BUDGET_SECONDS have passed; the
        rest come back "not_validated", so a large batch answers in bounded
        time and the caller lets those files through. A file that does not
        resolve or fails to read only affects its own outcome. Each file id
        is answered once, in the order given."""
        settings = await self._authorize(actor)
        unique_ids = list(dict.fromkeys(file_ids))

        async def _lookup(gw: IPdmGateway, token: str) -> list[PdmObjectInfo]:
            return await gw.files_info(token, unique_ids)

        by_id = {obj.id: obj for obj in await self._session.call(_lookup)}
        deadline = time.monotonic() + _BATCH_BUDGET_SECONDS
        return [
            await self._batch_outcome(settings, file_id, by_id, deadline) for file_id in unique_ids
        ]

    async def _batch_outcome(
        self,
        settings: AdminPdmSettings,
        file_id: int,
        by_id: dict[int, PdmObjectInfo],
        deadline: float,
    ) -> PdmBatchValidationOutcome:
        if time.monotonic() > deadline:
            return PdmBatchValidationOutcome(
                file_id=file_id, outcome="not_validated", detail="validation time budget spent"
            )
        obj = by_id.get(file_id)
        if obj is None:
            return PdmBatchValidationOutcome(
                file_id=file_id, outcome="not_found", detail="not found in the vault"
            )
        try:
            result = await self._validate_object(settings, obj)
        except PdmFileNotFoundError:
            return PdmBatchValidationOutcome(
                file_id=file_id, outcome="not_found", detail="not readable for the PDM user"
            )
        except PdmApiError as exc:
            return PdmBatchValidationOutcome(file_id=file_id, outcome="failed", detail=str(exc))
        return PdmBatchValidationOutcome(file_id=file_id, outcome="validated", validation=result)

    async def _authorize(self, actor: User) -> AdminPdmSettings:
        if not actor.has_permission(Permission.USE_PDM_ADDIN):
            raise InsufficientPermissionsError(
                f"User #{actor.id} ({actor.full_name}) cannot validate a PDM file."
            )

        settings = await self._admin_settings.get_pdm()
        if not is_pdm_enabled(settings):
            raise PdmNotEnabledError(
                "The PDM integration is not enabled and configured; there is nothing to validate."
            )
        return settings

    async def _validate_object(
        self, settings: AdminPdmSettings, obj: PdmObjectInfo
    ) -> PdmValidationResult:
        file_id = obj.id
        folder = match_watched_folder(settings.watched_folders, obj.path)
        if folder is None:
            return _unresolved("file is outside every watched folder")
        if folder.kind == "documents":
            return _unresolved("file is in a documents folder, not a catalogue item")
        if is_private_state(obj):
            raise PdmFileNotFoundError(f"PDM file #{file_id} is not readable for the PDM user.")

        async def _variables(gw: IPdmGateway, token: str) -> list[PdmConfigVariables]:
            return await gw.file_variables(token, obj.id, obj.version, obj.parent_folder_id)

        try:
            configs = await self._session.call(_variables)
        except PdmApiError as exc:
            if exc.status_code == _UNREADABLE_STATUS_CODE:
                raise PdmFileNotFoundError(
                    f"PDM file #{file_id} is not readable for the PDM user."
                ) from exc
            raise

        variables = select_configuration(configs)
        if variables is None:
            return _unresolved(NO_FILE_LEVEL_CONFIGURATION)
        resolution = resolve_file_kind(
            folder_kind=folder.kind, variables=variables, settings=settings
        )
        if resolution.conflict is not None:
            return _unresolved(resolution.conflict)
        if resolution.kind is None:
            message = (
                "kind not set"
                if not resolution.raw
                else f"kind not set (value: {resolution.raw!r})"
            )
            return _unresolved(message)

        vault_id = settings.vault_id or await fetch_vault_id(self._session)
        cmd = ValidatePdmPayloadCommand(
            kind=resolution.kind,
            variables=variables,
            file_name=obj.name,
            vault_id=vault_id,
            file_id=obj.id,
        )
        return await self._validate.execute(cmd)
