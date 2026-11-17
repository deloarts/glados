"""PDM-wide pure helpers: whether the integration is enabled, and
private-state detection shared by the poller, refresh and validation.
"""

from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmObjectInfo


def is_pdm_enabled(settings: AdminPdmSettings) -> bool:
    """True when switched on and configured; a vault without a connection
    ingests nothing, so it must not reserve a number space."""
    return settings.enabled and settings.is_configured


def is_private_state(obj: PdmObjectInfo) -> bool:
    """True for a file added but never checked in. Such a file has an
    empty state name but a non-zero state id, so only the name is a
    reliable signal. Its variables answer 403, so callers skip them."""
    return obj.state == ""
