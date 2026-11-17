"""
Unit tests for CreateMadeItem.
"""

import pytest

from src.modules.catalogue.application.dto.made_item_dto import CreateMadeItemCommand
from src.modules.catalogue.application.dto.made_item_dto import CreateMadeItemProcessCommand
from src.modules.catalogue.application.use_cases.made_item.create_made_item import CreateMadeItem
from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.errors import ArticleGroupNotFoundError
from src.modules.catalogue.domain.errors import BoughtItemInactiveError
from src.modules.catalogue.domain.errors import BoughtItemNotFoundError
from src.modules.catalogue.domain.errors import FabricationMethodArchivedError
from src.modules.catalogue.domain.errors import FabricationMethodNotFoundError
from src.modules.catalogue.domain.errors import MadeItemPartNumberDuplicateError
from src.modules.catalogue.domain.errors import MaterialSourceConflictError
from src.modules.catalogue.domain.errors import PartNumberReservedForPdmError
from src.modules.catalogue.domain.errors import SourceItemInactiveError
from src.modules.catalogue.domain.errors import SourceItemNotFoundError
from src.modules.catalogue.domain.errors import WebCreationDisabledError
from src.modules.catalogue.domain.policies.item_field_ownership import default_policy
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.external_data.application.services.pdm_cad_source import PdmCadSource
from src.modules.platform.adapters.outbound.persistence.constraint_violation import (
    SqlConstraintViolationError,
)
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import NumberingConflictError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeEventBus
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.made_item._helpers import make_bought_item
from tests.unit.made_item._helpers import make_fabrication_method
from tests.unit.made_item._helpers import make_inspection_method
from tests.unit.made_item._helpers import make_made_item
from tests.unit.made_item._helpers import make_pdm_settings
from tests.unit.made_item._helpers import make_source_item
from tests.unit.made_item.fakes import FakeAdminSettingsRepository
from tests.unit.made_item.fakes import FakeArticleGroupRepository
from tests.unit.made_item.fakes import FakeBoughtItemRepository
from tests.unit.made_item.fakes import FakeCustomerRepository
from tests.unit.made_item.fakes import FakeFabricationMethodRepository
from tests.unit.made_item.fakes import FakeInspectionMethodRepository
from tests.unit.made_item.fakes import FakeMadeItemRepository
from tests.unit.made_item.fakes import FakePartNumberRegistry
from tests.unit.made_item.fakes import FakeSourceItemRepository


