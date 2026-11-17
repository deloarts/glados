"""
Database-level guarantees of the public_id column on Base
(src/modules/platform/adapters/outbound/persistence/models/base.py): every mapped table
carries it, two rows never collide, and a save-mutate-save round trip
never rotates the value. The last guard catches public_id ending up in a
repository's entity->dict update payload, which would silently reassign
it on every update.
"""

from datetime import UTC
from datetime import datetime

from src.modules.catalogue.adapters.outbound.persistence.repositories.customer_repository import (
    SqlAlchemyCustomerRepository,
)
from src.modules.catalogue.domain.entities.customer import Customer
from src.modules.catalogue.domain.value_objects.customer_level import CustomerLevel
from src.modules.platform.adapters.outbound.persistence.models.base import Base


def _customer(**overrides) -> Customer:
    defaults = dict(
        id=0,
        created=datetime.now(UTC).date(),
        changed=None,
        changes=[],
        archived=False,
        name="ACME",
        legal_name=None,
        vat_id=None,
        level=CustomerLevel.A,
        street=None,
        city=None,
        country=None,
        postal_code=None,
        email=None,
        phone=None,
        weblink=None,
        creator_id=1,
    )
    defaults.update(overrides)
    return Customer(**defaults)


def test_every_mapped_table_has_a_public_id_column():
    for mapper in Base.registry.mappers:
        columns = {c.name for c in mapper.columns}
        assert "public_id" in columns, f"{mapper.class_.__name__} has no public_id column"


async def test_two_saved_rows_get_distinct_public_ids(db):
    repo = SqlAlchemyCustomerRepository(db)

    a = await repo.save(_customer(name="A"))
    b = await repo.save(_customer(name="B"))

    assert a.public_id != b.public_id


async def test_public_id_is_stable_across_updates(db):
    repo = SqlAlchemyCustomerRepository(db)

    saved = await repo.save(_customer(name="Original"))
    original_public_id = saved.public_id

    saved.name = "Renamed"
    updated = await repo.save(saved)

    assert updated.public_id == original_public_id
