"""
Unit tests for all inspection method use cases.
No database, no HTTP. All dependencies replaced with in-memory fakes.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from src.modules.catalogue.application.dto.inspection_method_dto import (
    CreateInspectionMethodCommand,
)
from src.modules.catalogue.application.dto.inspection_method_dto import (
    UpdateInspectionMethodCommand,
)
from src.modules.catalogue.application.use_cases.inspection_method.archive_inspection_method import (
    ArchiveInspectionMethod,
)
from src.modules.catalogue.application.use_cases.inspection_method.create_inspection_method import (
    CreateInspectionMethod,
)
from src.modules.catalogue.application.use_cases.inspection_method.get_inspection_method import (
    GetInspectionMethod,
)
from src.modules.catalogue.application.use_cases.inspection_method.get_inspection_method import (
    GetInspectionMethods,
)
from src.modules.catalogue.application.use_cases.inspection_method.restore_inspection_method import (
    RestoreInspectionMethod,
)
from src.modules.catalogue.application.use_cases.inspection_method.update_inspection_method import (
    UpdateInspectionMethod,
)
from src.modules.catalogue.domain.entities.inspection_method import InspectionMethod
from src.modules.catalogue.domain.errors import InspectionMethodConfigurationError
from src.modules.catalogue.domain.errors import InspectionMethodNotFoundError
from src.modules.catalogue.domain.errors import LabelTranslationConflictError
from src.modules.catalogue.domain.errors import MachineCapabilityMismatchError
from src.modules.catalogue.domain.errors import ProductionMachineNotFoundError
from src.modules.catalogue.ports.outbound.repositories.inspection_method_repository import (
    InspectionMethodFilterDto,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit._tenant_settings import TenantSettings
from tests.unit.fakes import FakeUnitOfWork

# ── Helpers ───────────────────────────────────────────────────────────


def make_inspection_method(
    id: int = 1,
    name: str = "Visual Inspection",
    requires_evidence: bool = False,
    archived: bool = False,
    default_machine_id: int | None = None,
) -> InspectionMethod:
    return InspectionMethod(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        name=LocalizedText({"enGB": name}),
        label_color="#999999",
        label_font_color="#000000",
        description=LocalizedText(),
        creator_id=1,
        requires_evidence=requires_evidence,
        archived=archived,
        default_machine_id=default_machine_id,
    )


def make_machine(
    id: int = 1,
    is_qa_machine: bool = True,
    archived: bool = False,
) -> ProductionMachine:
    return ProductionMachine(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        archived=archived,
        internal_name=f"Machine {id}",
        vendor="Fabrikam",
        model="CMM-500",
        fabrication_method_ids=[],
        max_part_dimension=None,
        note=None,
        creator_id=1,
        is_qa_machine=is_qa_machine,
    )


class FakeInspectionMethodRepository:
    def __init__(self, methods: list[InspectionMethod] | None = None):
        self._methods: dict[int, InspectionMethod] = {}
        self._next_id = 1
        for m in methods or []:
            self._methods[m.id] = m
            self._next_id = max(self._next_id, m.id + 1)

    async def get_by_id(self, id: int) -> InspectionMethod | None:
        return self._methods.get(id)

    async def get_live_names(self) -> list[tuple[int, LocalizedText]]:
        return [(m.id, m.name) for m in self._methods.values() if not m.archived]

    async def get_multi(
        self, filters: InspectionMethodFilterDto
    ) -> tuple[int, list[InspectionMethod]]:
        results = list(self._methods.values())
        if filters.name:
            results = [
                m
                for m in results
                if any(filters.name.lower() in text.lower() for text in m.name.values.values())
            ]
        if not filters.include_archived:
            results = [m for m in results if not m.archived]
        total = len(results)
        skip = filters.skip or 0
        limit = filters.limit
        return total, results[skip : skip + limit if limit else None]

    async def next_sort_order(self) -> int:
        return max((row.sort_order for row in self._methods.values()), default=-1) + 1

    async def save(self, inspection_method: InspectionMethod) -> InspectionMethod:
        if inspection_method.id == 0:
            inspection_method.id = self._next_id
            self._next_id += 1
        self._methods[inspection_method.id] = inspection_method
        return inspection_method

    async def delete(self, inspection_method: InspectionMethod) -> None:
        raise NotImplementedError


class FakeProductionMachineRepository:
    """get_by_id only: the only method create/update_inspection_method.py's
    default-machine validation calls. Mirrors the real repository's
    archived=False filter: an archived machine reads as not found."""

    def __init__(self, machines: list[ProductionMachine] | None = None) -> None:
        self._machines = {m.id: m for m in (machines or [])}

    async def get_by_id(self, id: int) -> ProductionMachine | None:
        machine = self._machines.get(id)
        return machine if machine and not machine.archived else None

    async def get_by_ids(self, ids: list[int]) -> list:
        found = [await self.get_by_id(i) for i in ids]
        return [item for item in found if item is not None]


class FakeAdminSettingsRepository:
    def __init__(self, default_inspection_method_id: int | None = None):
        self._default_inspection_method_id = default_inspection_method_id

    async def get_production(self) -> AdminProductionSettings:
        return AdminProductionSettings(
            id=1,
            production_order_number_format="PO-{year}-{seq:04d}",
            default_weekly_hours={0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0},
            default_external_lead_days=0,
            response_time_days=1,
            require_qa=self._default_inspection_method_id is not None,
            default_inspection_method_id=self._default_inspection_method_id,
        )


# ── CreateInspectionMethod ───────────────────────────────────────────


class TestCreateInspectionMethod:
    def setup_method(self):
        self.repo = FakeInspectionMethodRepository()
        self.machine_repo = FakeProductionMachineRepository([make_machine(id=1)])
        self.actor = make_user(permissions=[Permission.WRITE_INSPECTION_METHODS])
        self.use_case = CreateInspectionMethod(
            self.repo, self.machine_repo, settings=TenantSettings(), uow=FakeUnitOfWork()
        )

    def _cmd(self, **kwargs) -> CreateInspectionMethodCommand:
        defaults = dict(name={"enGB": "Measurement"})
        defaults.update(kwargs)
        return CreateInspectionMethodCommand(**defaults)

    async def test_creates_successfully(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.name == {"enGB": "Measurement"}
        assert result.id > 0

    async def test_unprivileged_user_cannot_create(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=self._cmd())

    async def test_duplicate_name_raises(self):
        await self.repo.save(make_inspection_method(name="Measurement"))
        with pytest.raises(LabelTranslationConflictError):
            await self.use_case.execute(
                actor=self.actor, cmd=self._cmd(name={"enGB": "Measurement"})
            )

    async def test_defaults_are_preserved(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.label_color == "#999999"
        assert result.label_font_color == "#000000"
        assert result.description == {}
        assert result.requires_evidence is False
        assert result.archived is False

    async def test_new_rows_are_never_archived(self):
        # `archived` is not a Create field at all (see
        # ArchiveInspectionMethod/RestoreInspectionMethod); a freshly
        # created method is always live.
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.archived is False

    async def test_creator_id_is_set(self):
        actor = make_user(id=7, permissions=[Permission.WRITE_INSPECTION_METHODS])
        result = await self.use_case.execute(actor=actor, cmd=self._cmd())
        assert result.creator_id == 7

    async def test_requires_evidence_round_trips(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=self._cmd(requires_evidence=True)
        )
        assert result.requires_evidence is True

    async def test_default_machine_id_round_trips_for_a_valid_qa_machine(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd(default_machine_id=1))
        assert result.default_machine_id == 1

    async def test_default_machine_id_none_stays_none(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.default_machine_id is None

    async def test_missing_default_machine_raises(self):
        with pytest.raises(ProductionMachineNotFoundError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(default_machine_id=999))

    async def test_non_qa_default_machine_raises(self):
        self.machine_repo = FakeProductionMachineRepository(
            [make_machine(id=2, is_qa_machine=False)]
        )
        self.use_case = CreateInspectionMethod(
            self.repo, self.machine_repo, settings=TenantSettings(), uow=FakeUnitOfWork()
        )
        with pytest.raises(MachineCapabilityMismatchError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(default_machine_id=2))


# ── UpdateInspectionMethod ───────────────────────────────────────────


class TestUpdateInspectionMethod:
    def setup_method(self):
        self.method = make_inspection_method(id=1, name="Visual Inspection")
        self.repo = FakeInspectionMethodRepository([self.method])
        self.machine_repo = FakeProductionMachineRepository([make_machine(id=1)])
        self.actor = make_user(permissions=[Permission.WRITE_INSPECTION_METHODS])
        self.use_case = UpdateInspectionMethod(
            self.repo, self.machine_repo, settings=TenantSettings(), uow=FakeUnitOfWork()
        )

    def _cmd(self, **kwargs) -> UpdateInspectionMethodCommand:
        defaults = dict(
            name={"enGB": "Visual Inspection"},
            label_color="#111111",
            label_font_color="#ffffff",
            description={"enGB": "Updated"},
        )
        defaults.update(kwargs)
        return UpdateInspectionMethodCommand(**defaults)

    async def test_updates_successfully(self):
        result = await self.use_case.execute(
            actor=self.actor, inspection_method_id=1, cmd=self._cmd(name={"enGB": "Measurement"})
        )
        assert result.name == {"enGB": "Measurement"}

    async def test_not_found_raises(self):
        with pytest.raises(InspectionMethodNotFoundError):
            await self.use_case.execute(actor=self.actor, inspection_method_id=999, cmd=self._cmd())

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, inspection_method_id=1, cmd=self._cmd())

    async def test_changing_to_existing_name_raises(self):
        await self.repo.save(make_inspection_method(id=2, name="Measurement"))
        with pytest.raises(LabelTranslationConflictError):
            await self.use_case.execute(
                actor=self.actor,
                inspection_method_id=1,
                cmd=self._cmd(name={"enGB": "Measurement"}),
            )

    async def test_keeping_same_name_does_not_raise(self):
        result = await self.use_case.execute(
            actor=self.actor,
            inspection_method_id=1,
            cmd=self._cmd(name={"enGB": "Visual Inspection"}),
        )
        assert result.name == {"enGB": "Visual Inspection"}

    async def test_requires_evidence_round_trips(self):
        result = await self.use_case.execute(
            actor=self.actor, inspection_method_id=1, cmd=self._cmd(requires_evidence=True)
        )
        assert result.requires_evidence is True

    async def test_update_never_touches_archived(self):
        # `archived` is not an Update field at all; it is only settable
        # via ArchiveInspectionMethod/RestoreInspectionMethod.
        self.method.archived = True
        result = await self.use_case.execute(
            actor=self.actor, inspection_method_id=1, cmd=self._cmd(name={"enGB": "Renamed"})
        )
        assert result.archived is True

    async def test_changelog_records_field_changes(self):
        await self.use_case.execute(
            actor=self.actor, inspection_method_id=1, cmd=self._cmd(requires_evidence=True)
        )
        saved = await self.repo.get_by_id(1)
        assert "requires_evidence" in saved.changes[-1]

    async def test_setting_a_valid_qa_machine_succeeds(self):
        result = await self.use_case.execute(
            actor=self.actor, inspection_method_id=1, cmd=self._cmd(default_machine_id=1)
        )
        assert result.default_machine_id == 1

    async def test_clearing_the_default_machine_succeeds(self):
        self.method.default_machine_id = 1
        result = await self.use_case.execute(
            actor=self.actor, inspection_method_id=1, cmd=self._cmd(default_machine_id=None)
        )
        assert result.default_machine_id is None

    async def test_missing_default_machine_raises(self):
        with pytest.raises(ProductionMachineNotFoundError):
            await self.use_case.execute(
                actor=self.actor, inspection_method_id=1, cmd=self._cmd(default_machine_id=999)
            )

    async def test_non_qa_default_machine_raises(self):
        self.machine_repo = FakeProductionMachineRepository(
            [make_machine(id=2, is_qa_machine=False)]
        )
        self.use_case = UpdateInspectionMethod(
            self.repo, self.machine_repo, settings=TenantSettings(), uow=FakeUnitOfWork()
        )
        with pytest.raises(MachineCapabilityMismatchError):
            await self.use_case.execute(
                actor=self.actor, inspection_method_id=1, cmd=self._cmd(default_machine_id=2)
            )

    async def test_changelog_mentions_default_machine_id_only_when_it_changes(self):
        # Saving with the same default_machine_id (None, unset) must not
        # manufacture a spurious changelog entry, so `old` must carry
        # default_machine_id too (diff_changes compares against the whole
        # command dump).
        await self.use_case.execute(actor=self.actor, inspection_method_id=1, cmd=self._cmd())
        saved = await self.repo.get_by_id(1)
        assert "default_machine_id" not in saved.changes[-1]

        await self.use_case.execute(
            actor=self.actor, inspection_method_id=1, cmd=self._cmd(default_machine_id=1)
        )
        saved = await self.repo.get_by_id(1)
        assert "default_machine_id" in saved.changes[-1]


# ── ArchiveInspectionMethod / RestoreInspectionMethod ────────────────


class TestArchiveInspectionMethod:
    def setup_method(self):
        self.method = make_inspection_method(id=1)
        self.repo = FakeInspectionMethodRepository([self.method])
        self.settings_repo = FakeAdminSettingsRepository(default_inspection_method_id=None)
        self.actor = make_user(permissions=[Permission.WRITE_INSPECTION_METHODS])
        self.use_case = ArchiveInspectionMethod(self.repo, self.settings_repo, uow=FakeUnitOfWork())

    async def test_archives_successfully(self):
        result = await self.use_case.execute(actor=self.actor, inspection_method_id=1)
        assert result.archived is True

    async def test_archiving_twice_is_idempotent(self):
        await self.use_case.execute(actor=self.actor, inspection_method_id=1)
        result = await self.use_case.execute(actor=self.actor, inspection_method_id=1)
        assert result.archived is True

    async def test_not_found_raises(self):
        with pytest.raises(InspectionMethodNotFoundError):
            await self.use_case.execute(actor=self.actor, inspection_method_id=999)

    async def test_unprivileged_cannot_archive(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, inspection_method_id=1)

    async def test_archiving_the_settings_default_raises(self):
        self.settings_repo = FakeAdminSettingsRepository(default_inspection_method_id=1)
        self.use_case = ArchiveInspectionMethod(self.repo, self.settings_repo, uow=FakeUnitOfWork())
        with pytest.raises(InspectionMethodConfigurationError):
            await self.use_case.execute(actor=self.actor, inspection_method_id=1)

    async def test_re_archiving_an_already_archived_default_does_not_raise(self):
        # The guard only fires when transitioning live -> archived; a
        # method that is already archived (however it got that way) can
        # always be re-archived idempotently even while it is still the
        # settings default.
        self.method.archived = True
        self.settings_repo = FakeAdminSettingsRepository(default_inspection_method_id=1)
        self.use_case = ArchiveInspectionMethod(self.repo, self.settings_repo, uow=FakeUnitOfWork())
        result = await self.use_case.execute(actor=self.actor, inspection_method_id=1)
        assert result.archived is True


class TestRestoreInspectionMethod:
    def setup_method(self):
        self.actor = make_user(permissions=[Permission.WRITE_INSPECTION_METHODS])

    async def test_restores_successfully(self):
        method = make_inspection_method(id=1, archived=True)
        repo = FakeInspectionMethodRepository([method])
        result = await RestoreInspectionMethod(repo, uow=FakeUnitOfWork()).execute(
            actor=self.actor, inspection_method_id=1
        )
        assert result.archived is False

    async def test_restoring_twice_is_idempotent(self):
        method = make_inspection_method(id=1, archived=True)
        repo = FakeInspectionMethodRepository([method])
        use_case = RestoreInspectionMethod(repo, uow=FakeUnitOfWork())
        await use_case.execute(actor=self.actor, inspection_method_id=1)
        result = await use_case.execute(actor=self.actor, inspection_method_id=1)
        assert result.archived is False

    async def test_restore_conflicts_when_name_already_taken_by_a_live_method(self):
        archived = make_inspection_method(id=1, name="Visual Inspection", archived=True)
        live = make_inspection_method(id=2, name="Visual Inspection", archived=False)
        repo = FakeInspectionMethodRepository([archived, live])
        with pytest.raises(LabelTranslationConflictError):
            await RestoreInspectionMethod(repo, uow=FakeUnitOfWork()).execute(
                actor=self.actor, inspection_method_id=1
            )

    async def test_not_found_raises(self):
        repo = FakeInspectionMethodRepository([])
        with pytest.raises(InspectionMethodNotFoundError):
            await RestoreInspectionMethod(repo, uow=FakeUnitOfWork()).execute(
                actor=self.actor, inspection_method_id=999
            )

    async def test_unprivileged_cannot_restore(self):
        method = make_inspection_method(id=1, archived=True)
        repo = FakeInspectionMethodRepository([method])
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await RestoreInspectionMethod(repo, uow=FakeUnitOfWork()).execute(
                actor=actor, inspection_method_id=1
            )


# ── GetInspectionMethod / GetInspectionMethods ───────────────────────


class TestGetInspectionMethod:
    def setup_method(self):
        self.methods = [
            make_inspection_method(id=1, name="Alpha"),
            make_inspection_method(id=2, name="Beta"),
            make_inspection_method(id=3, name="Gamma"),
        ]
        self.repo = FakeInspectionMethodRepository(self.methods)

    async def test_get_existing(self):
        result = await GetInspectionMethod(self.repo).execute(inspection_method_id=1)
        assert result.name == {"enGB": "Alpha"}

    async def test_get_nonexistent_raises(self):
        with pytest.raises(InspectionMethodNotFoundError):
            await GetInspectionMethod(self.repo).execute(inspection_method_id=999)

    async def test_get_all(self):
        result = await GetInspectionMethods(self.repo).execute(filters=InspectionMethodFilterDto())
        assert result.total == 3
        assert len(result.items) == 3

    async def test_get_with_limit(self):
        result = await GetInspectionMethods(self.repo).execute(
            filters=InspectionMethodFilterDto(limit=1)
        )
        assert len(result.items) == 1

    async def test_get_with_name_filter(self):
        result = await GetInspectionMethods(self.repo).execute(
            filters=InspectionMethodFilterDto(name="beta")
        )
        assert result.total == 1
        assert result.items[0].name == {"enGB": "Beta"}

    async def test_archived_excluded_by_default(self):
        await self.repo.save(make_inspection_method(id=4, name="Delta"))
        archived = await self.repo.get_by_id(4)
        archived.archived = True
        await self.repo.save(archived)
        result = await GetInspectionMethods(self.repo).execute(
            filters=InspectionMethodFilterDto(include_archived=False)
        )
        assert result.total == 3
        assert all(not m.archived for m in result.items)

    async def test_include_archived_returns_everything(self):
        await self.repo.save(make_inspection_method(id=4, name="Delta"))
        archived = await self.repo.get_by_id(4)
        archived.archived = True
        await self.repo.save(archived)
        result = await GetInspectionMethods(self.repo).execute(
            filters=InspectionMethodFilterDto(include_archived=True)
        )
        assert result.total == 4
