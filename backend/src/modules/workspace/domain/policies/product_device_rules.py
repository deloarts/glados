"""
Rules for product devices: who may edit them, and which references and
values a device and its components may hold. The use cases load what a
device points at and hand it in; nothing here does I/O.

A device may keep an archived kind, list entry or position it already has,
since archiving only hides an entry from new choices, but may not pick one
newly. Positions, parameters and position labels must belong to the
device's own kind.
"""

import math
import re
from collections.abc import Mapping
from typing import Any

from src.modules.platform.domain.entities.user import User
from src.modules.workspace.domain.entities.product import Product
from src.modules.workspace.domain.entities.product_device import ProductDevice
from src.modules.workspace.domain.entities.product_device import ProductDeviceComponent
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKind
from src.modules.workspace.domain.entities.product_device_option import ProductDeviceOption
from src.modules.workspace.domain.errors import ProductArchivedError
from src.modules.workspace.domain.errors import ProductDeviceReferenceInvalidError
from src.modules.workspace.domain.services.product_rules import ProductRules
from src.modules.workspace.domain.value_objects.product_device_option_category import (
    ProductDeviceOptionCategory,
)
from src.modules.workspace.domain.value_objects.product_device_parameter_type import (
    ProductDeviceParameterType,
)
from src.modules.workspace.domain.value_objects.product_device_signal import INPUT_SIGNAL_TYPES
from src.modules.workspace.domain.value_objects.product_device_signal import OUTPUT_SIGNAL_TYPES
from src.modules.workspace.domain.value_objects.product_device_signal import ProductDeviceSignal
from src.modules.workspace.domain.value_objects.product_device_signal import ProductDeviceSignalType

TEXT_MAX_LENGTH = 200
POSITION_LABEL_MAX_LENGTH = 60
# An hour; a longer travel time is a typing error.
TRAVEL_TIME_MAX_MS = 60 * 60 * 1000
EPLAN_TAG_MAX_LENGTH = 60
SIGNAL_MEANING_MAX_LENGTH = 80


class ProductDeviceRules:
    @staticmethod
    def assert_can_edit(actor: User, product: Product) -> None:
        """Devices are part of the product's editable state, so editing them
        needs the rights to edit the product, and the product must be live."""
        ProductRules.assert_can_update(actor, product)
        if product.archived:
            raise ProductArchivedError(
                f"Product #{product.id} ({product.product_number!r}) is archived; "
                "its devices cannot change."
            )


def check_option(
    option: ProductDeviceOption | None,
    category: ProductDeviceOptionCategory,
    current_id: int | None,
    what: str,
) -> None:
    """`option` must exist, belong to `category`, and be live unless the
    device already points at it."""
    if option is None:
        raise ProductDeviceReferenceInvalidError(f"The {what} does not exist.")
    if option.category is not category:
        raise ProductDeviceReferenceInvalidError(f"The {what} is not a {category.value} entry.")
    if option.archived and option.id != current_id:
        raise ProductDeviceReferenceInvalidError(f"The {what} is archived and cannot be chosen.")


def check_kind(kind: ProductDeviceKind | None, current_id: int | None) -> ProductDeviceKind:
    if kind is None:
        raise ProductDeviceReferenceInvalidError("The device kind does not exist.")
    if kind.archived and kind.id != current_id:
        raise ProductDeviceReferenceInvalidError(
            "The device kind is archived and cannot be chosen."
        )
    return kind


def check_position(
    kind: ProductDeviceKind, position_id: int | None, current_id: int | None, what: str
) -> None:
    if position_id is None:
        return
    position = next((p for p in kind.positions if p.id == position_id), None)
    if position is None:
        raise ProductDeviceReferenceInvalidError(f"The {what} is not a position of this kind.")
    if position.archived and position_id != current_id:
        raise ProductDeviceReferenceInvalidError(f"The {what} is archived and cannot be chosen.")


def initial_position_value(
    kind: ProductDeviceKind, position_id: int | None, value: float | None
) -> float | None:
    """The value stored with the initial position: kept only when the
    position takes one."""
    if position_id is None or value is None:
        return None
    position = next(p for p in kind.positions if p.id == position_id)
    if not position.takes_value:
        return None
    if not math.isfinite(value):
        raise ProductDeviceReferenceInvalidError("The initial position value must be a number.")
    return value


