"""
In-memory fake repositories and collaborators shared by the made_item test
modules.
"""

from datetime import date

from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.entities.article_group import ArticleGroup
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.customer import Customer
from src.modules.catalogue.domain.entities.fabrication_method import FabricationMethod
from src.modules.catalogue.domain.entities.inspection_method import InspectionMethod
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.made_item_process import MadeItemProcess
from src.modules.catalogue.domain.entities.part_number_registry import PartNumberRegistryEntry
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.domain.errors import PartNumberInUseError
from src.modules.catalogue.domain.policies.item_field_ownership import default_policy
from src.modules.catalogue.domain.policies.made_item_rules import normalize_process_groups
from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.catalogue.ports.outbound.catalogue_queries import ArticleGroupFilterDto
from src.modules.catalogue.ports.outbound.catalogue_queries import MadeItemFilterDto
from src.modules.catalogue.ports.outbound.repositories.fabrication_method_repository import (
    FabricationMethodFilterDto,
)
from src.modules.catalogue.ports.outbound.repositories.source_item_repository import (
    SourceItemFilterDto,
)
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from tests.unit.made_item._helpers import make_pdm_settings


class FakeMadeItemRepository:
    def __init__(self, items: list[MadeItem] | None = None):
        self._items: dict[int, MadeItem] = {}
        self._next_id = 1
        for i in items or []:
            self._items[i.id] = i
            self._next_id = max(self._next_id, i.id + 1)
        self._processes: dict[int, MadeItemProcess] = {}
        self._next_process_id = 1
        self.merged_article_groups: list[tuple[int, int]] = []
        self.merged_references: list[tuple[int, int]] = []

    @property
    def items(self) -> dict[int, MadeItem]:
        """The stored made items by id, for assertions."""
        return self._items

    async def get_by_id(self, id: int) -> MadeItem | None:
        item = self._items.get(id)
        if item is None:
            return None
        item.processes = await self.get_processes(id)
        return item

    async def lock_for_update(self, id: int) -> None:
        return None

    async def get_revisions(self, part_number: str) -> list[MadeItem]:
        return [i for i in self._items.values() if i.part_number == part_number and not i.archived]

    async def get_family(self, part_number: str) -> list[MadeItem]:
        return [i for i in self._items.values() if i.part_number == part_number]

    async def get_by_part_number_and_revision(
        self, part_number: str, revision: str
    ) -> MadeItem | None:
        return next(
            (
                i
                for i in self._items.values()
                if i.part_number == part_number and i.revision == revision and not i.archived
            ),
            None,
        )

    async def get_multi(self, filters: MadeItemFilterDto) -> tuple[int, list[MadeItem]]:
        raise NotImplementedError

    async def save(self, item: MadeItem) -> MadeItem:
        if item.id == 0:
            item.id = self._next_id
            self._next_id += 1
        self._items[item.id] = item
        return item

    async def delete(self, item: MadeItem) -> None:
        self._items.pop(item.id, None)

    async def merge_references(self, source_id: int, target_id: int) -> None:
        self.merged_references.append((source_id, target_id))

    async def merge_article_groups(self, source_id: int, target_id: int) -> None:
        self.merged_article_groups.append((source_id, target_id))

    async def get_processes(self, made_item_id: int) -> list[MadeItemProcess]:
        return sorted(
            (p for p in self._processes.values() if p.made_item_id == made_item_id),
            key=lambda p: p.position,
        )

    async def get_process_by_id(self, process_id: int) -> MadeItemProcess | None:
        return self._processes.get(process_id)

    async def save_process(self, process: MadeItemProcess) -> MadeItemProcess:
        if process.id == 0:
            process.id = self._next_process_id
            self._next_process_id += 1
        self._processes[process.id] = process
        return process

    async def delete_process(self, process: MadeItemProcess) -> None:
        self._processes.pop(process.id, None)

    async def reorder_processes(
        self, made_item_id: int, ordered_process_ids: list[int]
    ) -> list[MadeItemProcess]:
        ordered = [self._processes[pid] for pid in ordered_process_ids]
        for position, process in enumerate(ordered):
            process.position = position
        new_group_indexes = normalize_process_groups(ordered)
        for process, group_index in zip(ordered, new_group_indexes, strict=True):
            process.group_index = group_index
        return await self.get_processes(made_item_id)

    async def set_process_groups(
        self, made_item_id: int, groups: list[list[int]]
    ) -> list[MadeItemProcess]:
        for group_index, group in enumerate(groups):
            for process_id in group:
                self._processes[process_id].group_index = group_index
        return await self.get_processes(made_item_id)


