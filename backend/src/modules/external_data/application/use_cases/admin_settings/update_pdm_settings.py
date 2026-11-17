"""Updates the PDM settings: variable maps, connection, watched folders,
workflow states and poller options (see docs/reference/pdm-settings.md).

Shape and range checks are request validators; this use case enforces the
rules that need the stored settings: disjoint state lists per kind,
enabling only with a connection, an enabled folder and a released state,
an identical `kind` variable in both maps (only the made map is read), and
with write-back on, the three write-back variables mapped identically in
both maps, because one datacard is written whatever the kind. A change to
the sync scope marks snapshots outside every watched folder missing and
requeues the remaining skipped ones. `reconcile_requested_deep` is
never accepted, so a PUT cannot clobber a queued reconciliation.
"""

from src.modules.catalogue.domain.policies.item_field_ownership import WRITEBACK_MAPPABLE_FIELDS
from src.modules.catalogue.domain.policies.item_field_ownership import item_fields
from src.modules.catalogue.domain.value_objects.pdm_sync_state import PdmSyncState
from src.modules.catalogue.ports.outbound.cad_item_store_port import IBoughtItemCadStore
from src.modules.catalogue.ports.outbound.cad_item_store_port import IMadeItemCadStore
from src.modules.external_data.application.dto.admin_settings_dto.pdm import AdminPdmSettingsResult
from src.modules.external_data.application.dto.admin_settings_dto.pdm import (
    UpdatePdmSettingsCommand,
)
from src.modules.external_data.application.mappers.admin_settings_mapper.pdm import (
    PdmSettingsMapper,
)
from src.modules.external_data.application.services.pdm_item_link import set_item_pdm_sync_state
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.external_data.domain.errors import PdmSettingsInvalidError
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.domain.value_objects.pdm_watched_folder import PdmWatchedFolder
from src.modules.external_data.domain.value_objects.pdm_watched_folder import match_watched_folder
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.external_data.ports.outbound.repositories.pdm_file_snapshot_repository import (
    IPdmFileSnapshotRepository,
)
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def _validate_variable_map(
    *,
    kind: str,
    variable_map: dict[str, str],
    allowed_fields: set[str],
    require_every_field: bool,
) -> None:
    """Only known mappable fields, unique variable names among mapped
    entries, and part_number plus revision whenever anything else is
    mapped, since ingest needs an identity. A map the request sends must
    name every mappable field, with "" for an unmapped one, so the stored
    map is always complete."""
    unknown = sorted(set(variable_map) - allowed_fields)
    if unknown:
        raise PdmSettingsInvalidError(f"Unknown {kind} field(s) in variable map: {unknown}.")

    non_empty_values = [v for v in variable_map.values() if v]
    if len(non_empty_values) != len(set(non_empty_values)):
        duplicates = sorted({v for v in non_empty_values if non_empty_values.count(v) > 1})
        raise PdmSettingsInvalidError(
            f"Duplicate variable name(s) in {kind} variable map: {duplicates}."
        )

    other_fields_mapped = any(
        value
        for field, value in variable_map.items()
        if field not in ("part_number", "revision", "kind")
    )
    identity_mapped = variable_map.get("part_number") and variable_map.get("revision")
    if other_fields_mapped and not identity_mapped:
        raise PdmSettingsInvalidError(
            f"{kind} variable map: part_number and revision must both be mapped "
            "whenever any other field is mapped."
        )

    missing = sorted(allowed_fields - set(variable_map))
    if require_every_field and missing:
        raise PdmSettingsInvalidError(f"Missing {kind} field(s) in variable map: {missing}.")


