"""
Unit tests for saved calculations: who may see, change, release, revise
and delete one (CalculationRules), the use cases around them, and the
document control they share with checklists (revisions, edit lock). No
database, no HTTP, repositories replaced with in-memory fakes.
"""

from dataclasses import dataclass
from dataclasses import replace
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any
from uuid import UUID

import pytest

from src.modules.catalogue.domain.policies import revision_scheme
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.quality.application.dto.calculation_dto import CreateCalculationCommand
from src.modules.quality.application.dto.calculation_dto import ReviseCalculationCommand
from src.modules.quality.application.dto.calculation_dto import UpdateCalculationCommand
from src.modules.quality.application.dto.controlled_document_dto import LockCommand
from src.modules.quality.application.dto.controlled_document_dto import MarkInvalidCommand
from src.modules.quality.application.use_cases.calculation.delete_calculation import (
    DeleteCalculation,
)
from src.modules.quality.application.use_cases.calculation.get_calculations import (
    CalculationListQuery,
)
from src.modules.quality.application.use_cases.calculation.get_calculations import GetCalculation
from src.modules.quality.application.use_cases.calculation.get_calculations import (
    GetCalculationByPublicId,
)
from src.modules.quality.application.use_cases.calculation.get_calculations import (
    GetCalculationRevisions,
)
from src.modules.quality.application.use_cases.calculation.get_calculations import GetCalculations
from src.modules.quality.application.use_cases.calculation.lock_calculation import LockCalculation
from src.modules.quality.application.use_cases.calculation.lock_calculation import UnlockCalculation
from src.modules.quality.application.use_cases.calculation.release_calculation import (
    MarkCalculationInvalid,
)
from src.modules.quality.application.use_cases.calculation.release_calculation import (
    ReleaseCalculation,
)
from src.modules.quality.application.use_cases.calculation.revise_calculation import (
    ReviseCalculation,
)
from src.modules.quality.application.use_cases.calculation.save_calculation import CreateCalculation
from src.modules.quality.application.use_cases.calculation.save_calculation import UpdateCalculation
from src.modules.quality.domain.entities.calculation import Calculation
from src.modules.quality.domain.errors import CalculationAlreadyReleasedError
from src.modules.quality.domain.errors import CalculationNotFoundError
from src.modules.quality.domain.errors import CalculationNotLatestRevisionError
from src.modules.quality.domain.errors import CalculationNotReleasedError
from src.modules.quality.domain.errors import CalculationOfAnotherUserError
from src.modules.quality.domain.errors import CalculationOwnerConflictError
from src.modules.quality.domain.errors import CalculationReleasedError
from src.modules.quality.domain.errors import DocumentAlreadyInvalidError
from src.modules.quality.domain.errors import DocumentLockedError
from src.modules.quality.domain.errors import DocumentNotLockedError
from src.modules.quality.domain.errors import DocumentNotReleasedError
from src.modules.quality.domain.errors import ReleasedDocumentDeleteError
from src.modules.quality.domain.services.calculation_rules import CalculationRules
from src.modules.quality.domain.services.document_control import LOCK_LEASE
from src.modules.quality.ports.outbound.repositories.calculation_repository import (
    CalculationFilterDto,
)
from src.modules.workspace.domain.entities.product import Product
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.domain.errors import ProductArchivedError
from src.modules.workspace.domain.errors import ProjectNotFoundError
from src.shared_kernel.domain.services.clock import now_utc
from tests import factories
from tests.unit.fakes import FakeEventBus
from tests.unit.fakes import FakeUnitOfWork

WRITE = [Permission.WRITE_CALCULATIONS]
RELEASE = [Permission.RELEASE_CALCULATIONS]
MANAGE = [Permission.WRITE_CALCULATIONS, Permission.MANAGE_CALCULATIONS]

# ── Helpers ───────────────────────────────────────────────────────────


def make_user(*, id: int = 1, **overrides: Any) -> User:
    """A user named "User <id>", the name the lock messages and the change log quote."""
    return factories.make_user(id=id, full_name=f"User {id}", **overrides)


