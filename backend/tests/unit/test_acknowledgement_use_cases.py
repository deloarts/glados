"""
Unit tests for the acknowledgements use cases: admin CRUD
(manage_acknowledgements.py) and the user-facing pair
(announcements_for_user.py). No database, no HTTP, every dependency is
an in-memory fake.
"""

from datetime import UTC
from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.modules.platform.application.dto.acknowledgement_dto import CreateAcknowledgementCommand
from src.modules.platform.application.use_cases.acknowledgement.announcements_for_user import (
    AcknowledgeAnnouncement,
)
from src.modules.platform.application.use_cases.acknowledgement.announcements_for_user import (
    GetMyAnnouncements,
)
from src.modules.platform.application.use_cases.acknowledgement.manage_acknowledgements import (
    CreateAcknowledgement,
)
from src.modules.platform.application.use_cases.acknowledgement.manage_acknowledgements import (
    DeleteAcknowledgement,
)
from src.modules.platform.application.use_cases.acknowledgement.manage_acknowledgements import (
    ListAcknowledgementRecipients,
)
from src.modules.platform.application.use_cases.acknowledgement.manage_acknowledgements import (
    ListAcknowledgements,
)
from src.modules.platform.application.use_cases.acknowledgement.manage_acknowledgements import (
    SetAcknowledgementEnabled,
)
from src.modules.platform.domain.entities.acknowledgement import Acknowledgement
from src.modules.platform.domain.exceptions import AcknowledgementNotFoundError
from src.modules.platform.domain.exceptions import AcknowledgementRecipientsInvalidError
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.acknowledgement_show_when import (
    AcknowledgementShowWhen,
)
from src.modules.platform.domain.value_objects.announcement_severity import AnnouncementSeverity
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.ports.outbound.repositories.acknowledgement_repository import (
    AcknowledgementRecipientView,
)
from src.modules.platform.ports.outbound.repositories.acknowledgement_repository import (
    AcknowledgementSummary,
)
from tests.factories import make_user
from tests.unit.admin_settings.fakes import FakeAdminSettingsRepository
from tests.unit.fakes import FakeUnitOfWork

# ── Fakes ─────────────────────────────────────────────────────────────


class FakeAcknowledgementRepository:
    def __init__(self) -> None:
        self._acks: dict[int, Acknowledgement] = {}
        # ack_id -> {user_id: acknowledged_at | None}
        self._recipients: dict[int, dict[int, datetime | None]] = {}
        self._next_id = 1

    @property
    def recipients(self) -> dict[int, dict[int, datetime | None]]:
        """When each recipient acknowledged, by acknowledgement id and user id, for assertions."""
        return self._recipients

    async def create(self, ack: Acknowledgement, recipient_user_ids: list[int]) -> Acknowledgement:
        ack.id = self._next_id
        self._next_id += 1
        self._acks[ack.id] = ack
        self._recipients[ack.id] = dict.fromkeys(recipient_user_ids)
        return ack

    def _summary(self, ack: Acknowledgement) -> AcknowledgementSummary:
        recipients = self._recipients.get(ack.id, {})
        return AcknowledgementSummary(
            acknowledgement=ack,
            created_by_username="creator",
            recipients_total=len(recipients),
            recipients_acknowledged=sum(1 for v in recipients.values() if v is not None),
        )

    async def list_summaries(self) -> list[AcknowledgementSummary]:
        return [
            self._summary(a)
            for a in sorted(self._acks.values(), key=lambda a: a.created_at, reverse=True)
        ]

    async def get_by_public_id(self, public_id):
        return next((a for a in self._acks.values() if a.public_id == public_id), None)

    async def set_enabled(self, public_id, enabled: bool):
        ack = await self.get_by_public_id(public_id)
        if ack is None:
            return None
        ack.enabled = enabled
        return self._summary(ack)

    async def delete(self, public_id) -> bool:
        ack = await self.get_by_public_id(public_id)
        if ack is None:
            return False
        del self._acks[ack.id]
        self._recipients.pop(ack.id, None)
        return True

    async def list_recipients(self, ack_id: int) -> list[AcknowledgementRecipientView]:
        recipients = self._recipients.get(ack_id, {})
        views = [
            AcknowledgementRecipientView(
                user_id=uid, username=f"user{uid}", full_name=f"User {uid:02d}", acknowledged_at=ts
            )
            for uid, ts in recipients.items()
        ]
        views.sort(key=lambda v: (v.acknowledged_at is not None, v.full_name.lower()))
        return views

    async def get_pending_for_user(self, user_id: int, session_created_at):
        pending = []
        for ack in sorted(self._acks.values(), key=lambda a: a.created_at):
            recipients = self._recipients.get(ack.id, {})
            if user_id not in recipients or recipients[user_id] is not None or not ack.enabled:
                continue
            if ack.show_when == AcknowledgementShowWhen.IMMEDIATELY.value or (
                session_created_at is not None and session_created_at >= ack.created_at
            ):
                pending.append(ack)
        return pending

    async def acknowledge(self, public_id, user_id: int, now: datetime) -> bool:
        ack = await self.get_by_public_id(public_id)
        if ack is None or not ack.enabled:
            return False
        recipients = self._recipients.get(ack.id, {})
        if user_id not in recipients:
            return False
        if recipients[user_id] is None:
            recipients[user_id] = now
        return True


