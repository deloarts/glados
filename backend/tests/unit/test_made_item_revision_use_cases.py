"""
Unit tests for the made-item revision use cases (GetMadeItemRevisions,
CreateMadeItemRevision). No database, no HTTP. Reuses the fakes and entity
builders from tests/unit/made_item/ rather than re-declaring them, since
CreateMadeItemRevision shares CreateMadeItem's validation/process-
construction helpers and depends on the exact same repository shapes.
"""

import pytest

from src.modules.catalogue.application.dto.made_item_dto import CreateMadeItemProcessCommand
from src.modules.catalogue.application.dto.made_item_dto import CreateMadeItemRevisionCommand
from src.modules.catalogue.application.dto.made_item_dto import MadeItemRevisionItemCommand
from src.modules.catalogue.application.use_cases.made_item.create_made_item_revision import (
    CreateMadeItemRevision,
)
from src.modules.catalogue.application.use_cases.made_item.get_made_item_revisions import (
    GetMadeItemRevisions,
)
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.domain.errors import MadeItemNotNewestRevisionError
from src.modules.catalogue.domain.errors import MadeItemPartNumberDuplicateError
from src.modules.catalogue.domain.errors import MadeItemRevisionManagedByPdmError
from src.modules.catalogue.domain.errors import RevisionNotIncrementableError
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeEventBus
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.made_item._helpers import make_article_group
from tests.unit.made_item._helpers import make_bought_item
from tests.unit.made_item._helpers import make_fabrication_method
from tests.unit.made_item._helpers import make_inspection_method
from tests.unit.made_item._helpers import make_made_item
from tests.unit.made_item.fakes import FakeAdminSettingsRepository
from tests.unit.made_item.fakes import FakeArticleGroupRepository
from tests.unit.made_item.fakes import FakeBoughtItemRepository
from tests.unit.made_item.fakes import FakeCustomerRepository
from tests.unit.made_item.fakes import FakeFabricationMethodRepository
from tests.unit.made_item.fakes import FakeInspectionMethodRepository
from tests.unit.made_item.fakes import FakeMadeItemRepository
from tests.unit.made_item.fakes import FakePartNumberRegistry
from tests.unit.made_item.fakes import FakeSourceItemRepository

# ── GetMadeItemRevisions ─────────────────────────────────────────────


class TestGetMadeItemRevisions:
    def setup_method(self):
        self.item = make_made_item(id=1)
        self.item_repo = FakeMadeItemRepository([self.item])
        self.admin_settings_repo = FakeAdminSettingsRepository()
        self.actor = make_user(permissions=[Permission.WRITE_MADE_ITEMS])
        self.use_case = GetMadeItemRevisions(self.item_repo, self.admin_settings_repo)

    async def test_not_found_raises(self):
        with pytest.raises(MadeItemNotFoundError):
            await self.use_case.execute(actor=self.actor, item_id=999)

    async def test_null_part_number_returns_only_itself(self):
        # self.item.part_number is None by default.
        result = await self.use_case.execute(actor=self.actor, item_id=1)
        assert [i.id for i in result.items] == [1]
        assert result.items[0].is_newest is True
        assert result.next_revision == "B"  # increments off its own revision "A"
        assert result.can_create is True
        assert result.reason is None

    async def test_returns_siblings_newest_first(self):
        self.item.part_number = "FAM-1"
        self.item.revision = "0"
        older = make_made_item(id=2)
        older.part_number = "FAM-1"
        older.revision = "1"
        newest = make_made_item(id=3)
        newest.part_number = "FAM-1"
        newest.revision = "10"
        self.item_repo._items[2] = older
        self.item_repo._items[3] = newest

        result = await self.use_case.execute(actor=self.actor, item_id=1)

        assert [i.id for i in result.items] == [3, 2, 1]
        assert [i.is_newest for i in result.items] == [True, False, False]
        assert result.next_revision == "11"

    async def test_next_revision_error_when_unparseable(self):
        self.item.revision = "A.1"
        result = await self.use_case.execute(actor=self.actor, item_id=1)
        assert result.next_revision is None
        assert result.next_revision_error is not None
        assert result.can_create is False
        assert result.reason is None

    async def test_reason_no_write_when_actor_lacks_permission(self):
        actor = make_user(permissions=[])
        result = await self.use_case.execute(actor=actor, item_id=1)
        assert result.reason == "no_write"
        assert result.can_create is False

    async def test_reason_cad_when_item_is_cad(self):
        self.item.data_source = DataSource.CAD
        result = await self.use_case.execute(actor=self.actor, item_id=1)
        assert result.reason == "cad"
        assert result.can_create is False

    async def test_no_write_takes_priority_over_cad(self):
        # CreateMadeItemRevision's own gate order is assert_can_update then
        # the CAD check. A user without write:made_items would hit that
        # gate first, so GetMadeItemRevisions reports the same priority.
        self.item.data_source = DataSource.CAD
        actor = make_user(permissions=[])
        result = await self.use_case.execute(actor=actor, item_id=1)
        assert result.reason == "no_write"


