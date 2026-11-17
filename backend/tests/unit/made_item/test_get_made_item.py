"""
Unit tests for GetMadeItem.
"""

import pytest

from src.modules.catalogue.application.use_cases.made_item.get_made_item import GetMadeItem
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.external_data.application.services.pdm_cad_source import PdmCadSource
from tests.factories import make_user
from tests.unit.made_item._helpers import make_made_item
from tests.unit.made_item._helpers import make_pdm_settings
from tests.unit.made_item.fakes import FakeAdminSettingsRepository
from tests.unit.made_item.fakes import FakeMadeItemRepository


class TestGetMadeItem:
    def setup_method(self):
        self.item_repo = FakeMadeItemRepository(
            [
                make_made_item(id=1, part_number="PN-1", revision="A"),
                make_made_item(id=2, part_number="PN-1", revision="B"),
            ]
        )
        self.admin_settings_repo = FakeAdminSettingsRepository()
        self.use_case = GetMadeItem(
            made_item_repo=self.item_repo, cad_source=PdmCadSource(self.admin_settings_repo)
        )

    async def test_lookup_by_item_id(self):
        result = await self.use_case.execute(item_id=1)
        assert result.id == 1
        assert result.revision == "A"

    async def test_lookup_by_unknown_item_id_raises(self):
        with pytest.raises(MadeItemNotFoundError):
            await self.use_case.execute(item_id=999)

    async def test_lookup_by_part_number_and_revision(self):
        result = await self.use_case.execute(part_number="PN-1", revision="A")
        assert result.id == 1
        assert result.revision == "A"

    async def test_lookup_by_part_number_and_unknown_revision_raises(self):
        with pytest.raises(MadeItemNotFoundError):
            await self.use_case.execute(part_number="PN-1", revision="Z")

    async def test_lookup_by_unknown_part_number_raises(self):
        with pytest.raises(MadeItemNotFoundError):
            await self.use_case.execute(part_number="PN-UNKNOWN")

    async def test_lookup_by_part_number_alone_returns_newest_revision(self):
        # The sort key (len(revision), revision): "B" (len 1) beats "A"
        # (len 1) lexicographically; newest_of, not a second ordering.
        result = await self.use_case.execute(part_number="PN-1")
        assert result.id == 2
        assert result.revision == "B"

    async def test_lookup_by_part_number_alone_prefers_longer_revision(self):
        # "10" (len 2) beats "9" (len 1) even though "9" > "10" lexically,
        # a case plain string ordering gets wrong.
        item_repo = FakeMadeItemRepository(
            [
                make_made_item(id=1, part_number="PN-2", revision="9"),
                make_made_item(id=2, part_number="PN-2", revision="10"),
            ]
        )
        use_case = GetMadeItem(
            made_item_repo=item_repo, cad_source=PdmCadSource(FakeAdminSettingsRepository())
        )
        result = await use_case.execute(part_number="PN-2")
        assert result.id == 2
        assert result.revision == "10"

    async def test_neither_item_id_nor_part_number_raises_value_error(self):
        with pytest.raises(ValueError):
            await self.use_case.execute()

    # ── pdm_locked_fields ──────────────────────────────────────────

    async def test_locked_fields_empty_without_an_actor(self):
        result = await self.use_case.execute(item_id=1)
        assert result.pdm_locked_fields == []

    async def test_locked_fields_empty_when_pdm_disabled(self):
        result = await self.use_case.execute(item_id=1, actor=make_user())
        assert result.pdm_locked_fields == []

    async def test_locked_fields_empty_for_a_web_row_even_when_enforced(self):
        repo = FakeAdminSettingsRepository(pdm=make_pdm_settings(enabled=True))
        item_repo = FakeMadeItemRepository([make_made_item(id=1, data_source=DataSource.WEB)])
        use_case = GetMadeItem(made_item_repo=item_repo, cad_source=PdmCadSource(repo))

        result = await use_case.execute(item_id=1, actor=make_user())

        assert result.pdm_locked_fields == []

    async def test_locked_fields_populated_for_a_cad_row_when_enforced(self):
        repo = FakeAdminSettingsRepository(pdm=make_pdm_settings(enabled=True))
        item_repo = FakeMadeItemRepository([make_made_item(id=1, data_source=DataSource.CAD)])
        use_case = GetMadeItem(made_item_repo=item_repo, cad_source=PdmCadSource(repo))

        result = await use_case.execute(item_id=1, actor=make_user())

        assert "part_number" in result.pdm_locked_fields
        assert "article_name" in result.pdm_locked_fields

    async def test_locked_fields_empty_for_a_cad_row_when_override_off(self):
        repo = FakeAdminSettingsRepository(
            pdm=make_pdm_settings(enabled=True, cad_items_read_only=False)
        )
        item_repo = FakeMadeItemRepository([make_made_item(id=1, data_source=DataSource.CAD)])
        use_case = GetMadeItem(made_item_repo=item_repo, cad_source=PdmCadSource(repo))

        result = await use_case.execute(item_id=1, actor=make_user())

        assert result.pdm_locked_fields == []

    async def test_locked_fields_empty_for_the_system_user(self):
        repo = FakeAdminSettingsRepository(pdm=make_pdm_settings(enabled=True))
        item_repo = FakeMadeItemRepository([make_made_item(id=1, data_source=DataSource.CAD)])
        use_case = GetMadeItem(made_item_repo=item_repo, cad_source=PdmCadSource(repo))

        result = await use_case.execute(item_id=1, actor=make_user(is_systemuser=True))

        assert result.pdm_locked_fields == []
