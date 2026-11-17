"""
Unit tests for bought item catalogue use cases (create, update, delete).
No database, no HTTP. All dependencies replaced with in-memory fakes.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from src.modules.catalogue.application.dto.bought_item_dto import CreateBoughtItemCommand
from src.modules.catalogue.application.dto.bought_item_dto import UpdateBoughtItemCommand
from src.modules.catalogue.application.use_cases.bought_item.archive_bought_item import (
    ArchiveBoughtItem,
)
from src.modules.catalogue.application.use_cases.bought_item.create_bought_item import (
    CreateBoughtItem,
)
from src.modules.catalogue.application.use_cases.bought_item.get_bought_item import GetBoughtItem
from src.modules.catalogue.application.use_cases.bought_item.restore_bought_item import (
    RestoreBoughtItem,
)
from src.modules.catalogue.application.use_cases.bought_item.update_bought_item import (
    UpdateBoughtItem,
)
from src.modules.catalogue.domain.entities.admin_settings.orders import AdminOrderSettings
from src.modules.catalogue.domain.entities.article_group import ArticleGroup
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.part_number_registry import PartNumberRegistryEntry
from src.modules.catalogue.domain.entities.supplier import Supplier
from src.modules.catalogue.domain.errors import ArticleGroupNotFoundError
from src.modules.catalogue.domain.errors import BoughtItemGtinDuplicateError
from src.modules.catalogue.domain.errors import BoughtItemNotFoundError
from src.modules.catalogue.domain.errors import BoughtItemPartNumberDuplicateError
from src.modules.catalogue.domain.errors import BoughtItemPartNumberNotEditableError
from src.modules.catalogue.domain.errors import PartNumberInUseError
from src.modules.catalogue.domain.errors import PartNumberReservedForPdmError
from src.modules.catalogue.domain.errors import SupplierNotFoundError
from src.modules.catalogue.domain.errors import WebCreationDisabledError
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.catalogue.domain.value_objects.supplier_level import SupplierLevel
from src.modules.catalogue.ports.outbound.catalogue_queries import ArticleGroupFilterDto
from src.modules.catalogue.ports.outbound.catalogue_queries import BoughtItemFilterDto
from src.modules.catalogue.ports.outbound.catalogue_queries import SupplierFilterDto
from src.modules.external_data.application.services.pdm_cad_source import PdmCadSource
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.platform.adapters.outbound.persistence.constraint_violation import (
    SqlConstraintViolationError,
)
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import NumberingConflictError
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user

# ── Helpers ───────────────────────────────────────────────────────────


def make_supplier(id: int = 1, name: str = "Acme") -> Supplier:
    return Supplier(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=False,
        name=name,
        legal_name=None,
        vat_id=None,
        level=SupplierLevel.B,
        capability_ids=[],
        article_group_ids=[],
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
        creator_id=1,
    )


def make_article_group(id: int = 1, name: str = "Bolts") -> ArticleGroup:
    return ArticleGroup(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=False,
        name=name,
        label_color="#999999",
        label_font_color="#000000",
        description="",
        creator_id=1,
    )


def make_bought_item(
    id: int = 1,
    article_name: str = "Hex Bolt M8",
    status: BoughtItemCatalogueStatus = BoughtItemCatalogueStatus.ACTIVE,
    archived: bool = False,
    manufacturer_id: int = 1,
    data_source: DataSource = DataSource.WEB,
) -> BoughtItem:
    return BoughtItem(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=archived,
        article_name=article_name,
        order_code_1="ORD-001",
        order_code_2=None,
        gtin=None,
        ean=None,
        tariff_number=None,
        status=status,
        data_source=data_source,
        part_number=None,
        mass=None,
        note=None,
        weblink=None,
        files=[],
        creator_id=1,
        approver_id=None,
        manufacturer_id=manufacturer_id,
        article_group_ids=[],
        successor_item_id=None,
    )


class FakeBoughtItemRepository:
    def __init__(self, items: list[BoughtItem] | None = None):
        self._items: dict[int, BoughtItem] = {}
        self._next_id = 1
        for i in items or []:
            self._items[i.id] = i
            self._next_id = max(self._next_id, i.id + 1)
        self.merged_article_groups: list[tuple[int, int]] = []

    async def get_by_id(self, id: int) -> BoughtItem | None:
        return self._items.get(id)

    async def lock_for_update(self, id: int) -> None:
        return None

    async def get_by_part_number(self, part_number: str) -> BoughtItem | None:
        return next((i for i in self._items.values() if i.part_number == part_number), None)

    async def get_by_gtin(self, gtin: str) -> BoughtItem | None:
        return next((i for i in self._items.values() if i.gtin == gtin and not i.archived), None)

    async def save(self, item: BoughtItem) -> BoughtItem:
        if item.id == 0:
            item.id = self._next_id
            self._next_id += 1
        self._items[item.id] = item
        return item

    async def get_multi(self, filters: BoughtItemFilterDto) -> tuple[int, list[BoughtItem]]:
        raise NotImplementedError

    async def delete(self, item: BoughtItem) -> None:
        self._items.pop(item.id, None)

    async def merge_demand_items(self, source_id: int, target_id: int) -> None:
        pass

    async def merge_order_items(self, source_id: int, target_id: int) -> None:
        pass

    async def merge_substitutions(self, source_id: int, target_id: int) -> None:
        pass

    async def merge_lot_sources(self, source_id: int, target_id: int) -> None:
        pass

    async def merge_source_demands(self, source_id: int, target_id: int) -> None:
        pass

    async def merge_catalogue_references(self, source_id: int, target_id: int) -> None:
        pass

    async def merge_article_groups(self, source_id: int, target_id: int) -> None:
        self.merged_article_groups.append((source_id, target_id))


class FakeBoughtItemFileRepository:
    """Mirrors tests/unit/made_item/fakes.py::FakeMadeItemFileRepository,
    only needed by MergeBoughtItem's enforcement tests."""

    def __init__(self, files: list | None = None):
        self._files = {f.id: f for f in (files or [])}

    async def get_by_id(self, id: int):
        return self._files.get(id)

    async def get_by_item_id(self, item_id: int) -> list:
        return [f for f in self._files.values() if f.bought_item_id == item_id]

    async def get_by_item_ids(self, item_ids: list[int]) -> list:
        return [f for f in self._files.values() if f.bought_item_id in item_ids]

    async def get_by_item_id_and_category(self, item_id: int, category) -> list:
        raise NotImplementedError

    async def save(self, file):
        raise NotImplementedError

    async def reassign(self, file_id: int, target_item_id: int) -> None:
        if file_id in self._files:
            self._files[file_id].bought_item_id = target_item_id

    async def delete(self, file) -> None:
        self._files.pop(file.id, None)


