"""
Rules for the hand-maintained lists product devices pick from: who may
edit them, what a driving medium's letter may look like, and how the
positions, parameters and signals of a kind follow an edit of their list.
No I/O.
"""

import re
from dataclasses import dataclass
from typing import Protocol
from typing import TypeVar

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKindParameter
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKindPosition
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKindSignal
from src.modules.workspace.domain.errors import ProductDeviceOptionInvalidError
from src.modules.workspace.domain.errors import ProductDeviceReferenceInvalidError
from src.modules.workspace.domain.value_objects.product_device_option_category import (
    ProductDeviceOptionCategory,
)
from src.modules.workspace.domain.value_objects.product_device_parameter_type import (
    ProductDeviceParameterType,
)
from src.modules.workspace.domain.value_objects.product_device_signal import ProductDeviceSignalType

# Uppercase ASCII only, because the letter goes into the ASCII device name
# and CAD file names unchanged.
_LETTER = re.compile(r"[A-Z]{1,4}")

_NOUN = "product device resources"


class ProductDeviceResourceRules:
    @staticmethod
    def assert_can_write(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_PRODUCT_DEVICE_RESOURCES, "edit", _NOUN)

    @staticmethod
    def assert_can_archive(actor: User) -> None:
        assert_has_permission(
            actor, Permission.WRITE_PRODUCT_DEVICE_RESOURCES, "archive or restore", _NOUN
        )


def normalize_letter(category: ProductDeviceOptionCategory, letter: str | None) -> str | None:
    """The letter to store for an entry of `category`. A driving medium needs
    one of one to four uppercase ASCII letters; every other category has
    none."""
    value = (letter or "").strip()
    if category is not ProductDeviceOptionCategory.DRIVING_MEDIUM:
        if value:
            raise ProductDeviceOptionInvalidError("Only a driving medium has a letter.")
        return None
    if not _LETTER.fullmatch(value):
        raise ProductDeviceOptionInvalidError(
            f"A driving medium needs a letter of one to four uppercase letters A to Z, "
            f"got {value!r}."
        )
    return value


@dataclass(frozen=True)
class PositionDraft:
    """A position as an edit of its kind sends it; `id` is None for a new one."""

    id: int | None
    label: LocalizedText
    takes_value: bool
    unit: str | None
    plc_state_name: str | None = None
    plc_command_name: str | None = None


@dataclass(frozen=True)
class ParameterDraft:
    id: int | None
    label: LocalizedText
    unit: str | None
    value_type: ProductDeviceParameterType


@dataclass(frozen=True)
class SignalDraft:
    id: int | None
    label: LocalizedText
    signal_type: ProductDeviceSignalType
    plc_name: str


class _Child(Protocol):
    id: int
    archived: bool
    sort_order: int


TChild = TypeVar("TChild", bound=_Child)


def _check_ids(existing: list[TChild], draft_ids: list[int], what: str) -> dict[int, TChild]:
    by_id = {child.id: child for child in existing}
    for draft_id in draft_ids:
        if draft_id not in by_id:
            raise ProductDeviceReferenceInvalidError(
                f"{what} #{draft_id} is not part of this kind."
            )
    if len(set(draft_ids)) != len(draft_ids):
        raise ProductDeviceReferenceInvalidError(f"A {what.lower()} appears twice in the list.")
    return by_id


def _clean_unit(unit: str | None) -> str | None:
    value = (unit or "").strip()
    return value or None


PLC_NAME_MAX_LENGTH = 40
_PLC_NAME = re.compile(r"[A-Za-z0-9_]+")


def clean_plc_name(name: str | None, what: str, owner: str = "position") -> str | None:
    """A position's state or command name, or a kind signal's PLC name:
    letters, digits and underscores only, since it goes into PLC tags
    unchanged; empty means none."""
    value = (name or "").strip()
    if not value:
        return None
    if len(value) > PLC_NAME_MAX_LENGTH or not _PLC_NAME.fullmatch(value):
        raise ProductDeviceReferenceInvalidError(
            f"A {owner}'s {what} holds only letters, digits and underscores, at most "
            f"{PLC_NAME_MAX_LENGTH} of them; got {value!r}."
        )
    return value


