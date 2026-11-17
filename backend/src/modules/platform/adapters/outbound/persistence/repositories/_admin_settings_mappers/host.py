"""
Row mapping for the admin_host_settings singleton. Converts the ORM row to the
domain entity and the entity to the column dict
SqlAlchemyAdminSettingsRepository upserts.
"""

from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.host import (
    AdminHostSettingsOrmModel,
)
from src.modules.platform.domain.entities.admin_settings.host import AdminHostSettings


def to_entity(o: AdminHostSettingsOrmModel) -> AdminHostSettings:
    return AdminHostSettings(id=o.id, public_id=o.public_id)
