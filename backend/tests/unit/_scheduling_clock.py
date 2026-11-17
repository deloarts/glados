"""
Pins the clock the scheduling use cases read, for a test whose orders are
dated at fixed days. The walk never plans a queued order before now, so a
fixture dated in the past needs a clock that stands before its dates.
"""

from datetime import datetime
from typing import Any

from src.modules.fulfillment.application.services import scheduling_context
from src.modules.fulfillment.application.use_cases.production_schedule import auto_plan
from src.modules.fulfillment.application.use_cases.production_schedule import get_schedule_board
from src.modules.fulfillment.application.use_cases.production_schedule import (
    recompute_machine_schedule,
)

_MODULES = (auto_plan, recompute_machine_schedule, get_schedule_board, scheduling_context)


def pin_scheduling_clock(monkeypatch: Any, at: datetime) -> None:
    """Makes every scheduling read of now answer `at`."""
    for module in _MODULES:
        monkeypatch.setattr(module, "now_utc", lambda: at)
