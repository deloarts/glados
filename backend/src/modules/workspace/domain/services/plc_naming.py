"""
Builds the PLC tags of a machine from its devices for one PLC environment.

A signal's tag is the environment's prefix for its signal type (the safety
prefix for a safety signal), the device's name and a suffix: the tag
suffix the signal brings, or else the PLC name of its position (the state
name for an input that confirms it, the command name for an output that
drives to it), or else the PLC name of the kind signal it picks, or else
its meaning. A signal with a tag name of its own
uses that instead. The device name is built from the UTF-8 name, without
the product number, by the environment's character conversion; whatever
character is still not a letter, digit or underscore after it becomes an
underscore, runs of them collapse into one and none are left at either
end, so a tag is always a valid identifier.

A tag longer than the environment allows, or one that another signal of
the machine also gets, is flagged rather than refused, so the engineer
sees it while there is still time to rename. No I/O.
"""

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from dataclasses import replace

from src.modules.workspace.domain.entities.plc_environment import PlcEnvironment
from src.modules.workspace.domain.entities.plc_manual_tag import PlcManualTag
from src.modules.workspace.domain.entities.product_device import ProductDevice
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKind
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKindPosition
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKindSignal
from src.modules.workspace.domain.errors import PlcTagInvalidError
from src.modules.workspace.domain.value_objects.plc_environment_settings import CharConversion
from src.modules.workspace.domain.value_objects.product_device_signal import INPUT_SIGNAL_TYPES
from src.modules.workspace.domain.value_objects.product_device_signal import OUTPUT_SIGNAL_TYPES
from src.modules.workspace.domain.value_objects.product_device_signal import ProductDeviceSignal

_NOT_IDENTIFIER = re.compile(r"[^A-Za-z0-9]+")


@dataclass(frozen=True)
class PlcTag:
    # Zero for a manual tag, which belongs to no device.
    device_id: int
    component_id: int
    # The signal's place among its component's signals.
    signal_index: int
    name: str
    tag_table: str
    address: str | None
    # The device's UTF-8 name and what the signal means.
    comment: str
    signal_type: str
    safety: bool
    # The signal brings its own tag name or suffix instead of the built one.
    overridden: bool
    too_long: bool
    duplicate: bool
    # The id of a manual tag; None for a tag built from a device signal.
    manual_id: int | None = None


def convert(text: str, conversions: list[CharConversion]) -> str:
    """`text` through the conversion table, longest source first, then
    cleaned up to an identifier."""
    ordered = sorted(conversions, key=lambda c: len(c.source), reverse=True)
    out: list[str] = []
    i = 0
    while i < len(text):
        for conversion in ordered:
            if text.startswith(conversion.source, i):
                out.append(conversion.target)
                i += len(conversion.source)
                break
        else:
            out.append(text[i])
            i += 1
    return identifier("".join(out))


def identifier(text: str) -> str:
    """Accents dropped, every run of other characters but letters and digits
    turned into one underscore, none at either end."""
    decomposed = unicodedata.normalize("NFKD", text)
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return _NOT_IDENTIFIER.sub("_", plain).strip("_")


def prefix_key(signal: ProductDeviceSignal) -> str:
    key = signal.signal_type.value
    return f"safety_{key}" if signal.safety and key != "bus" else key


def _position(
    kind: ProductDeviceKind | None, position_id: int | None
) -> ProductDeviceKindPosition | None:
    if kind is None or position_id is None:
        return None
    return next((p for p in kind.positions if p.id == position_id), None)


def _kind_signal(
    kind: ProductDeviceKind | None, kind_signal_id: int | None
) -> ProductDeviceKindSignal | None:
    if kind is None or kind_signal_id is None:
        return None
    return next((s for s in kind.signals if s.id == kind_signal_id), None)


def signal_meaning(
    signal: ProductDeviceSignal, kind: ProductDeviceKind | None, language: str
) -> str:
    """What the signal means in `language`: its own meaning, or else the
    label of the kind signal it picks or of its position."""
    if signal.meaning:
        return signal.meaning
    picked = _kind_signal(kind, signal.kind_signal_id)
    if picked is not None:
        return picked.label.resolve(language, language)
    position = _position(kind, signal.confirms_position_id or signal.drives_position_id)
    return position.label.resolve(language, language) if position is not None else ""


