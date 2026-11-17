"""
Domain events emitted by meeting use cases.
"""

from dataclasses import dataclass

from src.shared_kernel.domain.events.base import DomainEvent


@dataclass(frozen=True)
class MeetingActivityDue(DomainEvent):
    """The mentions and todo assignments of one meeting that waited their
    five minutes for one recipient, to go out as one notification.
    `title` and `message` are what the notification reads, both in the
    recipient's language. An event without a title, written before it
    carried one, falls back to the English title."""

    meeting_id: int
    meeting_number: str
    recipient_id: int
    mention_count: int
    todo_count: int
    message: str
    title: str = ""
