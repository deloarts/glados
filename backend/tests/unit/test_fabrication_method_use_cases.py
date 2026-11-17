"""
Unit tests for all fabrication method use cases.
No database, no HTTP. All dependencies replaced with in-memory fakes.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.catalogue.application.dto.fabrication_method_dto import (
    CreateFabricationMethodCommand,
)
from src.modules.catalogue.application.dto.fabrication_method_dto import (
    UpdateFabricationMethodCommand,
)
from src.modules.catalogue.application.use_cases.fabrication_method.archive_fabrication_method import (
    ArchiveFabricationMethod,
)
from src.modules.catalogue.application.use_cases.fabrication_method.create_fabrication_method import (
    CreateFabricationMethod,
)
from src.modules.catalogue.application.use_cases.fabrication_method.get_fabrication_method import (
    GetAssemblyDefaultFabricationMethod,
)
from src.modules.catalogue.application.use_cases.fabrication_method.get_fabrication_method import (
    GetFabricationMethod,
)
from src.modules.catalogue.application.use_cases.fabrication_method.get_fabrication_method import (
    GetFabricationMethods,
)
from src.modules.catalogue.application.use_cases.fabrication_method.restore_fabrication_method import (
    RestoreFabricationMethod,
)
from src.modules.catalogue.application.use_cases.fabrication_method.update_fabrication_method import (
    UpdateFabricationMethod,
)
from src.modules.catalogue.domain.entities.fabrication_method import FabricationMethod
from src.modules.catalogue.domain.entities.supplier import Supplier
from src.modules.catalogue.domain.errors import FabricationMethodArchivedError
from src.modules.catalogue.domain.errors import FabricationMethodNotFoundError
from src.modules.catalogue.domain.errors import LabelTranslationConflictError
from src.modules.catalogue.domain.errors import SupplierNotFoundError
from src.modules.catalogue.domain.value_objects.supplier_level import SupplierLevel
from src.modules.catalogue.ports.outbound.repositories.fabrication_method_repository import (
    FabricationMethodFilterDto,
)
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit._tenant_settings import TenantSettings
from tests.unit.fakes import FakeUnitOfWork

# ── Helpers ───────────────────────────────────────────────────────────


def make_fabrication_method(
    id: int = 1,
    name: str = "Milling",
    archived: bool = False,
    default_for_assemblies: bool = False,
) -> FabricationMethod:
    return FabricationMethod(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        name=LocalizedText({"enGB": name}),
        label_color="#999999",
        label_font_color="#000000",
        description=LocalizedText(),
        creator_id=1,
        default_for_assemblies=default_for_assemblies,
        archived=archived,
    )


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


class FakeSupplierRepository:
    def __init__(self, suppliers: list[Supplier] | None = None):
        self._suppliers: dict[int, Supplier] = {s.id: s for s in (suppliers or [])}

    async def get_by_id(self, id: int) -> Supplier | None:
        return self._suppliers.get(id)


class FakeFabricationMethodRepository:
    def __init__(self, methods: list[FabricationMethod] | None = None):
        self._methods: dict[int, FabricationMethod] = {}
        self._next_id = 1
        for m in methods or []:
            self._methods[m.id] = m
            self._next_id = max(self._next_id, m.id + 1)

    async def get_by_id(self, id: int) -> FabricationMethod | None:
        return self._methods.get(id)

    async def get_live_names(self) -> list[tuple[int, LocalizedText]]:
        return [(m.id, m.name) for m in self._methods.values() if not m.archived]

    async def get_default_for_assemblies(self) -> FabricationMethod | None:
        return next((m for m in self._methods.values() if m.default_for_assemblies), None)

    async def get_multi(
        self, filters: FabricationMethodFilterDto
    ) -> tuple[int, list[FabricationMethod]]:
        results = list(self._methods.values())
        if not filters.include_archived:
            results = [m for m in results if not m.archived]
        if filters.name:
            results = [
                m
                for m in results
                if any(filters.name.lower() in text.lower() for text in m.name.values.values())
            ]
        total = len(results)
        skip = filters.skip or 0
        limit = filters.limit
        return total, results[skip : skip + limit if limit else None]

    async def next_sort_order(self) -> int:
        return max((row.sort_order for row in self._methods.values()), default=-1) + 1

    async def save(self, fabrication_method: FabricationMethod) -> FabricationMethod:
        if fabrication_method.id == 0:
            fabrication_method.id = self._next_id
            self._next_id += 1
        self._methods[fabrication_method.id] = fabrication_method
        return fabrication_method

    async def delete(self, fabrication_method: FabricationMethod) -> None:
        raise NotImplementedError


# ── CreateFabricationMethod ──────────────────────────────────────────


class TestCreateFabricationMethod:
    def setup_method(self):
        self.repo = FakeFabricationMethodRepository()
        self.supplier_repo = FakeSupplierRepository([make_supplier(id=1)])
        self.actor = make_user(permissions=[Permission.WRITE_FABRICATION_METHODS])
        self.use_case = CreateFabricationMethod(
            self.repo, self.supplier_repo, settings=TenantSettings(), uow=FakeUnitOfWork()
        )

    def _cmd(self, **kwargs) -> CreateFabricationMethodCommand:
        defaults = dict(name={"enGB": "Turning"})
        defaults.update(kwargs)
        return CreateFabricationMethodCommand(**defaults)

    async def test_creates_successfully(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.name == {"enGB": "Turning"}
        assert result.id > 0

    async def test_unprivileged_user_cannot_create(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=self._cmd())

    async def test_duplicate_name_raises(self):
        await self.repo.save(make_fabrication_method(name="Turning"))
        with pytest.raises(LabelTranslationConflictError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(name={"enGB": "Turning"}))

    async def test_defaults_are_preserved(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.label_color == "#999999"
        assert result.label_font_color == "#000000"
        assert result.description == {}

    async def test_creator_id_is_set(self):
        actor = make_user(id=7, permissions=[Permission.WRITE_FABRICATION_METHODS])
        result = await self.use_case.execute(actor=actor, cmd=self._cmd())
        assert result.creator_id == 7

    async def test_new_fields_round_trip(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=self._cmd(required_external=True, default_supplier_id=1),
        )
        assert result.required_external is True
        assert result.default_supplier_id == 1

    async def test_new_rows_are_never_archived(self):
        """`archived` is not a create field: a new row always starts
        live, only Archive/RestoreFabricationMethod ever flip it."""
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.archived is False

    async def test_unknown_default_supplier_raises(self):
        with pytest.raises(SupplierNotFoundError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(default_supplier_id=999))

    async def test_new_assembly_default_takes_the_flag_from_the_previous_holder(self):
        await self.repo.save(
            make_fabrication_method(id=5, name="Welding", default_for_assemblies=True)
        )
        result = await self.use_case.execute(
            actor=self.actor, cmd=self._cmd(default_for_assemblies=True)
        )
        previous = await self.repo.get_by_id(5)
        assert result.default_for_assemblies is True
        assert previous.default_for_assemblies is False
        assert "No longer the default for assemblies." in previous.changes[-1]
        assert previous.changed > datetime(2026, 1, 1, tzinfo=UTC)


# ── UpdateFabricationMethod ──────────────────────────────────────────


class TestUpdateFabricationMethod:
    def setup_method(self):
        self.method = make_fabrication_method(id=1, name="Milling")
        self.repo = FakeFabricationMethodRepository([self.method])
        self.supplier_repo = FakeSupplierRepository([make_supplier(id=1)])
        self.actor = make_user(permissions=[Permission.WRITE_FABRICATION_METHODS])
        self.use_case = UpdateFabricationMethod(
            self.repo, self.supplier_repo, settings=TenantSettings(), uow=FakeUnitOfWork()
        )

    def _cmd(self, **kwargs) -> UpdateFabricationMethodCommand:
        defaults = dict(
            name={"enGB": "Milling"},
            label_color="#111111",
            label_font_color="#ffffff",
            description={"enGB": "Updated"},
        )
        defaults.update(kwargs)
        return UpdateFabricationMethodCommand(**defaults)

    async def test_updates_successfully(self):
        result = await self.use_case.execute(
            actor=self.actor, fabrication_method_id=1, cmd=self._cmd(name={"enGB": "Turning"})
        )
        assert result.name == {"enGB": "Turning"}

    async def test_not_found_raises(self):
        with pytest.raises(FabricationMethodNotFoundError):
            await self.use_case.execute(
                actor=self.actor, fabrication_method_id=999, cmd=self._cmd()
            )

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, fabrication_method_id=1, cmd=self._cmd())

    async def test_changing_to_existing_name_raises(self):
        await self.repo.save(make_fabrication_method(id=2, name="Turning"))
        with pytest.raises(LabelTranslationConflictError):
            await self.use_case.execute(
                actor=self.actor, fabrication_method_id=1, cmd=self._cmd(name={"enGB": "Turning"})
            )

    async def test_keeping_same_name_does_not_raise(self):
        result = await self.use_case.execute(
            actor=self.actor, fabrication_method_id=1, cmd=self._cmd(name={"enGB": "Milling"})
        )
        assert result.name == {"enGB": "Milling"}

    async def test_new_fields_round_trip(self):
        result = await self.use_case.execute(
            actor=self.actor,
            fabrication_method_id=1,
            cmd=self._cmd(required_external=True, default_supplier_id=1),
        )
        assert result.required_external is True
        assert result.default_supplier_id == 1

    async def test_update_never_touches_archived(self):
        """`archived` is not an update field: only
        Archive/RestoreFabricationMethod ever flip it."""
        await self.use_case.execute(actor=self.actor, fabrication_method_id=1, cmd=self._cmd())
        assert (await self.repo.get_by_id(1)).archived is False

    async def test_unknown_default_supplier_raises(self):
        with pytest.raises(SupplierNotFoundError):
            await self.use_case.execute(
                actor=self.actor, fabrication_method_id=1, cmd=self._cmd(default_supplier_id=999)
            )

    async def test_changelog_records_field_changes(self):
        await self.use_case.execute(
            actor=self.actor, fabrication_method_id=1, cmd=self._cmd(required_external=True)
        )
        saved = await self.repo.get_by_id(1)
        assert "required_external" in saved.changes[-1]

    async def test_setting_assembly_default_moves_the_flag_off_the_previous_holder(self):
        await self.repo.save(
            make_fabrication_method(id=2, name="Welding", default_for_assemblies=True)
        )
        result = await self.use_case.execute(
            actor=self.actor, fabrication_method_id=1, cmd=self._cmd(default_for_assemblies=True)
        )
        previous = await self.repo.get_by_id(2)
        assert result.default_for_assemblies is True
        assert previous.default_for_assemblies is False
        assert "No longer the default for assemblies." in previous.changes[-1]
        assert "default_for_assemblies" in (await self.repo.get_by_id(1)).changes[-1]

    async def test_resaving_the_current_holder_leaves_other_methods_alone(self):
        self.method.default_for_assemblies = True
        other = make_fabrication_method(id=2, name="Welding")
        await self.repo.save(other)
        result = await self.use_case.execute(
            actor=self.actor, fabrication_method_id=1, cmd=self._cmd(default_for_assemblies=True)
        )
        assert result.default_for_assemblies is True
        assert other.changes == []

    async def test_unsetting_assembly_default_leaves_no_default(self):
        self.method.default_for_assemblies = True
        await self.use_case.execute(actor=self.actor, fabrication_method_id=1, cmd=self._cmd())
        assert await self.repo.get_default_for_assemblies() is None

    async def test_archived_method_cannot_become_assembly_default(self):
        self.method.archived = True
        with pytest.raises(FabricationMethodArchivedError):
            await self.use_case.execute(
                actor=self.actor,
                fabrication_method_id=1,
                cmd=self._cmd(default_for_assemblies=True),
            )


# ── ArchiveFabricationMethod / RestoreFabricationMethod ───────────────


class TestArchiveFabricationMethod:
    def setup_method(self):
        self.method = make_fabrication_method(id=1)
        self.repo = FakeFabricationMethodRepository([self.method])
        self.actor = make_user(permissions=[Permission.WRITE_FABRICATION_METHODS])
        self.use_case = ArchiveFabricationMethod(self.repo, uow=FakeUnitOfWork())

    async def test_archives_successfully(self):
        result = await self.use_case.execute(actor=self.actor, fabrication_method_id=1)
        assert result.archived is True

    async def test_archiving_twice_is_idempotent(self):
        await self.use_case.execute(actor=self.actor, fabrication_method_id=1)
        result = await self.use_case.execute(actor=self.actor, fabrication_method_id=1)
        assert result.archived is True

    async def test_not_found_raises(self):
        with pytest.raises(FabricationMethodNotFoundError):
            await self.use_case.execute(actor=self.actor, fabrication_method_id=999)

    async def test_unprivileged_cannot_archive(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, fabrication_method_id=1)

    async def test_archiving_the_assembly_default_clears_it(self):
        self.method.default_for_assemblies = True
        result = await self.use_case.execute(actor=self.actor, fabrication_method_id=1)
        assert result.archived is True
        assert result.default_for_assemblies is False
        assert "No longer the default for assemblies." in self.method.changes[-1]


class TestRestoreFabricationMethod:
    def setup_method(self):
        self.actor = make_user(permissions=[Permission.WRITE_FABRICATION_METHODS])

    async def test_restores_successfully(self):
        method = make_fabrication_method(id=1, archived=True)
        repo = FakeFabricationMethodRepository([method])
        result = await RestoreFabricationMethod(repo, uow=FakeUnitOfWork()).execute(
            actor=self.actor, fabrication_method_id=1
        )
        assert result.archived is False

    async def test_restore_conflicts_when_name_already_taken_by_a_live_method(self):
        archived = make_fabrication_method(id=1, name="Milling", archived=True)
        live = make_fabrication_method(id=2, name="Milling", archived=False)
        repo = FakeFabricationMethodRepository([archived, live])
        with pytest.raises(LabelTranslationConflictError):
            await RestoreFabricationMethod(repo, uow=FakeUnitOfWork()).execute(
                actor=self.actor, fabrication_method_id=1
            )

    async def test_not_found_raises(self):
        repo = FakeFabricationMethodRepository([])
        with pytest.raises(FabricationMethodNotFoundError):
            await RestoreFabricationMethod(repo, uow=FakeUnitOfWork()).execute(
                actor=self.actor, fabrication_method_id=999
            )


# ── GetFabricationMethod / GetFabricationMethods ─────────────────────


class TestGetFabricationMethod:
    def setup_method(self):
        self.methods = [
            make_fabrication_method(id=1, name="Alpha"),
            make_fabrication_method(id=2, name="Beta"),
            make_fabrication_method(id=3, name="Gamma"),
        ]
        self.repo = FakeFabricationMethodRepository(self.methods)

    async def test_get_existing(self):
        result = await GetFabricationMethod(self.repo).execute(fabrication_method_id=1)
        assert result.name == {"enGB": "Alpha"}

    async def test_get_nonexistent_raises(self):
        with pytest.raises(FabricationMethodNotFoundError):
            await GetFabricationMethod(self.repo).execute(fabrication_method_id=999)

    async def test_get_all(self):
        result = await GetFabricationMethods(self.repo).execute(
            filters=FabricationMethodFilterDto()
        )
        assert result.total == 3
        assert len(result.items) == 3

    async def test_get_with_limit(self):
        result = await GetFabricationMethods(self.repo).execute(
            filters=FabricationMethodFilterDto(limit=1)
        )
        assert len(result.items) == 1

    async def test_get_with_name_filter(self):
        result = await GetFabricationMethods(self.repo).execute(
            filters=FabricationMethodFilterDto(name="beta")
        )
        assert result.total == 1
        assert result.items[0].name == {"enGB": "Beta"}

    async def test_archived_excluded_by_default(self):
        await self.repo.save(make_fabrication_method(id=4, name="Delta", archived=True))
        result = await GetFabricationMethods(self.repo).execute(
            filters=FabricationMethodFilterDto()
        )
        assert result.total == 3
        assert all(not m.archived for m in result.items)

    async def test_include_archived_returns_everything(self):
        await self.repo.save(make_fabrication_method(id=4, name="Delta", archived=True))
        result = await GetFabricationMethods(self.repo).execute(
            filters=FabricationMethodFilterDto(include_archived=True)
        )
        assert result.total == 4


class TestGetAssemblyDefaultFabricationMethod:
    async def test_returns_the_flagged_method(self):
        repo = FakeFabricationMethodRepository(
            [
                make_fabrication_method(id=1, name="Milling"),
                make_fabrication_method(id=2, name="Welding", default_for_assemblies=True),
            ]
        )
        result = await GetAssemblyDefaultFabricationMethod(repo).execute()
        assert result is not None
        assert result.id == 2

    async def test_returns_none_when_no_method_is_flagged(self):
        repo = FakeFabricationMethodRepository([make_fabrication_method(id=1)])
        assert await GetAssemblyDefaultFabricationMethod(repo).execute() is None
