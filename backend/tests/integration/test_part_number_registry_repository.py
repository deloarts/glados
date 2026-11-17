"""
DB-backed coverage for SqlAlchemyPartNumberRegistryRepository
(docs/FIELD_OWNERSHIP.md principle 2): claim/assert_family conflict
semantics in both directions (made vs bought), release_if_unused
respecting soft-deleted rows, and the shared next_part_number sequence.
"""

from datetime import UTC
from datetime import datetime

import pytest
from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import Executable

from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
    BoughtItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
    MadeItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.part_number_registry_model import (
    PartNumberRegistryOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.part_number_registry_repository import (
    SqlAlchemyPartNumberRegistryRepository,
)
from src.modules.catalogue.domain.entities.part_number_registry import UnregisteredPartNumber
from src.modules.catalogue.domain.errors import PartNumberInUseError
from src.modules.platform.adapters.outbound.persistence.statements import count_rows


async def _make_made_item(
    db,
    creator_id: int,
    part_number: str | None,
    *,
    revision: str = "A",
    archived: bool = False,
) -> int:
    orm = MadeItemOrmModel(
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
    db.add(orm)
    await db.commit()
    await db.refresh(orm)
    return orm.id


async def _make_bought_item(
    db, creator_id: int, manufacturer_id: int, part_number: str | None, *, archived: bool = False
) -> int:
    orm = BoughtItemOrmModel(
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
    db.add(orm)
    await db.commit()
    await db.refresh(orm)
    return orm.id


async def _make_supplier(db, creator_id: int) -> int:
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


class _StatementSpy:
    """Forwards to the session and keeps every statement read through
    `scalar`, so a test can see whether a read locks its row."""

    def __init__(self, db) -> None:
        self._db = db
        self.statements: list[Executable] = []

    async def scalar(self, statement, *args, **kwargs):
        self.statements.append(statement)
        return await self._db.scalar(statement, *args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self._db, name)


def _registry_reads(spy: _StatementSpy) -> list[str]:
    """The registry reads among the spied statements, compiled for Postgres,
    since SQLite drops FOR UPDATE from its SQL."""
    compiled = [str(s.compile(dialect=postgresql.dialect())) for s in spy.statements]
    return [sql for sql in compiled if "FROM part_number_registry" in sql]


class TestRegistryRowLock:
    async def test_assert_family_locks_the_row_it_reads(self, db):
        await SqlAlchemyPartNumberRegistryRepository(db).claim("PN-1", "made")
        await db.commit()
        spy = _StatementSpy(db)

        await SqlAlchemyPartNumberRegistryRepository(spy).assert_family("PN-1", "made")

        reads = _registry_reads(spy)
        assert reads
        assert all("FOR UPDATE" in sql for sql in reads)

    async def test_claim_locks_the_row_it_reads(self, db):
        spy = _StatementSpy(db)

        await SqlAlchemyPartNumberRegistryRepository(spy).claim("PN-1", "made")

        reads = _registry_reads(spy)
        assert reads
        assert all("FOR UPDATE" in sql for sql in reads)

    async def test_release_locks_the_row_before_counting_holders(self, db):
        await SqlAlchemyPartNumberRegistryRepository(db).claim("PN-1", "made")
        await db.commit()
        spy = _StatementSpy(db)

        await SqlAlchemyPartNumberRegistryRepository(spy).release_if_unused("PN-1")

        compiled = [str(s.compile(dialect=postgresql.dialect())) for s in spy.statements]
        assert compiled
        assert "FROM part_number_registry" in compiled[0]
        assert "FOR UPDATE" in compiled[0]


class TestFindUnregisteredHolders:
    async def test_lists_numbers_carried_without_their_registry_entry(self, db, create_user):
        user = await create_user()
        supplier_id = await _make_supplier(db, user.id)
        made_id = await _make_made_item(db, user.id, "PN-M")
        await _make_made_item(db, user.id, "PN-M", revision="B")
        bought_id = await _make_bought_item(db, user.id, supplier_id, "PN-B")
        await _make_made_item(db, user.id, "PN-OK")
        await _make_made_item(db, user.id, None)
        repo = SqlAlchemyPartNumberRegistryRepository(db)
        await repo.claim("PN-OK", "made")
        await repo.claim("PN-B", "made")
        await db.commit()

        found = await repo.find_unregistered_holders()

        assert [(f.part_number, f.kind, f.registered_kind, f.item_id) for f in found] == [
            ("PN-B", "bought", "made", bought_id),
            ("PN-M", "made", None, made_id),
        ]
        assert all(isinstance(f, UnregisteredPartNumber) for f in found)


class TestClaim:
    async def test_claims_a_new_number(self, db):
        repo = SqlAlchemyPartNumberRegistryRepository(db)
        await repo.claim("PN-1", "made")
        await db.commit()

        row = (
            await db.scalars(select(PartNumberRegistryOrmModel).filter_by(part_number="PN-1"))
        ).one()
        assert row.kind == "made"

    async def test_made_then_bought_conflicts(self, db):
        repo = SqlAlchemyPartNumberRegistryRepository(db)
        await repo.claim("PN-1", "made")
        await db.commit()
        with pytest.raises(PartNumberInUseError, match="made"):
            await repo.claim("PN-1", "bought")

    async def test_bought_then_made_conflicts(self, db):
        repo = SqlAlchemyPartNumberRegistryRepository(db)
        await repo.claim("PN-1", "bought")
        await db.commit()
        with pytest.raises(PartNumberInUseError, match="bought"):
            await repo.claim("PN-1", "made")

    async def test_same_kind_duplicate_conflicts(self, db):
        repo = SqlAlchemyPartNumberRegistryRepository(db)
        await repo.claim("PN-1", "made")
        await db.commit()
        with pytest.raises(PartNumberInUseError):
            await repo.claim("PN-1", "made")


class TestAssertFamily:
    async def test_passes_for_same_kind_without_duplicating(self, db):
        repo = SqlAlchemyPartNumberRegistryRepository(db)
        await repo.claim("PN-1", "made")
        await db.commit()

        await repo.assert_family("PN-1", "made")  # no raise
        await db.commit()

        count = await count_rows(
            db, select(PartNumberRegistryOrmModel).filter_by(part_number="PN-1")
        )
        assert count == 1

    async def test_claims_when_missing(self, db):
        repo = SqlAlchemyPartNumberRegistryRepository(db)
        await repo.assert_family("PN-1", "made")
        await db.commit()

        row = (
            await db.scalars(select(PartNumberRegistryOrmModel).filter_by(part_number="PN-1"))
        ).one()
        assert row.kind == "made"

    async def test_raises_for_other_kind(self, db):
        repo = SqlAlchemyPartNumberRegistryRepository(db)
        await repo.claim("PN-1", "bought")
        await db.commit()
        with pytest.raises(PartNumberInUseError):
            await repo.assert_family("PN-1", "made")


class TestReleaseIfUnused:
    async def test_soft_deleted_made_item_still_holds_the_number(self, db, create_user):
        user = await create_user()
        await _make_made_item(db, user.id, "PN-1", archived=True)
        repo = SqlAlchemyPartNumberRegistryRepository(db)
        await repo.claim("PN-1", "made")
        await db.commit()

        await repo.release_if_unused("PN-1")
        await db.commit()

        row = await db.scalar(
            select(PartNumberRegistryOrmModel).filter_by(part_number="PN-1").limit(1)
        )
        assert row is not None

    async def test_soft_deleted_bought_item_still_holds_the_number(self, db, create_user):
        user = await create_user()
        supplier_id = await _make_supplier(db, user.id)
        await _make_bought_item(db, user.id, supplier_id, "PN-2", archived=True)
        repo = SqlAlchemyPartNumberRegistryRepository(db)
        await repo.claim("PN-2", "bought")
        await db.commit()

        await repo.release_if_unused("PN-2")
        await db.commit()

        row = await db.scalar(
            select(PartNumberRegistryOrmModel).filter_by(part_number="PN-2").limit(1)
        )
        assert row is not None

    async def test_releases_once_no_row_carries_the_number(self, db, create_user):
        user = await create_user()
        made_id = await _make_made_item(db, user.id, "PN-3")
        repo = SqlAlchemyPartNumberRegistryRepository(db)
        await repo.claim("PN-3", "made")
        await db.commit()

        await db.execute(delete(MadeItemOrmModel).filter_by(id=made_id))
        await db.commit()

        await repo.release_if_unused("PN-3")
        await db.commit()

        assert (
            await db.scalar(
                select(PartNumberRegistryOrmModel).filter_by(part_number="PN-3").limit(1)
            )
            is None
        )

    async def test_missing_entry_is_a_no_op(self, db):
        repo = SqlAlchemyPartNumberRegistryRepository(db)
        await repo.release_if_unused("NOPE")  # no raise
        await db.commit()

        assert await repo.owner_of("NOPE") is None


class TestNextPartNumber:
    async def test_shared_sequence_across_made_and_bought(self, db):
        repo = SqlAlchemyPartNumberRegistryRepository(db)
        first = await repo.next_part_number("PN-{seq:04d}")
        assert first == "PN-0001"
        await repo.claim(first, "made")
        await db.commit()

        second = await repo.next_part_number("PN-{seq:04d}")
        assert second == "PN-0002"
        await repo.claim(second, "bought")
        await db.commit()

        assert await repo.next_part_number("PN-{seq:04d}") == "PN-0003"
