"""
DB-backed coverage for SqlAlchemyMadeItemRepository's additions for the made
item revision rework: `get_revisions`, `get_by_part_number_and_revision`,
and the `latest_only` filter's window-function ranking (newest revision
ranking by highest (len(revision), revision), ties by created desc, id desc),
in particular the two cases plain string ordering gets wrong,
`"9" < "10"` and `"Z" < "AA"`.
"""

from datetime import UTC
from datetime import datetime

from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository import (
    item as made_item_repo_module,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository.item import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.ports.outbound.catalogue_queries import MadeItemFilterDto


async def _make_item(
    db,
    creator_id: int,
    *,
    part_number: str | None,
    revision: str,
    archived: bool = False,
    created: datetime = datetime(2026, 1, 1, tzinfo=UTC),
) -> MadeItem:
    seeded = await SqlAlchemyMadeItemRepository(db).save(
        MadeItem(
            id=0,
            created=created,
            changed=created,
            changes=[],
            archived=archived,
            revision=revision,
            revision_date=None,
            revision_note=None,
            article_name="Bracket",
            status=MadeItemCatalogueStatus.ACTIVE,
            data_source=DataSource.WEB,
            part_number=part_number,
            material=None,
            mass=None,
            base_size=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=creator_id,
            approver_id=None,
            bought_item_id=None,
            source_item_id=None,
            article_group_ids=[],
            successor_item_id=None,
            changed_by_id=None,
        )
    )
    await db.commit()
    return seeded


class TestGetRevisions:
    async def test_returns_all_non_deleted_rows_sharing_the_part_number(self, db, create_user):
        user = await create_user()
        rev_a = await _make_item(db, user.id, part_number="PN-1", revision="A")
        rev_b = await _make_item(db, user.id, part_number="PN-1", revision="B")
        await _make_item(db, user.id, part_number="PN-2", revision="A")

        repo = SqlAlchemyMadeItemRepository(db)
        results = await repo.get_revisions("PN-1")

        assert {r.id for r in results} == {rev_a.id, rev_b.id}

    async def test_excludes_deleted_rows(self, db, create_user):
        user = await create_user()
        live = await _make_item(db, user.id, part_number="PN-1", revision="A")
        await _make_item(db, user.id, part_number="PN-1", revision="B", archived=True)

        repo = SqlAlchemyMadeItemRepository(db)
        results = await repo.get_revisions("PN-1")

        assert [r.id for r in results] == [live.id]

    async def test_unknown_part_number_returns_empty(self, db, create_user):
        await create_user()
        repo = SqlAlchemyMadeItemRepository(db)
        assert await repo.get_revisions("NOPE") == []


class TestGetFamily:
    """Unlike get_revisions, get_family includes soft-deleted
    rows. The renumber path (UpdateMadeItem) must rename every row of a
    family, deleted included, to keep uq_made_item_part_number_revision (a
    TOTAL index) satisfied."""

    async def test_includes_deleted_rows(self, db, create_user):
        user = await create_user()
        live = await _make_item(db, user.id, part_number="PN-1", revision="A")
        archived = await _make_item(db, user.id, part_number="PN-1", revision="B", archived=True)

        repo = SqlAlchemyMadeItemRepository(db)
        results = await repo.get_family("PN-1")

        assert {r.id for r in results} == {live.id, archived.id}

    async def test_unknown_part_number_returns_empty(self, db, create_user):
        await create_user()
        repo = SqlAlchemyMadeItemRepository(db)
        assert await repo.get_family("NOPE") == []


class TestGetByPartNumberAndRevision:
    async def test_returns_the_exact_match(self, db, create_user):
        user = await create_user()
        target = await _make_item(db, user.id, part_number="PN-1", revision="B")
        await _make_item(db, user.id, part_number="PN-1", revision="A")

        repo = SqlAlchemyMadeItemRepository(db)
        result = await repo.get_by_part_number_and_revision("PN-1", "B")

        assert result is not None
        assert result.id == target.id

    async def test_returns_none_when_missing(self, db, create_user):
        await create_user()
        repo = SqlAlchemyMadeItemRepository(db)
        assert await repo.get_by_part_number_and_revision("PN-1", "A") is None

    async def test_ignores_deleted_rows(self, db, create_user):
        user = await create_user()
        await _make_item(db, user.id, part_number="PN-1", revision="A", archived=True)

        repo = SqlAlchemyMadeItemRepository(db)
        assert await repo.get_by_part_number_and_revision("PN-1", "A") is None


class TestLatestOnlyFilter:
    async def test_numeric_revision_9_and_10(self, db, create_user):
        """Plain string ordering would rank "9" above "10"; the window's
        length-first ordering must not."""
        user = await create_user()
        await _make_item(db, user.id, part_number="PN-1", revision="9")
        newest = await _make_item(db, user.id, part_number="PN-1", revision="10")

        repo = SqlAlchemyMadeItemRepository(db)
        _, items = await repo.get_multi(MadeItemFilterDto(latest_only=True))

        assert [i.id for i in items] == [newest.id]

    async def test_alpha_revision_z_and_aa(self, db, create_user):
        """Same idea for the alpha scheme: "Z" < "AA" by length, not by
        plain string comparison (which would rank "Z" above "AA")."""
        user = await create_user()
        await _make_item(db, user.id, part_number="PN-2", revision="Z")
        newest = await _make_item(db, user.id, part_number="PN-2", revision="AA")

        repo = SqlAlchemyMadeItemRepository(db)
        _, items = await repo.get_multi(MadeItemFilterDto(latest_only=True, part_number="PN-2"))

        assert [i.id for i in items] == [newest.id]

    async def test_null_part_number_rows_always_pass(self, db, create_user):
        user = await create_user()
        no_pn_1 = await _make_item(db, user.id, part_number=None, revision="0")
        no_pn_2 = await _make_item(db, user.id, part_number=None, revision="0")

        repo = SqlAlchemyMadeItemRepository(db)
        _, items = await repo.get_multi(MadeItemFilterDto(latest_only=True))

        assert {i.id for i in items} == {no_pn_1.id, no_pn_2.id}

    async def test_default_is_all_revisions(self, db, create_user):
        user = await create_user()
        older = await _make_item(db, user.id, part_number="PN-1", revision="9")
        newer = await _make_item(db, user.id, part_number="PN-1", revision="10")

        repo = SqlAlchemyMadeItemRepository(db)
        _, items = await repo.get_multi(MadeItemFilterDto())

        assert {i.id for i in items} == {older.id, newer.id}


class TestExistingPartNumbers:
    """Batch counterpart to get_revisions' existence check, used by
    reconcile_pdm_vault's registry cross-check."""

    async def test_returns_only_the_part_numbers_with_a_live_row(self, db, create_user):
        user = await create_user()
        await _make_item(db, user.id, part_number="PN-1", revision="A")
        await _make_item(db, user.id, part_number="PN-2", revision="A", archived=True)

        repo = SqlAlchemyMadeItemRepository(db)
        result = await repo.existing_part_numbers(["PN-1", "PN-2", "PN-3"])

        assert result == {"PN-1"}

    async def test_empty_input_returns_empty_set(self, db, create_user):
        await create_user()
        repo = SqlAlchemyMadeItemRepository(db)
        assert await repo.existing_part_numbers([]) == set()

    async def test_chunks_large_batches(self, db, create_user, monkeypatch):
        """A batch bigger than the chunk size must still be resolved in
        full, across more than one IN (...) query."""
        monkeypatch.setattr(made_item_repo_module, "_PART_NUMBER_CHUNK_SIZE", 2)
        user = await create_user()
        part_numbers = [f"PN-{i}" for i in range(5)]
        for part_number in part_numbers:
            await _make_item(db, user.id, part_number=part_number, revision="A")

        repo = SqlAlchemyMadeItemRepository(db)
        result = await repo.existing_part_numbers([*part_numbers, "PN-UNKNOWN"])

        assert result == set(part_numbers)