class FakeSupplierRepository:
    def __init__(self, suppliers: list[Supplier] | None = None):
        self._suppliers: dict[int, Supplier] = {s.id: s for s in (suppliers or [])}

    async def get_by_id(self, id: int) -> Supplier | None:
        return self._suppliers.get(id)

    async def get_by_vat_id(self, vat_id: str) -> Supplier | None:
        raise NotImplementedError

    async def get_multi(self, filters: SupplierFilterDto) -> tuple[int, list[Supplier]]:
        raise NotImplementedError

    async def save(self, supplier: Supplier) -> Supplier:
        raise NotImplementedError

    async def delete(self, supplier: Supplier) -> None:
        raise NotImplementedError


class FakeArticleGroupRepository:
    def __init__(self, groups: list[ArticleGroup] | None = None):
        self._groups: dict[int, ArticleGroup] = {g.id: g for g in (groups or [])}

    async def get_by_id(self, id: int) -> ArticleGroup | None:
        return self._groups.get(id)

    async def get_by_ids(self, ids: list[int]) -> list[ArticleGroup]:
        return [self._groups[i] for i in ids if i in self._groups]

    async def get_live_names(self) -> list[tuple[int, LocalizedText]]:
        raise NotImplementedError

    async def get_multi(self, filters: ArticleGroupFilterDto) -> tuple[int, list[ArticleGroup]]:
        raise NotImplementedError

    async def save(self, article_group: ArticleGroup) -> ArticleGroup:
        raise NotImplementedError

    async def delete(self, article_group: ArticleGroup) -> None:
        raise NotImplementedError


# ── CreateBoughtItem ──────────────────────────────────────────────────


class FakeEventBus:
    def __init__(self):
        self.published = []

    async def publish(self, event):
        self.published.append(event)


class FakeUnitOfWork:
    def __init__(self):
        self.committed = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass


