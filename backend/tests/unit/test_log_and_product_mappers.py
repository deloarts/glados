"""
Coverage for two entity->DTO mappers: log_mapper.py and
product_mapper.py's optional-relation branches (the `if entity.customer`
/ `if entity.creator` conditionals, exercised both set and unset).
"""

from datetime import UTC
from datetime import date
from datetime import datetime

from src.modules.catalogue.domain.entities.customer import Customer
from src.modules.catalogue.domain.value_objects.customer_level import CustomerLevel
from src.modules.platform.application.mappers.log_mapper import LogMapper
from src.modules.platform.domain.entities.log_entry import LogEntry
from src.modules.workspace.application.mappers.product_mapper import ProductMapper
from src.modules.workspace.domain.entities.product import Product
from tests.factories import make_user

# ── Helpers ───────────────────────────────────────────────────────────


def make_customer(id: int = 5) -> Customer:
    return Customer(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        archived=False,
        name="ACME",
        legal_name="ACME Ltd",
        vat_id="ATU123",
        level=CustomerLevel.A,
        street=None,
        city=None,
        country="AT",
        postal_code=None,
        email=None,
        phone=None,
        weblink=None,
        creator_id=1,
    )


# ── LogMapper ─────────────────────────────────────────────────────────


class TestLogMapper:
    def test_maps_an_http_log_entry_field_for_field(self):
        ts = datetime(2026, 8, 3, 12, 30, tzinfo=UTC)
        entry = LogEntry(
            id=1,
            timestamp=ts,
            user_id=7,
            username="tester",
            level="HTTP",
            message=None,
            method="GET",
            path="/api/v1/web/users",
            status_code=200,
            request_id="req-abc",
        )

        result = LogMapper.to_result(entry)

        assert result.id == 1
        assert result.timestamp == ts
        assert result.user_id == 7
        assert result.username == "tester"
        assert result.level == "HTTP"
        assert result.message is None
        assert result.method == "GET"
        assert result.path == "/api/v1/web/users"
        assert result.status_code == 200
        assert result.request_id == "req-abc"

    def test_maps_an_application_log_entry_with_null_http_fields(self):
        entry = LogEntry(
            id=2,
            timestamp=datetime(2026, 8, 3, tzinfo=UTC),
            user_id=None,
            username=None,
            level="ERROR",
            message="something broke",
            method=None,
            path=None,
            status_code=None,
            request_id=None,
        )

        result = LogMapper.to_result(entry)

        assert result.level == "ERROR"
        assert result.message == "something broke"
        assert result.method is None
        assert result.path is None
        assert result.status_code is None
        assert result.user_id is None


# ── ProductMapper ─────────────────────────────────────────────────────


class TestProductMapper:
    def test_maps_core_fields(self):
        created = datetime(2026, 1, 1, tzinfo=UTC)
        product = Product(
            id=3,
            created=created,
            product_number="P-042",
            description="a widget",
            is_active=True,
            designated_user_id=7,
            creator_id=1,
        )

        result = ProductMapper.to_result(product)

        assert result.id == 3
        assert result.product_number == "P-042"
        assert result.description == "a widget"
        assert result.is_active is True
        assert result.designated_user_id == 7
        assert result.created == created
        assert result.archived is False
        assert result.creator_id == 1

    def test_omits_relations_when_unpopulated(self):
        product = Product(id=3, created=datetime.now(UTC), product_number="P-042")

        result = ProductMapper.to_result(product)

        assert result.customer is None
        assert result.creator is None

    def test_maps_the_customer_relation_when_populated(self):
        product = Product(
            id=3,
            created=datetime.now(UTC),
            product_number="P-042",
            customer_id=5,
            customer=make_customer(id=5),
        )

        result = ProductMapper.to_result(product)

        assert result.customer_id == 5
        assert result.customer is not None
        assert result.customer.id == 5
        assert result.customer.name == "ACME"

    def test_maps_the_creator_relation_when_populated(self):
        product = Product(
            id=3,
            created=datetime.now(UTC),
            product_number="P-042",
            creator_id=9,
            creator=make_user(id=9, username="tester"),
        )

        result = ProductMapper.to_result(product)

        assert result.creator is not None
        assert result.creator.id == 9
        assert result.creator.username == "tester"

    def test_maps_an_archived_product(self):
        product = Product(id=3, created=datetime.now(UTC), product_number="P-042", archived=True)

        assert ProductMapper.to_result(product).archived is True
