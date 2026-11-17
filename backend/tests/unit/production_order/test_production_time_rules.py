"""
Unit tests for src/modules/fulfillment/domain/services/production_time_rules.py's pure
net_work_minutes function.
"""

from datetime import UTC
from datetime import datetime

from src.modules.fulfillment.domain.entities.production_order_interruption import (
    ProductionOrderInterruption,
)
from src.modules.fulfillment.domain.services.production_time_rules import net_work_minutes


def _interruption(paused_at: datetime, resumed_at: datetime | None) -> ProductionOrderInterruption:
    return ProductionOrderInterruption(
        id=1,
        production_order_id=1,
        paused_at=paused_at,
        resumed_at=resumed_at,
        paused_by_id=1,
        resumed_by_id=1 if resumed_at else None,
        created=paused_at,
    )


class TestNetWorkMinutes:
    def test_none_when_actual_start_missing(self):
        assert net_work_minutes(None, datetime(2026, 1, 1, tzinfo=UTC), []) is None

    def test_none_when_actual_end_missing(self):
        assert net_work_minutes(datetime(2026, 1, 1, tzinfo=UTC), None, []) is None

    def test_none_when_both_missing(self):
        assert net_work_minutes(None, None, []) is None

    def test_no_interruptions_returns_full_elapsed_minutes(self):
        start = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
        end = datetime(2026, 1, 1, 9, 30, tzinfo=UTC)
        assert net_work_minutes(start, end, []) == 90

    def test_one_closed_interruption_is_subtracted(self):
        start = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
        end = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
        interruption = _interruption(
            datetime(2026, 1, 1, 8, 30, tzinfo=UTC), datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
        )
        # 120 elapsed - 30 paused = 90
        assert net_work_minutes(start, end, [interruption]) == 90

    def test_several_closed_interruptions_all_subtracted(self):
        start = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
        end = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        first = _interruption(
            datetime(2026, 1, 1, 8, 30, tzinfo=UTC), datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
        )
        second = _interruption(
            datetime(2026, 1, 1, 10, 0, tzinfo=UTC), datetime(2026, 1, 1, 10, 15, tzinfo=UTC)
        )
        # 240 elapsed - 30 - 15 = 195
        assert net_work_minutes(start, end, [first, second]) == 195

    def test_open_interruption_is_ignored_rather_than_guessed_at(self):
        start = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
        end = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
        open_interruption = _interruption(datetime(2026, 1, 1, 8, 30, tzinfo=UTC), None)
        assert net_work_minutes(start, end, [open_interruption]) == 60

    def test_clamped_at_zero_never_negative(self):
        start = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
        end = datetime(2026, 1, 1, 8, 10, tzinfo=UTC)
        # Pathological input: interruption duration exceeds the elapsed
        # window entirely.
        interruption = _interruption(
            datetime(2026, 1, 1, 8, 0, tzinfo=UTC), datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
        )
        assert net_work_minutes(start, end, [interruption]) == 0
