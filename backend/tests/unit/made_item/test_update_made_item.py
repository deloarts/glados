"""
Unit tests for UpdateMadeItem.
"""

import pytest

from src.modules.catalogue.application.dto.made_item_dto import UpdateMadeItemCommand
from src.modules.catalogue.application.use_cases.made_item.update_made_item import UpdateMadeItem
from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.errors import ArticleGroupNotFoundError
from src.modules.catalogue.domain.errors import MadeItemFieldRequiresRevisionError
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.domain.errors import MadeItemNotNewestRevisionError
from src.modules.catalogue.domain.errors import MadeItemPartNumberDuplicateError
from src.modules.catalogue.domain.errors import MadeItemPartNumberNotEditableError
from src.modules.catalogue.domain.errors import MaterialSourceConflictError
from src.modules.catalogue.domain.errors import PartNumberReservedForPdmError
from src.modules.catalogue.domain.policies.item_field_ownership import default_policy
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.external_data.application.services.pdm_cad_source import PdmCadSource
from src.modules.platform.adapters.outbound.persistence.constraint_violation import (
    SqlConstraintViolationError,
)
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import NumberingConflictError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.made_item._helpers import make_bought_item
from tests.unit.made_item._helpers import make_made_item
from tests.unit.made_item._helpers import make_pdm_settings
from tests.unit.made_item._helpers import make_source_item
from tests.unit.made_item.fakes import FakeAdminSettingsRepository
from tests.unit.made_item.fakes import FakeArticleGroupRepository
from tests.unit.made_item.fakes import FakeBoughtItemRepository
from tests.unit.made_item.fakes import FakeCustomerRepository
from tests.unit.made_item.fakes import FakeMadeItemRepository
from tests.unit.made_item.fakes import FakePartNumberRegistry
from tests.unit.made_item.fakes import FakeSourceItemRepository


