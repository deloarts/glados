"""
Domain entity for the outbound webhook notification settings singleton.
"""

from dataclasses import dataclass

from src.shared_kernel.domain.entities.base import Entity


@dataclass
class AdminNotificationSettings(Entity):
    """Settings shared by every outbound webhook subscription."""

    # Per-delivery HTTP timeout, read on every dispatch so a change applies
    # without a restart. The event worker's retry count is a separate constant.
    webhook_timeout_seconds: int
