"""
Domain entity for the data retention settings singleton.
"""

from dataclasses import dataclass

from src.shared_kernel.domain.entities.base import Entity


@dataclass
class AdminRetentionSettings(Entity):
    """Data retention policies for automated cleanup jobs."""

    log_retention_days: int  # 0 = keep forever
    audit_retention_days: int  # 0 = keep forever
    soft_delete_cleanup_days: int  # 0 = never auto-purge soft-deleted rows
    # Meetings that started longer ago are purged with their files.
    meeting_retention_days: int = 0  # 0 = keep meetings forever