class UpdatePdmSettings:
    def __init__(
        self,
        repo: IExternalDataSettingsRepository,
        snapshot_repo: IPdmFileSnapshotRepository | None = None,
        *,
        uow: IUnitOfWork,
        made_item_repo: IMadeItemCadStore | None = None,
        bought_item_repo: IBoughtItemCadStore | None = None,
        mutating_operations_enabled: bool = False,
    ) -> None:
        self._uow = uow
        self._mutating_operations_enabled = mutating_operations_enabled
        self._repo = repo
        self._snapshots = snapshot_repo
        self._made_items = made_item_repo
        self._bought_items = bought_item_repo

    async def execute(self, actor: User, cmd: UpdatePdmSettingsCommand) -> AdminPdmSettingsResult:
        SettingsRules.assert_can_write(actor)

        current = await self._repo.get_pdm()
        fields = item_fields()
        made_allowed = {f.field for f in fields["made"] if f.mappable}
        bought_allowed = {f.field for f in fields["bought"] if f.mappable}

        made_item_variable_map = (
            dict(cmd.made_item_variable_map)
            if cmd.made_item_variable_map is not None
            else dict(current.made_item_variable_map)
        )
        bought_item_variable_map = (
            dict(cmd.bought_item_variable_map)
            if cmd.bought_item_variable_map is not None
            else dict(current.bought_item_variable_map)
        )
        _validate_variable_map(
            kind="made item",
            variable_map=made_item_variable_map,
            allowed_fields=made_allowed,
            require_every_field=cmd.made_item_variable_map is not None,
        )
        _validate_variable_map(
            kind="bought item",
            variable_map=bought_item_variable_map,
            allowed_fields=bought_allowed,
            require_every_field=cmd.bought_item_variable_map is not None,
        )
        self._assert_kind_variable_agrees(made_item_variable_map, bought_item_variable_map)

        settings = self._build_settings(
            cmd, current, made_item_variable_map, bought_item_variable_map
        )
        settings.required_fields = settings.normalized_required_fields()
        settings.document_excluded_kinds = settings.normalized_document_excluded_kinds()
        if settings.connection_differs(current):
            # A token from the old connection is useless; the session
            # service authenticates again on its next call.
            settings.session_token = None
            settings.session_user_id = None
            settings.session_obtained_at = None

        settings.assert_state_id_lists_disjoint()
        settings.assert_feature_tree_templates_valid()
        self._assert_writeback_config_valid(
            settings, made_item_variable_map, bought_item_variable_map
        )
        self._assert_enabled_config_valid(settings)

        saved = await self._repo.save_pdm(settings)

        summary = f"PDM settings updated by {actor.username}."
        if self._snapshots is not None and saved.vault_id and saved.sync_scope_differs(current):
            # Out-of-scope rows are marked missing first, so the requeue
            # below only reaches files a future poll will actually walk.
            out_of_scope = await self._mark_out_of_scope_missing(
                self._snapshots, saved.vault_id, saved.watched_folders
            )
            requeued = await self._snapshots.reset_skipped_to_pending(saved.vault_id)
            effects = [f"{requeued} skipped files queued for re-evaluation"]
            if out_of_scope:
                effects.append(f"{out_of_scope} files outside every watched folder marked missing")
            summary = f"PDM settings updated by {actor.username}, {', '.join(effects)}."

        await self._repo.append_audit(
            AdminSettingsAuditEntry.by_actor(
                actor,
                settings_domain="pdm",
                summary=summary,
            )
        )
        await self._uow.commit()

        log.info("Updated PDM settings.")
        return PdmSettingsMapper.pdm_to_result(
            saved, mutating_operations_enabled=self._mutating_operations_enabled
        )

    async def _mark_out_of_scope_missing(
        self,
        snapshots: IPdmFileSnapshotRepository,
        vault_id: str,
        folders: list[PdmWatchedFolder],
    ) -> int:
        """Marks every snapshot whose stored path no longer falls under an
        enabled watched folder as missing, and its made or bought item too,
        the same outcome the trigger path gives a file that moved outside
        every watched folder. The poller never walks such a file again, so
        without this it would keep whatever state it had forever. A stale
        stored path heals on the next poll, which treats a missing file it
        finds again as changed. Returns the number of rows marked."""
        marked: list[PdmFileSnapshot] = []
        for snapshot in await snapshots.get_all_for_vault(vault_id):
            if snapshot.sync_state == PdmFileSyncState.MISSING.value:
                continue
            if match_watched_folder(folders, snapshot.path) is not None:
                continue
            snapshot.sync_state = PdmFileSyncState.MISSING
            snapshot.last_error = "file is no longer under a watched folder"
            marked.append(snapshot)
            if snapshot.item_id is not None and snapshot.kind in ("made", "bought"):
                # A document snapshot does not own the item it names.
                await self._set_item_missing(snapshot.kind, snapshot.item_id)
        if marked:
            await snapshots.upsert_many(marked)
            log.info(
                "PDM settings: %d snapshots outside every watched folder marked missing.",
                len(marked),
            )
        return len(marked)

    async def _set_item_missing(self, kind: str, item_id: int) -> None:
        if self._made_items is None or self._bought_items is None:
            return
        await set_item_pdm_sync_state(
            self._made_items, self._bought_items, kind, item_id, PdmSyncState.MISSING
        )

    @staticmethod
    def _assert_kind_variable_agrees(
        made_item_variable_map: dict[str, str], bought_item_variable_map: dict[str, str]
    ) -> None:
        made_kind_variable = (made_item_variable_map.get("kind") or "").strip()
        bought_kind_variable = (bought_item_variable_map.get("kind") or "").strip()
        if (made_kind_variable or bought_kind_variable) and (
            not made_kind_variable
            or not bought_kind_variable
            or made_kind_variable != bought_kind_variable
        ):
            raise PdmSettingsInvalidError(
                "made and bought variable maps must name the same, non-empty variable for "
                f"kind whenever either is set: {made_kind_variable!r} vs "
                f"{bought_kind_variable!r}."
            )

    @staticmethod
    def _build_settings(
        cmd: UpdatePdmSettingsCommand,
        current: AdminPdmSettings,
        made_item_variable_map: dict[str, str],
        bought_item_variable_map: dict[str, str],
    ) -> AdminPdmSettings:
        """Merges the command onto `current`; None keeps the stored value."""
        return AdminPdmSettings(
            id=1,
            made_item_variable_map=made_item_variable_map,
            bought_item_variable_map=bought_item_variable_map,
            enabled=cmd.enabled if cmd.enabled is not None else current.enabled,
            base_url=cmd.base_url if cmd.base_url is not None else current.base_url,
            vault_name=(
                cmd.vault_name.strip() if cmd.vault_name is not None else current.vault_name
            ),
            username=(cmd.username.strip() if cmd.username is not None else current.username),
            password=cmd.password if cmd.password is not None else current.password,
            verify_certificate=(
                cmd.verify_certificate
                if cmd.verify_certificate is not None
                else current.verify_certificate
            ),
            timeout_seconds=(
                cmd.timeout_seconds if cmd.timeout_seconds is not None else current.timeout_seconds
            ),
            session_token=current.session_token,
            session_user_id=current.session_user_id,
            session_obtained_at=current.session_obtained_at,
            watched_folders=(
                [
                    PdmWatchedFolder(
                        path=f.path,
                        kind=f.kind,
                        recursive=f.recursive,
                        enabled=f.enabled,
                        match_by=f.match_by,
                        filename_pattern=f.filename_pattern,
                        folder_id=f.folder_id,
                    )
                    for f in cmd.watched_folders
                ]
                if cmd.watched_folders is not None
                else current.watched_folders
            ),
            made_released_state_ids=(
                list(cmd.made_released_state_ids)
                if cmd.made_released_state_ids is not None
                else current.made_released_state_ids
            ),
            made_obsolete_state_ids=(
                list(cmd.made_obsolete_state_ids)
                if cmd.made_obsolete_state_ids is not None
                else current.made_obsolete_state_ids
            ),
            made_replaced_state_ids=(
                list(cmd.made_replaced_state_ids)
                if cmd.made_replaced_state_ids is not None
                else current.made_replaced_state_ids
            ),
            bought_released_state_ids=(
                list(cmd.bought_released_state_ids)
                if cmd.bought_released_state_ids is not None
                else current.bought_released_state_ids
            ),
            bought_obsolete_state_ids=(
                list(cmd.bought_obsolete_state_ids)
                if cmd.bought_obsolete_state_ids is not None
                else current.bought_obsolete_state_ids
            ),
            bought_replaced_state_ids=(
                list(cmd.bought_replaced_state_ids)
                if cmd.bought_replaced_state_ids is not None
                else current.bought_replaced_state_ids
            ),
            poll_interval_minutes=(
                cmd.poll_interval_minutes
                if cmd.poll_interval_minutes is not None
                else current.poll_interval_minutes
            ),
            cold_folder_max_multiplier=(
                cmd.cold_folder_max_multiplier
                if cmd.cold_folder_max_multiplier is not None
                else current.cold_folder_max_multiplier
            ),
            ingest_concurrency=(
                cmd.ingest_concurrency
                if cmd.ingest_concurrency is not None
                else current.ingest_concurrency
            ),
            document_released_state_ids=(
                list(cmd.document_released_state_ids)
                if cmd.document_released_state_ids is not None
                else current.document_released_state_ids
            ),
            vault_id=current.vault_id,
            cad_items_read_only=(
                cmd.cad_items_read_only
                if cmd.cad_items_read_only is not None
                else current.cad_items_read_only
            ),
            addin_language=(
                cmd.addin_language if cmd.addin_language is not None else current.addin_language
            ),
            last_poll_at=current.last_poll_at,
            last_poll_error=current.last_poll_error,
            last_poll_summary=current.last_poll_summary,
            writeback_enabled=(
                cmd.writeback_enabled
                if cmd.writeback_enabled is not None
                else current.writeback_enabled
            ),
            made_item_extensions=(
                list(cmd.made_item_extensions)
                if cmd.made_item_extensions is not None
                else current.made_item_extensions
            ),
            bought_item_extensions=(
                list(cmd.bought_item_extensions)
                if cmd.bought_item_extensions is not None
                else current.bought_item_extensions
            ),
            document_categories=(
                dict(cmd.document_categories)
                if cmd.document_categories is not None
                else current.document_categories
            ),
            document_excluded_kinds=(
                dict(cmd.document_excluded_kinds)
                if cmd.document_excluded_kinds is not None
                else current.document_excluded_kinds
            ),
            thumbnails_enabled=(
                cmd.thumbnails_enabled
                if cmd.thumbnails_enabled is not None
                else current.thumbnails_enabled
            ),
            stuck_after_days=(
                cmd.stuck_after_days
                if cmd.stuck_after_days is not None
                else current.stuck_after_days
            ),
            reconcile_requested_deep=current.reconcile_requested_deep,
            required_fields=(
                {
                    "made": list(cmd.required_fields.get("made", [])),
                    "bought": list(cmd.required_fields.get("bought", [])),
                }
                if cmd.required_fields is not None
                else dict(current.required_fields)
            ),
            set_approver_from_pdm=(
                cmd.set_approver_from_pdm
                if cmd.set_approver_from_pdm is not None
                else current.set_approver_from_pdm
            ),
            made_feature_tree_template=(
                cmd.made_feature_tree_template
                if cmd.made_feature_tree_template is not None
                else current.made_feature_tree_template
            ),
            bought_feature_tree_template=(
                cmd.bought_feature_tree_template
                if cmd.bought_feature_tree_template is not None
                else current.bought_feature_tree_template
            ),
        )

    @staticmethod
    def _assert_writeback_config_valid(
        settings: AdminPdmSettings,
        made_item_variable_map: dict[str, str],
        bought_item_variable_map: dict[str, str],
    ) -> None:
        if not settings.writeback_enabled:
            return
        for field in WRITEBACK_MAPPABLE_FIELDS:
            made_variable = (made_item_variable_map.get(field) or "").strip()
            bought_variable = (bought_item_variable_map.get(field) or "").strip()
            if not made_variable or not bought_variable or made_variable != bought_variable:
                raise PdmSettingsInvalidError(
                    f"writeback_enabled requires {field!r} to be mapped to the same, "
                    f"non-empty variable in both maps: {made_variable!r} vs "
                    f"{bought_variable!r}."
                )

    @staticmethod
    def _assert_enabled_config_valid(settings: AdminPdmSettings) -> None:
        if not settings.enabled:
            return
        if not settings.is_configured:
            raise PdmSettingsInvalidError(
                "enabled requires a fully configured PDM connection "
                "(base_url, vault_name, username and password)."
            )
        if not any(f.enabled for f in settings.watched_folders):
            raise PdmSettingsInvalidError("enabled requires at least one enabled watched folder.")
        if not (settings.made_released_state_ids or settings.bought_released_state_ids):
            raise PdmSettingsInvalidError(
                "enabled requires at least one released state (made or bought)."
            )
        has_documents_folder = any(
            f.enabled and f.kind == "documents" for f in settings.watched_folders
        )
        if has_documents_folder and not settings.document_released_state_ids:
            raise PdmSettingsInvalidError(
                "an enabled documents folder requires at least one released state for "
                "exported documents."
            )