def make_pdm_settings(
    *, enabled: bool = False, cad_items_read_only: bool = True
) -> AdminPdmSettings:
    """is_pdm_enabled() is `enabled and is_configured`, so a caller that
    wants PDM "on" for a test must supply a fully configured connection
    too, not just enabled=True; mirrors AdminPdmSettings.is_configured."""
    return AdminPdmSettings(
        id=1,
        made_item_variable_map={},
        bought_item_variable_map={},
        enabled=enabled,
        base_url="http://pdm-host:65453" if enabled else "",
        vault_name="MyVault" if enabled else "",
        username="svc-account" if enabled else "",
        password="secret" if enabled else None,
        verify_certificate=True,
        timeout_seconds=15,
        session_token=None,
        session_user_id=None,
        session_obtained_at=None,
        watched_folders=[],
        made_released_state_ids=[],
        made_obsolete_state_ids=[],
        made_replaced_state_ids=[],
        bought_released_state_ids=[],
        bought_obsolete_state_ids=[],
        bought_replaced_state_ids=[],
        poll_interval_minutes=15,
        vault_id="",
        cad_items_read_only=cad_items_read_only,
        last_poll_at=None,
        last_poll_error=None,
        last_poll_summary=None,
        writeback_enabled=False,
        made_item_extensions=["sldprt"],
        bought_item_extensions=["sldprt", "sldasm"],
        document_categories={"pdf": "drawing", "dxf": "dxf", "step": "step", "stp": "step"},
        thumbnails_enabled=False,
        stuck_after_days=7,
        reconcile_requested_deep=None,
        required_fields={"made": [], "bought": []},
    )


class FakeAdminSettingsRepository:
    def __init__(
        self, orders: AdminOrderSettings | None = None, pdm: AdminPdmSettings | None = None
    ):
        self._orders = orders or AdminOrderSettings(
            id=1,
            order_number_format="ORD-{year}-{seq:04d}",
            part_number_format="PN-{year}-{seq:04d}",
            part_number_auto=False,
            part_number_editable=True,
            web_creation_allowed=True,
            pdm_part_number_pattern="",
        )
        self._pdm = pdm or make_pdm_settings(enabled=False)

    async def get_orders(self) -> AdminOrderSettings:
        return self._orders

    async def get_pdm(self) -> AdminPdmSettings:
        return self._pdm


class FakePartNumberRegistry:
    """In-memory IPartNumberRegistry: mirrors the shared made/bought
    sequence and the claim/assert_family conflict semantics without a
    database. See tests/unit/test_part_number_registry.py for the
    contract this pins."""

    def __init__(self) -> None:
        self._entries: dict[str, str] = {}
        self._next_seq = 1

    @property
    def entries(self) -> dict[str, str]:
        """Each claimed part number with the kind it is claimed for, for assertions."""
        return self._entries

    async def owner_of(self, part_number: str) -> PartNumberRegistryEntry | None:
        kind = self._entries.get(part_number)
        if kind is None:
            return None
        return PartNumberRegistryEntry(
            part_number=part_number, kind=ItemKind(kind), created=date(2026, 1, 1)
        )

    async def claim(self, part_number: str, kind: str) -> None:
        existing = self._entries.get(part_number)
        if existing is not None:
            raise PartNumberInUseError(
                f"Part number {part_number!r} is already registered to {existing!r}."
            )
        self._entries[part_number] = kind

    async def assert_family(self, part_number: str, kind: str) -> None:
        existing = self._entries.get(part_number)
        if existing is None:
            await self.claim(part_number, kind)
            return
        if existing != kind:
            raise PartNumberInUseError(
                f"Part number {part_number!r} is already registered to {existing!r}."
            )

    async def release_if_unused(self, part_number: str) -> None:
        self._entries.pop(part_number, None)

    async def next_part_number(self, template: str) -> str:
        value = f"AUTO-{self._next_seq}"
        self._next_seq += 1
        return value