def make_calculation(
    id: int = 1,
    creator_id: int = 1,
    project_id: int | None = None,
    product_id: int | None = None,
    released: bool = False,
    locked_by: int | None = None,
) -> Calculation:
    now = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
    return Calculation(
        id=id,
        created=now,
        changed=now,
        changes=[],
        tool="fit_calculator",
        title="Bearing seat",
        note=None,
        inputs={"d": 25, "hole": "H7", "shaft": "g6"},
        results={"fit": "clearance"},
        input_version=1,
        engine_version=1,
        project_id=project_id,
        product_id=product_id,
        creator_id=creator_id,
        released_at=now if released else None,
        released_by_id=creator_id if released else None,
        # A live edit lock of this user, as Edit leaves it before a save.
        locked_by_id=locked_by,
        locked_at=now_utc() if locked_by else None,
        lock_expires_at=now_utc() + timedelta(minutes=10) if locked_by else None,
    )


class FakeCalculationRepository:
    def __init__(self, items: list[Calculation] | None = None) -> None:
        self.items: dict[int, Calculation] = {c.id: c for c in items or []}
        self.last_filters: CalculationFilterDto | None = None
        self.locked: list[int] = []

    async def get_by_id(self, id: int) -> Calculation | None:
        item = self.items.get(id)
        return replace(item) if item else None

    async def get_for_update(self, id: int) -> Calculation | None:
        self.locked.append(id)
        return await self.get_by_id(id)

    async def get_by_public_id(self, public_id: UUID) -> Calculation | None:
        item = next((c for c in self.items.values() if c.public_id == public_id), None)
        return replace(item) if item else None

    async def get_multi(self, filters: CalculationFilterDto) -> tuple[int, list[Calculation]]:
        self.last_filters = filters
        rows = list(self.items.values())
        return len(rows), rows

    async def get_lineage(self, lineage: UUID) -> list[Calculation]:
        rows = [replace(c) for c in self.items.values() if c.lineage == lineage]
        return sorted(rows, key=lambda c: revision_scheme.sort_key(c.revision), reverse=True)

    async def next_document_number(self, template: str) -> str:
        """Numbers like the real repository, without its date placeholders."""
        taken = {c.document_number for c in self.items.values()}
        return f"DOC-{len(taken) + 1:04d}"

    async def save(self, item: Calculation) -> Calculation:
        if item.id == 0:
            item = replace(item, id=max(self.items, default=0) + 1)
        latest = [
            c
            for c in self.items.values()
            if c.lineage == item.lineage and c.is_latest and c.id != item.id
        ]
        # The one latest revision per lineage index of the real table.
        assert not (item.is_latest and latest), "two latest revisions in one lineage"
        self.items[item.id] = replace(item)
        return item

    async def delete(self, item: Calculation) -> None:
        self.items.pop(item.id, None)


class FakeProjectRepository:
    def __init__(self, ids: set[int]) -> None:
        self._ids = ids

    async def get_by_id(self, id: int) -> Project | None:
        if id not in self._ids:
            return None
        return Project(id=id, created=datetime.now(UTC), project_number=f"P-{id}")


class FakeProductRepository:
    def __init__(self, live: set[int], archived: set[int] | None = None) -> None:
        self._live = live
        self._archived = archived or set()

    async def get_by_id(self, id: int) -> Product | None:
        if id not in self._live | self._archived:
            return None
        return Product(
            id=id,
            created=datetime.now(UTC),
            product_number=f"PR-{id}",
            archived=id in self._archived,
        )


@dataclass
class _RevisionSettings:
    revision_start: str = "0"
    revision_skip_ambiguous_letters: bool = False
    calculation_number_format: str = "CAL-{yy}-{seq:04d}"
    checklist_number_format: str = "CHK-{yy}-{seq:04d}"


