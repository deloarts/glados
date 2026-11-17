"""
Unit tests for inspection checklists: the verdict and counts
(checklist_evaluation), who may see, change, revise, release and delete one
(ChecklistRules), and the use cases around them, including the revision
chain. No database, no HTTP, repositories replaced with in-memory fakes.
"""

from dataclasses import dataclass
from dataclasses import replace
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any
from uuid import UUID
from uuid import uuid4

import pytest

from src.modules.catalogue.domain.policies import revision_scheme
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.quality.application.dto.checklist_dto import CreateChecklistCommand
from src.modules.quality.application.dto.checklist_dto import ReviseChecklistCommand
from src.modules.quality.application.dto.checklist_dto import UpdateChecklistCommand
from src.modules.quality.application.dto.controlled_document_dto import MarkInvalidCommand
from src.modules.quality.application.use_cases.checklist.delete_checklist import DeleteChecklist
from src.modules.quality.application.use_cases.checklist.get_checklists import ChecklistListQuery
from src.modules.quality.application.use_cases.checklist.get_checklists import GetChecklist
from src.modules.quality.application.use_cases.checklist.get_checklists import GetChecklistRevisions
from src.modules.quality.application.use_cases.checklist.get_checklists import GetChecklists
from src.modules.quality.application.use_cases.checklist.release_checklist import (
    MarkChecklistInvalid,
)
from src.modules.quality.application.use_cases.checklist.release_checklist import ReleaseChecklist
from src.modules.quality.application.use_cases.checklist.revise_checklist import ReviseChecklist
from src.modules.quality.application.use_cases.checklist.save_checklist import CreateChecklist
from src.modules.quality.application.use_cases.checklist.save_checklist import UpdateChecklist
from src.modules.quality.domain.entities.checklist import Checklist
from src.modules.quality.domain.errors import ChecklistAlreadyReleasedError
from src.modules.quality.domain.errors import ChecklistIncompleteError
from src.modules.quality.domain.errors import ChecklistInvalidAnswersError
from src.modules.quality.domain.errors import ChecklistNotFoundError
from src.modules.quality.domain.errors import ChecklistNotLatestRevisionError
from src.modules.quality.domain.errors import ChecklistOfAnotherUserError
from src.modules.quality.domain.errors import ChecklistOwnerConflictError
from src.modules.quality.domain.errors import ChecklistOwnerLockedError
from src.modules.quality.domain.errors import ChecklistOwnerNotAllowedError
from src.modules.quality.domain.errors import ChecklistOwnReleaseError
from src.modules.quality.domain.errors import ChecklistReadOnlyError
from src.modules.quality.domain.errors import ChecklistReleaseNotApplicableError
from src.modules.quality.domain.errors import ChecklistTypeUnknownError
from src.modules.quality.domain.errors import DocumentAlreadyInvalidError
from src.modules.quality.domain.errors import ReleasedDocumentDeleteError
from src.modules.quality.domain.services.checklist_evaluation import evaluate
from src.modules.quality.domain.services.checklist_evaluation import findings_without_remark
from src.modules.quality.domain.services.checklist_rules import ChecklistRules
from src.modules.quality.domain.value_objects.checklist_answer import ChecklistVerdict
from src.modules.quality.domain.value_objects.checklist_type import ChecklistTypeSpec
from src.modules.quality.ports.outbound.repositories.checklist_repository import ChecklistFilterDto
from src.modules.workspace.domain.entities.product import Product
from src.modules.workspace.domain.entities.project import Project
from src.shared_kernel.domain.services.clock import now_utc
from tests.factories import make_user
from tests.unit.fakes import FakeEventBus
from tests.unit.fakes import FakeUnitOfWork

WRITE = [Permission.WRITE_CHECKLISTS]
RELEASE = [Permission.RELEASE_CHECKLISTS]
MANAGE = [Permission.WRITE_CHECKLISTS, Permission.MANAGE_CHECKLISTS]

ALL_YES = {"a.one": "yes", "a.two": "yes", "b.three": "na"}

# ── Helpers ───────────────────────────────────────────────────────────


