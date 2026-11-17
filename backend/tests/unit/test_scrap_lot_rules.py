"""
Direct characterization tests for the scrap-during-production additions to
lot_rules.py and lot_status.py: the terminal `scrapped` status, which the
lot derivation keeps once the lot quantity reaches zero
(lifecycle/test_derive_lot.py), and the scrap_capacity/assert_scrap_allowed
guards scrap_production_pieces.py relies on.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.errors import LotNotScrappableError
from src.modules.fulfillment.domain.errors import ScrapQuantityExceedsAvailableError
from src.modules.fulfillment.domain.services.lifecycle.intents import LOT_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import LotContext
from src.modules.fulfillment.domain.services.lot_rules import assert_scrap_allowed
from src.modules.fulfillment.domain.services.lot_rules import scrap_capacity
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface
from tests.factories import make_user


def _make_lot(status: LotStatus = LotStatus.IN_PROGRESS, quantity: float = 5.0) -> ProductionLot:
    return ProductionLot(
        id=1,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=None,
        changes=[],
        lot_number="LOT-1",
        quantity=quantity,
        status=status,
        priority=UrgencyClass.NORMAL,
        note=None,
        creator_id=1,
        made_item_id=1,
        project_id=1,
        input_demand_id=None,
    )


def _make_position(
    lot_id: int = 1,
    sequence: int = 1,
    kind: LotPositionKind = LotPositionKind.INTERNAL,
    quantity: float = 5.0,
    quantity_completed: float = 0.0,
) -> LotPosition:
    return LotPosition(
        id=1,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=None,
        changes=[],
        sequence=sequence,
        kind=kind,
        status=LotPositionStatus.IN_PROGRESS,
        quantity=quantity,
        quantity_completed=quantity_completed,
        note=None,
        creator_id=1,
        lot_id=lot_id,
    )


# ── LotStatus.SCRAPPED is terminal ──────────────────────────────────────


class TestScrappedIsTerminalTransition:
    def test_a_scrapped_lot_takes_no_action(self):
        """No action of the lot intent table starts from SCRAPPED, even for a
        manager of lots, so nothing moves a scrapped lot anywhere."""
        manager = User(
            id=9,
            username="manager",
            full_name="Manager",
            email="manager@example.com",
            created=datetime(2026, 1, 1, tzinfo=UTC),
            hashed_password="x",
            is_active=True,
            is_systemuser=False,
            permissions=[Permission.MANAGE_LOTS],
            language=Language.enGB,
            date_format=DateFormat.ISO,
            start_page=StartPage.DASHBOARD,
            theme_preset=ThemePreset.Aura,
            theme_surface=ThemeSurface.glados,
            theme_primary=ThemePrimary.glados,
            theme_dark_mode=False,
            button_flat_style=False,
            table_gridlines=False,
            table_striped_rows=False,
        )
        lot = _make_lot(status=LotStatus.SCRAPPED, quantity=0.0)
        assert LOT_INTENTS.allowed_actions(lot, LotContext(produced=0.0), manager) == ()


# ── scrap_capacity / assert_scrap_allowed ───────────────────────────────


class TestScrapCapacity:
    def test_capacity_is_available_minus_completed(self):
        lot = _make_lot(quantity=5.0)
        position = _make_position(quantity=5.0, quantity_completed=2.0)
        lot.positions = [position]
        assert scrap_capacity(lot, position) == pytest.approx(3.0)

    def test_capacity_respects_raw_material_arrived_on_first_position(self):
        lot = _make_lot(quantity=10.0)
        position = _make_position(sequence=1, quantity=10.0, quantity_completed=0.0)
        lot.positions = [position]
        # Only 3 pieces of raw material have arrived so far, even though
        # the lot's own ordered quantity is 10. Capacity must be bounded
        # by what's physically present, not by the lot's full quantity.
        assert scrap_capacity(lot, position, raw_material_arrived=3.0) == pytest.approx(3.0)


_ACTOR = make_user()


class TestAssertScrapAllowed:
    @pytest.mark.parametrize(
        "status",
        [LotStatus.COMPLETED, LotStatus.CANCELED, LotStatus.SCRAPPED],
    )
    def test_terminal_lot_rejected(self, status: LotStatus):
        lot = _make_lot(status=status)
        position = _make_position()
        lot.positions = [position]
        with pytest.raises(LotNotScrappableError):
            assert_scrap_allowed(lot, position, 1.0, _ACTOR)

    def test_external_position_rejected(self):
        lot = _make_lot()
        position = _make_position(kind=LotPositionKind.EXTERNAL)
        lot.positions = [position]
        with pytest.raises(LotNotScrappableError):
            assert_scrap_allowed(lot, position, 1.0, _ACTOR)

    def test_quantity_within_capacity_is_allowed(self):
        lot = _make_lot(quantity=5.0)
        position = _make_position(quantity=5.0, quantity_completed=1.0)
        lot.positions = [position]
        assert_scrap_allowed(lot, position, 4.0, _ACTOR)  # exactly at capacity, no raise

    def test_quantity_exceeding_capacity_rejected(self):
        lot = _make_lot(quantity=5.0)
        position = _make_position(quantity=5.0, quantity_completed=1.0)
        lot.positions = [position]
        with pytest.raises(ScrapQuantityExceedsAvailableError):
            assert_scrap_allowed(lot, position, 5.0, _ACTOR)
