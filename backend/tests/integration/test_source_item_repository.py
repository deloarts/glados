"""
DB-backed coverage for SqlAlchemySourceItemRepository.get_multi's `dimension`
filter: a plain ilike substring match, added so the source-item create
dialog's similar-items search can narrow by dimension the same way it
already does by material.
"""

from datetime import UTC
from datetime import datetime

from src.modules.catalogue.adapters.outbound.persistence.repositories.source_item_repository import (
    SqlAlchemySourceItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.source_item_type_repository import (
    SqlAlchemySourceItemTypeRepository,
)
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.domain.entities.source_item_type import SourceItemType
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.catalogue.ports.outbound.repositories.source_item_repository import (
    SourceItemFilterDto,
)
from src.modules.platform.domain.value_objects.localized_text import LocalizedText


async def _make_type(db, creator_id: int) -> int:
    return (
        await SqlAlchemySourceItemTypeRepository(db).save(
            SourceItemType(
                id=0,
                created=datetime(2026, 1, 1, tzinfo=UTC),
                changed=datetime(2026, 1, 1, tzinfo=UTC),
                changes=[],
                archived=False,
                name=LocalizedText({"enGB": "Round bar"}),
                label_color="#000000",
                label_font_color="#ffffff",
                description=LocalizedText(),
                creator_id=creator_id,
            )
        )
    ).id


async def _make_source_item(
    db,
    creator_id: int,
    type_id: int,
    dimension: str | None,
    order_code_1: str | None = None,
    order_code_2: str | None = None,
) -> int:
    return (
        await SqlAlchemySourceItemRepository(db).save(
            SourceItem(
                id=0,
                created=datetime(2026, 1, 1, tzinfo=UTC),
                changed=datetime(2026, 1, 1, tzinfo=UTC),
                changes=[],
                archived=False,
                type_id=type_id,
                dimension=dimension,
                material="S235",
                mass=None,
                note=None,
                order_code_1=order_code_1,
                order_code_2=order_code_2,
                status=SourceItemCatalogueStatus.ACTIVE,
                creator_id=creator_id,
                approver_id=None,
                manufacturer_id=None,
                successor_item_id=None,
            )
        )
    ).id


class TestDimensionFilter:
    async def test_matches_a_substring_case_insensitively(self, db, create_user):
        user = await create_user()
        type_id = await _make_type(db, user.id)
        match_id = await _make_source_item(db, user.id, type_id, "100 × 200 × 20")
        await _make_source_item(db, user.id, type_id, "50 × 60 × 10")

        repo = SqlAlchemySourceItemRepository(db)
        _, items = await repo.get_multi(SourceItemFilterDto(dimension="200"))

        assert [i.id for i in items] == [match_id]

    async def test_does_not_match_a_permuted_ordering(self, db, create_user):
        """The filter is a literal substring match. It can't recognize a
        permuted box dimension. Callers relying on that (SourceItemCreateForm)
        must not filter the duplicate-check candidate pool by dimension."""
        user = await create_user()
        type_id = await _make_type(db, user.id)
        await _make_source_item(db, user.id, type_id, "100 × 200 × 20")

        repo = SqlAlchemySourceItemRepository(db)
        _, items = await repo.get_multi(SourceItemFilterDto(dimension="200 × 100 × 20"))

        assert items == []

    async def test_no_filter_returns_all(self, db, create_user):
        user = await create_user()
        type_id = await _make_type(db, user.id)
        await _make_source_item(db, user.id, type_id, "100 × 200 × 20")
        await _make_source_item(db, user.id, type_id, "50 × 60 × 10")

        repo = SqlAlchemySourceItemRepository(db)
        total, items = await repo.get_multi(SourceItemFilterDto())

        assert total == len(items) == 2


class TestOrderCodeFilter:
    async def test_order_code_1_matches_a_substring_case_insensitively(self, db, create_user):
        user = await create_user()
        type_id = await _make_type(db, user.id)
        match_id = await _make_source_item(db, user.id, type_id, "1", order_code_1="ACME-1234")
        await _make_source_item(db, user.id, type_id, "2", order_code_1="OTHER-9999")

        repo = SqlAlchemySourceItemRepository(db)
        _, items = await repo.get_multi(SourceItemFilterDto(order_code_1="acme"))

        assert [i.id for i in items] == [match_id]

    async def test_order_code_2_matches_a_substring(self, db, create_user):
        user = await create_user()
        type_id = await _make_type(db, user.id)
        match_id = await _make_source_item(db, user.id, type_id, "1", order_code_2="ALT-42")
        await _make_source_item(db, user.id, type_id, "2", order_code_2="ALT-99")

        repo = SqlAlchemySourceItemRepository(db)
        _, items = await repo.get_multi(SourceItemFilterDto(order_code_2="ALT-42"))

        assert [i.id for i in items] == [match_id]

    async def test_percent_in_the_term_is_escaped_not_treated_as_a_wildcard(self, db, create_user):
        user = await create_user()
        type_id = await _make_type(db, user.id)
        match_id = await _make_source_item(db, user.id, type_id, "1", order_code_1="ACME-50%OFF")
        await _make_source_item(db, user.id, type_id, "2", order_code_1="ACME-50XOFF")

        repo = SqlAlchemySourceItemRepository(db)
        _, items = await repo.get_multi(SourceItemFilterDto(order_code_1="50%OFF"))

        assert [i.id for i in items] == [match_id]

    async def test_search_matches_either_order_code(self, db, create_user):
        user = await create_user()
        type_id = await _make_type(db, user.id)
        by_code_1 = await _make_source_item(db, user.id, type_id, "1", order_code_1="FIND-ME-1")
        by_code_2 = await _make_source_item(db, user.id, type_id, "2", order_code_2="FIND-ME-2")
        await _make_source_item(db, user.id, type_id, "3", order_code_1="NO-MATCH")

        repo = SqlAlchemySourceItemRepository(db)
        _, items = await repo.get_multi(SourceItemFilterDto(search="FIND-ME"))

        assert {i.id for i in items} == {by_code_1, by_code_2}