class FakeAdminSettingsRepository:
    def __init__(self, start: str = "0") -> None:
        self._settings = _RevisionSettings(start)

    async def get_made_items(self) -> _RevisionSettings:
        return self._settings


class FakeDeviceRepository:
    """No devices: these tests save calculations without a device."""

    async def get_by_id(self, id: int) -> None:
        return None


def writer_kwargs(repo: FakeCalculationRepository, uow: FakeUnitOfWork) -> dict[str, Any]:
    return {
        "calculation_repo": repo,
        "project_repo": FakeProjectRepository({10}),
        "product_repo": FakeProductRepository({20}, archived={21}),
        "device_repo": FakeDeviceRepository(),
        "uow": uow,
    }


def create_kwargs(
    repo: FakeCalculationRepository, uow: FakeUnitOfWork, start: str = "0"
) -> dict[str, Any]:
    return writer_kwargs(repo, uow) | {"admin_settings_repo": FakeAdminSettingsRepository(start)}


def create_cmd(**overrides: Any) -> CreateCalculationCommand:
    body: dict[str, Any] = {
        "tool": "fit_calculator",
        "title": "Bearing seat",
        "inputs": {"d": 25},
        "results": {"fit": "clearance"},
        "input_version": 1,
        "engine_version": 1,
    }
    return CreateCalculationCommand(**(body | overrides))


def update_cmd(**overrides: Any) -> UpdateCalculationCommand:
    body: dict[str, Any] = {
        "title": "Bearing seat",
        "inputs": {"d": 30},
        "results": {"fit": "transition"},
        "input_version": 1,
        "engine_version": 2,
    }
    return UpdateCalculationCommand(**(body | overrides))


# ── Rules ─────────────────────────────────────────────────────────────


class TestVisibility:
    def test_calculation_personal_visible_only_to_creator_and_manager(self) -> None:
        personal = make_calculation(creator_id=1)
        assert CalculationRules.can_view(make_user(id=1), personal)
        assert not CalculationRules.can_view(make_user(id=2), personal)
        assert CalculationRules.can_view(make_user(id=2, permissions=MANAGE), personal)

    def test_calculation_on_project_visible_to_everyone(self) -> None:
        assert CalculationRules.can_view(make_user(id=2), make_calculation(project_id=10))
        assert CalculationRules.can_view(make_user(id=2), make_calculation(product_id=20))

    def test_calculation_owner_conflict_rejected(self) -> None:
        with pytest.raises(CalculationOwnerConflictError):
            CalculationRules.assert_valid_owner(10, 20)


class TestEditRules:
    def test_calculation_update_by_other_user_needs_manage(self) -> None:
        calc = make_calculation(creator_id=1, project_id=10)
        with pytest.raises(CalculationOfAnotherUserError):
            CalculationRules.assert_can_update(make_user(id=2, permissions=WRITE), calc)
        CalculationRules.assert_can_update(
            make_user(id=2, permissions=MANAGE), calc
        )  # must not raise

    def test_calculation_released_is_read_only_even_for_manager(self) -> None:
        calc = make_calculation(released=True, project_id=10)
        with pytest.raises(CalculationReleasedError):
            CalculationRules.assert_can_update(make_user(id=1, permissions=MANAGE), calc)

    def test_calculation_released_is_never_deleted(self) -> None:
        calc = make_calculation(released=True, project_id=10)
        with pytest.raises(ReleasedDocumentDeleteError):
            CalculationRules.assert_can_delete(make_user(id=2, permissions=MANAGE), calc)

    def test_calculation_release_by_author_allowed(self) -> None:
        calc = make_calculation(creator_id=1)
        CalculationRules.assert_can_release(
            make_user(id=1, permissions=RELEASE), calc
        )  # must not raise
        with pytest.raises(InsufficientPermissionsError):
            CalculationRules.assert_can_release(make_user(id=1, permissions=WRITE), calc)


# ── Use cases ─────────────────────────────────────────────────────────