def make_checklist(
    id: int = 1,
    creator_id: int = 1,
    project_id: int | None = None,
    product_id: int | None = None,
    answers: dict[str, str] | None = None,
    remarks: dict[str, str] | None = None,
    released: bool = False,
    is_latest: bool = True,
    lineage: UUID | None = None,
    revision: str = "0",
    type: str = "hydraulics",
    locked_by: int | None = None,
) -> Checklist:
    now = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)
    answers = dict(ALL_YES) if answers is None else answers
    evaluation = evaluate(answers, 3)
    return Checklist(
        id=id,
        created=now,
        changed=now,
        changes=[],
        type=type,
        title="Hydraulics checklist, P-10",
        header={"designation": "Press 12"},
        answers=answers,
        remarks=remarks or {},
        definition_version=1,
        item_count=3,
        answered_count=evaluation.answered_count,
        finding_count=evaluation.finding_count,
        verdict=evaluation.verdict,
        project_id=project_id,
        product_id=product_id,
        lineage=lineage or uuid4(),
        revision=revision,
        revision_reason=None,
        is_latest=is_latest,
        superseded_at=None,
        creator_id=creator_id,
        released_at=now if released else None,
        released_by_id=99 if released else None,
        # A live edit lock of this user, as Edit leaves it before a save.
        locked_by_id=locked_by,
        locked_at=now_utc() if locked_by else None,
        lock_expires_at=now_utc() + timedelta(minutes=10) if locked_by else None,
    )


class FakeChecklistRepository:
    def __init__(self, items: list[Checklist] | None = None) -> None:
        self.items: dict[int, Checklist] = {c.id: c for c in items or []}
        self.last_filters: ChecklistFilterDto | None = None
        self.locked: list[int] = []

    async def get_by_id(self, id: int) -> Checklist | None:
        item = self.items.get(id)
        return replace(item) if item else None

    async def get_for_update(self, id: int) -> Checklist | None:
        self.locked.append(id)
        return await self.get_by_id(id)

    async def get_by_public_id(self, public_id: UUID) -> Checklist | None:
        item = next((c for c in self.items.values() if c.public_id == public_id), None)
        return replace(item) if item else None

    async def get_multi(self, filters: ChecklistFilterDto) -> tuple[int, list[Checklist]]:
        self.last_filters = filters
        rows = list(self.items.values())
        return len(rows), rows

    async def get_lineage(self, lineage: UUID) -> list[Checklist]:
        rows = [replace(c) for c in self.items.values() if c.lineage == lineage]
        return sorted(rows, key=lambda c: revision_scheme.sort_key(c.revision), reverse=True)

    async def next_document_number(self, template: str) -> str:
        """Numbers like the real repository, without its date placeholders."""
        taken = {c.document_number for c in self.items.values()}
        return f"DOC-{len(taken) + 1:04d}"

    async def save(self, item: Checklist) -> Checklist:
        if item.id == 0:
            item = replace(item, id=max(self.items, default=0) + 1)
        latest = [
            c
            for c in self.items.values()
            if c.lineage == item.lineage and c.is_latest and c.id != item.id
        ]
        assert not (item.is_latest and latest), "two latest revisions in one lineage"
        self.items[item.id] = replace(item)
        return item

    async def delete(self, item: Checklist) -> None:
        self.items.pop(item.id, None)


class FakeProjectRepository:
    async def get_by_id(self, id: int) -> Project | None:
        if id != 10:
            return None
        return Project(id=id, created=datetime.now(UTC), project_number=f"P-{id}")


class FakeProductRepository:
    async def get_by_id(self, id: int) -> Product | None:
        if id not in (20, 21):
            return None
        return Product(
            id=id, created=datetime.now(UTC), product_number=f"PR-{id}", archived=id == 21
        )


@dataclass
class _RevisionSettings:
    revision_start: str = "0"
    revision_skip_ambiguous_letters: bool = False
    calculation_number_format: str = "CAL-{yy}-{seq:04d}"
    checklist_number_format: str = "CHK-{yy}-{seq:04d}"


class FakeAdminSettingsRepository:
    def __init__(self, start: str = "0", skip_ambiguous: bool = False) -> None:
        self._settings = _RevisionSettings(start, skip_ambiguous)

    async def get_made_items(self) -> _RevisionSettings:
        return self._settings


def create_cmd(**overrides: Any) -> CreateChecklistCommand:
    body: dict[str, Any] = {
        "type": "hydraulics",
        "title": "Hydraulics checklist",
        "header": {"designation": "Press 12"},
        "answers": {"a.one": "yes"},
        "remarks": {},
        "definition_version": 1,
        "item_count": 3,
    }
    return CreateChecklistCommand(**(body | overrides))