# ── CreateMadeItemRevision ───────────────────────────────────────────


class TestCreateMadeItemRevision:
    def setup_method(self):
        self.item = make_made_item(id=1)
        self.item.part_number = "FAM-1"
        self.item.revision = "A"
        self.item_repo = FakeMadeItemRepository([self.item])
        self.article_group_repo = FakeArticleGroupRepository()
        self.bought_item_repo = FakeBoughtItemRepository()
        self.source_item_repo = FakeSourceItemRepository()
        self.fabrication_method_repo = FakeFabricationMethodRepository(
            [make_fabrication_method(id=1)]
        )
        self.inspection_method_repo = FakeInspectionMethodRepository([make_inspection_method(id=1)])
        self.admin_settings_repo = FakeAdminSettingsRepository()
        self.registry = FakePartNumberRegistry()
        self.actor = make_user(permissions=[Permission.WRITE_MADE_ITEMS])
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.use_case = CreateMadeItemRevision(
            self.item_repo,
            self.article_group_repo,
            self.bought_item_repo,
            self.source_item_repo,
            self.fabrication_method_repo,
            self.inspection_method_repo,
            self.admin_settings_repo,
            part_number_registry=self.registry,
            event_bus=self.bus,
            uow=self.uow,
            customer_repo=FakeCustomerRepository(),
        )

    def _cmd(
        self, predecessor_status: str = "replaced", **item_kwargs
    ) -> CreateMadeItemRevisionCommand:
        defaults = dict(article_name="Bracket")
        defaults.update(item_kwargs)
        return CreateMadeItemRevisionCommand(
            predecessor_status=predecessor_status,
            item=MadeItemRevisionItemCommand(**defaults),
        )

    async def test_not_found_raises(self):
        with pytest.raises(MadeItemNotFoundError):
            await self.use_case.execute(actor=self.actor, item_id=999, cmd=self._cmd())

    async def test_unprivileged_cannot_create(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, item_id=1, cmd=self._cmd())

    async def test_cad_item_rejected(self):
        self.item.data_source = DataSource.CAD
        with pytest.raises(MadeItemRevisionManagedByPdmError):
            await self.use_case.execute(actor=self.actor, item_id=1, cmd=self._cmd())

    async def test_not_newest_rejected(self):
        newest = make_made_item(id=2)
        newest.part_number = "FAM-1"
        newest.revision = "B"
        self.item_repo._items[2] = newest

        with pytest.raises(MadeItemNotNewestRevisionError):
            await self.use_case.execute(actor=self.actor, item_id=1, cmd=self._cmd())

    async def test_increments_revision_and_shares_part_number(self):
        result = await self.use_case.execute(actor=self.actor, item_id=1, cmd=self._cmd())
        assert result.revision == "B"
        assert result.part_number == "FAM-1"
        assert result.status == MadeItemCatalogueStatus.ACTIVE.value
        assert result.data_source == "WEB"
        assert result.creator_id == self.actor.id
        assert result.successor_item_id is None
        assert result.changes  # fresh, non-empty changelog

    async def test_registers_family_once_not_twice(self):
        await self.registry.claim("FAM-1", "made")
        # assert_family is a no-op when already registered as "made",
        # must not raise PartNumberInUseError.
        result = await self.use_case.execute(actor=self.actor, item_id=1, cmd=self._cmd())
        assert result.id > 0

    async def test_null_part_number_increments_from_own_revision(self):
        self.item.part_number = None
        result = await self.use_case.execute(actor=self.actor, item_id=1, cmd=self._cmd())
        assert result.part_number is None
        assert result.revision == "B"

    async def test_files_are_not_copied(self):
        # MadeItemResult does not expose `files` (see MadeItemMapper), so the
        # entity itself is the source of truth for what was actually saved.
        result = await self.use_case.execute(actor=self.actor, item_id=1, cmd=self._cmd())
        assert self.item_repo.items[result.id].files == []

    async def test_copies_article_groups_and_material_source(self):
        self.article_group_repo._groups[5] = make_article_group(id=5)
        bought = make_bought_item(id=7)
        self.bought_item_repo._items[7] = bought

        result = await self.use_case.execute(
            actor=self.actor,
            item_id=1,
            cmd=self._cmd(article_group_ids=[5], bought_item_id=7),
        )
        saved = self.item_repo._items[result.id]
        assert saved.article_group_ids == [5]
        assert result.bought_item_id == 7

    async def test_copies_processes_with_grouping(self):
        result = await self.use_case.execute(
            actor=self.actor,
            item_id=1,
            cmd=self._cmd(
                processes=[
                    CreateMadeItemProcessCommand(
                        fabrication_method_id=1, note="Sawing", group_index=0
                    ),
                    CreateMadeItemProcessCommand(
                        fabrication_method_id=1, note="Milling", group_index=1
                    ),
                    CreateMadeItemProcessCommand(
                        fabrication_method_id=1, note="Deburr", group_index=1
                    ),
                ]
            ),
        )
        assert [p.note for p in result.processes] == ["Sawing", "Milling", "Deburr"]
        assert [p.group_index for p in result.processes] == [0, 1, 1]
        assert all(p.made_item_id == result.id for p in result.processes)

    async def test_predecessor_replaced_sets_successor_link(self):
        result = await self.use_case.execute(
            actor=self.actor, item_id=1, cmd=self._cmd(predecessor_status="replaced")
        )
        predecessor = await self.item_repo.get_by_id(1)
        assert predecessor.status == "replaced"
        assert predecessor.successor_item_id == result.id

    async def test_predecessor_inactive_has_no_successor_link(self):
        await self.use_case.execute(
            actor=self.actor, item_id=1, cmd=self._cmd(predecessor_status="inactive")
        )
        predecessor = await self.item_repo.get_by_id(1)
        assert predecessor.status == "inactive"
        assert predecessor.successor_item_id is None

    async def test_predecessor_active_stays_active_no_successor_link(self):
        await self.use_case.execute(
            actor=self.actor, item_id=1, cmd=self._cmd(predecessor_status="active")
        )
        predecessor = await self.item_repo.get_by_id(1)
        assert predecessor.status == "active"
        assert predecessor.successor_item_id is None

    async def test_system_actor_revise_overrides_existing_successor_with_note(self):
        # PDM ingest's revise path (IngestPdmFile._made_revise) always
        # runs as the system actor and always overrides the predecessor's
        # successor when predecessor_status resolves to "replaced": when
        # a human had already set a DIFFERENT successor on that row, the
        # override gets its own changelog line naming the old value.
        self.item.successor_item_id = 999
        system_actor = make_user(id=2, username="system", is_systemuser=True)
        result = await self.use_case.execute(
            actor=system_actor, item_id=1, cmd=self._cmd(predecessor_status="replaced")
        )
        predecessor = await self.item_repo.get_by_id(1)
        assert predecessor.successor_item_id == result.id
        assert any(
            "successor changed from item #999" in line.lower() for line in predecessor.changes
        )

    async def test_system_actor_revise_no_note_when_successor_was_already_unset(self):
        system_actor = make_user(id=2, username="system", is_systemuser=True)
        await self.use_case.execute(
            actor=system_actor, item_id=1, cmd=self._cmd(predecessor_status="replaced")
        )
        predecessor = await self.item_repo.get_by_id(1)
        assert not any("successor changed from" in line.lower() for line in predecessor.changes)

    async def test_human_actor_revise_overrides_successor_without_a_note(self):
        # A human-triggered "New revision" carries no override note: an
        # explicit predecessor_status of "replaced" there is itself the
        # deliberate action, not a PDM-driven override of something a
        # human set earlier.
        self.item.data_source = DataSource.WEB
        self.item.successor_item_id = 999
        await self.use_case.execute(
            actor=self.actor, item_id=1, cmd=self._cmd(predecessor_status="replaced")
        )
        predecessor = await self.item_repo.get_by_id(1)
        assert not any("successor changed from" in line.lower() for line in predecessor.changes)

    async def test_explicit_revision_seam_skips_increment(self):
        cmd = self._cmd()
        cmd.revision = "Z9"
        result = await self.use_case.execute(actor=self.actor, item_id=1, cmd=cmd)
        assert result.revision == "Z9"

    async def test_explicit_revision_still_uniqueness_checked(self):
        # self.item ("B", after this override) must stay the family's
        # newest or the not-newest gate fires before the duplicate check
        # ever runs; the explicit revision ("A") collides with an older,
        # non-newest sibling instead.
        self.item.revision = "B"
        sibling = make_made_item(id=2)
        sibling.part_number = "FAM-1"
        sibling.revision = "A"
        self.item_repo._items[2] = sibling

        cmd = self._cmd()
        cmd.revision = "A"
        with pytest.raises(MadeItemPartNumberDuplicateError):
            await self.use_case.execute(actor=self.actor, item_id=1, cmd=cmd)

    async def test_data_source_override_seam(self):
        cmd = self._cmd()
        cmd.data_source = "CAD"
        result = await self.use_case.execute(actor=self.actor, item_id=1, cmd=cmd)
        assert result.data_source == "CAD"

    async def test_unparseable_revision_raises_409(self):
        self.item.revision = "A.1"
        with pytest.raises(RevisionNotIncrementableError):
            await self.use_case.execute(actor=self.actor, item_id=1, cmd=self._cmd())

    async def test_publishes_made_item_created_event(self):
        result = await self.use_case.execute(actor=self.actor, item_id=1, cmd=self._cmd())
        (event,) = self.bus.published
        assert event.item_id == result.id
        assert event.creator_id == self.actor.id
