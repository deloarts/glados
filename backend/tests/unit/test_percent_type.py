"""
A stored percentage is NUMERIC(7, 3) in the database and a float in
Python, rounded to three decimals on the way in. The delivery tolerances
use it, and their web request fields round to the same three decimals so a
use case compares what reads back.
"""

from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects import sqlite

from src.modules.catalogue.adapters.inbound.api.schemas.admin_settings_schema.orders import (
    UpdateOrderSettingsRequest,
)
from src.modules.catalogue.adapters.inbound.api.schemas.delivery_tolerance_schema import (
    DeliveryToleranceFields,
)
from src.modules.catalogue.adapters.outbound.persistence.models.admin_settings_model.orders import (
    AdminOrderSettingsOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
    BoughtItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.source_item_model import (
    SourceItemOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.percent_type import PercentType


def test_a_percentage_is_rounded_to_three_decimals_on_the_way_in() -> None:
    column = PercentType()

    for dialect in (sqlite.dialect(), postgresql.dialect()):
        assert column.process_bind_param(12.34567, dialect) == 12.346
        assert column.process_bind_param(100 / 3, dialect) == 33.333
        assert column.process_bind_param(None, dialect) is None


def test_a_stored_percentage_reads_back_as_a_float() -> None:
    column = PercentType()

    assert column.process_result_value(5, sqlite.dialect()) == 5.0
    assert isinstance(column.process_result_value(5, sqlite.dialect()), float)
    assert column.process_result_value(None, postgresql.dialect()) is None


def test_every_delivery_tolerance_column_is_a_percentage() -> None:
    for model in (AdminOrderSettingsOrmModel, BoughtItemOrmModel, SourceItemOrmModel):
        for name in ("over_delivery_tolerance_percent", "under_delivery_tolerance_percent"):
            assert isinstance(model.__table__.c[name].type, PercentType), (model, name)


def test_the_tolerance_requests_round_to_the_stored_decimals() -> None:
    fields = DeliveryToleranceFields(
        over_delivery_tolerance_percent=12.34567, under_delivery_tolerance_percent=None
    )
    assert fields.over_delivery_tolerance_percent == 12.346
    assert fields.under_delivery_tolerance_percent is None

    settings = UpdateOrderSettingsRequest(under_delivery_tolerance_percent=2.0004)
    assert settings.under_delivery_tolerance_percent == 2.0
    assert settings.over_delivery_tolerance_percent is None