def update_cmd(**overrides: Any) -> UpdateChecklistCommand:
    body: dict[str, Any] = {
        "title": "Hydraulics checklist",
        "header": {"designation": "Press 12"},
        "answers": dict(ALL_YES),
        "remarks": {},
        "definition_version": 1,
        "item_count": 3,
    }
    return UpdateChecklistCommand(**(body | overrides))


def creator(repo: FakeChecklistRepository, uow: FakeUnitOfWork, **kw: Any) -> CreateChecklist:
    return CreateChecklist(
        checklist_repo=repo,
        project_repo=FakeProjectRepository(),
        product_repo=FakeProductRepository(),
        admin_settings_repo=FakeAdminSettingsRepository(**kw),  # type: ignore[arg-type]
        uow=uow,
    )


def updater(repo: FakeChecklistRepository, uow: FakeUnitOfWork) -> UpdateChecklist:
    return UpdateChecklist(
        checklist_repo=repo,
        project_repo=FakeProjectRepository(),
        product_repo=FakeProductRepository(),
        uow=uow,
    )


def reviser(repo: FakeChecklistRepository, uow: FakeUnitOfWork, **kw: Any) -> ReviseChecklist:
    return ReviseChecklist(
        checklist_repo=repo,
        admin_settings_repo=FakeAdminSettingsRepository(**kw),  # type: ignore[arg-type]
        event_bus=FakeEventBus(),
        uow=uow,
    )


@pytest.fixture
def minor_types(monkeypatch: pytest.MonkeyPatch) -> None:
    """Makes "pneumatics" a type without a release step for one test."""

    def spec(slug: str) -> ChecklistTypeSpec:
        return ChecklistTypeSpec(
            slug=slug, release_required=slug != "pneumatics", owner_kinds=frozenset({"product"})
        )

    monkeypatch.setattr("src.modules.quality.domain.entities.checklist.checklist_type_spec", spec)


# ── Evaluation ────────────────────────────────────────────────────────


class TestEvaluation:
    def test_checklist_verdict_failed_as_soon_as_a_finding_exists(self) -> None:
        result = evaluate({"a.one": "no"}, 3)
        assert result.verdict is ChecklistVerdict.FAILED
        assert (result.answered_count, result.finding_count) == (1, 1)

    def test_checklist_verdict_open_while_unanswered_without_findings(self) -> None:
        assert evaluate({"a.one": "yes"}, 3).verdict is ChecklistVerdict.OPEN

    def test_checklist_verdict_passed_when_complete_without_findings(self) -> None:
        assert evaluate(dict(ALL_YES), 3).verdict is ChecklistVerdict.PASSED

    def test_checklist_evaluation_rejects_unknown_answer(self) -> None:
        with pytest.raises(ChecklistInvalidAnswersError):
            evaluate({"a.one": "maybe"}, 3)

    def test_checklist_evaluation_rejects_more_answers_than_items(self) -> None:
        with pytest.raises(ChecklistInvalidAnswersError):
            evaluate(dict(ALL_YES), 2)

    def test_checklist_findings_without_remark_ignores_blank_remarks(self) -> None:
        answers = {"a.one": "no", "a.two": "defect", "b.three": "yes"}
        assert findings_without_remark(answers, {"a.one": "Leaks", "a.two": "  "}) == ["a.two"]


# ── Rules ─────────────────────────────────────────────────────────────


