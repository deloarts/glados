"""
Maps the PDM settings entity to its result DTO. The password is replaced
with a presence flag and the cached session token with its session state.
"""

from src.modules.catalogue.domain.policies.item_field_ownership import item_fields
from src.modules.external_data.application.dto.admin_settings_dto.pdm import AdminPdmSettingsResult
from src.modules.external_data.application.dto.admin_settings_dto.pdm import (
    ItemFieldOwnershipResult,
)
from src.modules.external_data.application.dto.admin_settings_dto.pdm import ItemFieldsResult
from src.modules.external_data.application.dto.admin_settings_dto.pdm import PdmSessionResult
from src.modules.external_data.application.dto.admin_settings_dto.pdm import PdmWatchedFolderResult
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.services.pdm_required_fields import LOCKED_REQUIRED_FIELDS
from src.modules.external_data.domain.services.pdm_required_fields import REQUIRED_FIELD_RULES


class PdmSettingsMapper:
    @staticmethod
    def pdm_to_result(
        e: AdminPdmSettings,
        *,
        mutating_operations_enabled: bool,
        snapshot_counts: dict[str, int] | None = None,
    ) -> AdminPdmSettingsResult:
        """`snapshot_counts` is only ever populated by GetPdmSettings, which
        alone has the snapshot repository wired in; UpdatePdmSettings and
        the combined AllAdminSettingsResponse call this without it and get
        {}; neither response is the PDM tab's own status read, so a stale
        or absent count there costs nothing.

        `mutating_operations_enabled` is the deployment's
        PDM__ALLOW_MUTATING_OPERATIONS, which no admin can change, passed
        in by every caller so the console shows what the server allows."""
        fields = item_fields()
        return AdminPdmSettingsResult(
            id=e.id,
            public_id=e.public_id,
            made_item_variable_map=e.made_item_variable_map,
            bought_item_variable_map=e.bought_item_variable_map,
            item_fields=ItemFieldsResult(
                made=[
                    ItemFieldOwnershipResult(
                        field=f.field,
                        owner=f.owner,
                        mappable=f.mappable,
                        policy_applicable=f.policy_applicable,
                        label_of=f.label_of,
                    )
                    for f in fields["made"]
                ],
                bought=[
                    ItemFieldOwnershipResult(
                        field=f.field,
                        owner=f.owner,
                        mappable=f.mappable,
                        policy_applicable=f.policy_applicable,
                        label_of=f.label_of,
                    )
                    for f in fields["bought"]
                ],
            ),
            enabled=e.enabled,
            mutating_operations_enabled=mutating_operations_enabled,
            base_url=e.base_url,
            vault_name=e.vault_name,
            username=e.username,
            password_configured=e.password is not None and e.password != "",
            verify_certificate=e.verify_certificate,
            timeout_seconds=e.timeout_seconds,
            configured=e.is_configured,
            session=PdmSessionResult(
                active=e.session_token is not None,
                obtained_at=e.session_obtained_at,
                user_id=e.session_user_id,
            ),
            watched_folders=[
                PdmWatchedFolderResult(
                    path=f.path,
                    kind=f.kind,
                    recursive=f.recursive,
                    enabled=f.enabled,
                    match_by=f.match_by,
                    filename_pattern=f.filename_pattern,
                    folder_id=f.folder_id,
                )
                for f in e.watched_folders
            ],
            made_released_state_ids=list(e.made_released_state_ids),
            made_obsolete_state_ids=list(e.made_obsolete_state_ids),
            made_replaced_state_ids=list(e.made_replaced_state_ids),
            bought_released_state_ids=list(e.bought_released_state_ids),
            bought_obsolete_state_ids=list(e.bought_obsolete_state_ids),
            bought_replaced_state_ids=list(e.bought_replaced_state_ids),
            document_released_state_ids=list(e.document_released_state_ids),
            poll_interval_minutes=e.poll_interval_minutes,
            cold_folder_max_multiplier=e.cold_folder_max_multiplier,
            ingest_concurrency=e.ingest_concurrency,
            vault_id=e.vault_id,
            cad_items_read_only=e.cad_items_read_only,
            addin_language=e.addin_language,
            last_poll_at=e.last_poll_at,
            last_poll_error=e.last_poll_error,
            last_poll_summary=e.last_poll_summary,
            writeback_enabled=e.writeback_enabled,
            made_item_extensions=list(e.made_item_extensions),
            bought_item_extensions=list(e.bought_item_extensions),
            document_categories=dict(e.document_categories),
            document_excluded_kinds={
                ext: list(kinds) for ext, kinds in e.document_excluded_kinds.items()
            },
            thumbnails_enabled=e.thumbnails_enabled,
            stuck_after_days=e.stuck_after_days,
            snapshot_counts=dict(snapshot_counts) if snapshot_counts is not None else {},
            required_fields={
                "made": list(e.required_fields.get("made", [])),
                "bought": list(e.required_fields.get("bought", [])),
            },
            locked_required_fields={
                kind: list(fields) for kind, fields in LOCKED_REQUIRED_FIELDS.items()
            },
            required_field_rules={
                kind: [rule.name for rule in rules] for kind, rules in REQUIRED_FIELD_RULES.items()
            },
            set_approver_from_pdm=e.set_approver_from_pdm,
            made_feature_tree_template=e.made_feature_tree_template,
            bought_feature_tree_template=e.bought_feature_tree_template,
        )