class TestCreate:
    async def test_calculation_create_personal(self, fake_uow: FakeUnitOfWork) -> None:
        repo = FakeCalculationRepository()
        result = await CreateCalculation(**create_kwargs(repo, fake_uow)).execute(
            make_user(id=1, permissions=WRITE), create_cmd()
        )
        assert result.creator_id == 1
        assert result.project_id is None and result.product_id is None
        assert result.released_at is None
        assert fake_uow.committed

    async def test_calculation_create_needs_permission(self, fake_uow: FakeUnitOfWork) -> None:
        with pytest.raises(InsufficientPermissionsError):
            await CreateCalculation(**create_kwargs(FakeCalculationRepository(), fake_uow)).execute(
                make_user(id=1), create_cmd()
            )

    async def test_calculation_create_unknown_project(self, fake_uow: FakeUnitOfWork) -> None:
        with pytest.raises(ProjectNotFoundError):
            await CreateCalculation(**create_kwargs(FakeCalculationRepository(), fake_uow)).execute(
                make_user(id=1, permissions=WRITE), create_cmd(project_id=99)
            )

    async def test_calculation_create_on_archived_product(self, fake_uow: FakeUnitOfWork) -> None:
        with pytest.raises(ProductArchivedError):
            await CreateCalculation(**create_kwargs(FakeCalculationRepository(), fake_uow)).execute(
                make_user(id=1, permissions=WRITE), create_cmd(product_id=21)
            )


class TestUpdate:
    async def test_calculation_update_replaces_payload_and_logs(
        self, fake_uow: FakeUnitOfWork
    ) -> None:
        repo = FakeCalculationRepository([make_calculation(locked_by=1)])
        result = await UpdateCalculation(**writer_kwargs(repo, fake_uow)).execute(
            make_user(id=1, permissions=WRITE), 1, update_cmd(project_id=10)
        )
        assert result.inputs == {"d": 30}
        assert result.engine_version == 2
        assert result.project_id == 10
        assert "Inputs changed." in result.changes[-1]
        assert "Results changed." in result.changes[-1]

    async def test_calculation_update_reads_the_calculation_under_its_row_lock(
        self, fake_uow: FakeUnitOfWork
    ) -> None:
        repo = FakeCalculationRepository([make_calculation(locked_by=1)])
        await UpdateCalculation(**writer_kwargs(repo, fake_uow)).execute(
            make_user(id=1, permissions=WRITE), 1, update_cmd()
        )
        assert repo.locked == [1]

    async def test_calculation_update_keeps_owner_on_archived_product(
        self, fake_uow: FakeUnitOfWork
    ) -> None:
        repo = FakeCalculationRepository([make_calculation(product_id=21, locked_by=1)])
        result = await UpdateCalculation(**writer_kwargs(repo, fake_uow)).execute(
            make_user(id=1, permissions=WRITE), 1, update_cmd(product_id=21)
        )
        assert result.product_id == 21

    async def test_calculation_update_other_users_personal_is_hidden(
        self, fake_uow: FakeUnitOfWork
    ) -> None:
        repo = FakeCalculationRepository([make_calculation(creator_id=1)])
        with pytest.raises(CalculationNotFoundError):
            await UpdateCalculation(**writer_kwargs(repo, fake_uow)).execute(
                make_user(id=2, permissions=WRITE), 1, update_cmd()
            )


class TestReadAndList:
    async def test_calculation_get_other_users_personal_is_hidden(self) -> None:
        repo = FakeCalculationRepository([make_calculation(creator_id=1)])
        with pytest.raises(CalculationNotFoundError):
            await GetCalculation(calculation_repo=repo).execute(make_user(id=2), 1)

    async def test_calculation_list_restricts_visibility_unless_manager(self) -> None:
        repo = FakeCalculationRepository()
        await GetCalculations(calculation_repo=repo).execute(
            make_user(id=2), CalculationListQuery(mine=True)
        )
        assert repo.last_filters is not None
        assert repo.last_filters.visible_to_user_id == 2
        assert repo.last_filters.creator_id == 2

        await GetCalculations(calculation_repo=repo).execute(
            make_user(id=3, permissions=MANAGE), CalculationListQuery()
        )
        assert repo.last_filters.visible_to_user_id is None
        assert repo.last_filters.creator_id is None