class FakeUserRepository:
    def __init__(self, existing_ids: set[int]) -> None:
        self._existing = existing_ids

    async def get_by_id(self, id: int):
        return object() if id in self._existing else None


class FakeUserSessionRepository:
    def __init__(self, sessions: dict) -> None:
        self._sessions = sessions

    async def get_by_public_id(self, public_id):
        return self._sessions.get(public_id)


class _Session:
    def __init__(self, user_id: int, created_at: datetime) -> None:
        self.user_id = user_id
        self.created_at = created_at


def _make_ack(
    *,
    enabled: bool = True,
    show_when: AcknowledgementShowWhen = AcknowledgementShowWhen.IMMEDIATELY,
    created_at: datetime | None = None,
) -> Acknowledgement:
    return Acknowledgement(
        id=0,
        text="Please confirm you have read this.",
        severity=AnnouncementSeverity.INFO,
        enabled=enabled,
        show_when=show_when,
        created_at=created_at or datetime(2026, 1, 1, tzinfo=UTC),
        created_by_id=1,
    )


# ── CreateAcknowledgement ─────────────────────────────────────────────


class TestCreateAcknowledgement:
    def setup_method(self):
        self.acks = FakeAcknowledgementRepository()
        self.actor = make_user(permissions=[Permission.WRITE_SETTINGS])

    def test_empty_recipient_ids_rejected_by_the_command_itself(self):
        with pytest.raises(ValidationError):
            CreateAcknowledgementCommand(
                text="Hello",
                severity=AnnouncementSeverity.INFO,
                enabled=True,
                show_when=AcknowledgementShowWhen.IMMEDIATELY,
                recipient_ids=[],
            )

    async def test_unknown_recipient_id_raises(self):
        users = FakeUserRepository(existing_ids={1, 2})
        use_case = CreateAcknowledgement(self.acks, users, uow=FakeUnitOfWork())
        cmd = CreateAcknowledgementCommand(
            text="Hello",
            severity=AnnouncementSeverity.INFO,
            enabled=True,
            show_when=AcknowledgementShowWhen.IMMEDIATELY,
            recipient_ids=[1, 999],
        )
        with pytest.raises(AcknowledgementRecipientsInvalidError, match="999"):
            await use_case.execute(actor=self.actor, cmd=cmd)

    async def test_creates_with_valid_recipients_incl_a_shared_account(self):
        """The recipient snapshot has no special casing for shared
        accounts: any existing user id (however the caller assembled the
        list) is accepted."""
        users = FakeUserRepository(existing_ids={1, 2, 3})
        use_case = CreateAcknowledgement(self.acks, users, uow=FakeUnitOfWork())
        cmd = CreateAcknowledgementCommand(
            text="Hello",
            severity=AnnouncementSeverity.WARNING,
            enabled=True,
            show_when=AcknowledgementShowWhen.NEXT_LOGIN,
            recipient_ids=[1, 2, 3],
        )
        result = await use_case.execute(actor=self.actor, cmd=cmd)
        assert result.recipients_total == 3
        assert result.recipients_acknowledged == 0
        assert result.created_by_username == self.actor.username
        assert result.severity == AnnouncementSeverity.WARNING
        assert result.show_when == AcknowledgementShowWhen.NEXT_LOGIN

    async def test_unprivileged_cannot_create(self):
        actor = make_user(permissions=[])
        users = FakeUserRepository(existing_ids={1})
        use_case = CreateAcknowledgement(self.acks, users, uow=FakeUnitOfWork())
        cmd = CreateAcknowledgementCommand(
            text="Hello",
            severity=AnnouncementSeverity.INFO,
            enabled=True,
            show_when=AcknowledgementShowWhen.IMMEDIATELY,
            recipient_ids=[1],
        )
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor=actor, cmd=cmd)


# ── ListAcknowledgements ─────────────────────────────────────────────


class TestListAcknowledgements:
    async def test_unprivileged_cannot_read(self):
        use_case = ListAcknowledgements(FakeAcknowledgementRepository())
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor=make_user(permissions=[]))


