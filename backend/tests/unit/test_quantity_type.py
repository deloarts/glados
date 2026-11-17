"""
A piece quantity, and the items_per_unit factor that converts one, is
stored as NUMERIC(18, 6) and read back as a float, rounded to six decimals
on the way in, so a value with binary noise is stored as the decimal it
stands for.
"""

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects import sqlite

from src.modules.fulfillment.adapters.inbound.api.schemas.made_item_demand_schema import (
    MadeItemDemandUpdateRequest,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_demand_item_model import (
    BoughtItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_demand_item_model import (
    MadeItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_demand_item_model import (
    SourceItemDemandItemOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.quantity_type import QuantityType


def test_a_quantity_is_rounded_to_six_decimals_on_the_way_in() -> None:
    column = QuantityType()

    for dialect in (sqlite.dialect(), postgresql.dialect()):
        assert column.process_bind_param(0.1 + 0.2, dialect) == 0.3
        assert column.process_bind_param(1 / 3, dialect) == 0.333333
        assert column.process_bind_param(None, dialect) is None


def test_a_stored_quantity_reads_back_as_a_float() -> None:
    column = QuantityType()

    assert column.process_result_value(4, sqlite.dialect()) == 4.0
    assert isinstance(column.process_result_value(4, sqlite.dialect()), float)
    assert column.process_result_value(None, postgresql.dialect()) is None


def test_every_items_per_unit_factor_is_a_quantity() -> None:
    for model in (
        BoughtItemDemandItemOrmModel,
        MadeItemDemandItemOrmModel,
        OrderItemOrmModel,
        SourceItemDemandItemOrmModel,
    ):
        assert isinstance(model.__table__.c["items_per_unit"].type, QuantityType), model


def test_a_factor_that_would_store_as_nothing_is_refused() -> None:
    assert MadeItemDemandUpdateRequest(
        quantity=2, unit="PCS", items_per_unit=1 / 3
    ).items_per_unit == (0.333333)
    with pytest.raises(ValidationError, match="count as nothing"):
        MadeItemDemandUpdateRequest(quantity=2, unit="PCS", items_per_unit=1e-7)