class TestByPublicId:
    async def test_calculation_get_by_public_id(self) -> None:
        calc = make_calculation(project_id=10)
        repo = FakeCalculationRepository([calc])
        result = await GetCalculationByPublicId(calculation_repo=repo).execute(
            make_user(id=2), calc.public_id
        )
        assert result.id == calc.id

    async def test_calculation_get_by_public_id_hides_other_users_personal(self) -> None:
        calc = make_calculation(creator_id=1)
        repo = FakeCalculationRepository([calc])
        with pytest.raises(CalculationNotFoundError):
            await GetCalculationByPublicId(calculation_repo=repo).execute(
                make_user(id=2), calc.public_id
            )


class TestReleaseAndDelete:
    async def test_calculation_release_and_mark_invalid(self, fake_uow: FakeUnitOfWork) -> None:
        repo = FakeCalculationRepository([make_calculation(project_id=10)])
        with pytest.raises(DocumentNotReleasedError):
            await MarkCalculationInvalid(
                calculation_repo=repo, event_bus=FakeEventBus(), uow=fake_uow
            ).execute(make_user(id=2, permissions=MANAGE), 1, MarkInvalidCommand(reason="x"))
        released = await ReleaseCalculation(calculation_repo=repo, uow=fake_uow).execute(
            make_user(id=1, permissions=RELEASE), 1
        )
        assert released.released_by_id == 1
        assert released.released_at is not None

        with pytest.raises(CalculationAlreadyReleasedError):
            await ReleaseCalculation(calculation_repo=repo, uow=fake_uow).execute(
                make_user(id=1, permissions=RELEASE), 1
            )
        with pytest.raises(InsufficientPermissionsError):
            await MarkCalculationInvalid(
                calculation_repo=repo, event_bus=FakeEventBus(), uow=fake_uow
            ).execute(make_user(id=1, permissions=RELEASE), 1, MarkInvalidCommand(reason="x"))

        invalid = await MarkCalculationInvalid(
            calculation_repo=repo, event_bus=FakeEventBus(), uow=fake_uow
        ).execute(
            make_user(id=2, permissions=MANAGE),
            1,
            MarkInvalidCommand(reason="  Wrong friction factor "),
        )
        assert invalid.released_at is not None
        assert invalid.invalid_reason == "Wrong friction factor"
        assert invalid.invalid_by_id == 2
        assert invalid.read_only
        assert "Marked invalid: Wrong friction factor" in invalid.changes[-1]

        with pytest.raises(DocumentAlreadyInvalidError):
            await MarkCalculationInvalid(
                calculation_repo=repo, event_bus=FakeEventBus(), uow=fake_uow
            ).execute(make_user(id=2, permissions=MANAGE), 1, MarkInvalidCommand(reason="x"))

    async def test_calculation_delete_own_draft(self, fake_uow: FakeUnitOfWork) -> None:
        repo = FakeCalculationRepository([make_calculation()])
        await DeleteCalculation(calculation_repo=repo, uow=fake_uow).execute(
            make_user(id=1, permissions=WRITE), 1
        )
        assert repo.items == {}
        assert fake_uow.committed


class TestCreateRevision:
    async def test_calculation_create_starts_at_the_settings_start_revision(
        self, fake_uow: FakeUnitOfWork
    ) -> None:
        repo = FakeCalculationRepository()
        result = await CreateCalculation(**create_kwargs(repo, fake_uow, start="A")).execute(
            make_user(id=1, permissions=WRITE), create_cmd()
        )
        assert result.revision == "A"
        assert result.document_number == "DOC-0001"
        assert result.is_latest
        assert result.read_only is False


async def _released(repo: FakeCalculationRepository, uow: FakeUnitOfWork) -> None:
    await ReleaseCalculation(calculation_repo=repo, uow=uow).execute(
        make_user(id=1, permissions=RELEASE), 1
    )