class TestGetBoughtItem:
    """pdm_locked_fields is computed the same way
    UpdateBoughtItem's own write-path enforcement is; see
    tests/unit/made_item/test_get_made_item.py::TestGetMadeItem's matching
    coverage."""

    async def test_locked_fields_empty_without_an_actor(self):
        item_repo = FakeBoughtItemRepository([make_bought_item(id=1, data_source=DataSource.CAD)])
        settings_repo = FakeAdminSettingsRepository(pdm=make_pdm_settings(enabled=True))
        use_case = GetBoughtItem(bought_item_repo=item_repo, cad_source=PdmCadSource(settings_repo))

        result = await use_case.execute(item_id=1)

        assert result.pdm_locked_fields == []

    async def test_locked_fields_empty_when_pdm_disabled(self):
        item_repo = FakeBoughtItemRepository([make_bought_item(id=1, data_source=DataSource.CAD)])
        settings_repo = FakeAdminSettingsRepository()  # enabled=False by default
        use_case = GetBoughtItem(bought_item_repo=item_repo, cad_source=PdmCadSource(settings_repo))

        result = await use_case.execute(item_id=1, actor=make_user())

        assert result.pdm_locked_fields == []

    async def test_locked_fields_empty_for_a_web_row_even_when_enforced(self):
        item_repo = FakeBoughtItemRepository([make_bought_item(id=1, data_source=DataSource.WEB)])
        settings_repo = FakeAdminSettingsRepository(pdm=make_pdm_settings(enabled=True))
        use_case = GetBoughtItem(bought_item_repo=item_repo, cad_source=PdmCadSource(settings_repo))

        result = await use_case.execute(item_id=1, actor=make_user())

        assert result.pdm_locked_fields == []

    async def test_locked_fields_populated_for_a_cad_row_when_enforced(self):
        item_repo = FakeBoughtItemRepository([make_bought_item(id=1, data_source=DataSource.CAD)])
        settings_repo = FakeAdminSettingsRepository(pdm=make_pdm_settings(enabled=True))
        use_case = GetBoughtItem(bought_item_repo=item_repo, cad_source=PdmCadSource(settings_repo))

        result = await use_case.execute(item_id=1, actor=make_user())

        assert "part_number" in result.pdm_locked_fields
        assert "order_code_1" in result.pdm_locked_fields

    async def test_locked_fields_empty_for_a_cad_row_when_override_off(self):
        item_repo = FakeBoughtItemRepository([make_bought_item(id=1, data_source=DataSource.CAD)])
        settings_repo = FakeAdminSettingsRepository(
            pdm=make_pdm_settings(enabled=True, cad_items_read_only=False)
        )
        use_case = GetBoughtItem(bought_item_repo=item_repo, cad_source=PdmCadSource(settings_repo))

        result = await use_case.execute(item_id=1, actor=make_user())

        assert result.pdm_locked_fields == []

    async def test_locked_fields_empty_for_the_system_user(self):
        item_repo = FakeBoughtItemRepository([make_bought_item(id=1, data_source=DataSource.CAD)])
        settings_repo = FakeAdminSettingsRepository(pdm=make_pdm_settings(enabled=True))
        use_case = GetBoughtItem(bought_item_repo=item_repo, cad_source=PdmCadSource(settings_repo))

        result = await use_case.execute(item_id=1, actor=make_user(is_systemuser=True))

        assert result.pdm_locked_fields == []

    async def test_lookup_by_unknown_item_id_raises(self):
        item_repo = FakeBoughtItemRepository([])
        settings_repo = FakeAdminSettingsRepository()
        use_case = GetBoughtItem(bought_item_repo=item_repo, cad_source=PdmCadSource(settings_repo))

        with pytest.raises(BoughtItemNotFoundError):
            await use_case.execute(item_id=999)


