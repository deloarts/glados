"""
Domain entity for the host settings singleton.
"""

from dataclasses import dataclass

from src.shared_kernel.domain.entities.base import Entity


@dataclass
class AdminHostSettings(Entity):
    """Host-level settings.

    Empty on purpose: contact and legal details are organisation-wide and
    live in AdminGeneralSettings. The table is the home for future host-scoped
    settings; the Host tab shows live machine stats, which are not stored.
    """