class TestRules:
    def test_checklist_personal_visible_only_to_creator_and_manager(self) -> None:
        personal = make_checklist(creator_id=1)
        assert ChecklistRules.can_view(make_user(id=1), personal)
        assert not ChecklistRules.can_view(make_user(id=2), personal)
        assert ChecklistRules.can_view(
            make_user(id=2, permissions=[Permission.MANAGE_CHECKLISTS]), personal
        )
        assert ChecklistRules.can_view(make_user(id=2), make_checklist(project_id=10))

    def test_checklist_update_rejects_released_and_older_revisions(self) -> None:
        with pytest.raises(ChecklistReadOnlyError):
            ChecklistRules.assert_can_update(
                make_user(id=1, permissions=WRITE), make_checklist(released=True)
            )
        with pytest.raises(ChecklistReadOnlyError):
            ChecklistRules.assert_can_update(
                make_user(id=1, permissions=WRITE), make_checklist(is_latest=False)
            )

    def test_checklist_update_of_another_users_draft_needs_manage(self) -> None:
        draft = make_checklist(creator_id=1, project_id=10)
        with pytest.raises(ChecklistOfAnotherUserError):
            ChecklistRules.assert_can_update(make_user(id=2, permissions=WRITE), draft)
        ChecklistRules.assert_can_update(make_user(id=2, permissions=MANAGE), draft)

    def test_checklist_release_by_its_creator_is_refused(self) -> None:
        draft = make_checklist(creator_id=1, project_id=10)
        with pytest.raises(ChecklistOwnReleaseError):
            ChecklistRules.assert_can_release(make_user(id=1, permissions=RELEASE), draft)
        ChecklistRules.assert_can_release(make_user(id=2, permissions=RELEASE), draft)

    def test_checklist_release_needs_permission(self) -> None:
        with pytest.raises(InsufficientPermissionsError):
            ChecklistRules.assert_can_release(
                make_user(id=2, permissions=WRITE), make_checklist(project_id=10)
            )

    def test_checklist_release_needs_every_item_answered(self) -> None:
        draft = make_checklist(project_id=10, answers={"a.one": "yes"})
        with pytest.raises(ChecklistIncompleteError, match="2 unanswered"):
            ChecklistRules.assert_can_release(make_user(id=2, permissions=RELEASE), draft)

    def test_checklist_release_needs_a_remark_on_every_finding(self) -> None:
        answers = {"a.one": "no", "a.two": "yes", "b.three": "yes"}
        with pytest.raises(ChecklistIncompleteError, match="without a remark"):
            ChecklistRules.assert_can_release(
                make_user(id=2, permissions=RELEASE), make_checklist(project_id=10, answers=answers)
            )
        failed = make_checklist(project_id=10, answers=answers, remarks={"a.one": "Hose chafed"})
        ChecklistRules.assert_can_release(make_user(id=2, permissions=RELEASE), failed)

    def test_checklist_release_twice_is_refused(self) -> None:
        with pytest.raises(ChecklistAlreadyReleasedError):
            ChecklistRules.assert_can_release(
                make_user(id=2, permissions=RELEASE), make_checklist(project_id=10, released=True)
            )

    def test_checklist_release_of_a_type_without_release_is_refused(
        self, minor_types: None
    ) -> None:
        with pytest.raises(ChecklistReleaseNotApplicableError):
            ChecklistRules.assert_can_release(
                make_user(id=2, permissions=RELEASE),
                make_checklist(project_id=10, type="pneumatics"),
            )

    def test_checklist_revise_needs_a_released_latest_revision(self) -> None:
        with pytest.raises(ChecklistIncompleteError):
            ChecklistRules.assert_can_revise(make_user(id=1, permissions=WRITE), make_checklist())
        with pytest.raises(ChecklistNotLatestRevisionError):
            ChecklistRules.assert_can_revise(
                make_user(id=1, permissions=WRITE), make_checklist(released=True, is_latest=False)
            )
        ChecklistRules.assert_can_revise(
            make_user(id=1, permissions=WRITE), make_checklist(released=True)
        )

    def test_checklist_revise_of_a_minor_type_needs_it_complete(self, minor_types: None) -> None:
        with pytest.raises(ChecklistIncompleteError):
            ChecklistRules.assert_can_revise(
                make_user(id=1, permissions=WRITE),
                make_checklist(type="pneumatics", answers={"a.one": "yes"}),
            )
        ChecklistRules.assert_can_revise(
            make_user(id=1, permissions=WRITE), make_checklist(type="pneumatics")
        )

    def test_checklist_delete_only_the_latest_revision(self) -> None:
        with pytest.raises(ChecklistNotLatestRevisionError):
            ChecklistRules.assert_can_delete(
                make_user(id=1, permissions=WRITE), make_checklist(is_latest=False)
            )

    def test_checklist_released_is_never_deleted(self) -> None:
        released = make_checklist(released=True)
        with pytest.raises(ReleasedDocumentDeleteError):
            ChecklistRules.assert_can_delete(make_user(id=1, permissions=MANAGE), released)


# ── Use cases ─────────────────────────────────────────────────────────


