"""
Every planning exception names the catalogue item and the project it is
about in separate fields, so the list can show the item's picture and open
it, and keeps the joined label for readers that want one string.
"""

from types import SimpleNamespace

from src.modules.fulfillment.application.use_cases.production_lot.get_planning_exceptions import (
    _lot_subject,
)
from src.modules.fulfillment.application.use_cases.production_lot.get_planning_exceptions import (
    _source_subject,
)
from tests.unit.production_order._helpers import make_lot


def _source_demand(**item: object) -> SimpleNamespace:
    fields: dict[str, object] = {"source_item": None, "bought_item": None, **item}
    return SimpleNamespace(project_id=7, project_number="P-100", project_customer="Acme", **fields)


def test_a_lot_row_names_its_made_item_and_project() -> None:
    lot = make_lot()
    lot.made_item_id = 42
    lot.made_item_part_number = "100-200"
    lot.made_item_revision = "B"
    lot.made_item_article_name = "Bracket"
    lot.project_number = "P-100"
    lot.project_customer = "Acme"

    fields = _lot_subject(lot).fields()

    assert fields == {
        "item_kind": "made",
        "item_id": 42,
        "item_number": "100-200",
        "item_revision": "B",
        "item_name": "Bracket",
        "item_label": "100-200 Bracket",
        "project_id": 1,
        "project_number": "P-100",
        "project_customer": "Acme",
    }


def test_a_raw_material_demand_names_its_dimension_and_material() -> None:
    demand = _source_demand(
        source_item=SimpleNamespace(id=5, dimension="20x20x2", material="S235JR")
    )

    subject = _source_subject(demand)  # type: ignore[arg-type]

    assert (subject.item_kind, subject.item_id) == ("source", 5)
    assert (subject.item_number, subject.item_name) == ("20x20x2", "S235JR")
    assert subject.fields()["item_label"] == "20x20x2 S235JR"


def test_a_raw_material_demand_on_a_bought_item_names_the_bought_item() -> None:
    demand = _source_demand(
        bought_item=SimpleNamespace(id=9, order_code_1="RS-1234", article_name="Rod")
    )

    subject = _source_subject(demand)  # type: ignore[arg-type]

    assert (subject.item_kind, subject.item_id) == ("bought", 9)
    assert (subject.item_number, subject.item_name) == ("RS-1234", "Rod")
    assert subject.project_customer == "Acme"
