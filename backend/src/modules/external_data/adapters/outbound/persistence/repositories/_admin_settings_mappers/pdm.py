"""
Row mapping for the admin_pdm_settings singleton. Converts the ORM row to
the domain entity and the entity to the column dict
SqlAlchemyAdminSettingsRepository upserts.
"""

from typing import Any

from src.modules.external_data.adapters.outbound.persistence.models.admin_settings_model.pdm import (
    AdminPdmSettingsOrmModel,
)
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.value_objects.pdm_watched_folder import PdmWatchedFolder
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware


def _opt_str(value: bool | str | None) -> str | None:
    """A watched_folder JSON entry's `match_by`/`filename_pattern`: None
    stays None and anything else is a str in practice, since the bool half
    of the JSON column's declared value type only ever shows up for
    `recursive`/`enabled`, never these two fields."""
    return None if value is None else str(value)


def to_entity(o: AdminPdmSettingsOrmModel) -> AdminPdmSettings:
    return AdminPdmSettings(
        id=o.id,
        public_id=o.public_id,
        made_item_variable_map=dict(o.made_item_variable_map),
        bought_item_variable_map=dict(o.bought_item_variable_map),
        enabled=o.enabled,
        base_url=o.base_url,
        vault_name=o.vault_name,
        username=o.username,
        password=o.password,
        verify_certificate=o.verify_certificate,
        timeout_seconds=o.timeout_seconds,
        session_token=o.session_token,
        session_user_id=o.session_user_id,
        session_obtained_at=utc_aware(o.session_obtained_at),
        watched_folders=[
            PdmWatchedFolder(
                path=str(f["path"]),
                kind=str(f["kind"]),
                recursive=bool(f["recursive"]),
                enabled=bool(f["enabled"]),
                match_by=_opt_str(f["match_by"]),
                filename_pattern=_opt_str(f["filename_pattern"]),
                folder_id=(int(f["folder_id"]) if f["folder_id"] is not None else None),
            )
            for f in (o.watched_folders or [])
        ],
        made_released_state_ids=[int(i) for i in (o.made_released_state_ids or [])],
        made_obsolete_state_ids=[int(i) for i in (o.made_obsolete_state_ids or [])],
        made_replaced_state_ids=[int(i) for i in (o.made_replaced_state_ids or [])],
        bought_released_state_ids=[int(i) for i in (o.bought_released_state_ids or [])],
        bought_obsolete_state_ids=[int(i) for i in (o.bought_obsolete_state_ids or [])],
        bought_replaced_state_ids=[int(i) for i in (o.bought_replaced_state_ids or [])],
        document_released_state_ids=[int(i) for i in (o.document_released_state_ids or [])],
        poll_interval_minutes=o.poll_interval_minutes,
        cold_folder_max_multiplier=o.cold_folder_max_multiplier,
        ingest_concurrency=o.ingest_concurrency,
        vault_id=o.vault_id,
        cad_items_read_only=o.cad_items_read_only,
        addin_language=o.addin_language,
        last_poll_at=o.last_poll_at,
        last_poll_error=o.last_poll_error,
        last_poll_summary=o.last_poll_summary,
        writeback_enabled=o.writeback_enabled,
        made_item_extensions=list(o.made_item_extensions or []),
        bought_item_extensions=list(o.bought_item_extensions or []),
        document_categories=dict(o.document_categories or {}),
        document_excluded_kinds={
            ext: [str(k) for k in kinds] for ext, kinds in (o.document_excluded_kinds or {}).items()
        },
        thumbnails_enabled=o.thumbnails_enabled,
        stuck_after_days=o.stuck_after_days,
        reconcile_requested_deep=o.reconcile_requested_deep,
        required_fields={
            "made": list(o.required_fields["made"]),
            "bought": list(o.required_fields["bought"]),
        },
        set_approver_from_pdm=o.set_approver_from_pdm,
        made_feature_tree_template=o.made_feature_tree_template,
        bought_feature_tree_template=o.bought_feature_tree_template,
    )


def to_dict(s: AdminPdmSettings) -> dict[str, Any]:
    return {
        "made_item_variable_map": dict(s.made_item_variable_map),
        "bought_item_variable_map": dict(s.bought_item_variable_map),
        "enabled": s.enabled,
        "base_url": s.base_url,
        "vault_name": s.vault_name,
        "username": s.username,
        "password": s.password,
        "verify_certificate": s.verify_certificate,
        "timeout_seconds": s.timeout_seconds,
        "session_token": s.session_token,
        "session_user_id": s.session_user_id,
        "session_obtained_at": s.session_obtained_at,
        "watched_folders": [
            {
                "path": f.path,
                "kind": f.kind,
                "recursive": f.recursive,
                "enabled": f.enabled,
                "match_by": f.match_by,
                "filename_pattern": f.filename_pattern,
                "folder_id": f.folder_id,
            }
            for f in s.watched_folders
        ],
        "made_released_state_ids": list(s.made_released_state_ids),
        "made_obsolete_state_ids": list(s.made_obsolete_state_ids),
        "made_replaced_state_ids": list(s.made_replaced_state_ids),
        "bought_released_state_ids": list(s.bought_released_state_ids),
        "bought_obsolete_state_ids": list(s.bought_obsolete_state_ids),
        "bought_replaced_state_ids": list(s.bought_replaced_state_ids),
        "document_released_state_ids": list(s.document_released_state_ids),
        "poll_interval_minutes": s.poll_interval_minutes,
        "cold_folder_max_multiplier": s.cold_folder_max_multiplier,
        "ingest_concurrency": s.ingest_concurrency,
        "vault_id": s.vault_id,
        "cad_items_read_only": s.cad_items_read_only,
        "addin_language": s.addin_language,
        "last_poll_at": s.last_poll_at,
        "last_poll_error": s.last_poll_error,
        "last_poll_summary": s.last_poll_summary,
        "writeback_enabled": s.writeback_enabled,
        "made_item_extensions": list(s.made_item_extensions),
        "bought_item_extensions": list(s.bought_item_extensions),
        "document_categories": dict(s.document_categories),
        "document_excluded_kinds": {
            ext: list(kinds) for ext, kinds in s.document_excluded_kinds.items()
        },
        "thumbnails_enabled": s.thumbnails_enabled,
        "stuck_after_days": s.stuck_after_days,
        "required_fields": {
            "made": list(s.required_fields.get("made", [])),
            "bought": list(s.required_fields.get("bought", [])),
        },
        "set_approver_from_pdm": s.set_approver_from_pdm,
        "made_feature_tree_template": s.made_feature_tree_template,
        "bought_feature_tree_template": s.bought_feature_tree_template,
    }