# ── SetAcknowledgementEnabled ────────────────────────────────────────


class TestSetAcknowledgementEnabled:
    async def test_toggles_enabled(self):
        acks = FakeAcknowledgementRepository()
        ack = await acks.create(_make_ack(enabled=True), [1])
        actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        result = await SetAcknowledgementEnabled(acks, uow=FakeUnitOfWork()).execute(
            actor=actor, public_id=ack.public_id, enabled=False
        )
        assert result.enabled is False

    async def test_missing_raises_not_found(self):
        actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        with pytest.raises(AcknowledgementNotFoundError):
            await SetAcknowledgementEnabled(
                FakeAcknowledgementRepository(), uow=FakeUnitOfWork()
            ).execute(actor=actor, public_id=uuid4(), enabled=False)

    async def test_unprivileged_cannot_write(self):
        acks = FakeAcknowledgementRepository()
        ack = await acks.create(_make_ack(), [1])
        with pytest.raises(InsufficientPermissionsError):
            await SetAcknowledgementEnabled(acks, uow=FakeUnitOfWork()).execute(
                actor=make_user(permissions=[]), public_id=ack.public_id, enabled=False
            )


# ── DeleteAcknowledgement ────────────────────────────────────────────


class TestDeleteAcknowledgement:
    async def test_deletes(self):
        acks = FakeAcknowledgementRepository()
        ack = await acks.create(_make_ack(), [1])
        actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        await DeleteAcknowledgement(acks, uow=FakeUnitOfWork()).execute(
            actor=actor, public_id=ack.public_id
        )
        assert await acks.get_by_public_id(ack.public_id) is None

    async def test_missing_raises_not_found(self):
        actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        with pytest.raises(AcknowledgementNotFoundError):
            await DeleteAcknowledgement(
                FakeAcknowledgementRepository(), uow=FakeUnitOfWork()
            ).execute(actor=actor, public_id=uuid4())


# ── ListAcknowledgementRecipients ────────────────────────────────────


class TestListAcknowledgementRecipients:
    async def test_missing_raises_not_found(self):
        actor = make_user(permissions=[Permission.READ_SETTINGS])
        with pytest.raises(AcknowledgementNotFoundError):
            await ListAcknowledgementRecipients(FakeAcknowledgementRepository()).execute(
                actor=actor, public_id=uuid4()
            )

    async def test_sorted_pending_first_then_by_full_name(self):
        acks = FakeAcknowledgementRepository()
        ack = await acks.create(_make_ack(), [3, 1, 2])
        await acks.acknowledge(ack.public_id, 1, datetime(2026, 1, 2, tzinfo=UTC))
        actor = make_user(permissions=[Permission.READ_SETTINGS])
        result = await ListAcknowledgementRecipients(acks).execute(
            actor=actor, public_id=ack.public_id
        )
        # user 1 acknowledged, so it sorts after the still-pending 2 and 3
        # (alphabetically among themselves: "User 02" before "User 03").
        assert [r.user_id for r in result] == [2, 3, 1]


# ── GetMyAnnouncements ────────────────────────────────────────────────


