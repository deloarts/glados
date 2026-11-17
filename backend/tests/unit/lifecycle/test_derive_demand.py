"""Table tests for the demand status derivation of the bought, made and
source families (src/modules/fulfillment/domain/services/lifecycle/demand.py): coverage and
placement per allocation, one or more cases per row, then every fact
combination of a small domain against a transcription of the target table."""

import pytest

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.domain.services.lifecycle.demand import BOUGHT_DEMAND_STATUS
from src.modules.fulfillment.domain.services.lifecycle.demand import MADE_DEMAND_STATUS
from src.modules.fulfillment.domain.services.lifecycle.demand import SOURCE_DEMAND_STATUS
from src.modules.fulfillment.domain.services.lifecycle.demand import covered_pieces
from src.modules.fulfillment.domain.services.lifecycle.demand import demand_coverage
from src.modules.fulfillment.domain.services.lifecycle.demand import is_placed
from src.modules.fulfillment.domain.services.lifecycle.facts import AllocationFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import CoveringLineFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import CoveringLotFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import DemandFacts
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from tests.unit.lifecycle.small_domains import T0
from tests.unit.lifecycle.small_domains import demand_facts

EPS = 1e-6

FAMILIES = [
    (BOUGHT_DEMAND_STATUS.derive, BoughtItemDemandStatus),
    (MADE_DEMAND_STATUS.derive, MadeItemDemandStatus),
    (SOURCE_DEMAND_STATUS.derive, SourceItemDemandStatus),
]
FAMILY_IDS = ["bought", "made", "source"]


def _line(
    status: OrderItemStatus, quantity: float = 10.0, delivered: float = 0.0, lost: float = 0.0
) -> CoveringLineFacts:
    return CoveringLineFacts(status=status, quantity=quantity, delivered=delivered, lost=lost)


def _lot(status: LotStatus, quantity: float = 10.0, completed: float = 0.0) -> CoveringLotFacts:
    return CoveringLotFacts(status=status, quantity=quantity, quantity_completed=completed)


def _demand(
    *allocations: AllocationFacts,
    quantity: float = 10.0,
    canceled_at=None,
    fulfilled_manually_at=None,
) -> DemandFacts:
    return DemandFacts(
        quantity=quantity,
        allocations=allocations,
        canceled_at=canceled_at,
        fulfilled_manually_at=fulfilled_manually_at,
    )


on_line = AllocationFacts.on_line
on_lot = AllocationFacts.on_lot
stock = AllocationFacts.stock


# ── Coverage and placement of one allocation ────────────────────────────


@pytest.mark.parametrize(
    ("allocation", "pieces"),
    [
        (stock(4.0), 0.0),
        (on_line(4.0, _line(OrderItemStatus.ORDERED, delivered=5.0)), 4.0),
        (on_line(4.0, _line(OrderItemStatus.ORDERED, delivered=3.0)), 3.0),
        # Lost pieces never arrived.
        (on_line(4.0, _line(OrderItemStatus.PARTIALLY_DELIVERED, delivered=3.0, lost=2.0)), 3.0),
        (on_line(4.0, _line(OrderItemStatus.DELIVERED, delivered=12.0)), 4.0),
        (on_line(4.0, _line(OrderItemStatus.CANCELED, delivered=5.0)), 0.0),
        (on_line(4.0, _line(OrderItemStatus.ORDERED, quantity=0.0)), 0.0),
        # Arrived pieces fill the allocations ahead first.
        (on_line(4.0, _line(OrderItemStatus.ORDERED, delivered=5.0), ahead=3.0), 2.0),
        (on_line(4.0, _line(OrderItemStatus.ORDERED, delivered=5.0), ahead=6.0), 0.0),
        (on_lot(4.0, _lot(LotStatus.IN_PROGRESS, completed=2.5)), 2.5),
        (on_lot(4.0, _lot(LotStatus.IN_PROGRESS, completed=2.5), ahead=2.0), 0.5),
        (on_lot(4.0, _lot(LotStatus.CANCELED, completed=5.0)), 0.0),
        (on_lot(4.0, _lot(LotStatus.SCRAPPED, quantity=0.0)), 0.0),
        (AllocationFacts(quantity=4.0, from_stock=False, line=None, lot=None), 0.0),
    ],
)
def test_covered_pieces_of_one_allocation(allocation, pieces):
    assert covered_pieces(allocation) == pieces