def clean_parameters(kind: ProductDeviceKind, raw: Mapping[str, Any]) -> dict[str, Any]:
    """The device's parameter values keyed by parameter id, each checked
    against its parameter's type. Empty values are dropped."""
    by_id = {str(p.id): p for p in kind.parameters}
    cleaned: dict[str, Any] = {}
    for key, value in raw.items():
        parameter = by_id.get(key)
        if parameter is None:
            raise ProductDeviceReferenceInvalidError(
                f"Parameter #{key} is not a parameter of this kind."
            )
        if value is None or value == "":
            continue
        checked = _parameter_value(key, parameter.value_type, value)
        if checked is not None:
            cleaned[key] = checked
    return cleaned


def _parameter_value(key: str, value_type: ProductDeviceParameterType, value: Any) -> Any:
    """The value checked against the parameter's type, a text trimmed, or
    None for a text that is only whitespace."""
    match value_type:
        case ProductDeviceParameterType.NUMBER:
            ok = isinstance(value, int | float) and not isinstance(value, bool)
            if not ok or not math.isfinite(value):
                raise ProductDeviceReferenceInvalidError(f"Parameter #{key} takes a number.")
        case ProductDeviceParameterType.BOOLEAN:
            if not isinstance(value, bool):
                raise ProductDeviceReferenceInvalidError(f"Parameter #{key} takes yes or no.")
        case ProductDeviceParameterType.TEXT:
            if not isinstance(value, str):
                raise ProductDeviceReferenceInvalidError(f"Parameter #{key} takes a text.")
            text = value.strip()
            if len(text) > TEXT_MAX_LENGTH:
                raise ProductDeviceReferenceInvalidError(f"Parameter #{key} is too long.")
            return text or None
    return value


def clean_position_labels(kind: ProductDeviceKind, raw: Mapping[str, str]) -> dict[str, str]:
    ids = {str(p.id) for p in kind.positions}
    cleaned: dict[str, str] = {}
    for key, label in raw.items():
        if key not in ids:
            raise ProductDeviceReferenceInvalidError(
                f"Position #{key} is not a position of this kind."
            )
        value = " ".join(label.split())
        if len(value) > POSITION_LABEL_MAX_LENGTH:
            raise ProductDeviceReferenceInvalidError("A position label is too long.")
        if value:
            cleaned[key] = value
    return cleaned


def clean_travel_times(kind: ProductDeviceKind, raw: Mapping[str, int]) -> dict[str, int]:
    """The time to reach each position, keyed by position id; a position
    left out has no estimate."""
    ids = {str(p.id) for p in kind.positions}
    for key, value in raw.items():
        if key not in ids:
            raise ProductDeviceReferenceInvalidError(
                f"Position #{key} is not a position of this kind."
            )
        if not 0 <= value <= TRAVEL_TIME_MAX_MS:
            raise ProductDeviceReferenceInvalidError(
                f"A travel time lies between 0 and {TRAVEL_TIME_MAX_MS} ms."
            )
    return dict(raw)


def check_marker(x: float | None, y: float | None) -> None:
    if (x is None) != (y is None):
        raise ProductDeviceReferenceInvalidError("A marker needs both coordinates.")
    for coordinate in (x, y):
        if coordinate is not None and not 0.0 <= coordinate <= 1.0:
            raise ProductDeviceReferenceInvalidError("Marker coordinates lie between 0 and 1.")


def clean_eplan_tag(tag: str | None) -> str | None:
    value = (tag or "").strip()
    if len(value) > EPLAN_TAG_MAX_LENGTH:
        raise ProductDeviceReferenceInvalidError("The EPLAN tag is too long.")
    return value or None