class TestGetMyAnnouncements:
    def setup_method(self):
        self.acks = FakeAcknowledgementRepository()
        self.settings = FakeAdminSettingsRepository()
        self.sessions = FakeUserSessionRepository({})
        self.use_case = GetMyAnnouncements(self.acks, self.settings, self.sessions)
        self.actor = make_user(id=42, permissions=[])

    async def test_banner_omitted_when_disabled(self):
        self.settings.banner.enabled = False
        self.settings.banner.text = "Hello"
        result = await self.use_case.execute(self.actor, None)
        assert result.banner is None

    async def test_banner_omitted_when_text_is_blank(self):
        self.settings.banner.enabled = True
        self.settings.banner.text = "   "
        result = await self.use_case.execute(self.actor, None)
        assert result.banner is None

    async def test_banner_included_when_enabled_with_text(self):
        self.settings.banner.enabled = True
        self.settings.banner.text = "We upgrade at 18:00"
        result = await self.use_case.execute(self.actor, None)
        assert result.banner is not None
        assert result.banner.text == "We upgrade at 18:00"

    async def test_immediately_ack_is_pending_regardless_of_session(self):
        await self.acks.create(_make_ack(show_when=AcknowledgementShowWhen.IMMEDIATELY), [42])
        result = await self.use_case.execute(self.actor, None)
        assert len(result.pending_acknowledgements) == 1

    async def test_next_login_ack_omitted_when_session_is_none(self):
        await self.acks.create(_make_ack(show_when=AcknowledgementShowWhen.NEXT_LOGIN), [42])
        result = await self.use_case.execute(self.actor, None)
        assert result.pending_acknowledgements == []

    async def test_next_login_ack_omitted_when_session_predates_it(self):
        created_at = datetime(2026, 1, 10, tzinfo=UTC)
        ack = await self.acks.create(
            _make_ack(show_when=AcknowledgementShowWhen.NEXT_LOGIN, created_at=created_at),
            [42],
        )
        sid = uuid4()
        self.sessions._sessions[sid] = _Session(
            user_id=42, created_at=datetime(2026, 1, 5, tzinfo=UTC)
        )
        result = await self.use_case.execute(self.actor, sid)
        assert result.pending_acknowledgements == []
        assert ack.show_when == AcknowledgementShowWhen.NEXT_LOGIN.value  # sanity

    async def test_next_login_ack_included_when_session_postdates_it(self):
        created_at = datetime(2026, 1, 10, tzinfo=UTC)
        await self.acks.create(
            _make_ack(show_when=AcknowledgementShowWhen.NEXT_LOGIN, created_at=created_at),
            [42],
        )
        sid = uuid4()
        self.sessions._sessions[sid] = _Session(
            user_id=42, created_at=datetime(2026, 1, 15, tzinfo=UTC)
        )
        result = await self.use_case.execute(self.actor, sid)
        assert len(result.pending_acknowledgements) == 1

    async def test_disabled_ack_is_not_pending(self):
        await self.acks.create(_make_ack(enabled=False), [42])
        result = await self.use_case.execute(self.actor, None)
        assert result.pending_acknowledgements == []

    async def test_already_acknowledged_is_not_pending(self):
        ack = await self.acks.create(_make_ack(), [42])
        await self.acks.acknowledge(ack.public_id, 42, datetime.now(UTC))
        result = await self.use_case.execute(self.actor, None)
        assert result.pending_acknowledgements == []

    async def test_non_recipient_is_not_pending(self):
        await self.acks.create(_make_ack(), [99])
        result = await self.use_case.execute(self.actor, None)
        assert result.pending_acknowledgements == []

    async def test_oldest_first(self):
        older = await self.acks.create(_make_ack(created_at=datetime(2026, 1, 1, tzinfo=UTC)), [42])
        newer = await self.acks.create(_make_ack(created_at=datetime(2026, 1, 2, tzinfo=UTC)), [42])
        result = await self.use_case.execute(self.actor, None)
        assert [p.public_id for p in result.pending_acknowledgements] == [
            older.public_id,
            newer.public_id,
        ]


# ── AcknowledgeAnnouncement ──────────────────────────────────────────


class TestAcknowledgeAnnouncement:
    async def test_acknowledges_a_pending_one(self):
        acks = FakeAcknowledgementRepository()
        ack = await acks.create(_make_ack(), [42])
        actor = make_user(id=42, permissions=[])
        await AcknowledgeAnnouncement(acks, uow=FakeUnitOfWork()).execute(actor, ack.public_id)
        assert acks.recipients[ack.id][42] is not None

    async def test_idempotent_when_already_acknowledged(self):
        acks = FakeAcknowledgementRepository()
        ack = await acks.create(_make_ack(), [42])
        actor = make_user(id=42, permissions=[])
        await AcknowledgeAnnouncement(acks, uow=FakeUnitOfWork()).execute(actor, ack.public_id)
        first_ts = acks._recipients[ack.id][42]
        await AcknowledgeAnnouncement(acks, uow=FakeUnitOfWork()).execute(
            actor, ack.public_id
        )  # must not raise
        assert acks.recipients[ack.id][42] == first_ts

    async def test_non_recipient_raises_not_found(self):
        acks = FakeAcknowledgementRepository()
        ack = await acks.create(_make_ack(), [1])
        actor = make_user(id=42, permissions=[])
        with pytest.raises(AcknowledgementNotFoundError):
            await AcknowledgeAnnouncement(acks, uow=FakeUnitOfWork()).execute(actor, ack.public_id)

    async def test_disabled_raises_not_found(self):
        acks = FakeAcknowledgementRepository()
        ack = await acks.create(_make_ack(enabled=False), [42])
        actor = make_user(id=42, permissions=[])
        with pytest.raises(AcknowledgementNotFoundError):
            await AcknowledgeAnnouncement(acks, uow=FakeUnitOfWork()).execute(actor, ack.public_id)

    async def test_unknown_public_id_raises_not_found(self):
        actor = make_user(id=42, permissions=[])
        with pytest.raises(AcknowledgementNotFoundError):
            await AcknowledgeAnnouncement(
                FakeAcknowledgementRepository(), uow=FakeUnitOfWork()
            ).execute(actor, uuid4())