class TestCreateBoughtItem:
    def setup_method(self):
        self.supplier = make_supplier(id=1)
        self.item_repo = FakeBoughtItemRepository()
        self.supplier_repo = FakeSupplierRepository([self.supplier])
        self.article_group_repo = FakeArticleGroupRepository()
        self.admin_settings_repo = FakeAdminSettingsRepository()
        self.registry = FakePartNumberRegistry()
        self.actor = make_user(permissions=[Permission.WRITE_BOUGHT_ITEMS])
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.use_case = self._use_case(self.admin_settings_repo, self.article_group_repo)

    def _use_case(
        self,
        admin_settings_repo: "FakeAdminSettingsRepository",
        article_group_repo: FakeArticleGroupRepository | None = None,
    ) -> CreateBoughtItem:
        return CreateBoughtItem(
            self.item_repo,
            self.supplier_repo,
            article_group_repo if article_group_repo is not None else self.article_group_repo,
            admin_settings_repo,
            part_number_registry=self.registry,
            event_bus=self.bus,
            uow=self.uow,
            cad_source=PdmCadSource(admin_settings_repo),
        )

    def _cmd(self, **kwargs) -> CreateBoughtItemCommand:
        defaults = dict(order_code_1="ORD-NEW", article_name="Widget", manufacturer_id=1)
        defaults.update(kwargs)
        return CreateBoughtItemCommand(**defaults)

    async def test_creates_item_successfully(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.article_name == "Widget"
        assert result.id > 0

    async def test_event_carries_correct_fields(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        (event,) = self.bus.published
        assert event.item_id == result.id
        assert event.article_name == "Widget"
        assert event.creator_id == self.actor.id

    async def test_unprivileged_cannot_create(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=self._cmd())

    async def test_missing_supplier_raises(self):
        with pytest.raises(SupplierNotFoundError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(manufacturer_id=999))

    async def test_missing_article_group_raises(self):
        with pytest.raises(ArticleGroupNotFoundError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(article_group_ids=[99]))

    async def test_valid_article_group_is_accepted(self):
        group = make_article_group(id=5)
        article_group_repo = FakeArticleGroupRepository([group])
        use_case = self._use_case(self.admin_settings_repo, article_group_repo)
        result = await use_case.execute(actor=self.actor, cmd=self._cmd(article_group_ids=[5]))
        assert result.id > 0

    async def test_auto_numbering_ignores_manual_part_number(self):
        settings = AdminOrderSettings(
            id=1,
            order_number_format="ORD-{year}-{seq:04d}",
            part_number_format="PN-{year}-{seq:04d}",
            part_number_auto=True,
            part_number_editable=True,
            web_creation_allowed=True,
            pdm_part_number_pattern="",
        )
        use_case = self._use_case(FakeAdminSettingsRepository(settings))
        result = await use_case.execute(actor=self.actor, cmd=self._cmd(part_number="MANUAL-1"))
        assert result.part_number == "AUTO-1"

    async def test_manual_part_number_used_when_not_auto(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=self._cmd(part_number="MANUAL-1")
        )
        assert result.part_number == "MANUAL-1"

    async def test_duplicate_part_number_rejected_when_unique(self):
        existing = make_bought_item(id=1)
        existing.part_number = "MANUAL-1"
        self.item_repo._items[1] = existing
        with pytest.raises(BoughtItemPartNumberDuplicateError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(part_number="MANUAL-1"))

    async def test_claims_part_number_in_registry(self):
        await self.use_case.execute(actor=self.actor, cmd=self._cmd(part_number="MANUAL-2"))
        assert self.registry.entries.get("MANUAL-2") == "bought"

    async def test_duplicate_gtin_rejected(self):
        existing = make_bought_item(id=1)
        existing.gtin = "01234567890128"
        self.item_repo._items[1] = existing
        with pytest.raises(BoughtItemGtinDuplicateError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(gtin="01234567890128"))

    async def test_none_gtin_allowed_and_repeatable(self):
        first = await self.use_case.execute(actor=self.actor, cmd=self._cmd(gtin=None))
        second = await self.use_case.execute(actor=self.actor, cmd=self._cmd(gtin=None))
        assert first.gtin is None
        assert second.gtin is None

    async def test_web_creation_disabled_when_pdm_enabled(self):
        # PDM "on" per is_pdm_enabled() = enabled and is_configured, see
        # make_pdm_settings.
        settings = AdminOrderSettings(
            id=1,
            order_number_format="ORD-{year}-{seq:04d}",
            part_number_format="PN-{year}-{seq:04d}",
            part_number_auto=False,
            part_number_editable=True,
            web_creation_allowed=False,
            pdm_part_number_pattern="",
        )
        use_case = self._use_case(
            FakeAdminSettingsRepository(settings, pdm=make_pdm_settings(enabled=True))
        )
        with pytest.raises(WebCreationDisabledError):
            await use_case.execute(actor=self.actor, cmd=self._cmd())

    async def test_web_creation_allowed_when_pdm_disabled_even_if_setting_off(self):
        # FakeAdminSettingsRepository's default pdm is enabled=False, so
        # is_pdm_enabled() is False here regardless of web_creation_allowed.
        settings = AdminOrderSettings(
            id=1,
            order_number_format="ORD-{year}-{seq:04d}",
            part_number_format="PN-{year}-{seq:04d}",
            part_number_auto=False,
            part_number_editable=True,
            web_creation_allowed=False,
            pdm_part_number_pattern="",
        )
        use_case = self._use_case(FakeAdminSettingsRepository(settings))
        result = await use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.id > 0

    async def test_typed_part_number_matching_pdm_pattern_rejected_when_pdm_enabled(self):
        settings = AdminOrderSettings(
            id=1,
            order_number_format="ORD-{year}-{seq:04d}",
            part_number_format="PN-{year}-{seq:04d}",
            part_number_auto=False,
            part_number_editable=True,
            web_creation_allowed=True,
            pdm_part_number_pattern=r"EXT-\d+",
        )
        use_case = self._use_case(
            FakeAdminSettingsRepository(settings, pdm=make_pdm_settings(enabled=True))
        )
        with pytest.raises(PartNumberReservedForPdmError):
            await use_case.execute(actor=self.actor, cmd=self._cmd(part_number="EXT-123"))

    async def test_typed_part_number_matching_pdm_pattern_accepted_when_pdm_disabled(self):
        settings = AdminOrderSettings(
            id=1,
            order_number_format="ORD-{year}-{seq:04d}",
            part_number_format="PN-{year}-{seq:04d}",
            part_number_auto=False,
            part_number_editable=True,
            web_creation_allowed=True,
            pdm_part_number_pattern=r"EXT-\d+",
        )
        use_case = self._use_case(FakeAdminSettingsRepository(settings))
        result = await use_case.execute(actor=self.actor, cmd=self._cmd(part_number="EXT-123"))
        assert result.part_number == "EXT-123"

    async def test_registry_pk_collision_from_claim_maps_to_numbering_conflict(self):
        # Mirrors the made-item test of the same name; see its comment.
        class RacingRegistry(FakePartNumberRegistry):
            async def claim(self, part_number: str, kind: str) -> None:
                raise SqlConstraintViolationError(
                    statement="INSERT INTO part_number_registry ...",
                    params={},
                    orig=Exception("UNIQUE constraint failed: part_number_registry.part_number"),
                )

        use_case = CreateBoughtItem(
            self.item_repo,
            self.supplier_repo,
            self.article_group_repo,
            self.admin_settings_repo,
            part_number_registry=RacingRegistry(),
            event_bus=self.bus,
            uow=self.uow,
            cad_source=PdmCadSource(self.admin_settings_repo),
        )
        with pytest.raises(NumberingConflictError):
            await use_case.execute(actor=self.actor, cmd=self._cmd(part_number="RACE-1"))


# ── UpdateBoughtItem ──────────────────────────────────────────────────


class TestUpdateBoughtItem:
    def setup_method(self):
        self.item = make_bought_item(id=1)
        self.supplier = make_supplier(id=1)
        self.item_repo = FakeBoughtItemRepository([self.item])
        self.supplier_repo = FakeSupplierRepository([self.supplier])
        self.article_group_repo = FakeArticleGroupRepository()
        self.actor = make_user(permissions=[Permission.WRITE_BOUGHT_ITEMS])
        self.admin_settings_repo = FakeAdminSettingsRepository()
        self.registry = FakePartNumberRegistry()
        self.uow = FakeUnitOfWork()
        self.use_case = self._use_case(self.admin_settings_repo)

    def _use_case(self, admin_settings_repo: "FakeAdminSettingsRepository") -> UpdateBoughtItem:
        return UpdateBoughtItem(
            self.item_repo,
            self.supplier_repo,
            self.article_group_repo,
            admin_settings_repo,
            part_number_registry=self.registry,
            uow=self.uow,
            cad_source=PdmCadSource(admin_settings_repo),
        )

    def _cmd(self, **kwargs) -> UpdateBoughtItemCommand:
        defaults = dict(order_code_1="ORD-001", article_name="Hex Bolt M8", manufacturer_id=1)
        defaults.update(kwargs)
        return UpdateBoughtItemCommand(**defaults)

    async def test_updates_successfully(self):
        result = await self.use_case.execute(
            actor=self.actor, item_id=1, cmd=self._cmd(article_name="New Name")
        )
        assert result.article_name == "New Name"

    async def test_not_found_raises(self):
        with pytest.raises(BoughtItemNotFoundError):
            await self.use_case.execute(actor=self.actor, item_id=999, cmd=self._cmd())

    async def test_update_never_moves_a_cad_row_back_to_web(self):
        # The command has no data_source field, so a client sending WEB is
        # ignored and the row stays CAD.
        self.item.data_source = DataSource.CAD
        result = await self.use_case.execute(
            actor=self.actor, item_id=1, cmd=self._cmd(note="x", data_source="WEB")
        )
        assert result.data_source == "CAD"

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, item_id=1, cmd=self._cmd())

    async def test_missing_supplier_raises(self):
        with pytest.raises(SupplierNotFoundError):
            await self.use_case.execute(
                actor=self.actor, item_id=1, cmd=self._cmd(manufacturer_id=999)
            )

    async def test_missing_article_group_raises(self):
        with pytest.raises(ArticleGroupNotFoundError):
            await self.use_case.execute(
                actor=self.actor, item_id=1, cmd=self._cmd(article_group_ids=[99])
            )

    async def test_part_number_change_rejected_when_not_editable(self):
        settings = AdminOrderSettings(
            id=1,
            order_number_format="ORD-{year}-{seq:04d}",
            part_number_format="PN-{year}-{seq:04d}",
            part_number_auto=False,
            part_number_editable=False,
            web_creation_allowed=True,
            pdm_part_number_pattern="",
        )
        use_case = self._use_case(FakeAdminSettingsRepository(settings))
        with pytest.raises(BoughtItemPartNumberNotEditableError):
            await use_case.execute(actor=self.actor, item_id=1, cmd=self._cmd(part_number="NEW-1"))

    # test_part_number_change_rejected_when_source_external removed: see
    # the matching note by CreateBoughtItem's
    # test_external_source_ignores_manual_part_number above.

    async def test_unchanged_part_number_allowed_even_when_not_editable(self):
        settings = AdminOrderSettings(
            id=1,
            order_number_format="ORD-{year}-{seq:04d}",
            part_number_format="PN-{year}-{seq:04d}",
            part_number_auto=False,
            part_number_editable=False,
            web_creation_allowed=True,
            pdm_part_number_pattern="",
        )
        use_case = self._use_case(FakeAdminSettingsRepository(settings))
        result = await use_case.execute(actor=self.actor, item_id=1, cmd=self._cmd())
        assert result.part_number == self.item.part_number

    async def test_part_number_change_allowed_when_editable(self):
        result = await self.use_case.execute(
            actor=self.actor, item_id=1, cmd=self._cmd(part_number="NEW-1")
        )
        assert result.part_number == "NEW-1"

    async def test_renumber_to_pdm_reserved_pattern_rejected_when_pdm_enabled(self):
        settings = AdminOrderSettings(
            id=1,
            order_number_format="ORD-{year}-{seq:04d}",
            part_number_format="PN-{year}-{seq:04d}",
            part_number_auto=False,
            part_number_editable=True,
            web_creation_allowed=True,
            pdm_part_number_pattern=r"EXT-\d+",
        )
        use_case = self._use_case(
            FakeAdminSettingsRepository(settings, pdm=make_pdm_settings(enabled=True))
        )
        with pytest.raises(PartNumberReservedForPdmError):
            await use_case.execute(
                actor=self.actor, item_id=1, cmd=self._cmd(part_number="EXT-123")
            )

    async def test_renumber_to_pdm_reserved_pattern_accepted_when_pdm_disabled(self):
        settings = AdminOrderSettings(
            id=1,
            order_number_format="ORD-{year}-{seq:04d}",
            part_number_format="PN-{year}-{seq:04d}",
            part_number_auto=False,
            part_number_editable=True,
            web_creation_allowed=True,
            pdm_part_number_pattern=r"EXT-\d+",
        )
        use_case = self._use_case(FakeAdminSettingsRepository(settings))

        result = await use_case.execute(
            actor=self.actor, item_id=1, cmd=self._cmd(part_number="EXT-123")
        )

        assert result.part_number == "EXT-123"

    async def test_duplicate_part_number_rejected_when_unique(self):
        other = make_bought_item(id=2)
        other.part_number = "TAKEN-1"
        self.item_repo._items[2] = other
        with pytest.raises(BoughtItemPartNumberDuplicateError):
            await self.use_case.execute(
                actor=self.actor, item_id=1, cmd=self._cmd(part_number="TAKEN-1")
            )

    async def test_renumber_claims_new_and_releases_old(self):
        self.item.part_number = "OLD-1"
        await self.registry.claim("OLD-1", "bought")

        result = await self.use_case.execute(
            actor=self.actor, item_id=1, cmd=self._cmd(part_number="NEW-2")
        )

        assert result.part_number == "NEW-2"
        assert self.registry.entries.get("NEW-2") == "bought"
        assert self.registry.entries.get("OLD-1") is None

    async def test_renumber_registry_pk_collision_maps_to_numbering_conflict(self):
        class RacingRegistry(FakePartNumberRegistry):
            async def claim(self, part_number: str, kind: str) -> None:
                raise SqlConstraintViolationError(
                    statement="INSERT INTO part_number_registry ...",
                    params={},
                    orig=Exception("UNIQUE constraint failed: part_number_registry.part_number"),
                )

        use_case = UpdateBoughtItem(
            self.item_repo,
            self.supplier_repo,
            self.article_group_repo,
            self.admin_settings_repo,
            part_number_registry=RacingRegistry(),
            uow=self.uow,
            cad_source=PdmCadSource(self.admin_settings_repo),
        )
        with pytest.raises(NumberingConflictError):
            await use_case.execute(actor=self.actor, item_id=1, cmd=self._cmd(part_number="RACE-1"))

    async def test_duplicate_gtin_rejected(self):
        other = make_bought_item(id=2)
        other.gtin = "01234567890128"
        self.item_repo._items[2] = other
        with pytest.raises(BoughtItemGtinDuplicateError):
            await self.use_case.execute(
                actor=self.actor, item_id=1, cmd=self._cmd(gtin="01234567890128")
            )

    async def test_unchanged_gtin_allowed(self):
        self.item.gtin = "01234567890128"
        result = await self.use_case.execute(
            actor=self.actor, item_id=1, cmd=self._cmd(gtin="01234567890128")
        )
        assert result.gtin == "01234567890128"


# ── ArchiveBoughtItem / RestoreBoughtItem ────────────────────────────


class TestArchiveBoughtItem:
    def setup_method(self):
        self.item = make_bought_item(id=1)
        self.item_repo = FakeBoughtItemRepository([self.item])
        self.actor = make_user(permissions=[Permission.DELETE_BOUGHT_ITEMS])
        self.use_case = ArchiveBoughtItem(self.item_repo, uow=FakeUnitOfWork())

    async def test_archives_successfully(self):
        result = await self.use_case.execute(actor=self.actor, item_id=1)
        assert result.archived is True

    async def test_archiving_twice_is_idempotent(self):
        await self.use_case.execute(actor=self.actor, item_id=1)
        result = await self.use_case.execute(actor=self.actor, item_id=1)
        assert result.archived is True

    async def test_not_found_raises(self):
        with pytest.raises(BoughtItemNotFoundError):
            await self.use_case.execute(actor=self.actor, item_id=999)

    async def test_unprivileged_cannot_archive(self):
        actor = make_user(permissions=[Permission.WRITE_BOUGHT_ITEMS])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, item_id=1)


