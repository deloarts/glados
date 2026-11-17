"""
The delivery tolerance fields of a catalogue item's create and update
commands. An update that does not send them, as a pat client's does not,
keeps the item's own values, so the update use cases fill them in from the
item before they diff and apply the command.
"""

from typing import Protocol

from pydantic import BaseModel

from src.modules.catalogue.domain.services.item_delivery_tolerance_rules import (
    assert_valid_tolerance,
)

TOLERANCE_FIELDS = ("over_delivery_tolerance_percent", "under_delivery_tolerance_percent")


class _ToleranceCommand(Protocol):
    over_delivery_tolerance_percent: float | None
    under_delivery_tolerance_percent: float | None


def keep_unsent_tolerances[C: BaseModel](cmd: C, item: object) -> C:
    """The command with the item's tolerances where it does not send its own."""
    sent = cmd.model_fields_set
    kept = {name: getattr(item, name) for name in TOLERANCE_FIELDS if name not in sent}
    return cmd.model_copy(update=kept) if kept else cmd


def assert_valid_item_tolerances(cmd: _ToleranceCommand) -> None:
    assert_valid_tolerance(
        cmd.over_delivery_tolerance_percent, what="The item's over-delivery tolerance"
    )
    assert_valid_tolerance(
        cmd.under_delivery_tolerance_percent, what="The item's under-delivery tolerance"
    )
