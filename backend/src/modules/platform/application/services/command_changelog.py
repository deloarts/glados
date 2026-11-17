"""The changelog entry for an update command applied to an entity.

An update use case notes every command field whose value differs from the
entity's current value (diff_changes in domain/services/changelog_service.py).
Reading the current values off the command's own fields keeps both halves of
the comparison in step, so a field added to a command is compared against
the entity instead of being reported as changed from None.
"""

from typing import Any
from typing import Protocol

from src.shared_kernel.domain.services.changelog_service import diff_changes


class _Command(Protocol):
    def model_dump(self) -> dict[str, Any]: ...


def entity_values(entity: object, fields: dict[str, Any]) -> dict[str, Any]:
    """The entity's current value of each of `fields` it has. A field the
    entity lacks is left out, so diff_changes compares it against None."""
    return {name: getattr(entity, name) for name in fields if hasattr(entity, name)}


# A command's expected edit version is a precondition of the write, not a
# field it changes.
_NOT_FIELDS = frozenset({"expected_edit_version"})


def diff_command(entity: object, cmd: _Command, heading: str = "Item updated:") -> str:
    """The diff_changes text between the entity's current values and the
    command, in the command's field order. Call it before the command is
    applied to the entity."""
    new = {k: v for k, v in cmd.model_dump().items() if k not in _NOT_FIELDS}
    return diff_changes(entity_values(entity, new), new, heading)
