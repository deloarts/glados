"""
Write-back to PDM (docs/PDM_INTEGRATION.md "Write-back to PDM"): after every
ingest of a linked file, writes three version-free datacard variables onto
the vault file so PDM and the SolidWorks add-in can show "in Glados" without
querying Glados themselves. `Glados.Ids` (every non-deleted Glados row of
the family, so a viewer in PDM can see every revision Glados knows about),
`Glados.NewestRevisionSyncState` (the outcome of the newest write) and
`Glados.NewestRevisionSyncedAt` (when). Glados never transitions a PDM
file's workflow state; write-back is strictly limited to these three
variables.

`PdmWriteBack.after_outcome` is called once per touched file, right after
the ingest transaction that produced `outcome` has already committed; see
PollPdmVault._ingest_one/_record_private_state_skip and
RefreshPdmFile._finish_ingested/_finish_private_state_skip. It is a no-op
unless `writeback_enabled` is set AND the file is linked (`outcome.item_id`
is not None; an unlinked/never-ingested file has nothing to write an id
list for). Every PDM error (missing/non-version-free variable, transport
failure, non-2xx response) is caught here and recorded as a `writeback_error`
run entry; nothing ever propagates out of this method, so a write-back
failure can never fail the ingest it follows or abort a poll run.

Returns the run-entry action it recorded (`"writeback"` or
`"writeback_error"`), or None when write-back was skipped entirely
(disabled, or the file is not linked); the pollers use this to tally
"N written back" into their own in-memory run summary, since
IPdmSyncRunRepository.add_entries only flushes rows, it does not hand them
back for counting.
"""

import json

from src.modules.catalogue.domain.policies.item_field_ownership import WRITEBACK_MAPPABLE_FIELDS
from src.modules.catalogue.ports.outbound.cad_item_store_port import IBoughtItemCadStore
from src.modules.catalogue.ports.outbound.cad_item_store_port import IMadeItemCadStore
from src.modules.external_data.application.dto.pdm_dto import IngestOutcome
from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.external_data.application.services.pdm_variables import NO_FILE_LEVEL_CONFIGURATION
from src.modules.external_data.application.services.pdm_vault import sync_run_entry
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRun
from src.modules.external_data.domain.errors import PdmApiError
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.external_data.ports.outbound.pdm_gateway_port import IPdmGateway
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmDataCard
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmDataCardConfiguration
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmDataCardVariable
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmObjectInfo
from src.modules.external_data.ports.outbound.repositories.pdm_sync_run_repository import (
    IPdmSyncRunRepository,
)
from src.modules.platform.infrastructure.logging.logger import log
from src.shared_kernel.domain.services.clock import now_utc

# Outcomes that represent a genuine write onto the item this run: the newest
# revision's sync state reads "synced" for these, "conflict: <message>" /
# "skipped: <message>" (the outcome's own reason) for everything else.
_SYNCED_ACTIONS = frozenset({"created", "revised", "updated", "claimed", "status"})

_WRITEBACK_ACTION = "writeback"
_WRITEBACK_ERROR_ACTION = "writeback_error"

# Enough of a PDM error body to carry its reason without flooding the run log.
_MAX_ERROR_BODY_CHARS = 300


def _describe_pdm_error(step: str, exc: PdmApiError) -> str:
    """The run entry message for a refused Web API call: which step failed
    and PDM's own reason, which for a refused write usually names the
    missing permission or the lock that blocked it."""
    body = " ".join(exc.body.split())[:_MAX_ERROR_BODY_CHARS]
    return f"{step} failed: {exc}" + (f" PDM said: {body}" if body else "")


def _resolve_sync_state(outcome: IngestOutcome) -> str:
    if outcome.action in _SYNCED_ACTIONS:
        return "synced"
    if outcome.action == "conflict":
        return f"conflict: {outcome.message}"
    return f"skipped: {outcome.message}"


def _select_configuration(card: PdmDataCard) -> PdmDataCardConfiguration | None:
    """Same "@"-only selection as pdm_variables.select_configuration,
    applied to the richer PdmDataCard shape: the "@" file-level
    configuration every SolidWorks file always carries, never a fallback
    to whichever configuration the card happened to return first. None
    whenever no "@" configuration is present, whether the card carries no
    configuration at all or only differently-named ones."""
    for configuration in card.configurations:
        if configuration.name == "@":
            return configuration
    return None


def _find_variable(
    configuration: PdmDataCardConfiguration, variable_name: str
) -> PdmDataCardVariable | None:
    return next((v for v in configuration.variables if v.name == variable_name), None)


