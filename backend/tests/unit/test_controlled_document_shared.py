"""
Unit tests for the pieces every kind of controlled document shares: the
access rules of DocumentAccess (domain/services/controlled_document_rules.py),
the generic use cases in application/use_cases/_controlled_documents/ and
the owner check in application/services/controlled_documents.py. They bind a
made-up "memo" kind, so they exercise the shared code rather than the
calculation or checklist bindings, which their own test modules cover.
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
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.quality.application.dto.controlled_document_dto import LockCommand
from src.modules.quality.application.dto.controlled_document_dto import MarkInvalidCommand
from src.modules.quality.application.services import controlled_documents
from src.modules.quality.application.use_cases._controlled_documents.base import (
    DeleteControlledDocument,
)
from src.modules.quality.application.use_cases._controlled_documents.base import (
    GetControlledDocument,
)
from src.modules.quality.application.use_cases._controlled_documents.base import (
    GetControlledDocumentByPublicId,
)
from src.modules.quality.application.use_cases._controlled_documents.base import (
    LockControlledDocument,
)
from src.modules.quality.application.use_cases._controlled_documents.base import (
    MarkControlledDocumentInvalid,
)
from src.modules.quality.application.use_cases._controlled_documents.base import (
    ReleaseControlledDocument,
)
from src.modules.quality.application.use_cases._controlled_documents.base import (
    ReviseControlledDocument,
)
from src.modules.quality.application.use_cases._controlled_documents.base import (
    UnlockControlledDocument,
)
from src.modules.quality.application.use_cases._controlled_documents.kind import (
    ControlledDocumentKind,
)
from src.modules.quality.domain.entities.controlled_document import ControlledDocument
from src.modules.quality.domain.errors import CalculationAlreadyReleasedError
from src.modules.quality.domain.errors import CalculationNotFoundError
from src.modules.quality.domain.errors import CalculationNotLatestRevisionError
from src.modules.quality.domain.errors import CalculationOwnerConflictError
from src.modules.quality.domain.events.document_events import DocumentEditingTakenOver
from src.modules.quality.domain.events.document_events import DocumentRevised
from src.modules.quality.domain.services.controlled_document_rules import DocumentAccess
from src.modules.workspace.domain.entities.product import Product
from src.modules.workspace.domain.errors import ProductArchivedError
from src.shared_kernel.domain.services.clock import now_utc
from tests import factories
from tests.unit.fakes import FakeEventBus
from tests.unit.fakes import FakeUnitOfWork

WRITE = "write:memos"
RELEASE = "release:memos"
MANAGE = "manage:memos"


# The memo errors subclass mapped calculation errors rather than DomainError
# directly, so the exception-status completeness scan, which walks every
# DomainError subclass, never sees an unmapped test-only class.


class MemoNotFoundError(CalculationNotFoundError):
    pass


class MemoOwnerConflictError(CalculationOwnerConflictError):
    pass


class MemoNotLatestError(CalculationNotLatestRevisionError):
    pass


class MemoAlreadyReleasedError(CalculationAlreadyReleasedError):
    pass


class MemoOfAnotherUserError(InsufficientPermissionsError):
    pass


ACCESS = DocumentAccess(
    noun="memo",
    write_permission=WRITE,
    release_permission=RELEASE,
    manage_permission=MANAGE,
    not_found_error=MemoNotFoundError,
    owner_conflict_error=MemoOwnerConflictError,
    not_latest_error=MemoNotLatestError,
    already_released_error=MemoAlreadyReleasedError,
    of_another_user_error=MemoOfAnotherUserError,
)


@dataclass
class Memo(ControlledDocument):
    title: str = "Shift notes"
    project_id: int | None = None
    product_id: int | None = None

    @property
    def is_personal(self) -> bool:
        return self.project_id is None and self.product_id is None


class MemoRules:
    @staticmethod
    def assert_can_view(actor: User, memo: Memo) -> None:
        ACCESS.assert_can_view(actor, memo)

    @staticmethod
    def assert_can_write(actor: User, action: str) -> None:
        ACCESS.assert_can_write(actor, action)

    @staticmethod
    def assert_can_update(actor: User, memo: Memo) -> None:
        ACCESS.assert_can_view(actor, memo)
        ACCESS.assert_own_or_manager(actor, memo, "update")

    @staticmethod
    def assert_can_delete_any(actor: User) -> None:
        ACCESS.assert_can_delete_any(actor)

    @staticmethod
    def assert_can_delete(actor: User, memo: Memo) -> None:
        ACCESS.assert_latest(memo, "deleted")

    @staticmethod
    def assert_can_release_any(actor: User) -> None:
        ACCESS.assert_can_release_any(actor)

    @staticmethod
    def assert_can_release(actor: User, memo: Memo) -> None:
        ACCESS.assert_not_released(memo)

    @staticmethod
    def assert_can_manage(actor: User, action: str) -> None:
        ACCESS.assert_can_manage(actor, action)

    @staticmethod
    def assert_can_mark_invalid(actor: User, memo: Memo) -> None:
        ACCESS.assert_can_view(actor, memo)

    @staticmethod
    def assert_can_revise(actor: User, memo: Memo) -> None:
        ACCESS.assert_latest(memo, "revised")


def memo_kind(*, takes_over_now: bool = False) -> ControlledDocumentKind[Memo, Memo, str]:
    return ControlledDocumentKind(
        access=ACCESS,
        rules=MemoRules,
        live_resource="memos",
        to_result=lambda memo: memo,
        to_summary_result=lambda memo: memo.revision,
        title=lambda memo: memo.title,
        takes_over_now=lambda _memo: takes_over_now,
    )


def make_user(*, id: int = 1, **overrides: Any) -> User:
    """A user named "User <id>", the name the access errors quote."""
    return factories.make_user(id=id, full_name=f"User {id}", **overrides)


def make_memo(id: int = 1, creator_id: int = 1, **fields: Any) -> Memo:
    now = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
    return Memo(id=id, created=now, changed=now, changes=[], creator_id=creator_id, **fields)


class FakeMemoRepository:
    def __init__(self, items: list[Memo] | None = None) -> None:
        self.items: dict[int, Memo] = {m.id: m for m in items or []}
        self.reads = 0
        self.locked: list[int] = []

    async def get_by_id(self, id: int) -> Memo | None:
        self.reads += 1
        item = self.items.get(id)
        return replace(item) if item else None

    async def get_for_update(self, id: int) -> Memo | None:
        self.locked.append(id)
        return await self.get_by_id(id)

    async def get_by_public_id(self, public_id: UUID) -> Memo | None:
        self.reads += 1
        item = next((m for m in self.items.values() if m.public_id == public_id), None)
        return replace(item) if item else None

    async def get_lineage(self, lineage: UUID) -> list[Memo]:
        rows = [replace(m) for m in self.items.values() if m.lineage == lineage]
        return sorted(rows, key=lambda m: revision_scheme.sort_key(m.revision), reverse=True)

    async def next_document_number(self, template: str) -> str:
        return "MEMO-0001"

    async def save(self, item: Memo) -> Memo:
        if item.id == 0:
            item = replace(item, id=max(self.items, default=0) + 1)
        self.items[item.id] = replace(item)
        return item

    async def delete(self, item: Memo) -> None:
        self.items.pop(item.id, None)


@dataclass
class _RevisionSettings:
    revision_skip_ambiguous_letters: bool = False


class FakeAdminSettingsRepository:
    async def get_made_items(self) -> _RevisionSettings:
        return _RevisionSettings()


class GetMemo(GetControlledDocument[Memo, Memo, str]):
    _kind = memo_kind()

    async def execute(self, actor: User, memo_id: int) -> Memo:
        return await self._get(actor, memo_id)


class GetMemoByPublicId(GetControlledDocumentByPublicId[Memo, Memo, str]):
    _kind = memo_kind()

    async def execute(self, actor: User, public_id: UUID) -> Memo:
        return await self._get(actor, public_id)


class DeleteMemo(DeleteControlledDocument[Memo, Memo, str]):
    _kind = memo_kind()

    async def execute(self, actor: User, memo_id: int) -> None:
        await self._delete(actor, memo_id)


class LockMemo(LockControlledDocument[Memo, Memo, str]):
    _kind = memo_kind()

    async def execute(self, actor: User, memo_id: int, cmd: LockCommand) -> Memo:
        return await self._lock(actor, memo_id, cmd)


class UnlockMemo(UnlockControlledDocument[Memo, Memo, str]):
    _kind = memo_kind()

    async def execute(self, actor: User, memo_id: int) -> Memo:
        return await self._unlock(actor, memo_id, force=False)


class ReleaseMemo(ReleaseControlledDocument[Memo, Memo, str]):
    _kind = memo_kind()

    async def execute(self, actor: User, memo_id: int) -> Memo:
        return await self._release(actor, memo_id)


class MarkMemoInvalid(MarkControlledDocumentInvalid[Memo, Memo, str]):
    _kind = memo_kind()

    async def execute(self, actor: User, memo_id: int) -> Memo:
        return await self._mark_invalid(actor, memo_id, MarkInvalidCommand(reason="Wrong rate"))


class ReviseMemo(ReviseControlledDocument[Memo, Memo, str]):
    _kind = memo_kind()

    async def execute(self, actor: User, memo_id: int) -> Memo:
        return await self._revise(actor, memo_id, "New supplier")


# ── DocumentAccess ────────────────────────────────────────────────────


def test_document_access_hides_a_personal_document_from_other_users() -> None:
    personal = make_memo(creator_id=1)
    on_project = make_memo(creator_id=1, project_id=5)

    assert ACCESS.can_view(make_user(id=1), personal)
    assert ACCESS.can_view(make_user(id=3, permissions=[MANAGE]), personal)
    assert not ACCESS.can_view(make_user(id=2), personal)
    assert ACCESS.can_view(make_user(id=2), on_project)
    with pytest.raises(MemoNotFoundError, match=r"^Memo #1 not found\.$"):
        ACCESS.assert_can_view(make_user(id=2), personal)


def test_document_access_phrases_its_errors_with_the_kind_noun() -> None:
    superseded = make_memo(id=4, revision="B", is_latest=False)
    released = make_memo(id=4, released_at=now_utc())

    assert ACCESS.label(superseded) == "Memo #4"
    with pytest.raises(
        MemoNotLatestError,
        match=r"^Revision B of memo #4 is not the latest revision and cannot be deleted\.$",
    ):
        ACCESS.assert_latest(superseded, "deleted")
    with pytest.raises(MemoAlreadyReleasedError, match=r"^Memo #4 is already released\.$"):
        ACCESS.assert_not_released(released)
    with pytest.raises(
        MemoOwnerConflictError,
        match=r"^A memo belongs to a project or to a product, not to both\.$",
    ):
        ACCESS.assert_single_owner(1, 2)
    with pytest.raises(
        MemoOfAnotherUserError,
        match=r"^User #2 \(User 2\) cannot update memo #4, it belongs to another user\.$",
    ):
        ACCESS.assert_own_or_manager(make_user(id=2), superseded, "update")
    ACCESS.assert_own_or_manager(make_user(id=2, permissions=[MANAGE]), superseded, "update")


def test_document_access_actor_gates_name_the_plural_noun() -> None:
    with pytest.raises(InsufficientPermissionsError, match=r"cannot revise memos\.$"):
        ACCESS.assert_can_write(make_user(id=2), "revise")
    with pytest.raises(InsufficientPermissionsError, match=r"cannot release memos\.$"):
        ACCESS.assert_can_release_any(make_user(id=2))
    with pytest.raises(InsufficientPermissionsError, match=r"cannot mark invalid memos\.$"):
        ACCESS.assert_can_manage(make_user(id=2), "mark invalid")
    with pytest.raises(InsufficientPermissionsError, match=r"cannot delete memos\.$"):
        ACCESS.assert_can_delete_any(make_user(id=2))
    ACCESS.assert_can_delete_any(make_user(id=2, permissions=[WRITE]))
    ACCESS.assert_can_delete_any(make_user(id=2, permissions=[MANAGE]))


# ── Generic use cases ─────────────────────────────────────────────────


async def test_shared_use_case_names_the_kind_when_a_document_is_missing() -> None:
    repo = FakeMemoRepository()
    public_id = uuid4()

    with pytest.raises(MemoNotFoundError, match=r"^Memo #9 not found\.$"):
        await GetMemo(repo).execute(make_user(), 9)
    with pytest.raises(MemoNotFoundError, match=rf"^Memo {public_id} not found\.$"):
        await GetMemoByPublicId(repo).execute(make_user(), public_id)


async def test_shared_use_case_checks_the_actor_gate_before_loading() -> None:
    repo = FakeMemoRepository([make_memo()])
    uow = FakeUnitOfWork()

    with pytest.raises(InsufficientPermissionsError):
        await DeleteMemo(repo, uow=uow).execute(make_user(id=2), 1)

    assert repo.reads == 0
    assert 1 in repo.items
    assert uow.commits == 0


async def test_shared_lock_take_over_tells_the_previous_editor_through_the_kind() -> None:
    memo = make_memo(
        creator_id=2,
        project_id=5,
        locked_by_id=2,
        locked_at=now_utc(),
        lock_expires_at=now_utc() + timedelta(minutes=10),
    )
    repo = FakeMemoRepository([memo])
    bus = FakeEventBus()
    uow = FakeUnitOfWork()

    saved = await LockMemo(repo, bus, uow=uow).execute(
        make_user(id=1, permissions=[WRITE, MANAGE]), 1, LockCommand(take_over=True)
    )

    assert saved.locked_by_id == 1
    [event] = bus.published
    assert isinstance(event, DocumentEditingTakenOver)
    assert (event.resource, event.title, event.previous_editor_id) == ("memos", "Shift notes", 2)
    assert uow.commits == 1


_ALL = [WRITE, RELEASE, MANAGE]


@pytest.mark.parametrize(
    ("run", "memo_fields"),
    [
        pytest.param(
            lambda repo, uow: DeleteMemo(repo, uow=uow).execute(make_user(permissions=_ALL), 1),
            {},
            id="delete",
        ),
        pytest.param(
            lambda repo, uow: LockMemo(repo, FakeEventBus(), uow=uow).execute(
                make_user(permissions=_ALL), 1, LockCommand()
            ),
            {},
            id="lock",
        ),
        pytest.param(
            lambda repo, uow: UnlockMemo(repo, FakeEventBus(), uow=uow).execute(
                make_user(permissions=_ALL), 1
            ),
            {"locked_by_id": 1, "locked_at": now_utc()},
            id="unlock",
        ),
        pytest.param(
            lambda repo, uow: ReleaseMemo(repo, uow=uow).execute(make_user(permissions=_ALL), 1),
            {},
            id="release",
        ),
        pytest.param(
            lambda repo, uow: MarkMemoInvalid(repo, FakeEventBus(), uow=uow).execute(
                make_user(permissions=_ALL), 1
            ),
            {"released_at": now_utc()},
            id="mark invalid",
        ),
        pytest.param(
            lambda repo, uow: ReviseMemo(
                repo, FakeAdminSettingsRepository(), FakeEventBus(), uow=uow
            ).execute(make_user(permissions=_ALL), 1),
            {"released_at": now_utc()},
            id="revise",
        ),
    ],
)
async def test_every_document_transition_reads_the_document_under_its_row_lock(
    run: Any, memo_fields: dict[str, Any]
) -> None:
    """Two transitions of one document, such as a release and a take over of
    the edit lock, run one after the other, each seeing what the other
    committed."""
    repo = FakeMemoRepository([make_memo(project_id=5, **memo_fields)])
    uow = FakeUnitOfWork()

    await run(repo, uow)

    assert repo.locked == [1]
    assert uow.commits == 1


@pytest.mark.parametrize("takes_over_now", [True, False])
async def test_shared_revise_supersedes_at_once_only_when_the_kind_says_so(
    takes_over_now: bool,
) -> None:
    class ReviseMemo(ReviseControlledDocument[Memo, Memo, str]):
        _kind = memo_kind(takes_over_now=takes_over_now)

        async def execute(self, actor: User, memo_id: int, reason: str) -> Memo:
            return await self._revise(actor, memo_id, reason)

    current = make_memo(project_id=5, released_at=now_utc())
    repo = FakeMemoRepository([current])
    bus = FakeEventBus()

    saved = await ReviseMemo(
        repo, FakeAdminSettingsRepository(), bus, uow=FakeUnitOfWork()
    ).execute(make_user(id=1, permissions=[WRITE]), 1, "  New supplier  ")

    previous = repo.items[1]
    assert (saved.revision, saved.revision_reason, saved.is_latest) == ("B", "New supplier", True)
    assert previous.is_latest is False
    assert (previous.superseded_at is not None) is takes_over_now
    [event] = bus.published
    assert isinstance(event, DocumentRevised)
    assert (event.resource, event.previous_revision) == ("memos", "A")


# ── Owner check ───────────────────────────────────────────────────────


class _Products:
    def __init__(self) -> None:
        self.reads = 0

    async def get_by_id(self, id: int) -> Product | None:
        self.reads += 1
        return Product(id=id, created=datetime.now(UTC), product_number=f"PR-{id}", archived=True)


class _Projects:
    async def get_by_id(self, id: int) -> None:
        return None


async def test_owner_check_applies_the_kind_rule_first_and_names_the_kind() -> None:
    products = _Products()

    with pytest.raises(MemoOwnerConflictError):
        await controlled_documents.assert_owner_exists(
            _Projects(),
            products,
            1,
            2,
            valid_owner=ACCESS.assert_single_owner,
            plural="memos",
        )
    assert products.reads == 0

    with pytest.raises(
        ProductArchivedError, match=r"^Product #2 is archived; memos cannot be attached to it\.$"
    ):
        await controlled_documents.assert_owner_exists(
            _Projects(),
            products,
            None,
            2,
            valid_owner=ACCESS.assert_single_owner,
            plural="memos",
        )