class TestCreateMadeItem:
    def setup_method(self):
        self.item_repo = FakeMadeItemRepository()
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
        self.use_case = CreateMadeItem(
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
            cad_source=PdmCadSource(self.admin_settings_repo),
        )

    def _cmd(self, **kwargs) -> CreateMadeItemCommand:
        defaults = dict(revision="A", article_name="Bracket")
        defaults.update(kwargs)
        return CreateMadeItemCommand(**defaults)

    async def test_creates_item_successfully(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.article_name == "Bracket"
        assert result.id > 0

    async def test_event_carries_correct_fields(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        (event,) = self.bus.published
        assert event.item_id == result.id
        assert event.article_name == "Bracket"
        assert event.creator_id == self.actor.id

    async def test_unprivileged_cannot_create(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=self._cmd())

    async def test_missing_article_group_raises(self):
        with pytest.raises(ArticleGroupNotFoundError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(article_group_ids=[99]))

    async def test_missing_source_item_raises(self):
        with pytest.raises(SourceItemNotFoundError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(source_item_id=999))

    async def test_inactive_source_item_raises(self):
        inactive = make_source_item(id=5, status=SourceItemCatalogueStatus.INACTIVE)
        source_item_repo = FakeSourceItemRepository([inactive])
        use_case = CreateMadeItem(
            self.item_repo,
            self.article_group_repo,
            self.bought_item_repo,
            source_item_repo,
            self.fabrication_method_repo,
            self.inspection_method_repo,
            self.admin_settings_repo,
            part_number_registry=self.registry,
            event_bus=self.bus,
            uow=self.uow,
            customer_repo=FakeCustomerRepository(),
            cad_source=PdmCadSource(self.admin_settings_repo),
        )
        with pytest.raises(SourceItemInactiveError):
            await use_case.execute(actor=self.actor, cmd=self._cmd(source_item_id=5))

    async def test_active_source_item_is_accepted(self):
        active = make_source_item(id=5, status=SourceItemCatalogueStatus.ACTIVE)
        source_item_repo = FakeSourceItemRepository([active])
        use_case = CreateMadeItem(
            self.item_repo,
            self.article_group_repo,
            self.bought_item_repo,
            source_item_repo,
            self.fabrication_method_repo,
            self.inspection_method_repo,
            self.admin_settings_repo,
            part_number_registry=self.registry,
            event_bus=self.bus,
            uow=self.uow,
            customer_repo=FakeCustomerRepository(),
            cad_source=PdmCadSource(self.admin_settings_repo),
        )
        result = await use_case.execute(actor=self.actor, cmd=self._cmd(source_item_id=5))
        assert result.source_item_id == 5

    async def test_missing_bought_item_raises(self):
        with pytest.raises(BoughtItemNotFoundError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(bought_item_id=999))

    async def test_inactive_bought_item_raises(self):
        inactive = make_bought_item(id=5, status=BoughtItemCatalogueStatus.INACTIVE)
        bought_item_repo = FakeBoughtItemRepository([inactive])
        use_case = CreateMadeItem(
            self.item_repo,
            self.article_group_repo,
            bought_item_repo,
            self.source_item_repo,
            self.fabrication_method_repo,
            self.inspection_method_repo,
            self.admin_settings_repo,
            part_number_registry=self.registry,
            event_bus=self.bus,
            uow=self.uow,
            customer_repo=FakeCustomerRepository(),
            cad_source=PdmCadSource(self.admin_settings_repo),
        )
        with pytest.raises(BoughtItemInactiveError):
            await use_case.execute(actor=self.actor, cmd=self._cmd(bought_item_id=5))

    async def test_active_bought_item_is_accepted(self):
        active = make_bought_item(id=5, status=BoughtItemCatalogueStatus.ACTIVE)
        bought_item_repo = FakeBoughtItemRepository([active])
        use_case = CreateMadeItem(
            self.item_repo,
            self.article_group_repo,
            bought_item_repo,
            self.source_item_repo,
            self.fabrication_method_repo,
            self.inspection_method_repo,
            self.admin_settings_repo,
            part_number_registry=self.registry,
            event_bus=self.bus,
            uow=self.uow,
            customer_repo=FakeCustomerRepository(),
            cad_source=PdmCadSource(self.admin_settings_repo),
        )
        result = await use_case.execute(actor=self.actor, cmd=self._cmd(bought_item_id=5))
        assert result.bought_item_id == 5

    async def test_auto_numbering_ignores_manual_part_number(self):
        settings = AdminMadeItemSettings(
            id=1,
            item_number_format="MADE-{year}-{seq:04d}",
            lot_number_format="LOT-{year}-{seq:04d}",
            part_number_auto=True,
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
        use_case = CreateMadeItem(
            self.item_repo,
            self.article_group_repo,
            self.bought_item_repo,
            self.source_item_repo,
            self.fabrication_method_repo,
            self.inspection_method_repo,
            FakeAdminSettingsRepository(settings),
            part_number_registry=self.registry,
            event_bus=self.bus,
            uow=self.uow,
            customer_repo=FakeCustomerRepository(),
            cad_source=PdmCadSource(FakeAdminSettingsRepository(settings)),
        )
        result = await use_case.execute(actor=self.actor, cmd=self._cmd(part_number="MANUAL-1"))
        assert result.part_number == "AUTO-1"

    # External numbering is not reachable via settings until it is
    # built around part_number_registry and the external pattern, so
    # no test covers an external source here.

    async def test_manual_part_number_used_when_not_auto(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=self._cmd(part_number="MANUAL-1")
        )
        assert result.part_number == "MANUAL-1"

    async def test_duplicate_part_number_rejected_when_unique(self):
        existing = make_made_item(id=1)
        existing.part_number = "MANUAL-1"
        self.item_repo._items[1] = existing
        settings = AdminMadeItemSettings(
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
        use_case = CreateMadeItem(
            self.item_repo,
            self.article_group_repo,
            self.bought_item_repo,
            self.source_item_repo,
            self.fabrication_method_repo,
            self.inspection_method_repo,
            FakeAdminSettingsRepository(settings),
            part_number_registry=self.registry,
            event_bus=self.bus,
            uow=self.uow,
            customer_repo=FakeCustomerRepository(),
            cad_source=PdmCadSource(FakeAdminSettingsRepository(settings)),
        )
        with pytest.raises(MadeItemPartNumberDuplicateError):
            await use_case.execute(actor=self.actor, cmd=self._cmd(part_number="MANUAL-1"))

    async def test_both_material_sources_rejected(self):
        with pytest.raises(MaterialSourceConflictError):
            await self.use_case.execute(
                actor=self.actor, cmd=self._cmd(bought_item_id=1, source_item_id=1)
            )

    async def test_creates_item_with_processes(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=self._cmd(
                processes=[
                    CreateMadeItemProcessCommand(fabrication_method_id=1, note="Mill"),
                    CreateMadeItemProcessCommand(fabrication_method_id=1, note="Deburr"),
                ]
            ),
        )
        assert [p.note for p in result.processes] == ["Mill", "Deburr"]
        assert [p.position for p in result.processes] == [0, 1]
        assert all(p.made_item_id == result.id for p in result.processes)
        assert self.uow.committed is True

    async def test_creates_item_with_default_grouping_when_no_group_index_given(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=self._cmd(
                processes=[
                    CreateMadeItemProcessCommand(fabrication_method_id=1, note="Mill"),
                    CreateMadeItemProcessCommand(fabrication_method_id=1, note="Deburr"),
                ]
            ),
        )
        # No group_index hint on either staged process -> each is its own group.
        assert [p.group_index for p in result.processes] == [0, 1]

    async def test_creates_item_with_staged_grouping(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=self._cmd(
                processes=[
                    CreateMadeItemProcessCommand(
                        fabrication_method_id=1, note="Sawing", group_index=0
                    ),
                    CreateMadeItemProcessCommand(
                        fabrication_method_id=1, note="Bluing", group_index=1
                    ),
                    CreateMadeItemProcessCommand(
                        fabrication_method_id=1, note="Heat treat", group_index=1
                    ),
                ]
            ),
        )
        assert [p.group_index for p in result.processes] == [0, 1, 1]

    async def test_creates_item_with_non_contiguous_staged_group_index_normalized(self):
        # Malformed input (groups 5 and 2 instead of 0 and 1) still degrades
        # gracefully: two adjacent equal values merge, everything else splits.
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=self._cmd(
                processes=[
                    CreateMadeItemProcessCommand(fabrication_method_id=1, group_index=5),
                    CreateMadeItemProcessCommand(fabrication_method_id=1, group_index=5),
                    CreateMadeItemProcessCommand(fabrication_method_id=1, group_index=2),
                ]
            ),
        )
        assert [p.group_index for p in result.processes] == [0, 0, 1]

    async def test_invalid_process_fabrication_method_raises(self):
        with pytest.raises(FabricationMethodNotFoundError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=self._cmd(processes=[CreateMadeItemProcessCommand(fabrication_method_id=999)]),
            )
        # nothing should have been persisted
        assert len(self.item_repo.items) == 0

    async def test_archived_process_fabrication_method_raises(self):
        fabrication_method_repo = FakeFabricationMethodRepository(
            [make_fabrication_method(id=1), make_fabrication_method(id=2, archived=True)]
        )
        use_case = CreateMadeItem(
            self.item_repo,
            self.article_group_repo,
            self.bought_item_repo,
            self.source_item_repo,
            fabrication_method_repo,
            self.inspection_method_repo,
            self.admin_settings_repo,
            part_number_registry=self.registry,
            event_bus=self.bus,
            uow=self.uow,
            customer_repo=FakeCustomerRepository(),
            cad_source=PdmCadSource(self.admin_settings_repo),
        )
        with pytest.raises(FabricationMethodArchivedError):
            await use_case.execute(
                actor=self.actor,
                cmd=self._cmd(processes=[CreateMadeItemProcessCommand(fabrication_method_id=2)]),
            )
        assert len(self.item_repo.items) == 0

    async def test_claims_manual_part_number_in_registry(self):
        await self.use_case.execute(actor=self.actor, cmd=self._cmd(part_number="MANUAL-9"))
        assert self.registry.entries.get("MANUAL-9") == "made"

    async def test_web_creation_disabled_when_pdm_enabled(self):
        # PDM "on" per is_pdm_enabled() = enabled and is_configured, see
        # make_pdm_settings.
        settings = AdminMadeItemSettings(
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
            web_creation_allowed=False,
            pdm_part_number_pattern="",
        )
        use_case = CreateMadeItem(
            self.item_repo,
            self.article_group_repo,
            self.bought_item_repo,
            self.source_item_repo,
            self.fabrication_method_repo,
            self.inspection_method_repo,
            FakeAdminSettingsRepository(settings, pdm=make_pdm_settings(enabled=True)),
            part_number_registry=self.registry,
            event_bus=self.bus,
            uow=self.uow,
            customer_repo=FakeCustomerRepository(),
            cad_source=PdmCadSource(
                FakeAdminSettingsRepository(settings, pdm=make_pdm_settings(enabled=True))
            ),
        )
        with pytest.raises(WebCreationDisabledError):
            await use_case.execute(actor=self.actor, cmd=self._cmd())

    async def test_web_creation_allowed_when_pdm_disabled_even_if_setting_off(self):
        # FakeAdminSettingsRepository's default pdm is enabled=False, so
        # is_pdm_enabled() is False here regardless of web_creation_allowed.
        settings = AdminMadeItemSettings(
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
            web_creation_allowed=False,
            pdm_part_number_pattern="",
        )
        use_case = CreateMadeItem(
            self.item_repo,
            self.article_group_repo,
            self.bought_item_repo,
            self.source_item_repo,
            self.fabrication_method_repo,
            self.inspection_method_repo,
            FakeAdminSettingsRepository(settings),
            part_number_registry=self.registry,
            event_bus=self.bus,
            uow=self.uow,
            customer_repo=FakeCustomerRepository(),
            cad_source=PdmCadSource(FakeAdminSettingsRepository(settings)),
        )
        result = await use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.id > 0

    async def test_typed_part_number_matching_pdm_pattern_rejected_when_pdm_enabled(self):
        settings = AdminMadeItemSettings(
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
            pdm_part_number_pattern=r"EXT-\d+",
        )
        use_case = CreateMadeItem(
            self.item_repo,
            self.article_group_repo,
            self.bought_item_repo,
            self.source_item_repo,
            self.fabrication_method_repo,
            self.inspection_method_repo,
            FakeAdminSettingsRepository(settings, pdm=make_pdm_settings(enabled=True)),
            part_number_registry=self.registry,
            event_bus=self.bus,
            uow=self.uow,
            customer_repo=FakeCustomerRepository(),
            cad_source=PdmCadSource(
                FakeAdminSettingsRepository(settings, pdm=make_pdm_settings(enabled=True))
            ),
        )
        with pytest.raises(PartNumberReservedForPdmError):
            await use_case.execute(actor=self.actor, cmd=self._cmd(part_number="EXT-123"))

    async def test_typed_part_number_matching_pdm_pattern_accepted_when_pdm_not_configured(self):
        """enabled=True alone is not enough: is_pdm_enabled() also requires
        is_configured, so an enabled-but-unconfigured row behaves as
        disabled here."""
        settings = AdminMadeItemSettings(
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
            pdm_part_number_pattern=r"EXT-\d+",
        )
        pdm = make_pdm_settings(enabled=False)
        pdm.enabled = True  # on, but base_url/vault_name/username/password stay blank
        use_case = CreateMadeItem(
            self.item_repo,
            self.article_group_repo,
            self.bought_item_repo,
            self.source_item_repo,
            self.fabrication_method_repo,
            self.inspection_method_repo,
            FakeAdminSettingsRepository(settings, pdm=pdm),
            part_number_registry=self.registry,
            event_bus=self.bus,
            uow=self.uow,
            customer_repo=FakeCustomerRepository(),
            cad_source=PdmCadSource(FakeAdminSettingsRepository(settings, pdm=pdm)),
        )
        result = await use_case.execute(actor=self.actor, cmd=self._cmd(part_number="EXT-123"))
        assert result.part_number == "EXT-123"

    async def test_typed_part_number_not_matching_pdm_pattern_is_accepted(self):
        settings = AdminMadeItemSettings(
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
            pdm_part_number_pattern=r"EXT-\d+",
        )
        use_case = CreateMadeItem(
            self.item_repo,
            self.article_group_repo,
            self.bought_item_repo,
            self.source_item_repo,
            self.fabrication_method_repo,
            self.inspection_method_repo,
            FakeAdminSettingsRepository(settings, pdm=make_pdm_settings(enabled=True)),
            part_number_registry=self.registry,
            event_bus=self.bus,
            uow=self.uow,
            customer_repo=FakeCustomerRepository(),
            cad_source=PdmCadSource(
                FakeAdminSettingsRepository(settings, pdm=make_pdm_settings(enabled=True))
            ),
        )
        result = await use_case.execute(actor=self.actor, cmd=self._cmd(part_number="INT-1"))
        assert result.part_number == "INT-1"

    async def test_auto_generated_part_number_never_checked_against_pdm_pattern(self):
        settings = AdminMadeItemSettings(
            id=1,
            item_number_format="MADE-{year}-{seq:04d}",
            lot_number_format="LOT-{year}-{seq:04d}",
            part_number_auto=True,
            part_number_editable=True,
            revision_start="0",
            revision_separator=":",
            revision_skip_ambiguous_letters=False,
            revision_only_newest_editable=True,
            revision_predecessor_status_web="ask",
            revision_predecessor_status_pdm="replaced",
            revision_field_policy=default_policy(),
            web_creation_allowed=True,
            # Matches the fake registry's own "AUTO-{n}" output, so if the
            # auto-generated value actually were checked, this would raise.
            pdm_part_number_pattern=r"AUTO-\d+",
        )
        use_case = CreateMadeItem(
            self.item_repo,
            self.article_group_repo,
            self.bought_item_repo,
            self.source_item_repo,
            self.fabrication_method_repo,
            self.inspection_method_repo,
            FakeAdminSettingsRepository(settings, pdm=make_pdm_settings(enabled=True)),
            part_number_registry=self.registry,
            event_bus=self.bus,
            uow=self.uow,
            customer_repo=FakeCustomerRepository(),
            cad_source=PdmCadSource(
                FakeAdminSettingsRepository(settings, pdm=make_pdm_settings(enabled=True))
            ),
        )
        result = await use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.part_number == "AUTO-1"

    async def test_registry_pk_collision_from_claim_maps_to_numbering_conflict(self):
        # Closes the previous worker's untested-constraint note:
        # IPartNumberRegistry.claim() flushes eagerly (see
        # part_number_registry_repository.py), so a genuine race raises
        # the IntegrityError from *inside* claim() itself, before any
        # later uow.commit() call. This proves commit_with_number_retry
        # (which wraps the whole write(), not just a bare commit) still
        # maps it to a clean NumberingConflictError (409) instead of a raw
        # 500.
        class RacingRegistry(FakePartNumberRegistry):
            async def claim(self, part_number: str, kind: str) -> None:
                raise SqlConstraintViolationError(
                    statement="INSERT INTO part_number_registry ...",
                    params={},
                    orig=Exception("UNIQUE constraint failed: part_number_registry.part_number"),
                )

        use_case = CreateMadeItem(
            self.item_repo,
            self.article_group_repo,
            self.bought_item_repo,
            self.source_item_repo,
            self.fabrication_method_repo,
            self.inspection_method_repo,
            self.admin_settings_repo,
            part_number_registry=RacingRegistry(),
            event_bus=self.bus,
            uow=self.uow,
            customer_repo=FakeCustomerRepository(),
            cad_source=PdmCadSource(self.admin_settings_repo),
        )
        with pytest.raises(NumberingConflictError):
            await use_case.execute(actor=self.actor, cmd=self._cmd(part_number="RACE-1"))
