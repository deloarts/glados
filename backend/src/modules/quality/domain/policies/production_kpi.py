"""
The production KPI rules other readers apply to the rows they show, so a lot
counts as late on an infoscreen exactly when the late lots KPI counts it.
"""

from src.modules.quality.domain.services.kpi_rules import is_lot_late

__all__ = ["is_lot_late"]