def _revise(repo: FakeCalculationRepository, uow: FakeUnitOfWork) -> ReviseCalculation:
    return ReviseCalculation(
        calculation_repo=repo,
        admin_settings_repo=FakeAdminSettingsRepository(),
        event_bus=FakeEventBus(),
        uow=uow,
    )


class TestRevisions:
    async def test_calculation_revise_continues_the_released_document_as_a_draft(
        self, fake_uow: FakeUnitOfWork
    ) -> None:
        repo = FakeCalculationRepository([replace(make_calculation(project_id=10), revision="0")])
        await _released(repo, fake_uow)

        draft = await _revise(repo, fake_uow).execute(
            make_user(id=2, permissions=WRITE), 1, ReviseCalculationCommand(reason="New motor")
        )

        assert draft.revision == "1"
        assert draft.revision_reason == "New motor"
        assert draft.lineage == repo.items[1].lineage
        assert draft.creator_id == 2
        assert draft.released_at is None and draft.is_latest and not draft.read_only
        assert draft.inputs == repo.items[1].inputs
        previous = repo.items[1]
        assert not previous.is_latest
        # The released revision stays valid until its successor is released.
        assert previous.superseded_at is None
        assert previous.changes[-1].endswith("Revision 1 started.")

    async def test_calculation_revise_needs_a_released_latest_revision(
        self, fake_uow: FakeUnitOfWork
    ) -> None:
        repo = FakeCalculationRepository([make_calculation(project_id=10)])
        with pytest.raises(CalculationNotReleasedError):
            await _revise(repo, fake_uow).execute(
                make_user(id=1, permissions=WRITE), 1, ReviseCalculationCommand(reason="x")
            )
        await _released(repo, fake_uow)
        await _revise(repo, fake_uow).execute(
            make_user(id=1, permissions=WRITE), 1, ReviseCalculationCommand(reason="x")
        )
        with pytest.raises(CalculationNotLatestRevisionError):
            await _revise(repo, fake_uow).execute(
                make_user(id=1, permissions=WRITE), 1, ReviseCalculationCommand(reason="again")
            )

    async def test_calculation_release_of_a_revision_supersedes_the_one_before(
        self, fake_uow: FakeUnitOfWork
    ) -> None:
        repo = FakeCalculationRepository([make_calculation(project_id=10)])
        await _released(repo, fake_uow)
        draft = await _revise(repo, fake_uow).execute(
            make_user(id=1, permissions=WRITE), 1, ReviseCalculationCommand(reason="x")
        )

        await ReleaseCalculation(calculation_repo=repo, uow=fake_uow).execute(
            make_user(id=1, permissions=RELEASE), draft.id
        )

        assert repo.items[1].superseded_at is not None
        with pytest.raises(CalculationReleasedError):
            await UpdateCalculation(**writer_kwargs(repo, fake_uow)).execute(
                make_user(id=1, permissions=MANAGE), 1, update_cmd()
            )
        revisions = await GetCalculationRevisions(calculation_repo=repo).execute(
            make_user(id=1), draft.id
        )
        assert [r.id for r in revisions] == [draft.id, 1]

    async def test_calculation_delete_of_a_revision_restores_the_one_before(
        self, fake_uow: FakeUnitOfWork
    ) -> None:
        repo = FakeCalculationRepository([make_calculation(project_id=10)])
        await _released(repo, fake_uow)
        draft = await _revise(repo, fake_uow).execute(
            make_user(id=1, permissions=WRITE), 1, ReviseCalculationCommand(reason="x")
        )
        with pytest.raises(CalculationNotLatestRevisionError):
            await DeleteCalculation(calculation_repo=repo, uow=fake_uow).execute(
                make_user(id=1, permissions=MANAGE), 1
            )

        await DeleteCalculation(calculation_repo=repo, uow=fake_uow).execute(
            make_user(id=1, permissions=WRITE), draft.id
        )

        assert list(repo.items) == [1]
        assert repo.items[1].is_latest