class TestCreateAndUpdate:
    async def test_checklist_create_starts_at_the_configured_revision(self) -> None:
        repo, uow = FakeChecklistRepository(), FakeUnitOfWork()
        result = await creator(repo, uow, start="A").execute(
            make_user(id=1, permissions=WRITE), create_cmd(product_id=20)
        )
        assert result.revision == "A"
        assert result.is_latest
        assert (result.answered_count, result.verdict) == (1, "open")
        assert uow.committed

    async def test_checklist_create_rejects_unknown_type(self) -> None:
        with pytest.raises(ChecklistTypeUnknownError):
            await creator(FakeChecklistRepository(), FakeUnitOfWork()).execute(
                make_user(id=1, permissions=WRITE), create_cmd(type="welding")
            )

    async def test_checklist_create_rejects_two_owners(self) -> None:
        with pytest.raises(ChecklistOwnerConflictError):
            await creator(FakeChecklistRepository(), FakeUnitOfWork()).execute(
                make_user(id=1, permissions=WRITE), create_cmd(project_id=10, product_id=20)
            )

    @pytest.mark.parametrize(
        ("project_id", "kind"), [(10, "project"), (None, "personal")], ids=["project", "personal"]
    )
    async def test_checklist_create_of_a_machinery_type_needs_a_product(
        self, project_id: int | None, kind: str
    ) -> None:
        with pytest.raises(ChecklistOwnerNotAllowedError, match=kind):
            await creator(FakeChecklistRepository(), FakeUnitOfWork()).execute(
                make_user(id=1, permissions=WRITE), create_cmd(project_id=project_id)
            )

    async def test_checklist_owner_change_keeps_a_machinery_type_on_a_product(self) -> None:
        repo = FakeChecklistRepository([make_checklist(product_id=20, locked_by=1)])
        with pytest.raises(ChecklistOwnerNotAllowedError):
            await updater(repo, FakeUnitOfWork()).execute(
                make_user(id=1, permissions=WRITE), 1, update_cmd(project_id=10)
            )

    async def test_checklist_update_recomputes_the_verdict(self) -> None:
        repo = FakeChecklistRepository([make_checklist(answers={"a.one": "yes"}, locked_by=1)])
        result = await updater(repo, FakeUnitOfWork()).execute(
            make_user(id=1, permissions=WRITE), 1, update_cmd(answers={"a.one": "defect"})
        )
        assert (result.verdict, result.finding_count) == ("failed", 1)
        assert "Answers changed." in result.changes[-1]

    async def test_checklist_update_reads_the_checklist_under_its_row_lock(self) -> None:
        repo = FakeChecklistRepository([make_checklist(locked_by=1)])
        await updater(repo, FakeUnitOfWork()).execute(
            make_user(id=1, permissions=WRITE), 1, update_cmd()
        )
        assert repo.locked == [1]

    async def test_checklist_owner_locked_once_earlier_revisions_exist(self) -> None:
        lineage = uuid4()
        repo = FakeChecklistRepository(
            [
                make_checklist(id=1, lineage=lineage, released=True, is_latest=False),
                make_checklist(id=2, lineage=lineage, revision="1", locked_by=1),
            ]
        )
        with pytest.raises(ChecklistOwnerLockedError):
            await updater(repo, FakeUnitOfWork()).execute(
                make_user(id=1, permissions=WRITE), 2, update_cmd(project_id=10)
            )

    async def test_checklist_owner_changes_on_a_single_draft(self) -> None:
        repo = FakeChecklistRepository([make_checklist(locked_by=1)])
        result = await updater(repo, FakeUnitOfWork()).execute(
            make_user(id=1, permissions=WRITE), 1, update_cmd(product_id=20)
        )
        assert result.product_id == 20


