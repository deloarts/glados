"""
Admin CRUD for acknowledgements, mirroring
webhook/manage_webhook_subscriptions.py's permission split: reads require
read:settings, writes require write:settings. Text, severity, show_when
and the recipient list are immutable after creation: a changed text
would invalidate confirmations already given by earlier recipients, so
the only mutable field is `enabled` (SetAcknowledgementEnabled); an admin
who wants different wording creates a new acknowledgement instead.
"""

from uuid import UUID

from src.modules.platform.application.dto.acknowledgement_dto import AcknowledgementRecipientResult
from src.modules.platform.application.dto.acknowledgement_dto import AcknowledgementSummaryResult
from src.modules.platform.application.dto.acknowledgement_dto import CreateAcknowledgementCommand
from src.modules.platform.application.mappers.acknowledgement_mapper import AcknowledgementMapper
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.acknowledgement import Acknowledgement
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import AcknowledgementNotFoundError
from src.modules.platform.domain.exceptions import AcknowledgementRecipientsInvalidError
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.repositories.acknowledgement_repository import (
    AcknowledgementSummary,
)
from src.modules.platform.ports.outbound.repositories.acknowledgement_repository import (
    IAcknowledgementRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


def _assert_can_read(actor: User) -> None:
    if not actor.has_permission(Permission.READ_SETTINGS):
        raise InsufficientPermissionsError("Reading acknowledgements requires read:settings.")


def _assert_can_write(actor: User) -> None:
    if not actor.has_permission(Permission.WRITE_SETTINGS):
        raise InsufficientPermissionsError("Changing acknowledgements requires write:settings.")


class CreateAcknowledgement:
    def __init__(
        self,
        ack_repo: IAcknowledgementRepository,
        user_repo: IUserRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._acks = ack_repo
        self._users = user_repo
        self._uow = uow

    async def execute(
        self, actor: User, cmd: CreateAcknowledgementCommand
    ) -> AcknowledgementSummaryResult:
        _assert_can_write(actor)

        if not cmd.recipient_ids:
            raise AcknowledgementRecipientsInvalidError("At least one recipient is required.")
        # No bulk "get by ids" on IUserRepository (verified: get_multi's
        # UserFilterDto takes a single optional id, not a list), so this
        # loops get_by_id per recipient, bounded by the recipient list a
        # single admin action can name, not a hot path.
        unknown = sorted(
            {uid for uid in cmd.recipient_ids if await self._users.get_by_id(uid) is None}
        )
        if unknown:
            raise AcknowledgementRecipientsInvalidError(f"Unknown user id(s): {unknown}.")

        ack = Acknowledgement(
            id=0,
            text=cmd.text,
            severity=cmd.severity,
            enabled=cmd.enabled,
            show_when=cmd.show_when,
            created_at=now_utc(),
            created_by_id=actor.id,
        )
        saved = await self._acks.create(ack, cmd.recipient_ids)
        await self._uow.commit()

        log.info(
            f"Created acknowledgement (ID={saved.id}) for {len(cmd.recipient_ids)} recipient(s)."
        )
        summary = AcknowledgementSummary(
            acknowledgement=saved,
            created_by_username=actor.username,
            recipients_total=len(cmd.recipient_ids),
            recipients_acknowledged=0,
        )
        return AcknowledgementMapper.summary_to_result(summary)


class ListAcknowledgements:
    def __init__(self, ack_repo: IAcknowledgementRepository) -> None:
        self._acks = ack_repo

    async def execute(self, actor: User) -> list[AcknowledgementSummaryResult]:
        _assert_can_read(actor)
        return [
            AcknowledgementMapper.summary_to_result(s) for s in await self._acks.list_summaries()
        ]


class SetAcknowledgementEnabled:
    def __init__(
        self,
        ack_repo: IAcknowledgementRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._acks = ack_repo
        self._uow = uow

    async def execute(
        self, actor: User, public_id: UUID, enabled: bool
    ) -> AcknowledgementSummaryResult:
        _assert_can_write(actor)
        summary = found_or_raise(
            await self._acks.set_enabled(public_id, enabled),
            AcknowledgementNotFoundError,
            f"Acknowledgement {public_id} not found.",
        )
        await self._uow.commit()
        log.info(f"{'Enabled' if enabled else 'Disabled'} acknowledgement {public_id}.")
        return AcknowledgementMapper.summary_to_result(summary)


class DeleteAcknowledgement:
    def __init__(
        self,
        ack_repo: IAcknowledgementRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._acks = ack_repo
        self._uow = uow

    async def execute(self, actor: User, public_id: UUID) -> None:
        _assert_can_write(actor)
        if not await self._acks.delete(public_id):
            raise AcknowledgementNotFoundError(f"Acknowledgement {public_id} not found.")
        await self._uow.commit()
        log.info(f"Deleted acknowledgement {public_id}.")


class ListAcknowledgementRecipients:
    def __init__(self, ack_repo: IAcknowledgementRepository) -> None:
        self._acks = ack_repo

    async def execute(self, actor: User, public_id: UUID) -> list[AcknowledgementRecipientResult]:
        _assert_can_read(actor)
        ack = found_or_raise(
            await self._acks.get_by_public_id(public_id),
            AcknowledgementNotFoundError,
            f"Acknowledgement {public_id} not found.",
        )
        return [
            AcknowledgementMapper.recipient_view_to_result(v)
            for v in await self._acks.list_recipients(ack.id)
        ]