class TestEditLock:
    async def test_calculation_held_by_another_editor_cannot_be_saved_or_released(
        self, fake_uow: FakeUnitOfWork
    ) -> None:
        now = now_utc()
        locked = replace(
            make_calculation(project_id=10),
            locked_by_id=2,
            locked_by_full_name="User 2",
            locked_at=now,
            lock_expires_at=now + timedelta(minutes=10),
        )
        repo = FakeCalculationRepository([locked])
        with pytest.raises(DocumentLockedError, match="User 2"):
            await UpdateCalculation(**writer_kwargs(repo, fake_uow)).execute(
                make_user(id=1, permissions=MANAGE), 1, update_cmd()
            )
        with pytest.raises(DocumentLockedError):
            await ReleaseCalculation(calculation_repo=repo, uow=fake_uow).execute(
                make_user(id=1, permissions=RELEASE), 1
            )
        # The holder saves as usual.
        await UpdateCalculation(**writer_kwargs(repo, fake_uow)).execute(
            make_user(id=2, permissions=MANAGE), 1, update_cmd()
        )

    async def test_calculation_lock_that_ran_out_blocks_nobody_but_saves_nothing(
        self, fake_uow: FakeUnitOfWork
    ) -> None:
        now = now_utc()
        stale = replace(
            make_calculation(project_id=10),
            locked_by_id=2,
            locked_at=now - timedelta(hours=1),
            lock_expires_at=now - timedelta(minutes=1),
        )
        repo = FakeCalculationRepository([stale])
        # Saving needs a live lock of one's own, also the former holder's.
        with pytest.raises(DocumentNotLockedError):
            await UpdateCalculation(**writer_kwargs(repo, fake_uow)).execute(
                make_user(id=2, permissions=MANAGE), 1, update_cmd()
            )
        locked = await _lock(repo, fake_uow).execute(
            make_user(id=1, permissions=WRITE), 1, LockCommand()
        )
        assert locked.locked_by_id == 1

    async def test_calculation_save_records_its_editors(self, fake_uow: FakeUnitOfWork) -> None:
        repo = FakeCalculationRepository([make_calculation(project_id=10, locked_by=2)])
        await UpdateCalculation(**writer_kwargs(repo, fake_uow)).execute(
            make_user(id=2, permissions=MANAGE), 1, update_cmd()
        )
        assert repo.items[1].editor_ids == [2]


def _lock(
    repo: FakeCalculationRepository, uow: FakeUnitOfWork, bus: FakeEventBus | None = None
) -> LockCalculation:
    return LockCalculation(calculation_repo=repo, event_bus=bus or FakeEventBus(), uow=uow)


