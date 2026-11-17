"""
Unit tests for all source item type use cases.
No database, no HTTP. All dependencies replaced with in-memory fakes.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.catalogue.application.dto.source_item_type_dto import CreateSourceItemTypeCommand
from src.modules.catalogue.application.dto.source_item_type_dto import UpdateSourceItemTypeCommand
from src.modules.catalogue.application.use_cases.source_item_type.archive_source_item_type import (
    ArchiveSourceItemType,
)
from src.modules.catalogue.application.use_cases.source_item_type.create_source_item_type import (
    CreateSourceItemType,
)
from src.modules.catalogue.application.use_cases.source_item_type.get_source_item_type import (
    GetSourceItemType,
)
from src.modules.catalogue.application.use_cases.source_item_type.get_source_item_type import (
    GetSourceItemTypes,
)
from src.modules.catalogue.application.use_cases.source_item_type.restore_source_item_type import (
    RestoreSourceItemType,
)
from src.modules.catalogue.application.use_cases.source_item_type.update_source_item_type import (
    UpdateSourceItemType,
)
from src.modules.catalogue.domain.entities.source_item_type import SourceItemType
from src.modules.catalogue.domain.errors import LabelTranslationConflictError
from src.modules.catalogue.domain.errors import SourceItemTypeNotFoundError
from src.modules.catalogue.ports.outbound.repositories.source_item_type_repository import (
    SourceItemTypeFilterDto,
)
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit._tenant_settings import TenantSettings
from tests.unit.fakes import FakeUnitOfWork

# ── Helpers ───────────────────────────────────────────────────────────


def make_source_item_type(
    id: int = 1,
    name: str = "Round bar",
    archived: bool = False,
) -> SourceItemType:
    return SourceItemType(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=archived,
        name=LocalizedText({"enGB": name}),
        label_color="#999999",
        label_font_color="#000000",
        description=LocalizedText(),
        creator_id=1,
    )


class FakeSourceItemTypeRepository:
    def __init__(self, types: list[SourceItemType] | None = None):
        self._types: dict[int, SourceItemType] = {}
        self._next_id = 1
        for t in types or []:
            self._types[t.id] = t
            self._next_id = max(self._next_id, t.id + 1)

    async def get_by_id(self, id: int) -> SourceItemType | None:
        return self._types.get(id)

    async def get_live_names(self) -> list[tuple[int, LocalizedText]]:
        return [(t.id, t.name) for t in self._types.values() if not t.archived]

    async def get_multi(self, filters: SourceItemTypeFilterDto) -> tuple[int, list[SourceItemType]]:
        results = list(self._types.values())
        if filters.name:
            results = [
                t
                for t in results
                if any(filters.name.lower() in text.lower() for text in t.name.values.values())
            ]
        total = len(results)
        skip = filters.skip or 0
        limit = filters.limit
        return total, results[skip : skip + limit if limit else None]

    async def next_sort_order(self) -> int:
        return max((row.sort_order for row in self._types.values()), default=-1) + 1

    async def save(self, source_item_type: SourceItemType) -> SourceItemType:
        if source_item_type.id == 0:
            source_item_type.id = self._next_id
            self._next_id += 1
        self._types[source_item_type.id] = source_item_type
        return source_item_type

    async def delete(self, source_item_type: SourceItemType) -> None:
        raise NotImplementedError


# ── CreateSourceItemType ───────────────────────────────────────────────


class TestCreateSourceItemType:
    def setup_method(self):
        self.repo = FakeSourceItemTypeRepository()
        self.actor = make_user(permissions=[Permission.WRITE_SOURCE_ITEM_TYPES])
        self.use_case = CreateSourceItemType(
            self.repo, settings=TenantSettings(), uow=FakeUnitOfWork()
        )

    def _cmd(self, **kwargs) -> CreateSourceItemTypeCommand:
        defaults = dict(name={"enGB": "Round bar"})
        defaults.update(kwargs)
        return CreateSourceItemTypeCommand(**defaults)

    async def test_creates_successfully(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.name == {"enGB": "Round bar"}
        assert result.id > 0

    async def test_unprivileged_user_cannot_create(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=self._cmd())

    async def test_duplicate_name_raises(self):
        await self.repo.save(make_source_item_type(name="Round bar"))
        with pytest.raises(LabelTranslationConflictError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(name={"enGB": "Round bar"}))

    async def test_defaults_are_preserved(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.label_color == "#999999"
        assert result.label_font_color == "#000000"
        assert result.description == {}

    async def test_creator_id_is_set(self):
        actor = make_user(id=7, permissions=[Permission.WRITE_SOURCE_ITEM_TYPES])
        result = await self.use_case.execute(actor=actor, cmd=self._cmd())
        assert result.creator_id == 7


# ── UpdateSourceItemType ───────────────────────────────────────────────


class TestUpdateSourceItemType:
    def setup_method(self):
        self.source_item_type = make_source_item_type(id=1, name="Round bar")
        self.repo = FakeSourceItemTypeRepository([self.source_item_type])
        self.actor = make_user(permissions=[Permission.WRITE_SOURCE_ITEM_TYPES])
        self.use_case = UpdateSourceItemType(
            self.repo, settings=TenantSettings(), uow=FakeUnitOfWork()
        )

    def _cmd(self, **kwargs) -> UpdateSourceItemTypeCommand:
        defaults = dict(
            name={"enGB": "Round bar"},
            label_color="#111111",
            label_font_color="#ffffff",
            description={"enGB": "Updated"},
        )
        defaults.update(kwargs)
        return UpdateSourceItemTypeCommand(**defaults)

    async def test_updates_successfully(self):
        result = await self.use_case.execute(
            actor=self.actor, source_item_type_id=1, cmd=self._cmd(name={"enGB": "Square bar"})
        )
        assert result.name == {"enGB": "Square bar"}

    async def test_not_found_raises(self):
        with pytest.raises(SourceItemTypeNotFoundError):
            await self.use_case.execute(actor=self.actor, source_item_type_id=999, cmd=self._cmd())

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, source_item_type_id=1, cmd=self._cmd())

    async def test_changing_to_existing_name_raises(self):
        await self.repo.save(make_source_item_type(id=2, name="Square bar"))
        with pytest.raises(LabelTranslationConflictError):
            await self.use_case.execute(
                actor=self.actor, source_item_type_id=1, cmd=self._cmd(name={"enGB": "Square bar"})
            )

    async def test_keeping_same_name_does_not_raise(self):
        result = await self.use_case.execute(
            actor=self.actor, source_item_type_id=1, cmd=self._cmd(name={"enGB": "Round bar"})
        )
        assert result.name == {"enGB": "Round bar"}


# ── ArchiveSourceItemType / RestoreSourceItemType ───────────────────────


class TestArchiveSourceItemType:
    def setup_method(self):
        self.source_item_type = make_source_item_type(id=1)
        self.repo = FakeSourceItemTypeRepository([self.source_item_type])
        self.actor = make_user(permissions=[Permission.WRITE_SOURCE_ITEM_TYPES])
        self.use_case = ArchiveSourceItemType(self.repo, uow=FakeUnitOfWork())

    async def test_archives_successfully(self):
        result = await self.use_case.execute(actor=self.actor, source_item_type_id=1)
        assert result.archived is True

    async def test_archiving_twice_is_idempotent(self):
        await self.use_case.execute(actor=self.actor, source_item_type_id=1)
        result = await self.use_case.execute(actor=self.actor, source_item_type_id=1)
        assert result.archived is True

    async def test_not_found_raises(self):
        with pytest.raises(SourceItemTypeNotFoundError):
            await self.use_case.execute(actor=self.actor, source_item_type_id=999)

    async def test_unprivileged_cannot_archive(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, source_item_type_id=1)


class TestRestoreSourceItemType:
    def setup_method(self):
        self.actor = make_user(permissions=[Permission.WRITE_SOURCE_ITEM_TYPES])

    async def test_restores_successfully(self):
        t = make_source_item_type(id=1, archived=True)
        repo = FakeSourceItemTypeRepository([t])
        result = await RestoreSourceItemType(repo, uow=FakeUnitOfWork()).execute(
            actor=self.actor, source_item_type_id=1
        )
        assert result.archived is False

    async def test_restore_conflicts_when_name_already_taken_by_a_live_type(self):
        archived = make_source_item_type(id=1, name="Round bar", archived=True)
        live = make_source_item_type(id=2, name="Round bar", archived=False)
        repo = FakeSourceItemTypeRepository([archived, live])
        with pytest.raises(LabelTranslationConflictError):
            await RestoreSourceItemType(repo, uow=FakeUnitOfWork()).execute(
                actor=self.actor, source_item_type_id=1
            )

    async def test_not_found_raises(self):
        repo = FakeSourceItemTypeRepository([])
        with pytest.raises(SourceItemTypeNotFoundError):
            await RestoreSourceItemType(repo, uow=FakeUnitOfWork()).execute(
                actor=self.actor, source_item_type_id=999
            )


# ── GetSourceItemType / GetSourceItemTypes ─────────────────────────────────


class TestGetSourceItemType:
    def setup_method(self):
        self.types = [
            make_source_item_type(id=1, name="Alpha"),
            make_source_item_type(id=2, name="Beta"),
            make_source_item_type(id=3, name="Gamma"),
        ]
        self.repo = FakeSourceItemTypeRepository(self.types)

    async def test_get_existing(self):
        result = await GetSourceItemType(self.repo).execute(source_item_type_id=1)
        assert result.name == {"enGB": "Alpha"}

    async def test_get_nonexistent_raises(self):
        with pytest.raises(SourceItemTypeNotFoundError):
            await GetSourceItemType(self.repo).execute(source_item_type_id=999)

    async def test_get_all(self):
        result = await GetSourceItemTypes(self.repo).execute(filters=SourceItemTypeFilterDto())
        assert result.total == 3
        assert len(result.items) == 3

    async def test_get_with_limit(self):
        result = await GetSourceItemTypes(self.repo).execute(
            filters=SourceItemTypeFilterDto(limit=1)
        )
        assert len(result.items) == 1

    async def test_get_with_name_filter(self):
        result = await GetSourceItemTypes(self.repo).execute(
            filters=SourceItemTypeFilterDto(name="beta")
        )
        assert result.total == 1
        assert result.items[0].name == {"enGB": "Beta"}
