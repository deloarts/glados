"""
Domain entity for the maintenance mode settings singleton.
"""

from dataclasses import dataclass
from dataclasses import field

from src.shared_kernel.domain.entities.base import Entity


@dataclass
class AdminMaintenanceSettings(Entity):
    """Maintenance mode, when enabled all non-admin API requests return 503."""

    enabled: bool
    message: str | None
    allowed_ips: list[str] = field(default_factory=list)  # IPs that bypass the block