class TestLockUseCases:
    async def test_calculation_edit_takes_the_lock_and_discard_ends_it(
        self, fake_uow: FakeUnitOfWork
    ) -> None:
        repo = FakeCalculationRepository([make_calculation(project_id=10)])
        locked = await _lock(repo, fake_uow).execute(
            make_user(id=1, permissions=WRITE), 1, LockCommand()
        )
        assert locked.locked_by_id == 1
        assert locked.lock_expires_at is not None
        assert locked.lock_expires_at - locked.locked_at == LOCK_LEASE  # type: ignore[operator]

        renewed = await _lock(repo, fake_uow).execute(
            make_user(id=1, permissions=WRITE), 1, LockCommand()
        )
        assert renewed.locked_at == locked.locked_at

        with pytest.raises(DocumentLockedError):
            await _lock(repo, fake_uow).execute(
                make_user(id=2, permissions=MANAGE), 1, LockCommand()
            )

        unlocked = await UnlockCalculation(
            calculation_repo=repo, event_bus=FakeEventBus(), uow=fake_uow
        ).execute(make_user(id=1), 1)
        assert unlocked.locked_by_id is None
        assert repo.items[1].locked_by_id is None

    async def test_calculation_take_over_needs_manage_and_is_logged(
        self, fake_uow: FakeUnitOfWork
    ) -> None:
        repo = FakeCalculationRepository([make_calculation(creator_id=1, project_id=10)])
        await _lock(repo, fake_uow).execute(make_user(id=1, permissions=WRITE), 1, LockCommand())

        with pytest.raises(InsufficientPermissionsError):
            await _lock(repo, fake_uow).execute(
                make_user(id=3, permissions=WRITE),
                1,
                LockCommand(take_over=True),
            )
        bus = FakeEventBus()
        taken = await _lock(repo, fake_uow, bus).execute(
            make_user(id=2, permissions=MANAGE), 1, LockCommand(take_over=True)
        )
        assert taken.locked_by_id == 2
        assert taken.changes[-1].endswith("Took over editing from User 1.")
        # The previous editor is told their unsaved changes are gone.
        assert [(e.previous_editor_id, e.actor_id, e.resource) for e in bus.published] == [
            (1, 2, "calculations")
        ]

        # The previous editor's unlock leaves the new lock alone.
        await UnlockCalculation(
            calculation_repo=repo, event_bus=FakeEventBus(), uow=fake_uow
        ).execute(make_user(id=1), 1)
        assert repo.items[1].locked_by_id == 2

    async def test_calculation_released_cannot_be_locked(self, fake_uow: FakeUnitOfWork) -> None:
        repo = FakeCalculationRepository([make_calculation(project_id=10, released=True)])
        with pytest.raises(CalculationReleasedError):
            await _lock(repo, fake_uow).execute(
                make_user(id=1, permissions=MANAGE), 1, LockCommand()
            )


class TestEndEditing:
    async def test_calculation_manager_ends_someone_elses_editing(
        self, fake_uow: FakeUnitOfWork
    ) -> None:
        repo = FakeCalculationRepository([make_calculation(project_id=10, locked_by=1)])
        unlock = UnlockCalculation(calculation_repo=repo, event_bus=FakeEventBus(), uow=fake_uow)

        # Without force a lock of someone else is left alone.
        await unlock.execute(make_user(id=2, permissions=MANAGE), 1)
        assert repo.items[1].locked_by_id == 1
        with pytest.raises(InsufficientPermissionsError):
            await unlock.execute(make_user(id=3, permissions=WRITE), 1, force=True)

        bus = FakeEventBus()
        ended = await UnlockCalculation(calculation_repo=repo, event_bus=bus, uow=fake_uow).execute(
            make_user(id=2, permissions=MANAGE), 1, force=True
        )
        assert ended.locked_by_id is None
        assert [(e.previous_editor_id, e.actor_id) for e in bus.published] == [(1, 2)]


class TestDocumentNotifications:
    async def test_calculation_revision_and_invalid_marking_tell_everyone_involved(
        self, fake_uow: FakeUnitOfWork
    ) -> None:
        first = replace(make_calculation(project_id=10, released=True), editor_ids=[4])
        repo = FakeCalculationRepository([first])
        bus = FakeEventBus()
        await ReviseCalculation(
            calculation_repo=repo,
            admin_settings_repo=FakeAdminSettingsRepository(),
            event_bus=bus,
            uow=fake_uow,
        ).execute(
            make_user(id=2, permissions=WRITE), 1, ReviseCalculationCommand(reason="New gearbox")
        )
        await MarkCalculationInvalid(calculation_repo=repo, event_bus=bus, uow=fake_uow).execute(
            make_user(id=3, permissions=MANAGE), 1, MarkInvalidCommand(reason="Wrong load")
        )

        revised, invalid = bus.published
        assert (revised.revision, revised.previous_revision, revised.reason) == (
            "B",
            "A",
            "New gearbox",
        )
        # Creators and editors of every revision; the actor is left out when notifying.
        assert revised.recipient_ids == [1, 2, 4]
        assert (invalid.revision, invalid.reason) == ("A", "Wrong load")
        assert invalid.recipient_ids == [1, 2, 4]
