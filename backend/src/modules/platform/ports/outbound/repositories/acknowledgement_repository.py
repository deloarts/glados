"""
Abstract interface for the acknowledgements feature (an admin-authored
message every selected user must confirm). Mirrors
global_search_repository.py's shape: the two read projections below
(AcknowledgementSummary, AcknowledgementRecipientView) are joined,
aggregate read shapes with no 1:1 domain entity of their own, and not
something Acknowledgement/AcknowledgementRecipient themselves model, so
they live here as plain dataclasses rather than in domain/entities.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from typing import runtime_checkable
from uuid import UUID

from src.modules.platform.domain.entities.acknowledgement import Acknowledgement


@dataclass(frozen=True)
class AcknowledgementSummary:
    """One row for the admin list/create/patch response: the
    acknowledgement itself, its creator's username (resolved live via
    created_by_id, a nullable FK, None once the creator account is
    deleted, rather than a frozen-at-creation-time snapshot like
    AdminSettingsAuditEntry.changed_by_username), and recipient progress."""

    acknowledgement: Acknowledgement
    created_by_username: str | None
    recipients_total: int
    recipients_acknowledged: int


@dataclass(frozen=True)
class AcknowledgementRecipientView:
    """One row for the admin recipients dialog: a recipient plus the
    display fields joined from the users table."""

    user_id: int
    username: str
    full_name: str
    acknowledged_at: datetime | None


@runtime_checkable
class IAcknowledgementRepository(Protocol):
    async def create(self, ack: Acknowledgement, recipient_user_ids: list[int]) -> Acknowledgement:
        """Inserts the acknowledgement and every recipient row in one
        transaction. Recipient id validity is the caller's job
        (CreateAcknowledgement, via IUserRepository)."""
        ...

    async def list_summaries(self) -> list[AcknowledgementSummary]:
        """Newest first. One query with aggregates, not N+1."""
        ...

    async def get_by_public_id(self, public_id: UUID) -> Acknowledgement | None: ...

    async def set_enabled(self, public_id: UUID, enabled: bool) -> AcknowledgementSummary | None:
        """None when no acknowledgement has this public_id (the use case
        turns that into 404)."""
        ...

    async def delete(self, public_id: UUID) -> bool:
        """True if a row was found and removed (cascading to its
        recipients); False if no acknowledgement has this public_id."""
        ...

    async def list_recipients(self, ack_id: int) -> list[AcknowledgementRecipientView]:
        """Sorted pending first, then by full_name."""
        ...

    async def get_pending_for_user(
        self, user_id: int, session_created_at: datetime | None
    ) -> list[Acknowledgement]:
        """Enabled acknowledgements where `user_id` is a recipient with
        acknowledged_at IS NULL, and (show_when == "immediately" OR
        session_created_at is not None and session_created_at >= the
        acknowledgement's own created_at). Oldest first."""
        ...

    async def acknowledge(self, public_id: UUID, user_id: int, now: datetime) -> bool:
        """Sets acknowledged_at if not already set. False when `user_id`
        is not a recipient of an existing, enabled acknowledgement (the
        use case turns that into 404); True otherwise, including when
        already acknowledged (idempotent)."""
        ...
