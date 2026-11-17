"""
Whether time tracking is available, which the read tier's capabilities route
reports so every client knows whether to offer it.
"""

from src.modules.operations.application.services.time_tracking_service import (
    is_time_tracking_available,
)

__all__ = ["is_time_tracking_available"]