class TestRevisions:
    async def test_checklist_revise_copies_answers_into_the_next_revision(self) -> None:
        repo = FakeChecklistRepository([make_checklist(released=True)])
        result = await reviser(repo, FakeUnitOfWork()).execute(
            make_user(id=1, permissions=WRITE),
            1,
            ReviseChecklistCommand(reason="Valve block replaced"),
        )
        assert result.revision == "1"
        assert result.revision_reason == "Valve block replaced"
        assert result.answers == ALL_YES
        assert result.released_at is None
        previous = repo.items[1]
        assert not previous.is_latest
        # A release type stays valid until the new revision is released.
        assert previous.superseded_at is None

    async def test_checklist_revise_skips_ambiguous_letters(self) -> None:
        repo = FakeChecklistRepository([make_checklist(released=True, revision="H")])
        result = await reviser(repo, FakeUnitOfWork(), skip_ambiguous=True).execute(
            make_user(id=1, permissions=WRITE), 1, ReviseChecklistCommand(reason="x")
        )
        assert result.revision == "J"

    async def test_checklist_revise_of_minor_type_supersedes_at_once(
        self, minor_types: None
    ) -> None:
        repo = FakeChecklistRepository([make_checklist(type="pneumatics")])
        await reviser(repo, FakeUnitOfWork()).execute(
            make_user(id=1, permissions=WRITE), 1, ReviseChecklistCommand(reason="x")
        )
        assert repo.items[1].superseded_at is not None

    async def test_checklist_release_supersedes_and_invalid_keeps_the_release(self) -> None:
        lineage = uuid4()
        repo = FakeChecklistRepository(
            [
                make_checklist(
                    id=1, project_id=10, lineage=lineage, released=True, is_latest=False
                ),
                make_checklist(id=2, project_id=10, lineage=lineage, revision="1"),
            ]
        )
        released = await ReleaseChecklist(repo, uow=FakeUnitOfWork()).execute(
            make_user(id=2, permissions=RELEASE), 2
        )
        assert released.released_by_id == 2
        assert repo.items[1].superseded_at is not None

        with pytest.raises(InsufficientPermissionsError):
            await MarkChecklistInvalid(repo, FakeEventBus(), uow=FakeUnitOfWork()).execute(
                make_user(id=2, permissions=RELEASE), 2, MarkInvalidCommand(reason="Wrong pump")
            )
        await MarkChecklistInvalid(repo, FakeEventBus(), uow=FakeUnitOfWork()).execute(
            make_user(id=3, permissions=[Permission.MANAGE_CHECKLISTS]),
            2,
            MarkInvalidCommand(reason="Wrong pump"),
        )
        assert repo.items[2].released_at is not None
        assert repo.items[2].invalid_reason == "Wrong pump"
        assert repo.items[2].invalid_by_id == 3
        assert repo.items[1].superseded_at is not None
        with pytest.raises(DocumentAlreadyInvalidError):
            await MarkChecklistInvalid(repo, FakeEventBus(), uow=FakeUnitOfWork()).execute(
                make_user(id=3, permissions=[Permission.MANAGE_CHECKLISTS]),
                2,
                MarkInvalidCommand(reason="x"),
            )

    async def test_checklist_delete_makes_the_previous_revision_latest(self) -> None:
        lineage = uuid4()
        repo = FakeChecklistRepository(
            [
                make_checklist(id=1, lineage=lineage, released=True, is_latest=False),
                make_checklist(id=2, lineage=lineage, revision="1"),
            ]
        )
        await DeleteChecklist(repo, uow=FakeUnitOfWork()).execute(
            make_user(id=1, permissions=WRITE), 2
        )
        assert 2 not in repo.items
        assert repo.items[1].is_latest

    async def test_checklist_revisions_listed_newest_first(self) -> None:
        lineage = uuid4()
        repo = FakeChecklistRepository(
            [
                make_checklist(id=1, lineage=lineage, revision="9", is_latest=False),
                make_checklist(id=2, lineage=lineage, revision="10"),
            ]
        )
        rows = await GetChecklistRevisions(repo).execute(make_user(id=1), 1)
        assert [r.revision for r in rows] == ["10", "9"]


class TestReads:
    async def test_checklist_list_hides_personal_ones_of_others(self) -> None:
        repo = FakeChecklistRepository()
        await GetChecklists(repo).execute(make_user(id=5), ChecklistListQuery(mine=True))
        assert repo.last_filters is not None
        assert repo.last_filters.visible_to_user_id == 5
        assert repo.last_filters.creator_id == 5
        assert repo.last_filters.latest_only

        await GetChecklists(repo).execute(
            make_user(id=5, permissions=[Permission.MANAGE_CHECKLISTS]), ChecklistListQuery()
        )
        assert repo.last_filters.visible_to_user_id is None

    async def test_checklist_personal_of_another_user_reads_as_missing(self) -> None:
        repo = FakeChecklistRepository([make_checklist(creator_id=1)])
        with pytest.raises(ChecklistNotFoundError):
            await GetChecklist(repo).execute(make_user(id=2), 1)