class PdmWriteBack:
    def __init__(
        self,
        session: PdmSessionService,
        settings_repo: IExternalDataSettingsRepository,
        made_repo: IMadeItemCadStore,
        bought_repo: IBoughtItemCadStore,
        run_repo: IPdmSyncRunRepository,
    ) -> None:
        self._session = session
        self._settings = settings_repo
        self._made_items = made_repo
        self._bought_items = bought_repo
        self._runs = run_repo

    async def after_outcome(
        self,
        vault_id: str,
        file: PdmObjectInfo,
        kind: str,
        outcome: IngestOutcome,
        run: PdmSyncRun,
    ) -> str | None:
        if outcome.item_id is None:
            return None
        settings = await self._settings.get_pdm()
        if not settings.writeback_enabled:
            return None

        variable_map = (
            settings.made_item_variable_map if kind == "made" else settings.bought_item_variable_map
        )
        variable_names = {
            field: (variable_map.get(field) or "").strip() for field in WRITEBACK_MAPPABLE_FIELDS
        }
        new_values = {
            "glados_ids": await self._build_glados_ids(vault_id, file.id, kind),
            "newest_revision_sync_state": _resolve_sync_state(outcome),
            "newest_revision_synced_at": now_utc().isoformat(),
        }

        try:
            return await self._write(
                vault_id, file, kind, outcome.item_id, variable_names, new_values, run
            )
        except Exception as exc:
            log.warning("PDM write-back %s/%s failed: %s", vault_id, file.id, exc)
            await self._record(
                run, vault_id, file, kind, outcome.item_id, _WRITEBACK_ERROR_ACTION, str(exc)
            )
            return _WRITEBACK_ERROR_ACTION

    # ── mechanics ────────────────────────────────────────────────────

    async def _write(
        self,
        vault_id: str,
        file: PdmObjectInfo,
        kind: str,
        item_id: int,
        variable_names: dict[str, str],
        new_values: dict[str, str],
        run: PdmSyncRun,
    ) -> str:
        async def fetch_card(gw: IPdmGateway, token: str) -> PdmDataCard:
            return await gw.get_datacard(token, file.id, file.version, file.parent_folder_id)

        try:
            card = await self._session.call(fetch_card)
        except PdmApiError as exc:
            reason = _describe_pdm_error("reading the data card", exc)
            log.warning("PDM write-back %s/%s: %s", vault_id, file.id, reason)
            await self._record(run, vault_id, file, kind, item_id, _WRITEBACK_ERROR_ACTION, reason)
            return _WRITEBACK_ERROR_ACTION

        configuration = _select_configuration(card)
        if configuration is None:
            await self._record(
                run,
                vault_id,
                file,
                kind,
                item_id,
                _WRITEBACK_ERROR_ACTION,
                NO_FILE_LEVEL_CONFIGURATION,
            )
            return _WRITEBACK_ERROR_ACTION

        missing: list[str] = []
        variables_by_field: dict[str, PdmDataCardVariable] = {}
        for field, variable_name in variable_names.items():
            variable = _find_variable(configuration, variable_name) if variable_name else None
            if variable is None or not variable.version_free:
                missing.append(variable_name or f"<{field} unmapped>")
            else:
                variables_by_field[field] = variable
        if missing:
            reason = (
                f"variable(s) missing or not version-free on the datacard: {', '.join(missing)}"
            )
            await self._record(run, vault_id, file, kind, item_id, _WRITEBACK_ERROR_ACTION, reason)
            return _WRITEBACK_ERROR_ACTION

        values = {variable_names[field]: new_values[field] for field in variable_names}
        write_all = any(
            variables_by_field[field].var_id in card.variables_with_write_all_configs
            for field in variable_names
        )
        target_configurations = list(card.configurations) if write_all else [configuration]

        for target in target_configurations:

            async def set_variables(
                gw: IPdmGateway, token: str, target: PdmDataCardConfiguration = target
            ) -> bool:
                return await gw.set_datacard_variables(
                    token, file.id, file.parent_folder_id, target.id, card, values
                )

            try:
                await self._session.call(set_variables)
            except PdmApiError as exc:
                reason = _describe_pdm_error(
                    f"writing configuration {target.name or target.id!r} of the data card", exc
                )
                log.warning("PDM write-back %s/%s: %s", vault_id, file.id, reason)
                await self._record(
                    run, vault_id, file, kind, item_id, _WRITEBACK_ERROR_ACTION, reason
                )
                return _WRITEBACK_ERROR_ACTION

        message = (
            f"wrote back {len(values)} variable(s) to {len(target_configurations)} "
            "configuration(s)."
        )
        await self._record(run, vault_id, file, kind, item_id, _WRITEBACK_ACTION, message)
        return _WRITEBACK_ACTION

    async def _build_glados_ids(self, vault_id: str, file_id: int, kind: str) -> str:
        """Single-line JSON array of {"revision", "public_id", "pdm_version"}
        for every non-deleted Glados row of the family. Made: every
        revision (get_family_by_pdm_file, newest first); bought: the one
        linked row, `revision` always null (bought items are not
        revisioned)."""
        if kind == "made":
            family = await self._made_items.get_family_by_pdm_file(vault_id, file_id)
            entries = [
                {
                    "revision": item.revision,
                    "public_id": str(item.public_id),
                    "pdm_version": item.pdm_file_version,
                }
                for item in family
            ]
        else:
            bought = await self._bought_items.get_by_pdm_file(vault_id, file_id)
            entries = (
                [
                    {
                        "revision": None,
                        "public_id": str(bought.public_id),
                        "pdm_version": bought.pdm_file_version,
                    }
                ]
                if bought is not None
                else []
            )
        return json.dumps(entries)

    async def _record(
        self,
        run: PdmSyncRun,
        vault_id: str,
        file: PdmObjectInfo,
        kind: str,
        item_id: int,
        action: str,
        message: str,
    ) -> None:
        await self._runs.add_entries(
            run.id,
            [sync_run_entry(run.id, vault_id, file, kind, action, item_id, message)],
        )
