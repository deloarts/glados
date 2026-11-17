"""
DB-backed coverage for SqlAlchemyPdmDocumentLinkRepository: get_by_pdm_file,
upsert (insert then update, matched on vault_id + file_id), delete and
get_linked_item_file_ids (the item-file listing's cheap `from_pdm` lookup).
"""

from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_document_link_repository import (
    SqlAlchemyPdmDocumentLinkRepository,
)
from src.modules.external_data.domain.entities.pdm_document_link import PdmDocumentLink


def _link(
    *,
    kind: ItemKind = ItemKind.MADE,
    item_id: int = 1,
    item_file_id: int = 10,
    vault_id: str = "V1",
    file_id: int = 100,
    version: int = 1,
) -> PdmDocumentLink:
    return PdmDocumentLink(
        id=0,
        kind=kind,
        item_id=item_id,
        item_file_id=item_file_id,
        vault_id=vault_id,
        file_id=file_id,
        version=version,
    )


class TestUpsert:
    async def test_inserts_a_new_row(self, db):
        repo = SqlAlchemyPdmDocumentLinkRepository(db)
        await repo.upsert(_link())
        await db.commit()

        link = await repo.get_by_pdm_file("V1", 100)
        assert link is not None
        assert link.kind == "made"
        assert link.item_id == 1
        assert link.item_file_id == 10
        assert link.version == 1

    async def test_updates_the_existing_row_matched_on_vault_and_file(self, db):
        repo = SqlAlchemyPdmDocumentLinkRepository(db)
        await repo.upsert(_link(item_file_id=10, version=1))
        await db.commit()

        await repo.upsert(_link(item_file_id=11, version=2))
        await db.commit()

        rows = [link for link in [await repo.get_by_pdm_file("V1", 100)] if link is not None]
        assert len(rows) == 1
        assert rows[0].item_file_id == 11
        assert rows[0].version == 2

    async def test_get_by_pdm_file_returns_none_when_absent(self, db):
        repo = SqlAlchemyPdmDocumentLinkRepository(db)
        assert await repo.get_by_pdm_file("V1", 999) is None


class TestDelete:
    async def test_removes_the_row(self, db):
        repo = SqlAlchemyPdmDocumentLinkRepository(db)
        saved = await repo.upsert(_link())
        await db.commit()

        await repo.delete(saved)
        await db.commit()

        assert await repo.get_by_pdm_file("V1", 100) is None


class TestGetLinkedItemFileIds:
    async def test_returns_the_subset_that_is_linked(self, db):
        repo = SqlAlchemyPdmDocumentLinkRepository(db)
        await repo.upsert(_link(item_file_id=10, file_id=100))
        await repo.upsert(_link(item_file_id=11, file_id=101))
        await db.commit()

        result = await repo.get_linked_item_file_ids([10, 11, 12, 13])

        assert result == {10, 11}

    async def test_empty_input_returns_empty_set_without_a_query(self, db):
        repo = SqlAlchemyPdmDocumentLinkRepository(db)
        assert await repo.get_linked_item_file_ids([]) == set()

    async def test_no_matches_returns_empty_set(self, db):
        repo = SqlAlchemyPdmDocumentLinkRepository(db)
        await repo.upsert(_link(item_file_id=10))
        await db.commit()

        assert await repo.get_linked_item_file_ids([999]) == set()

    async def test_a_link_to_a_picture_names_no_file(self, db):
        repo = SqlAlchemyPdmDocumentLinkRepository(db)
        link = _link(item_file_id=10)
        link.item_file_id = None
        link.item_picture_id = 20
        await repo.upsert(link)
        await db.commit()

        assert await repo.get_linked_item_file_ids([10, 20]) == set()
        stored = await repo.get_by_pdm_file("V1", 100)
        assert stored is not None
        assert (stored.item_file_id, stored.item_picture_id) == (None, 20)


class TestGetByPdmFiles:
    async def test_returns_the_links_of_the_listed_files_in_the_vault(self, db):
        repo = SqlAlchemyPdmDocumentLinkRepository(db)
        await repo.upsert(_link(file_id=100))
        await repo.upsert(_link(file_id=101, kind=ItemKind.BOUGHT))
        await repo.upsert(_link(file_id=102))
        await repo.upsert(_link(file_id=100, vault_id="V2"))
        await db.commit()

        found = await repo.get_by_pdm_files("V1", [100, 101, 999])

        assert sorted((link.file_id, link.kind) for link in found) == [
            (100, "made"),
            (101, "bought"),
        ]

    async def test_empty_input_returns_nothing(self, db):
        repo = SqlAlchemyPdmDocumentLinkRepository(db)
        assert await repo.get_by_pdm_files("V1", []) == []