def check_kind_signal(
    kind: ProductDeviceKind, signal: ProductDeviceSignal, current_ids: set[int]
) -> None:
    """A signal that picks one of its kind's signals takes that signal's
    type and names no position, since the kind signal says what it is; an
    archived kind signal only when the component already picked it."""
    if signal.kind_signal_id is None:
        return
    picked = next((k for k in kind.signals if k.id == signal.kind_signal_id), None)
    if picked is None:
        raise ProductDeviceReferenceInvalidError("The signal is not a signal of this kind.")
    if picked.archived and signal.kind_signal_id not in current_ids:
        raise ProductDeviceReferenceInvalidError(
            "The kind's signal is archived and cannot be chosen."
        )
    if signal.confirms_position_id is not None or signal.drives_position_id is not None:
        raise ProductDeviceReferenceInvalidError(
            "A signal names either a position or a signal of its kind, not both."
        )
    if signal.signal_type != picked.signal_type:
        raise ProductDeviceReferenceInvalidError(
            f"The kind's signal is a {picked.signal_type.value.upper()} signal."
        )


def clean_signals(
    kind: ProductDeviceKind,
    signals: list[ProductDeviceSignal],
    current_position_ids: set[int],
    current_kind_signal_ids: set[int] | None = None,
) -> list[ProductDeviceSignal]:
    """The component's signals. Only an input signal may confirm a position
    and only an output may drive one, and it must be one of the kind's; an
    archived position only when the component already referred to it. A
    signal without a position may pick one of the kind's signals instead
    (`check_kind_signal`), and one that names neither needs a meaning. A bus
    signal is never a safety signal. The address, suffix and tag name are
    checked by `clean_signal_plc_fields`."""
    cleaned: list[ProductDeviceSignal] = []
    for signal in signals:
        meaning = " ".join(signal.meaning.split())
        named = (
            signal.confirms_position_id is not None
            or signal.drives_position_id is not None
            or signal.kind_signal_id is not None
        )
        if not meaning and not named:
            raise ProductDeviceReferenceInvalidError(
                "A signal without a position or a signal of its kind needs a meaning."
            )
        if len(meaning) > SIGNAL_MEANING_MAX_LENGTH:
            raise ProductDeviceReferenceInvalidError("A signal meaning is too long.")
        check_kind_signal(kind, signal, current_kind_signal_ids or set())
        for position_id, allowed, refusal, what in (
            (
                signal.confirms_position_id,
                INPUT_SIGNAL_TYPES,
                "Only an input signal can confirm a position.",
                "confirmed position",
            ),
            (
                signal.drives_position_id,
                OUTPUT_SIGNAL_TYPES,
                "Only an output signal can drive a position.",
                "driven position",
            ),
        ):
            if position_id is None:
                continue
            if signal.signal_type not in allowed:
                raise ProductDeviceReferenceInvalidError(refusal)
            check_position(
                kind,
                position_id,
                position_id if position_id in current_position_ids else None,
                what,
            )
        if signal.safety and signal.signal_type == ProductDeviceSignalType.BUS:
            raise ProductDeviceReferenceInvalidError("A bus signal cannot be a safety signal.")
        cleaned.append(
            ProductDeviceSignal(
                signal.signal_type,
                meaning,
                signal.confirms_position_id,
                signal.drives_position_id,
                signal.safety,
                *clean_signal_plc_fields(signal),
                signal.kind_signal_id,
            )
        )
    return cleaned


SIGNAL_ADDRESS_MAX_LENGTH = 30
SIGNAL_TAG_MAX_LENGTH = 200
_ADDRESS = re.compile(r"%?[A-Za-z]{1,4}\s?[0-9]+(\.[0-9]+)?")
_IDENTIFIER = re.compile(r"[A-Za-z0-9_]+")


def clean_address(address: str | None) -> str | None:
    """A PLC address as stored, such as I150.0, %Q24.1 or IW100; empty means none."""
    value = (address or "").strip() or None
    if value is not None and (
        len(value) > SIGNAL_ADDRESS_MAX_LENGTH or not _ADDRESS.fullmatch(value)
    ):
        raise ProductDeviceReferenceInvalidError(
            f"{value!r} is not a PLC address such as I150.0 or IW100."
        )
    return value