class TestRestoreBoughtItem:
    def setup_method(self):
        self.actor = make_user(permissions=[Permission.DELETE_BOUGHT_ITEMS])

    async def test_restores_successfully(self):
        item = make_bought_item(id=1, archived=True)
        repo = FakeBoughtItemRepository([item])
        result = await RestoreBoughtItem(repo, uow=FakeUnitOfWork()).execute(
            actor=self.actor, item_id=1
        )
        assert result.archived is False

    async def test_restoring_twice_is_idempotent(self):
        item = make_bought_item(id=1, archived=True)
        repo = FakeBoughtItemRepository([item])
        use_case = RestoreBoughtItem(repo, uow=FakeUnitOfWork())
        await use_case.execute(actor=self.actor, item_id=1)
        result = await use_case.execute(actor=self.actor, item_id=1)
        assert result.archived is False

    async def test_restore_conflicts_when_gtin_already_taken_by_a_live_item(self):
        archived = make_bought_item(id=1, archived=True)
        archived.gtin = "01234567890128"
        live = make_bought_item(id=2, archived=False)
        live.gtin = "01234567890128"
        repo = FakeBoughtItemRepository([archived, live])
        with pytest.raises(BoughtItemGtinDuplicateError):
            await RestoreBoughtItem(repo, uow=FakeUnitOfWork()).execute(actor=self.actor, item_id=1)

    async def test_not_found_raises(self):
        repo = FakeBoughtItemRepository([])
        with pytest.raises(BoughtItemNotFoundError):
            await RestoreBoughtItem(repo, uow=FakeUnitOfWork()).execute(
                actor=self.actor, item_id=999
            )

    async def test_unprivileged_cannot_restore(self):
        item = make_bought_item(id=1, archived=True)
        repo = FakeBoughtItemRepository([item])
        actor = make_user(permissions=[Permission.WRITE_BOUGHT_ITEMS])
        with pytest.raises(InsufficientPermissionsError):
            await RestoreBoughtItem(repo, uow=FakeUnitOfWork()).execute(actor=actor, item_id=1)