def signal_suffix(signal: ProductDeviceSignal, kind: ProductDeviceKind | None) -> str:
    """What ends the tag: the signal's own suffix, the position's PLC name
    for its direction, the kind signal's PLC name, or else its meaning."""
    if signal.tag_suffix:
        return signal.tag_suffix
    if signal.signal_type in INPUT_SIGNAL_TYPES:
        position = _position(kind, signal.confirms_position_id)
        if position is not None and position.plc_state_name:
            return position.plc_state_name
    if signal.signal_type in OUTPUT_SIGNAL_TYPES:
        position = _position(kind, signal.drives_position_id)
        if position is not None and position.plc_command_name:
            return position.plc_command_name
    picked = _kind_signal(kind, signal.kind_signal_id)
    if picked is not None:
        return picked.plc_name
    return signal.meaning


def signal_tag_name(
    device_name: str,
    signal: ProductDeviceSignal,
    kind: ProductDeviceKind | None,
    environment: PlcEnvironment,
) -> str:
    if signal.tag_name:
        return signal.tag_name
    prefix = environment.prefixes.get(prefix_key(signal), "")
    base = convert(device_name, environment.conversions)
    suffix = convert(signal_suffix(signal, kind), environment.conversions)
    body = "_".join(part for part in (base, suffix) if part)
    return f"{prefix}{body}"


def longest_tag_length(
    device_name: str, kind: ProductDeviceKind | None, environment: PlcEnvironment
) -> int:
    """The length of the longest tag a device of this name and kind can get
    from its positions' PLC names, for the warning while the name is typed:
    the longest prefix, the converted name and the longest position name."""
    base = convert(device_name, environment.conversions)
    names = [
        convert(name, environment.conversions)
        for position in (kind.positions if kind else [])
        if not position.archived
        for name in (position.plc_state_name, position.plc_command_name)
        if name
    ]
    suffix = max((len(n) for n in names), default=0)
    prefix = max((len(p) for p in environment.prefixes.values()), default=0)
    return prefix + len(base) + (suffix + 1 if suffix else 0)


def build_tags(
    devices: list[ProductDevice],
    kinds: dict[int, ProductDeviceKind],
    environment: PlcEnvironment,
    manual_tags: list[PlcManualTag] | None = None,
    language: str = "",
) -> list[PlcTag]:
    """Every tag of the live devices in their order, each signal once, then
    the manual tags, which keep their names as written. A signal without a
    meaning of its own is described in `language` by its kind signal or
    position."""
    drafts: list[PlcTag] = []
    for device in devices:
        if device.archived:
            continue
        kind = kinds.get(device.kind_id)
        for component in device.components:
            for index, signal in enumerate(component.signals):
                name = signal_tag_name(device.name_utf8, signal, kind, environment)
                drafts.append(
                    PlcTag(
                        device_id=device.id,
                        component_id=component.id,
                        signal_index=index,
                        name=name,
                        tag_table=(environment.safety_tag_table or environment.tag_table)
                        if signal.safety
                        else environment.tag_table,
                        address=signal.address,
                        comment=f"{device.name_utf8}: {signal_meaning(signal, kind, language)}",
                        signal_type=signal.signal_type.value,
                        safety=signal.safety,
                        overridden=bool(signal.tag_name or signal.tag_suffix),
                        too_long=len(name) > environment.max_tag_length,
                        duplicate=False,
                    )
                )
    drafts.extend(
        PlcTag(
            device_id=0,
            component_id=0,
            signal_index=0,
            name=manual.name,
            tag_table=(environment.safety_tag_table or environment.tag_table)
            if manual.safety
            else environment.tag_table,
            address=manual.address,
            comment=manual.comment,
            signal_type=manual.signal_type.value,
            safety=manual.safety,
            overridden=True,
            too_long=len(manual.name) > environment.max_tag_length,
            duplicate=False,
            manual_id=manual.id,
        )
        for manual in manual_tags or []
    )
    counts = Counter(tag.name.lower() for tag in drafts)
    return [replace(tag, duplicate=counts[tag.name.lower()] > 1) for tag in drafts]


MANUAL_NAME_MAX_LENGTH = 200
MANUAL_COMMENT_MAX_LENGTH = 500
_TAG_NAME = re.compile(r"[A-Za-z0-9_]+")


def clean_tag_name(name: str) -> str:
    """A tag name typed by hand: letters, digits and underscores only."""
    value = name.strip()
    if not value or len(value) > MANUAL_NAME_MAX_LENGTH or not _TAG_NAME.fullmatch(value):
        raise PlcTagInvalidError(
            f"A tag name holds only letters, digits and underscores, at most "
            f"{MANUAL_NAME_MAX_LENGTH} of them; got {value!r}."
        )
    return value