def clean_signal_plc_fields(
    signal: ProductDeviceSignal,
) -> tuple[str | None, str | None, str | None]:
    """The signal's address, tag suffix and tag name as stored. An address
    looks like I150.0, %Q24.1 or IW100; a suffix or tag name holds only
    letters, digits and underscores, since it goes into the tag unchanged."""
    result: list[str | None] = [clean_address(signal.address)]
    for value, what in ((signal.tag_suffix, "tag suffix"), (signal.tag_name, "tag name")):
        cleaned = (value or "").strip() or None
        if cleaned is not None and (
            len(cleaned) > SIGNAL_TAG_MAX_LENGTH or not _IDENTIFIER.fullmatch(cleaned)
        ):
            raise ProductDeviceReferenceInvalidError(
                f"A signal's {what} holds only letters, digits and underscores; got {cleaned!r}."
            )
        result.append(cleaned)
    return result[0], result[1], result[2]


def duplicate_eplan_tags(components: list[ProductDeviceComponent]) -> set[str]:
    """EPLAN tags that appear on more than one of the given components."""
    seen: set[str] = set()
    duplicates: set[str] = set()
    for component in components:
        if component.eplan_tag is None:
            continue
        if component.eplan_tag in seen:
            duplicates.add(component.eplan_tag)
        seen.add(component.eplan_tag)
    return duplicates


def check_document_device(
    device: ProductDevice | None, owner_product_id: int | None, current_id: int | None
) -> None:
    """A document (a calculation) may reference a device of the product it
    belongs to, directly or through its project. An archived device may only
    stay referenced, not be picked newly."""
    if device is None:
        raise ProductDeviceReferenceInvalidError("The device does not exist.")
    if owner_product_id is None or device.product_id != owner_product_id:
        raise ProductDeviceReferenceInvalidError(
            "Only a device of the document's own product can be referenced."
        )
    if device.archived and device.id != current_id:
        raise ProductDeviceReferenceInvalidError("The device is archived and cannot be chosen.")


def check_driver(
    device: ProductDevice,
    driver: ProductDevice | None,
    driver_id: int | None,
    product_id: int,
    has_followers: bool,
    current_driver_id: int | None,
) -> None:
    """A device may be driven by another live device of the same product.
    It cannot drive itself, a driven device drives nothing, and a device
    others follow cannot be driven itself. A driver archived since it was
    chosen may stay."""
    if driver_id is None:
        return
    if driver is None or driver.product_id != product_id:
        raise ProductDeviceReferenceInvalidError(
            f"Device #{driver_id} is not a device of this product."
        )
    if driver.id == device.id:
        raise ProductDeviceReferenceInvalidError("A device cannot drive itself.")
    if driver.driven_by_id is not None:
        raise ProductDeviceReferenceInvalidError(
            f"{driver.name_utf8} is driven by another device and drives nothing itself."
        )
    if has_followers:
        raise ProductDeviceReferenceInvalidError(
            f"{device.name_utf8} drives other devices and cannot be driven itself."
        )
    if driver.archived and driver_id != current_driver_id:
        raise ProductDeviceReferenceInvalidError(f"{driver.name_utf8} is archived.")


def clean_position_map(
    kind: ProductDeviceKind,
    driver_kind: ProductDeviceKind | None,
    position_map: Mapping[str, str],
) -> dict[str, str]:
    """The driver position to own position map of a driven device: only for
    a driver of another kind, from the driver kind's positions to this
    kind's live positions. A driver of the same kind needs none."""
    if driver_kind is None or driver_kind.id == kind.id:
        return {}
    driver_positions = {str(p.id) for p in driver_kind.positions}
    own_positions = {str(p.id) for p in kind.positions if not p.archived}
    cleaned: dict[str, str] = {}
    for driver_position, own_position in position_map.items():
        if not own_position:
            continue
        if driver_position not in driver_positions or str(own_position) not in own_positions:
            raise ProductDeviceReferenceInvalidError(
                "The position map names a position the kinds do not have."
            )
        cleaned[driver_position] = str(own_position)
    return cleaned


def check_driving_medium(kind: ProductDeviceKind, medium_id: int | None) -> None:
    """A device of a kind without driving medium has none; every other device
    needs one, since its letter goes into the name."""
    if kind.without_driving_medium and medium_id is not None:
        raise ProductDeviceReferenceInvalidError("A device of this kind has no driving medium.")
    if not kind.without_driving_medium and medium_id is None:
        raise ProductDeviceReferenceInvalidError("The device needs a driving medium.")