@pytest.mark.parametrize(
    ("allocation", "placed"),
    [
        (stock(4.0), False),
        (on_line(4.0, _line(OrderItemStatus.PENDING)), False),
        (on_line(4.0, _line(OrderItemStatus.REQUESTED)), False),
        (on_line(4.0, _line(OrderItemStatus.ORDERED)), True),
        (on_line(4.0, _line(OrderItemStatus.PARTIALLY_DELIVERED)), True),
        (on_line(4.0, _line(OrderItemStatus.DELIVERED)), True),
        (on_line(4.0, _line(OrderItemStatus.CANCELED)), False),
        (on_lot(4.0, _lot(LotStatus.DRAFT)), False),
        (on_lot(4.0, _lot(LotStatus.PARTIALLY_PLANNED)), True),
        (on_lot(4.0, _lot(LotStatus.ON_HOLD)), True),
        (on_lot(4.0, _lot(LotStatus.COMPLETED)), True),
        (on_lot(4.0, _lot(LotStatus.SCRAPPED, quantity=0.0)), False),
        (on_lot(4.0, _lot(LotStatus.CANCELED)), False),
        (AllocationFacts(quantity=4.0, from_stock=False, line=None, lot=None), False),
    ],
)
def test_is_placed_for_one_allocation(allocation, placed):
    assert is_placed(allocation) is placed


def test_demand_coverage_totals():
    coverage = demand_coverage(
        _demand(
            stock(2.0),
            on_line(4.0, _line(OrderItemStatus.ORDERED, delivered=5.0)),
            on_lot(3.0, _lot(LotStatus.DRAFT)),
        )
    )
    assert coverage.stock == 2.0
    assert coverage.allocated == 7.0
    assert coverage.delivered == 4.0
    assert coverage.all_placed is False


# ── Rows, for each family ───────────────────────────────────────────────

ROW_CASES = [
    (_demand(stock(10.0), canceled_at=T0, fulfilled_manually_at=T0), "canceled", 1),
    (
        _demand(on_line(4.0, _line(OrderItemStatus.ORDERED)), fulfilled_manually_at=T0),
        "fulfilled",
        2,
    ),
    (_demand(stock(10.0)), "fulfilled", 3),
    (_demand(stock(4.0), stock(6.0)), "fulfilled", 3),
    (_demand(on_line(10.0, _line(OrderItemStatus.DELIVERED, delivered=10.0))), "fulfilled", 3),
    (
        _demand(
            on_line(1.0, _line(OrderItemStatus.DELIVERED, quantity=1.0, delivered=0.7 + 0.2 + 0.1)),
            quantity=1.0,
        ),
        "fulfilled",
        3,
    ),
    # Pieces lost at receipt never arrived, so they fulfil nothing.
    (_demand(on_line(10.0, _line(OrderItemStatus.DELIVERED, lost=10.0))), "ordered", 4),
    (_demand(on_lot(10.0, _lot(LotStatus.COMPLETED, completed=10.0))), "fulfilled", 3),
    (
        _demand(on_line(6.0, _line(OrderItemStatus.DELIVERED, 6.0, delivered=6.0)), stock(4.0)),
        "fulfilled",
        3,
    ),
    (_demand(on_line(10.0, _line(OrderItemStatus.ORDERED))), "ordered", 4),
    (
        _demand(
            on_line(6.0, _line(OrderItemStatus.PARTIALLY_DELIVERED, delivered=2.0)), stock(4.0)
        ),
        "ordered",
        4,
    ),
    (_demand(on_lot(10.0, _lot(LotStatus.PLANNED))), "ordered", 4),
    (_demand(on_lot(10.0, _lot(LotStatus.ON_HOLD))), "ordered", 4),
    (_demand(on_line(5.0, _line(OrderItemStatus.ORDERED))), "allocated", 5),
    (
        _demand(
            on_line(5.0, _line(OrderItemStatus.ORDERED)),
            on_line(5.0, _line(OrderItemStatus.PENDING)),
        ),
        "allocated",
        5,
    ),
    (_demand(on_lot(10.0, _lot(LotStatus.DRAFT))), "allocated", 5),
    (_demand(on_lot(10.0, _lot(LotStatus.CANCELED))), "allocated", 5),
    (_demand(stock(4.0)), "allocated", 5),
    (_demand(), "open", 6),
    (_demand(stock(1e-7)), "open", 6),
]


