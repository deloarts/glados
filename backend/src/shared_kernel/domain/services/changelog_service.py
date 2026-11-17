"""
Pure functions for building changelog entries (value_objects/change_entry.py).
They take plain values, never ORM models.
"""

from collections.abc import Mapping
from datetime import date
from enum import Enum
from typing import Any

from src.shared_kernel.domain.services.clock import now_utc
from src.shared_kernel.domain.value_objects.change_entry import ChangeEntry


def append_changelog(
    existing: list[str],
    user_full_name: str,
    changes: str,
    *,
    field: str | None = None,
    old: str | None = None,
    new: str | None = None,
) -> list[str]:
    """
    Returns a new changelog list with the new entry appended, a ChangeEntry
    stamped now and naming the actor; an edit of one field may name it with
    its old and new value. Does not mutate the existing list.
    """
    updated = list(existing)
    updated.append(
        ChangeEntry(
            changes,
            at=now_utc().replace(microsecond=0),
            actor=user_full_name,
            field=field,
            old=old,
            new=new,
        )
    )
    return updated


def append_field_changes(
    existing: list[str],
    user_full_name: str,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> list[str]:
    """
    Returns a new changelog list with one entry per key of `after` whose
    value differs from `before`, each naming the field with its old and new
    value as shown to a reader; the list unchanged when nothing differs.
    """
    updated = list(existing)
    for key, new_value in after.items():
        old_value = before.get(key)
        if old_value == new_value:
            continue
        old_text, new_text = shown_value(old_value), shown_value(new_value)
        updated = append_changelog(
            updated,
            user_full_name,
            f"{key}: {old_text} → {new_text}",
            field=key,
            old=old_text,
            new=new_text,
        )
    return updated


def shown_value(value: Any) -> str:
    """A field value as a changelog shows it: empty for None or a blank
    text, an enum member as its value, a date in ISO form and a number
    without trailing zeros."""
    if isinstance(value, Enum):
        value = value.value
    if value is None or (isinstance(value, str) and not value.strip()):
        return "empty"
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def diff_changes(old: dict[str, Any], new: dict[str, Any], heading: str = "Item updated:") -> str:
    """
    Produces a human-readable diff string between two dicts, one line per
    key of `new` whose value differs from `old`, in the order of `new`. A
    key missing from `old` compares against None. The update use cases build
    their changelog entries with it, most through diff_command in
    application/services/command_changelog.py. Skips the 'changed' and
    'changes' keys. An enum member is shown as its value, so a field typed
    with an enum reads like the plain text it is stored as.
    """
    SKIP = {"changed", "changes"}
    lines = []
    for key, new_val in new.items():
        if key in SKIP:
            continue
        old_val = _plain(old.get(key))
        new_val = _plain(new_val)
        if old_val != new_val:
            lines.append(f"  • {key}: {old_val!r} → {new_val!r}")
    if not lines:
        return "No changes."
    return f"{heading}\n" + "\n".join(lines)


def _plain(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value
