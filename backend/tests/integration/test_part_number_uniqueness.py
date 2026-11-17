"""
Database-level guarantees of the two partial unique indexes
`uq_made_item_part_number_revision` on
made_item_table(part_number, revision) and `uq_bought_item_part_number` on
bought_item_table(part_number). Both are partial on
`part_number IS NOT NULL` (a NULL part number is exempt, repeatable
without limit) but, unlike the `uq_*_active` indexes covered by
test_soft_delete_uniqueness.py, TOTAL with respect to `deleted`. A
soft-deleted row still holds its number (only
part_number_registry.release_if_unused, i.e. a hard delete, frees one),
so a duplicate must be rejected even when one of the two colliding rows
is already soft-deleted.
"""

from datetime import UTC
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
    BoughtItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
    MadeItemOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.statements import count_rows


def _made_item(creator_id: int, part_number: str | None, revision: str, *, archived: bool = False):
    return MadeItemOrmModel(
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=archived,
        revision=revision,
        revision_date=None,
        revision_note=None,
        article_name="Bracket",
        status="active",
        data_source="WEB",
        part_number=part_number,
        material=None,
        mass=None,
        base_size=None,
        note=None,
        weblink=None,
        creator_id=creator_id,
        approver_id=None,
        bought_item_id=None,
        source_item_id=None,
        successor_item_id=None,
    )


def _bought_item(creator_id: int, manufacturer_id: int, part_number: str | None, *, archived=False):
    return BoughtItemOrmModel(
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=archived,
        order_code_1="ORD-1",
        order_code_2=None,
        gtin=None,
        ean=None,
        tariff_number=None,
        status="active",
        article_name="Hex bolt",
        data_source="WEB",
        part_number=part_number,
        mass=None,
        successor_item_id=None,
        note=None,
        weblink=None,
        creator_id=creator_id,
        approver_id=None,
        manufacturer_id=manufacturer_id,
    )


async def _make_supplier_id(db, creator_id: int) -> int:
    from src.modules.catalogue.adapters.outbound.persistence.models.supplier_model import (
        SupplierOrmModel,
    )

    orm = SupplierOrmModel(
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=False,
        name="Acme",
        legal_name=None,
        vat_id=None,
        level="B",
        street=None,
        city=None,
        country=None,
        postal_code=None,
        email=None,
        phone=None,
        weblink=None,
        order_email=None,
        order_language=None,
        order_template=None,
        request_email=None,
        request_language=None,
        request_template=None,
        creator_id=creator_id,
    )
    db.add(orm)
    await db.commit()
    await db.refresh(orm)
    return orm.id


class TestIndexesExistAndArePartial:
    async def test_made_item_index(self, db):
        row = (
            await db.execute(
                text("SELECT sql FROM sqlite_master WHERE type='index' AND name=:n"),
                {"n": "uq_made_item_part_number_revision"},
            )
        ).first()
        assert row is not None, "uq_made_item_part_number_revision is missing"
        assert "UNIQUE" in row[0].upper()
        assert "WHERE" in row[0].upper()

    async def test_bought_item_index(self, db):
        row = (
            await db.execute(
                text("SELECT sql FROM sqlite_master WHERE type='index' AND name=:n"),
                {"n": "uq_bought_item_part_number"},
            )
        ).first()
        assert row is not None, "uq_bought_item_part_number is missing"
        assert "UNIQUE" in row[0].upper()
        assert "WHERE" in row[0].upper()


class TestMadeItemPartNumberRevisionUniqueness:
    async def test_duplicate_among_live_rows_rejected(self, db, create_user):
        user = await create_user()
        db.add(_made_item(user.id, "PN-1", "A"))
        await db.commit()

        with pytest.raises(IntegrityError):
            db.add(_made_item(user.id, "PN-1", "A"))
            await db.commit()
        await db.rollback()

    async def test_duplicate_against_a_soft_deleted_row_still_rejected(self, db, create_user):
        """TOTAL, unlike uq_*_active: a soft delete must NOT free the
        (part_number, revision) pair."""
        user = await create_user()
        db.add(_made_item(user.id, "PN-1", "A", archived=True))
        await db.commit()

        with pytest.raises(IntegrityError):
            db.add(_made_item(user.id, "PN-1", "A"))
            await db.commit()
        await db.rollback()

    async def test_same_part_number_different_revision_is_fine(self, db, create_user):
        user = await create_user()
        db.add(_made_item(user.id, "PN-1", "A"))
        db.add(_made_item(user.id, "PN-1", "B"))
        await db.commit()

        count = await count_rows(db, select(MadeItemOrmModel).filter_by(part_number="PN-1"))
        assert count == 2

    async def test_null_part_number_rows_repeat_freely(self, db, create_user):
        user = await create_user()
        db.add(_made_item(user.id, None, "A"))
        db.add(_made_item(user.id, None, "A"))
        await db.commit()

        count = await count_rows(
            db, select(MadeItemOrmModel).where(MadeItemOrmModel.part_number.is_(None))
        )
        assert count == 2


class TestBoughtItemPartNumberUniqueness:
    async def test_duplicate_among_live_rows_rejected(self, db, create_user):
        user = await create_user()
        supplier_id = await _make_supplier_id(db, user.id)
        db.add(_bought_item(user.id, supplier_id, "PN-1"))
        await db.commit()

        with pytest.raises(IntegrityError):
            db.add(_bought_item(user.id, supplier_id, "PN-1"))
            await db.commit()
        await db.rollback()

    async def test_duplicate_against_a_soft_deleted_row_still_rejected(self, db, create_user):
        user = await create_user()
        supplier_id = await _make_supplier_id(db, user.id)
        db.add(_bought_item(user.id, supplier_id, "PN-1", archived=True))
        await db.commit()

        with pytest.raises(IntegrityError):
            db.add(_bought_item(user.id, supplier_id, "PN-1"))
            await db.commit()
        await db.rollback()

    async def test_null_part_number_rows_repeat_freely(self, db, create_user):
        user = await create_user()
        supplier_id = await _make_supplier_id(db, user.id)
        db.add(_bought_item(user.id, supplier_id, None))
        db.add(_bought_item(user.id, supplier_id, None))
        await db.commit()

        count = await count_rows(
            db, select(BoughtItemOrmModel).where(BoughtItemOrmModel.part_number.is_(None))
        )
        assert count == 2