@pytest.mark.parametrize(("derive", "enum"), FAMILIES, ids=FAMILY_IDS)
@pytest.mark.parametrize(("facts", "value", "row"), ROW_CASES)
def test_derive_demand_status_rows(derive, enum, facts, value, row):
    derivation = derive(facts)
    assert type(derivation.value) is enum
    assert (derivation.value, derivation.rule) == (enum(value), row)


@pytest.mark.parametrize(("derive", "enum"), FAMILIES, ids=FAMILY_IDS)
def test_stock_alone_fulfils_an_open_demand_in_one_step(derive, enum):
    assert derive(_demand(stock(10.0))).value == enum.FULFILLED


@pytest.mark.parametrize(("derive", "enum"), FAMILIES, ids=FAMILY_IDS)
def test_partial_cover_with_a_placed_line_stays_allocated(derive, enum):
    assert derive(_demand(on_line(4.0, _line(OrderItemStatus.ORDERED)))).value == enum.ALLOCATED


@pytest.mark.parametrize(("derive", "enum"), FAMILIES, ids=FAMILY_IDS)
def test_a_scrapped_lot_is_not_placed(derive, enum):
    scrapped = _lot(LotStatus.SCRAPPED, quantity=0.0)
    assert is_placed(on_lot(10.0, scrapped)) is False
    derivation = derive(_demand(on_lot(10.0, scrapped)))
    assert (derivation.value, derivation.rule) == (enum.ALLOCATED, 5)


@pytest.mark.parametrize(("derive", "enum"), FAMILIES, ids=FAMILY_IDS)
def test_an_allocation_of_zero_quantity_does_not_block_ordered(derive, enum):
    # A full scrap leaves the lot's allocations at zero; they cover nothing
    # and must not keep a demand covered elsewhere from ORDERED.
    left_by_scrap = on_lot(0.0, _lot(LotStatus.SCRAPPED, quantity=0.0))
    unplaced_and_empty = on_line(0.0, _line(OrderItemStatus.PENDING))
    facts = _demand(
        on_line(10.0, _line(OrderItemStatus.ORDERED)), left_by_scrap, unplaced_and_empty
    )
    derivation = derive(facts)
    assert (derivation.value, derivation.rule) == (enum.ORDERED, 4)


def test_the_three_family_tables_share_their_rows():
    shapes = [
        [(row.number, row.condition, row.result) for row in table.rows]
        for table in (BOUGHT_DEMAND_STATUS, MADE_DEMAND_STATUS, SOURCE_DEMAND_STATUS)
    ]
    assert shapes[0] == shapes[1] == shapes[2]


# ── Every small case against the transcribed table ──────────────────────


def _transcribed(f: DemandFacts) -> tuple[str, int]:
    """The target table, written out independently of the module."""
    allocated = stock_total = delivered = 0.0
    every_placed = True
    for a in f.allocations:
        if a.from_stock:
            stock_total += a.quantity
            continue
        allocated += a.quantity
        if a.line is not None:
            line = a.line
            arrived = line.delivered if line.status != OrderItemStatus.CANCELED else 0.0
            placed = line.status in (
                OrderItemStatus.ORDERED,
                OrderItemStatus.PARTIALLY_DELIVERED,
                OrderItemStatus.DELIVERED,
            )
        elif a.lot is not None:
            lot = a.lot
            arrived = lot.quantity_completed if lot.status != LotStatus.CANCELED else 0.0
            placed = lot.status not in (LotStatus.DRAFT, LotStatus.CANCELED, LotStatus.SCRAPPED)
        else:
            arrived, placed = 0.0, False
        delivered += min(max(arrived - a.ahead, 0.0), a.quantity)
        if abs(a.quantity) > EPS:
            every_placed = every_placed and placed
    if f.canceled_at is not None:
        return "canceled", 1
    if f.fulfilled_manually_at is not None:
        return "fulfilled", 2
    if delivered + stock_total >= f.quantity - EPS:
        return "fulfilled", 3
    if allocated + stock_total >= f.quantity - EPS and every_placed:
        return "ordered", 4
    if allocated + stock_total > EPS:
        return "allocated", 5
    return "open", 6


@pytest.mark.parametrize(("derive", "enum"), FAMILIES, ids=FAMILY_IDS)
def test_derive_demand_status_matches_the_table_on_every_small_case(derive, enum):
    reached = set()
    for facts in demand_facts():
        derivation = derive(facts)
        value, row = _transcribed(facts)
        assert (derivation.value, derivation.rule) == (enum(value), row), facts
        reached.add(derivation.rule)
    assert reached == set(range(1, 7))
