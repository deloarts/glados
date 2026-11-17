"""
Row mapping for the admin_edp_settings singleton.
"""

from typing import Any

from src.modules.external_data.adapters.outbound.persistence.models.admin_settings_model.eplan_data_portal import (
    AdminEdpSettingsOrmModel,
)
from src.modules.external_data.domain.entities.admin_settings.eplan_data_portal import (
    AdminEdpSettings,
)


def to_entity(o: AdminEdpSettingsOrmModel) -> AdminEdpSettings:
    ids = o.default_article_group_ids if isinstance(o.default_article_group_ids, list) else []
    return AdminEdpSettings(
        id=o.id,
        public_id=o.public_id,
        enabled=o.enabled,
        base_url=o.base_url,
        pat=o.pat or None,
        default_article_group_ids=[i for i in ids if isinstance(i, int)],
        language=o.language,
    )


def to_dict(s: AdminEdpSettings) -> dict[str, Any]:
    return {
        "enabled": s.enabled,
        "base_url": s.base_url,
        "pat": s.pat,
        "default_article_group_ids": list(s.default_article_group_ids),
        "language": s.language,
    }


def disabled_defaults() -> AdminEdpSettings:
    """What a database without the row reads as: switched off."""
    return AdminEdpSettings(id=1)