class FakeMadeItemFileRepository:
    def __init__(self, files: list | None = None):
        self._files = {f.id: f for f in (files or [])}

    async def get_by_id(self, id: int):
        return self._files.get(id)

    async def get_by_item_id(self, item_id: int) -> list:
        return [f for f in self._files.values() if f.made_item_id == item_id]

    async def get_by_item_id_and_category(self, item_id: int, category) -> list:
        raise NotImplementedError

    async def save(self, file):
        raise NotImplementedError

    async def reassign(self, file_id: int, target_item_id: int) -> None:
        if file_id in self._files:
            self._files[file_id].made_item_id = target_item_id

    async def delete(self, file) -> None:
        self._files.pop(file.id, None)


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


class FakeSourceItemRepository:
    def __init__(self, items: list[SourceItem] | None = None):
        self._items: dict[int, SourceItem] = {i.id: i for i in (items or [])}

    async def get_by_id(self, id: int) -> SourceItem | None:
        return self._items.get(id)

    async def get_multi(self, filters: SourceItemFilterDto) -> tuple[int, list[SourceItem]]:
        raise NotImplementedError

    async def save(self, item: SourceItem) -> SourceItem:
        raise NotImplementedError

    async def delete(self, item: SourceItem) -> None:
        raise NotImplementedError


class FakeBoughtItemRepository:
    def __init__(self, items: list[BoughtItem] | None = None):
        self._items: dict[int, BoughtItem] = {i.id: i for i in (items or [])}

    async def get_by_id(self, id: int) -> BoughtItem | None:
        return self._items.get(id)


class FakeCustomerRepository:
    """Only what the made-item use cases and PDM ingest read: a lookup by
    id that, like the real repository, also finds archived customers."""

    def __init__(self, customers: list[Customer] | None = None):
        self._customers: dict[int, Customer] = {c.id: c for c in (customers or [])}

    async def get_by_id(self, id: int) -> Customer | None:
        return self._customers.get(id)


class FakeFabricationMethodRepository:
    def __init__(self, methods: list[FabricationMethod] | None = None):
        self._methods: dict[int, FabricationMethod] = {m.id: m for m in (methods or [])}

    async def get_by_id(self, id: int) -> FabricationMethod | None:
        return self._methods.get(id)

    async def get_live_names(self) -> list[tuple[int, LocalizedText]]:
        raise NotImplementedError

    async def get_multi(
        self, filters: FabricationMethodFilterDto
    ) -> tuple[int, list[FabricationMethod]]:
        raise NotImplementedError

    async def save(self, fabrication_method: FabricationMethod) -> FabricationMethod:
        raise NotImplementedError

    async def delete(self, fabrication_method: FabricationMethod) -> None:
        raise NotImplementedError


class FakeInspectionMethodRepository:
    def __init__(self, methods: list[InspectionMethod] | None = None):
        self._methods: dict[int, InspectionMethod] = {m.id: m for m in (methods or [])}

    async def get_by_id(self, id: int) -> InspectionMethod | None:
        return self._methods.get(id)

    async def get_live_names(self) -> list[tuple[int, LocalizedText]]:
        raise NotImplementedError

    async def get_multi(self, filters):
        raise NotImplementedError

    async def save(self, inspection_method: InspectionMethod) -> InspectionMethod:
        raise NotImplementedError

    async def delete(self, inspection_method: InspectionMethod) -> None:
        raise NotImplementedError


class FakeAdminSettingsRepository:
    def __init__(
        self,
        made_items: AdminMadeItemSettings | None = None,
        pdm: AdminPdmSettings | None = None,
    ):
        self._made_items = made_items or AdminMadeItemSettings(
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
        self._pdm = pdm or make_pdm_settings(enabled=False)

    async def get_made_items(self) -> AdminMadeItemSettings:
        return self._made_items

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


class FakeMadeItemFileStorage:
    """Never reached once _assert_editable raises; only needs to be
    non-None so UploadItemFileBase.execute() gets past its own
    StorageNotEnabledError check before the newest-only gate runs."""
