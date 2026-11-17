"""
Every quantity a request body or form carries must be a finite number. JSON
as FastAPI parses it accepts NaN, Infinity and overflowing literals such as
1e999, and pydantic's float accepts them unless `allow_inf_nan=False`;
`gt=0` and `ge=0` refuse NaN but let infinity through. This walks every
`*Request` model of the schema package and fails on a quantity field whose
validator still accepts a non-finite float, so a new field cannot slip in
without the flag.
"""

import importlib
import inspect
import json
from collections.abc import Iterator
from typing import Any

import pytest
from pydantic import BaseModel
from pydantic import ValidationError

from src.modules.fulfillment.adapters.inbound.api.schemas.allocation_schema import (
    AllocationCreateRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.made_item_demand_schema import (
    MadeItemDemandCreateRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    LotCreateRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_order_schema import (
    SplitProductionOrderRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.source_item_demand_schema import (
    SourceItemDemandCreateRequest,
)
from tests.layer_packages import layer_module_names


def _request_models() -> list[type[BaseModel]]:
    found: dict[str, type[BaseModel]] = {}
    for module_name in layer_module_names("adapters/inbound/api/schemas"):
        module = importlib.import_module(module_name)
        for name, value in inspect.getmembers(module, inspect.isclass):
            if (
                name.endswith("Request")
                and issubclass(value, BaseModel)
                and value.__module__ == module.__name__
            ):
                found[f"{value.__module__}.{name}"] = value
    return [found[key] for key in sorted(found)]


def _is_quantity(field_name: str) -> bool:
    return "quantit" in field_name or field_name == "items_per_unit"


def _float_nodes(schema: Any) -> Iterator[dict[str, Any]]:
    """Every float validator inside a core schema node, through optionals,
    lists, defaults and wrappers."""
    if isinstance(schema, dict):
        if schema.get("type") == "float":
            yield schema
        for value in schema.values():
            yield from _float_nodes(value)
    elif isinstance(schema, list):
        for value in schema:
            yield from _float_nodes(value)


def _model_fields_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """The `model-fields` node of a model's core schema."""
    while schema.get("type") != "model-fields":
        schema = schema["schema"]
    return schema


def _quantity_fields() -> list[tuple[str, dict[str, Any]]]:
    fields = []
    for model in _request_models():
        core = _model_fields_schema(dict(model.__pydantic_core_schema__))
        for name, field in core["fields"].items():
            if _is_quantity(name) and any(True for _ in _float_nodes(field)):
                fields.append((f"{model.__name__}.{name}", field))
    return fields


QUANTITY_FIELDS = _quantity_fields()


def test_the_walk_finds_the_quantity_fields_of_every_family() -> None:
    """Guards the walk itself: an empty or tiny result would pass vacuously."""
    names = {name for name, _ in QUANTITY_FIELDS}
    assert len(names) >= 40
    for expected in (
        "AllocationCreateRequest.quantity",
        "DemandItemCreateRequest.items_per_unit",
        "MadeItemDemandUpdateRequest.quantity",
        "SourceItemAllocationCreateRequest.quantity",
        "LotCreateRequest.quantity",
        "RecordProductionOrderCompletionRequest.quantity_scrap",
        "SplitProductionOrderRequest.quantities",
        "OrderItemCreateRequest.quantity",
        "CorrectDeliveryRequest.quantity",
    ):
        assert expected in names, expected


@pytest.mark.parametrize(
    "field", [field for _, field in QUANTITY_FIELDS], ids=[name for name, _ in QUANTITY_FIELDS]
)
def test_every_request_quantity_refuses_nan_and_infinity(field: dict[str, Any]) -> None:
    for node in _float_nodes(field):
        assert node.get("allow_inf_nan") is False


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (AllocationCreateRequest, '{"demand_item_id": 1, "order_item_id": 1, "quantity": %s}'),
        (
            MadeItemDemandCreateRequest,
            '{"made_item_id": 1, "project_id": 1, "quantity": %s, "unit": "pcs"}',
        ),
        (SourceItemDemandCreateRequest, '{"lot_id": 1, "quantity": %s}'),
        (LotCreateRequest, '{"made_item_id": 1, "project_id": 1, "quantity": %s}'),
        (SplitProductionOrderRequest, '{"quantities": [1, %s]}'),
    ],
)
@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity", "1e999"])
def test_a_non_finite_quantity_in_a_json_body_is_refused(
    model: type[BaseModel], payload: str, literal: str
) -> None:
    # The finite payload is valid, so the refusal below is the literal's.
    model.model_validate(json.loads(payload % "2"))
    with pytest.raises(ValidationError):
        model.model_validate(json.loads(payload % literal))