class TestUpdateMadeItem:
    def setup_method(self):
        self.item = make_made_item(id=1)
        self.item_repo = FakeMadeItemRepository([self.item])
        self.article_group_repo = FakeArticleGroupRepository()
        self.bought_item_repo = FakeBoughtItemRepository([make_bought_item(id=1)])
        self.source_item_repo = FakeSourceItemRepository([make_source_item(id=1)])
        self.actor = make_user(permissions=[Permission.WRITE_MADE_ITEMS])
        self.admin_settings_repo = FakeAdminSettingsRepository()
        self.registry = FakePartNumberRegistry()
        self.uow = FakeUnitOfWork()
        self.use_case = self._use_case(self.admin_settings_repo)

    def _use_case(self, admin_settings_repo: FakeAdminSettingsRepository) -> UpdateMadeItem:
        return UpdateMadeItem(
            self.item_repo,
            self.article_group_repo,
            self.bought_item_repo,
            self.source_item_repo,
            admin_settings_repo,
            part_number_registry=self.registry,
            uow=self.uow,
            customer_repo=FakeCustomerRepository(),
            cad_source=PdmCadSource(admin_settings_repo),
        )

    @staticmethod
    def _settings(**overrides) -> AdminMadeItemSettings:
        defaults = dict(
            id=1,
            item_number_format="MADE-{year}-{seq:04d}",
            lot_number_format="LOT-{year}-{seq:04d}",
            part_number_auto=False,
            part_number_editable=True,
            revision_start="0",
            revision_separator=":",
            revision_skip_ambiguous_letters=False,
            revision_only_newest_editable=True,
            revision_predecessor_status_web="ask",
            revision_predecessor_status_pdm="replaced",
            revision_field_policy=default_policy(),
            web_creation_allowed=True,
            pdm_part_number_pattern="",
        )
        defaults.update(overrides)
        return AdminMadeItemSettings(**defaults)

    def _cmd(self, **kwargs) -> UpdateMadeItemCommand:
        # Defaults mirror self.item's CURRENT state (as a real PUT from a
        # prefilled form would), so only the fields a test explicitly
        # overrides count as a "change" for policy-gate purposes. A fixed
        # literal default (e.g. material=None) could spuriously differ
        # from make_made_item()'s own defaults (material="1.0037") and
        # trip the policy gate by accident.
        defaults = dict(
            article_name=self.item.article_name,
            article_group_ids=list(self.item.article_group_ids),
            status=self.item.status,
            part_number=self.item.part_number,
            material=self.item.material,
            mass=self.item.mass,
            base_size=self.item.base_size,
            note=self.item.note,
            weblink=self.item.weblink,
            bought_item_id=self.item.bought_item_id,
            source_item_id=self.item.source_item_id,
            successor_item_id=self.item.successor_item_id,
        )
        defaults.update(kwargs)
        return UpdateMadeItemCommand(**defaults)

    async def test_updates_successfully(self):
        # weblink is not a revision-policy field (web_requires_revision
        # is False for it by default), so a plain in-place edit succeeds.
        result = await self.use_case.execute(
            actor=self.actor, item_id=1, cmd=self._cmd(weblink="https://example.com")
        )
        assert result.weblink == "https://example.com"

    async def test_not_found_raises(self):
        with pytest.raises(MadeItemNotFoundError):
            await self.use_case.execute(actor=self.actor, item_id=999, cmd=self._cmd())

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, item_id=1, cmd=self._cmd())

    async def test_missing_article_group_raises(self):
        with pytest.raises(ArticleGroupNotFoundError):
            await self.use_case.execute(
                actor=self.actor, item_id=1, cmd=self._cmd(article_group_ids=[99])
            )

    async def test_sets_bought_item_source(self):
        # bought_item_id/source_item_id are web_requires_revision
        # fields on a WEB item; a CAD row (out of scope for that policy)
        # isolates this test to the material-source-assignment behaviour
        # it means to check.
        self.item.data_source = DataSource.CAD
        result = await self.use_case.execute(
            actor=self.actor, item_id=1, cmd=self._cmd(bought_item_id=1)
        )
        assert result.bought_item_id == 1

    async def test_sets_source_item_source(self):
        self.item.data_source = DataSource.CAD
        result = await self.use_case.execute(
            actor=self.actor, item_id=1, cmd=self._cmd(source_item_id=1)
        )
        assert result.source_item_id == 1

    async def test_both_material_sources_rejected(self):
        with pytest.raises(MaterialSourceConflictError):
            await self.use_case.execute(
                actor=self.actor, item_id=1, cmd=self._cmd(bought_item_id=1, source_item_id=1)
            )

    async def test_policy_field_change_on_web_item_requires_revision(self):
        # article_name is a web_requires_revision field by default,
        # changing it in place on a WEB item is rejected, naming the field.
        with pytest.raises(MadeItemFieldRequiresRevisionError, match=r"\['article_name'\]"):
            await self.use_case.execute(
                actor=self.actor, item_id=1, cmd=self._cmd(article_name="New")
            )

    async def test_policy_field_change_names_every_blocked_field(self):
        with pytest.raises(
            MadeItemFieldRequiresRevisionError, match=r"\['article_name', 'material'\]"
        ):
            await self.use_case.execute(
                actor=self.actor,
                item_id=1,
                cmd=self._cmd(article_name="New", material="1.4301"),
            )

    async def test_policy_field_change_on_cad_item_is_allowed(self):
        # The revision policy gate only applies to WEB items: a CAD row's
        # fields are out of its scope.
        self.item.data_source = DataSource.CAD
        result = await self.use_case.execute(
            actor=self.actor, item_id=1, cmd=self._cmd(article_name="New")
        )
        assert result.article_name == "New"

    async def test_update_never_moves_a_cad_row_back_to_web(self):
        # The command has no data_source field, so a client sending WEB is
        # ignored and the row stays CAD.
        self.item.data_source = DataSource.CAD
        result = await self.use_case.execute(
            actor=self.actor, item_id=1, cmd=self._cmd(note="x", data_source="WEB")
        )
        assert result.data_source == "CAD"

    async def test_part_number_change_rejected_when_not_editable(self):
        use_case = self._use_case(
            FakeAdminSettingsRepository(self._settings(part_number_editable=False))
        )
        with pytest.raises(MadeItemPartNumberNotEditableError):
            await use_case.execute(actor=self.actor, item_id=1, cmd=self._cmd(part_number="NEW-1"))

    # test_part_number_change_rejected_when_source_external removed: see
    # the matching note by CreateMadeItem's
    # test_external_source_ignores_manual_part_number above.

    async def test_unchanged_part_number_allowed_even_when_not_editable(self):
        use_case = self._use_case(
            FakeAdminSettingsRepository(self._settings(part_number_editable=False))
        )
        result = await use_case.execute(actor=self.actor, item_id=1, cmd=self._cmd())
        assert result.part_number == self.item.part_number

    async def test_part_number_change_allowed_when_editable(self):
        result = await self.use_case.execute(
            actor=self.actor, item_id=1, cmd=self._cmd(part_number="NEW-1")
        )
        assert result.part_number == "NEW-1"

    async def test_duplicate_part_number_rejected_when_unique(self):
        other = make_made_item(id=2)
        other.part_number = "TAKEN-1"
        self.item_repo._items[2] = other
        with pytest.raises(MadeItemPartNumberDuplicateError):
            await self.use_case.execute(
                actor=self.actor, item_id=1, cmd=self._cmd(part_number="TAKEN-1")
            )

    async def test_renumber_to_pdm_reserved_pattern_rejected_when_pdm_enabled(self):
        settings = self._settings(pdm_part_number_pattern=r"EXT-\d+")
        use_case = self._use_case(
            FakeAdminSettingsRepository(settings, pdm=make_pdm_settings(enabled=True))
        )
        with pytest.raises(PartNumberReservedForPdmError):
            await use_case.execute(
                actor=self.actor, item_id=1, cmd=self._cmd(part_number="EXT-123")
            )

    async def test_renumber_to_pdm_reserved_pattern_accepted_when_pdm_disabled(self):
        settings = self._settings(pdm_part_number_pattern=r"EXT-\d+")
        use_case = self._use_case(FakeAdminSettingsRepository(settings))

        result = await use_case.execute(
            actor=self.actor, item_id=1, cmd=self._cmd(part_number="EXT-123")
        )

        assert result.part_number == "EXT-123"

    async def test_renumber_claims_new_number_in_registry(self):
        await self.use_case.execute(actor=self.actor, item_id=1, cmd=self._cmd(part_number="NEW-1"))
        assert self.registry.entries.get("NEW-1") == "made"

    async def test_renumber_renames_every_row_of_the_family(self):
        # self.item's revision ("A") must stay the newest of the family
        # (len then lexicographic) so this renumber isn't itself
        # blocked by the newest-only gate.
        self.item.part_number = "FAM-1"
        sibling = make_made_item(id=2)
        sibling.part_number = "FAM-1"
        sibling.revision = "0"
        self.item_repo._items[2] = sibling
        await self.registry.claim("FAM-1", "made")

        await self.use_case.execute(actor=self.actor, item_id=1, cmd=self._cmd(part_number="FAM-2"))

        assert self.item_repo.items[1].part_number == "FAM-2"
        assert self.item_repo.items[2].part_number == "FAM-2"
        assert self.registry.entries.get("FAM-1") is None
        assert self.registry.entries.get("FAM-2") == "made"

    async def test_renumber_releases_old_number_when_unused(self):
        self.item.part_number = "OLD-1"
        await self.registry.claim("OLD-1", "made")

        await self.use_case.execute(actor=self.actor, item_id=1, cmd=self._cmd(part_number="NEW-2"))

        assert self.registry.entries.get("OLD-1") is None

    async def test_renumber_registry_pk_collision_maps_to_numbering_conflict(self):
        # Same closing note as CreateMadeItem's matching test, for the
        # renumber path: claim() flushes eagerly, so commit_with_number_
        # retry(..., attempts=1) must wrap the whole write() (not just a
        # bare commit) to catch it.
        class RacingRegistry(FakePartNumberRegistry):
            async def claim(self, part_number: str, kind: str) -> None:
                raise SqlConstraintViolationError(
                    statement="INSERT INTO part_number_registry ...",
                    params={},
                    orig=Exception("UNIQUE constraint failed: part_number_registry.part_number"),
                )

        use_case = UpdateMadeItem(
            self.item_repo,
            self.article_group_repo,
            self.bought_item_repo,
            self.source_item_repo,
            self.admin_settings_repo,
            part_number_registry=RacingRegistry(),
            uow=self.uow,
            customer_repo=FakeCustomerRepository(),
            cad_source=PdmCadSource(self.admin_settings_repo),
        )
        with pytest.raises(NumberingConflictError):
            await use_case.execute(actor=self.actor, item_id=1, cmd=self._cmd(part_number="RACE-1"))

    async def test_newest_only_blocks_field_change_on_older_revision(self):
        self.item.part_number = "FAM-3"
        self.item.revision = "A"
        newest = make_made_item(id=2)
        newest.part_number = "FAM-3"
        newest.revision = "B"
        self.item_repo._items[2] = newest

        with pytest.raises(MadeItemNotNewestRevisionError):
            await self.use_case.execute(
                actor=self.actor,
                item_id=1,
                cmd=self._cmd(part_number="FAM-3", weblink="https://example.com"),
            )

    async def test_newest_only_allows_status_change_on_older_revision(self):
        self.item.part_number = "FAM-4"
        self.item.revision = "A"
        newest = make_made_item(id=2)
        newest.part_number = "FAM-4"
        newest.revision = "B"
        self.item_repo._items[2] = newest

        result = await self.use_case.execute(
            actor=self.actor, item_id=1, cmd=self._cmd(part_number="FAM-4", status="inactive")
        )
        assert result.status == "inactive"

    async def test_newest_only_allows_edit_on_newest_revision(self):
        self.item.part_number = "FAM-5"
        self.item.revision = "B"
        older = make_made_item(id=2)
        older.part_number = "FAM-5"
        older.revision = "A"
        self.item_repo._items[2] = older

        result = await self.use_case.execute(
            actor=self.actor,
            item_id=1,
            cmd=self._cmd(part_number="FAM-5", weblink="https://example.com"),
        )
        assert result.weblink == "https://example.com"

    async def test_newest_only_disabled_by_setting(self):
        self.item.part_number = "FAM-6"
        self.item.revision = "A"
        newest = make_made_item(id=2)
        newest.part_number = "FAM-6"
        newest.revision = "B"
        self.item_repo._items[2] = newest

        use_case = self._use_case(
            FakeAdminSettingsRepository(self._settings(revision_only_newest_editable=False))
        )
        result = await use_case.execute(
            actor=self.actor,
            item_id=1,
            cmd=self._cmd(part_number="FAM-6", weblink="https://example.com"),
        )
        assert result.weblink == "https://example.com"