def sync_positions(
    kind_id: int, existing: list[ProductDeviceKindPosition], drafts: list[PositionDraft]
) -> list[ProductDeviceKindPosition]:
    """The kind's positions after an edit: drafts with an id update that
    position and bring it back if it was archived, drafts without one are
    new, list order becomes `sort_order`, and positions missing from the
    drafts are archived."""
    by_id = _check_ids(existing, [d.id for d in drafts if d.id is not None], "Position")
    kept: set[int] = set()
    result: list[ProductDeviceKindPosition] = []
    for index, draft in enumerate(drafts):
        if draft.id is None:
            result.append(
                ProductDeviceKindPosition(
                    id=0,
                    kind_id=kind_id,
                    label=draft.label,
                    takes_value=draft.takes_value,
                    unit=_clean_unit(draft.unit),
                    sort_order=index,
                    plc_state_name=clean_plc_name(draft.plc_state_name, "state name"),
                    plc_command_name=clean_plc_name(draft.plc_command_name, "command name"),
                )
            )
            continue
        position = by_id[draft.id]
        position.label = draft.label
        position.takes_value = draft.takes_value
        position.unit = _clean_unit(draft.unit)
        position.plc_state_name = clean_plc_name(draft.plc_state_name, "state name")
        position.plc_command_name = clean_plc_name(draft.plc_command_name, "command name")
        position.sort_order = index
        position.archived = False
        kept.add(position.id)
        result.append(position)
    for position in existing:
        if position.id not in kept:
            position.archived = True
            result.append(position)
    return result


def sync_parameters(
    kind_id: int, existing: list[ProductDeviceKindParameter], drafts: list[ParameterDraft]
) -> list[ProductDeviceKindParameter]:
    """The kind's parameters after an edit, by the same rules as
    `sync_positions`."""
    by_id = _check_ids(existing, [d.id for d in drafts if d.id is not None], "Parameter")
    kept: set[int] = set()
    result: list[ProductDeviceKindParameter] = []
    for index, draft in enumerate(drafts):
        if draft.id is None:
            result.append(
                ProductDeviceKindParameter(
                    id=0,
                    kind_id=kind_id,
                    label=draft.label,
                    unit=_clean_unit(draft.unit),
                    value_type=draft.value_type,
                    sort_order=index,
                )
            )
            continue
        parameter = by_id[draft.id]
        parameter.label = draft.label
        parameter.unit = _clean_unit(draft.unit)
        parameter.value_type = draft.value_type
        parameter.sort_order = index
        parameter.archived = False
        kept.add(parameter.id)
        result.append(parameter)
    for parameter in existing:
        if parameter.id not in kept:
            parameter.archived = True
            result.append(parameter)
    return result


def _signal_plc_name(draft: SignalDraft) -> str:
    """A kind signal needs a PLC name, since naming its devices' tags is
    what it is for."""
    name = clean_plc_name(draft.plc_name, "PLC name", "signal")
    if name is None:
        raise ProductDeviceReferenceInvalidError("Every signal of a kind needs a PLC name.")
    return name


def sync_signals(
    kind_id: int, existing: list[ProductDeviceKindSignal], drafts: list[SignalDraft]
) -> list[ProductDeviceKindSignal]:
    """The kind's signals after an edit, by the same rules as
    `sync_positions`."""
    by_id = _check_ids(existing, [d.id for d in drafts if d.id is not None], "Signal")
    kept: set[int] = set()
    result: list[ProductDeviceKindSignal] = []
    for index, draft in enumerate(drafts):
        if draft.id is None:
            result.append(
                ProductDeviceKindSignal(
                    id=0,
                    kind_id=kind_id,
                    label=draft.label,
                    signal_type=draft.signal_type,
                    plc_name=_signal_plc_name(draft),
                    sort_order=index,
                )
            )
            continue
        signal = by_id[draft.id]
        signal.label = draft.label
        signal.signal_type = draft.signal_type
        signal.plc_name = _signal_plc_name(draft)
        signal.sort_order = index
        signal.archived = False
        kept.add(signal.id)
        result.append(signal)
    for signal in existing:
        if signal.id not in kept:
            signal.archived = True
            result.append(signal)
    return result
