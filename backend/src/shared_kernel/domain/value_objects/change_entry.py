"""One line of an entity's changelog, kept as a structured record.

A ChangeEntry is the line itself, "YYYY-MM-DD HH:MM:SS, actor, text", so
every caller that reads a changelog as text keeps working, and it carries the
parts the line is made of: when, who and what, and, for an edit of one field,
that field with its old and new value, the shape of an SAP change document.
The record form is what the database stores.

A plain string, as a test passes for a changelog it builds by hand, becomes
an entry of that text with no time or actor.
"""

from datetime import UTC
from datetime import datetime
from typing import Any
from typing import Self

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
_SEPARATOR = ", "


class ChangeEntry(str):
    """A changelog line with its parts; see the module docstring."""

    at: datetime | None
    actor: str | None
    text: str
    field: str | None
    old: str | None
    new: str | None

    def __new__(
        cls,
        text: str,
        *,
        at: datetime | None = None,
        actor: str | None = None,
        field: str | None = None,
        old: str | None = None,
        new: str | None = None,
    ) -> Self:
        line = (
            f"{at.astimezone(UTC):{TIMESTAMP_FORMAT}}{_SEPARATOR}{actor}{_SEPARATOR}{text}"
            if at is not None and actor is not None
            else text
        )
        entry = super().__new__(cls, line)
        entry.at = at
        entry.actor = actor
        entry.text = text
        entry.field = field
        entry.old = old
        entry.new = new
        return entry

    # A changelog line is a value: copying it, as a copied changelog list
    # does, keeps the same entry.
    def __copy__(self) -> Self:
        return self

    def __deepcopy__(self, memo: dict[int, Any]) -> Self:
        return self

    def __reduce__(self) -> tuple[Any, ...]:
        return (_from_record, (self.to_record(),))

    @classmethod
    def parse(cls, line: str) -> "ChangeEntry":
        """The entry a line stands for: the entry itself, or a plain string
        as an entry of that text only."""
        if isinstance(line, ChangeEntry):
            return line
        return cls(line)

    def to_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {"text": self.text}
        if self.at is not None and self.actor is not None:
            record["at"] = self.at.astimezone(UTC).strftime(TIMESTAMP_FORMAT)
            record["actor"] = self.actor
        for key in ("field", "old", "new"):
            value = getattr(self, key)
            if value is not None:
                record[key] = value
        return record

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "ChangeEntry":
        at = record.get("at")
        return cls(
            str(record.get("text", "")),
            at=datetime.strptime(at, TIMESTAMP_FORMAT).replace(tzinfo=UTC) if at else None,
            actor=record.get("actor"),
            field=record.get("field"),
            old=record.get("old"),
            new=record.get("new"),
        )


def _from_record(record: dict[str, Any]) -> ChangeEntry:
    return ChangeEntry.from_record(record)
