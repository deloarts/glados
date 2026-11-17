"""
Who may see, change, release and delete a flow sequence, whether its
content holds together, and what a release freezes. No I/O.

Every logged-in user sees every sequence, like the product it belongs to.
Only the latest revision of a sequence can change, and only while it is a
draft; it is edited by its creator or a manager, and only a draft is ever
deleted. Release needs release:sequences and may be done by the author. A
new revision starts from the released latest revision.

The content refers to the product's devices, their kinds' positions and the
product's variants by id, and to its own steps by key. A draft may keep a
reference to something archived since it was chosen, so archiving a device
never makes a draft unsaveable; a release needs every reference live.

The checks every controlled document phrases the same way come from
controlled_document_rules.py; this class names the ones a sequence uses.
"""

import re
from collections.abc import Iterable
from collections.abc import Iterator
from dataclasses import dataclass
from dataclasses import field
from typing import Any

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.quality.domain.entities.sequence import Sequence
from src.modules.quality.domain.errors import SequenceAlreadyReleasedError
from src.modules.quality.domain.errors import SequenceInvalidError
from src.modules.quality.domain.errors import SequenceNotFoundError
from src.modules.quality.domain.errors import SequenceNotLatestRevisionError
from src.modules.quality.domain.errors import SequenceNotReleasedError
from src.modules.quality.domain.errors import SequenceOfAnotherUserError
from src.modules.quality.domain.errors import SequenceOwnerConflictError
from src.modules.quality.domain.errors import SequenceReleasedError
from src.modules.quality.domain.services import document_control
from src.modules.quality.domain.services.controlled_document_rules import DocumentAccess
from src.modules.quality.domain.value_objects.sequence_content import TARGET_END
from src.modules.quality.domain.value_objects.sequence_content import TARGET_NEXT
from src.modules.quality.domain.value_objects.sequence_content import SequenceActionKind
from src.modules.quality.domain.value_objects.sequence_content import SequenceConditionKind
from src.modules.quality.domain.value_objects.sequence_content import SequenceConditionTerm
from src.modules.quality.domain.value_objects.sequence_content import SequenceStep
from src.modules.quality.domain.value_objects.sequence_content import VariantValue
from src.modules.workspace.domain.entities.product_device import ProductDevice
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKind
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKindPosition
from src.modules.workspace.domain.entities.product_variant import ProductVariant

ACCESS = DocumentAccess(
    noun="sequence",
    write_permission=Permission.WRITE_SEQUENCES,
    release_permission=Permission.RELEASE_SEQUENCES,
    manage_permission=Permission.MANAGE_SEQUENCES,
    not_found_error=SequenceNotFoundError,
    owner_conflict_error=SequenceOwnerConflictError,
    not_latest_error=SequenceNotLatestRevisionError,
    already_released_error=SequenceAlreadyReleasedError,
    of_another_user_error=SequenceOfAnotherUserError,
)

NAME_MAX_LENGTH = 200
TEXT_MAX_LENGTH = 500
MAX_STEPS = 500
MAX_ACTIONS = 50
MAX_TRANSITIONS = 20
MAX_TERMS = 20
# A day; a longer step timeout is a typing error rather than a monitoring time.
MAX_DURATION_MS = 24 * 60 * 60 * 1000
KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


class SequenceRules:
    @staticmethod
    def can_view(actor: User, sequence: Sequence) -> bool:
        return ACCESS.can_view(actor, sequence)

    @staticmethod
    def assert_can_view(actor: User, sequence: Sequence) -> None:
        ACCESS.assert_can_view(actor, sequence)

    @staticmethod
    def assert_can_create(actor: User) -> None:
        ACCESS.assert_can_write(actor, "create")

    # The actor-only parts of the rules below, checked before the sequence
    # is loaded, so a caller without the permission cannot tell an existing
    # id from a missing one.

    @staticmethod
    def assert_can_write(actor: User, action: str) -> None:
        ACCESS.assert_can_write(actor, action)

    @staticmethod
    def assert_can_release_any(actor: User) -> None:
        ACCESS.assert_can_release_any(actor)

    @staticmethod
    def assert_can_manage(actor: User, action: str) -> None:
        ACCESS.assert_can_manage(actor, action)

    @staticmethod
    def assert_can_delete_any(actor: User) -> None:
        ACCESS.assert_can_delete_any(actor)

    @staticmethod
    def assert_can_update(actor: User, sequence: Sequence) -> None:
        ACCESS.assert_can_write(actor, "update")
        ACCESS.assert_can_view(actor, sequence)
        if sequence.read_only:
            raise SequenceReleasedError(
                f"Sequence #{sequence.id} (revision {sequence.revision}) is "
                f"{'released' if sequence.is_latest else 'superseded'} and cannot be "
                "changed; start a new revision instead."
            )
        ACCESS.assert_own_or_manager(actor, sequence, "update")

    @staticmethod
    def assert_can_delete(actor: User, sequence: Sequence) -> None:
        ACCESS.assert_can_view(actor, sequence)
        ACCESS.assert_latest(sequence, "deleted")
        document_control.assert_deletable(sequence, ACCESS.label(sequence))
        ACCESS.assert_can_write(actor, "delete")
        ACCESS.assert_own_or_manager(actor, sequence, "delete")

    @staticmethod
    def assert_can_release(actor: User, sequence: Sequence) -> None:
        ACCESS.assert_can_release_any(actor)
        ACCESS.assert_can_view(actor, sequence)
        ACCESS.assert_not_released(sequence)
        ACCESS.assert_latest(sequence, "released")
        if not sequence.steps:
            raise SequenceInvalidError(f"Sequence #{sequence.id} has no steps to release.")

    @staticmethod
    def assert_can_mark_invalid(actor: User, sequence: Sequence) -> None:
        ACCESS.assert_can_manage(actor, "mark invalid")
        ACCESS.assert_can_view(actor, sequence)
        document_control.assert_can_be_marked_invalid(sequence, ACCESS.label(sequence))

    @staticmethod
    def assert_can_revise(actor: User, sequence: Sequence) -> None:
        ACCESS.assert_can_write(actor, "revise")
        ACCESS.assert_can_view(actor, sequence)
        ACCESS.assert_latest(sequence, "revised")
        if not sequence.is_released:
            raise SequenceNotReleasedError(
                f"Sequence #{sequence.id} must be released before a new revision is "
                "started; a draft is changed in place."
            )


def clean_name(name: str) -> str:
    cleaned = " ".join(name.split())
    if not cleaned:
        raise SequenceInvalidError("A sequence needs a name.")
    if len(cleaned) > NAME_MAX_LENGTH:
        raise SequenceInvalidError(f"A sequence name is longer than {NAME_MAX_LENGTH} characters.")
    return cleaned


# ── Content ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SequenceReferences:
    """The ids a sequence's content refers to."""

    device_ids: frozenset[int] = frozenset()
    position_ids: frozenset[int] = frozenset()
    variant_ids: frozenset[int] = frozenset()


@dataclass(frozen=True)
class SequenceContext:
    """What a sequence's content may refer to: the product's devices
    (archived ones included), the kinds of those devices with all their
    positions, and the product's variants (archived ones included).
    `kept` names what the stored draft already refers to, which may stay
    even when archived since; empty for a release."""

    devices: dict[int, ProductDevice]
    kinds: dict[int, ProductDeviceKind]
    variants: dict[int, ProductVariant]
    kept: SequenceReferences = field(default_factory=SequenceReferences)


def _terms(steps: Iterable[SequenceStep]) -> Iterator[SequenceConditionTerm]:
    for step in steps:
        for action in step.actions:
            yield from action.condition
        for transition in step.transitions:
            yield from transition.condition


def _values(steps: list[SequenceStep]) -> Iterator[VariantValue]:
    for step in steps:
        if step.expected_duration_ms is not None:
            yield step.expected_duration_ms
        for action in step.actions:
            for value in (action.value, action.duration_ms):
                if value is not None:
                    yield value
    for term in _terms(steps):
        for value in (term.value, term.duration_ms):
            if value is not None:
                yield value


def references_of(steps: list[SequenceStep]) -> SequenceReferences:
    devices: set[int] = set()
    positions: set[int] = set()
    for step in steps:
        for action in step.actions:
            if action.device_id is not None:
                devices.add(action.device_id)
            if action.position_id is not None:
                positions.add(action.position_id)
    for term in _terms(steps):
        if term.device_id is not None:
            devices.add(term.device_id)
        if term.position_id is not None:
            positions.add(term.position_id)
    variants = {variant_id for value in _values(steps) for variant_id in value.per_variant}
    return SequenceReferences(frozenset(devices), frozenset(positions), frozenset(variants))


class _ContentCheck:
    def __init__(self, steps: list[SequenceStep], context: SequenceContext) -> None:
        self._steps = steps
        self._context = context
        self._step_keys = {step.key for step in steps}

    def run(self) -> None:
        if len(self._steps) > MAX_STEPS:
            raise SequenceInvalidError(f"A sequence has at most {MAX_STEPS} steps.")
        self._check_keys()
        for number, step in enumerate(self._steps, start=1):
            self._check_step(number, step, is_last=number == len(self._steps))
        for value in _values(self._steps):
            self._check_variants(value)

    def _check_keys(self) -> None:
        keys: list[str] = []
        for step in self._steps:
            keys.append(step.key)
            keys.extend(action.key for action in step.actions)
            keys.extend(transition.key for transition in step.transitions)
        for key in keys:
            if not KEY_PATTERN.match(key):
                raise SequenceInvalidError(f"{key!r} is not a valid key.")
        if len(set(keys)) != len(keys):
            raise SequenceInvalidError("A key of a step, action or transition appears twice.")

    def _check_step(self, number: int, step: SequenceStep, *, is_last: bool) -> None:
        where = f"Step {number}"
        self._check_text(step.description, where, required=False)
        if step.timeout_ms is not None and not 1 <= step.timeout_ms <= MAX_DURATION_MS:
            raise SequenceInvalidError(f"{where}: the timeout is out of range.")
        self._check_duration(step.expected_duration_ms, where)
        if len(step.actions) > MAX_ACTIONS:
            raise SequenceInvalidError(f"{where} has more than {MAX_ACTIONS} actions.")
        for action in step.actions:
            self._check_text(action.description, where, required=False)
            self._check_duration(action.duration_ms, where)
            if action.kind == SequenceActionKind.DEVICE:
                if action.device_id is None or action.position_id is None:
                    raise SequenceInvalidError(f"{where}: a device action needs a position.")
                position = self._position(action.device_id, action.position_id, where)
                self._check_not_driven(action.device_id, where)
                self._check_position_value(position, action.value, where)
                if action.text is not None:
                    raise SequenceInvalidError(f"{where}: a device action has no text.")
            else:
                self._check_text(action.text, where, required=True)
                if action.device_id is not None or action.position_id is not None:
                    raise SequenceInvalidError(f"{where}: a text action names no device.")
                if action.value is not None:
                    raise SequenceInvalidError(f"{where}: a text action has no value.")
            self._check_condition(action.condition, where)
        self._check_transitions(step, where, is_last=is_last)

    def _check_transitions(self, step: SequenceStep, where: str, *, is_last: bool) -> None:
        if not step.transitions:
            raise SequenceInvalidError(f"{where} needs a transition.")
        if len(step.transitions) > MAX_TRANSITIONS:
            raise SequenceInvalidError(f"{where} has more than {MAX_TRANSITIONS} transitions.")
        for transition in step.transitions:
            target = transition.target
            if target == TARGET_NEXT and is_last:
                raise SequenceInvalidError(f"{where} is the last step and has no next step.")
            if target not in (TARGET_NEXT, TARGET_END) and target not in self._step_keys:
                raise SequenceInvalidError(f"{where}: a transition leads to an unknown step.")
            if len(step.transitions) > 1 and not transition.condition:
                raise SequenceInvalidError(
                    f"{where} has alternative transitions, so each needs a condition."
                )
            self._check_condition(transition.condition, where)

    def _check_condition(self, condition: tuple[SequenceConditionTerm, ...], where: str) -> None:
        if len(condition) > MAX_TERMS:
            raise SequenceInvalidError(f"{where}: a condition has more than {MAX_TERMS} terms.")
        for term in condition:
            self._check_term(term, where)

    def _check_term(self, term: SequenceConditionTerm, where: str) -> None:
        self._check_term_fields(term, where)
        match term.kind:
            case SequenceConditionKind.DEVICE_POSITION:
                self._check_position_term(term, where)
            case SequenceConditionKind.DEVICE_VALUE:
                self._check_value_term(term, where)
            case SequenceConditionKind.STEP_COMPLETE:
                if term.step_key not in self._step_keys:
                    raise SequenceInvalidError(f"{where}: a step condition names an unknown step.")
            case SequenceConditionKind.TIME:
                self._check_time_term(term, where)
            case SequenceConditionKind.EXTERNAL:
                self._check_text(term.text, where, required=True)

    @staticmethod
    def _check_term_fields(term: SequenceConditionTerm, where: str) -> None:
        """Rejects a field that belongs to another kind of condition."""
        kind = term.kind
        uses_device = kind in (
            SequenceConditionKind.DEVICE_POSITION,
            SequenceConditionKind.DEVICE_VALUE,
        )
        if not uses_device and (term.device_id is not None or term.position_id is not None):
            raise SequenceInvalidError(f"{where}: the {kind.value!r} condition names no device.")
        if kind != SequenceConditionKind.DEVICE_VALUE and (
            term.comparator is not None or term.value is not None
        ):
            raise SequenceInvalidError(f"{where}: only a device value condition compares.")
        if kind != SequenceConditionKind.STEP_COMPLETE and term.step_key is not None:
            raise SequenceInvalidError(f"{where}: only a step condition names a step.")
        if kind != SequenceConditionKind.TIME and term.duration_ms is not None:
            raise SequenceInvalidError(f"{where}: only a time condition has a duration.")
        if kind != SequenceConditionKind.EXTERNAL and term.text is not None:
            raise SequenceInvalidError(f"{where}: only an external condition has a text.")

    def _check_position_term(self, term: SequenceConditionTerm, where: str) -> None:
        if term.device_id is None or term.position_id is None:
            raise SequenceInvalidError(f"{where}: a position condition needs a position.")
        self._position(term.device_id, term.position_id, where)

    def _check_value_term(self, term: SequenceConditionTerm, where: str) -> None:
        if term.device_id is None or term.comparator is None:
            raise SequenceInvalidError(
                f"{where}: a value condition needs a device and a comparison."
            )
        if term.position_id is None:
            self._device(term.device_id, where)
        else:
            self._position(term.device_id, term.position_id, where)
        self._check_complete(term.value, where, "a value condition")

    def _check_time_term(self, term: SequenceConditionTerm, where: str) -> None:
        self._check_complete(term.duration_ms, where, "a time condition")
        self._check_duration(term.duration_ms, where)

    @staticmethod
    def _check_duration(value: VariantValue | None, where: str) -> None:
        """A duration may be left open for some variants, which then have no
        estimate, but none lies outside a day."""
        if value is None:
            return
        durations = [value.common, *value.per_variant.values()]
        if any(d is not None and not 0 <= d <= MAX_DURATION_MS for d in durations):
            raise SequenceInvalidError(f"{where}: a duration is out of range.")

    def _device(self, device_id: int, where: str) -> ProductDevice:
        device = self._context.devices.get(device_id)
        if device is None:
            raise SequenceInvalidError(f"{where}: device #{device_id} is not one of the product's.")
        if device.archived and device_id not in self._context.kept.device_ids:
            raise SequenceInvalidError(f"{where}: device #{device_id} is archived.")
        return device

    def _check_not_driven(self, device_id: int, where: str) -> None:
        """A driven device moves with its driver, so a step moves the driver."""
        device = self._context.devices[device_id]
        if device.driven_by_id is None:
            return
        driver = self._context.devices.get(device.driven_by_id)
        name = driver.name_utf8 if driver else f"device #{device.driven_by_id}"
        raise SequenceInvalidError(
            f"{where}: {device.name_utf8} moves with {name}; move {name} instead."
        )

    def _position(self, device_id: int, position_id: int, where: str) -> ProductDeviceKindPosition:
        device = self._device(device_id, where)
        kind = self._context.kinds.get(device.kind_id)
        position = next((p for p in kind.positions if p.id == position_id), None) if kind else None
        if position is None:
            raise SequenceInvalidError(
                f"{where}: position #{position_id} is not a position of device #{device_id}."
            )
        if position.archived and position_id not in self._context.kept.position_ids:
            raise SequenceInvalidError(f"{where}: position #{position_id} is archived.")
        return position

    def _check_position_value(
        self, position: ProductDeviceKindPosition, value: VariantValue | None, where: str
    ) -> None:
        if not position.takes_value:
            if value is not None:
                raise SequenceInvalidError(f"{where}: the position takes no value.")
            return
        self._check_complete(value, where, "the position")

    def _check_complete(self, value: VariantValue | None, where: str, what: str) -> None:
        """A value applies to every variant: a common one, or one of its own
        for each live variant."""
        if value is None:
            raise SequenceInvalidError(f"{where}: {what} needs a value.")
        if value.common is not None:
            return
        live = {v.id for v in self._context.variants.values() if not v.archived}
        if not live or live - set(value.per_variant):
            raise SequenceInvalidError(
                f"{where}: {what} needs a common value or one for every variant."
            )

    def _check_variants(self, value: VariantValue) -> None:
        for variant_id in value.per_variant:
            variant = self._context.variants.get(variant_id)
            if variant is None:
                raise SequenceInvalidError(
                    f"Variant #{variant_id} is not one of the product's variants."
                )
            if variant.archived and variant_id not in self._context.kept.variant_ids:
                raise SequenceInvalidError(f"Variant #{variant_id} ({variant.name!r}) is archived.")

    @staticmethod
    def _check_text(text: str | None, where: str, *, required: bool) -> None:
        if text is None or not text.strip():
            if required:
                raise SequenceInvalidError(f"{where}: a text is missing.")
            return
        if len(text) > TEXT_MAX_LENGTH:
            raise SequenceInvalidError(f"{where}: a text is longer than {TEXT_MAX_LENGTH}.")


def check_content(steps: list[SequenceStep], context: SequenceContext) -> None:
    """Raises SequenceInvalidError for the first rule the steps break."""
    _ContentCheck(steps, context).run()


# ── Release ───────────────────────────────────────────────────────────


def freeze_names(product_number: str | None, context: SequenceContext) -> dict[str, Any]:
    """The names a released revision shows: every live device with its kind,
    positions, travel times and initial position (the start state), every
    device the content refers to besides, and the product's variants. Ids
    are JSON keys, so they are strings."""
    devices: dict[str, Any] = {}
    for device in context.devices.values():
        if device.archived and device.id not in context.kept.device_ids:
            continue
        kind = context.kinds.get(device.kind_id)
        devices[str(device.id)] = {
            "name": device.name_utf8,
            "name_ascii": device.name_ascii,
            "kind": kind.label.as_dict() if kind else {},
            "initial_position_id": device.initial_position_id,
            "initial_position_value": device.initial_position_value,
            "driven_by_id": device.driven_by_id,
            "driven_position_map": dict(device.driven_position_map),
            "positions": {
                str(position.id): {
                    "label": position.label.as_dict(),
                    "device_label": device.position_labels.get(str(position.id)),
                    "unit": position.unit,
                    "takes_value": position.takes_value,
                    "travel_time_ms": device.travel_times_ms.get(str(position.id)),
                }
                for position in (kind.positions if kind else [])
            },
        }
    return {
        "product_number": product_number,
        "devices": devices,
        "variants": {
            str(variant.id): variant.name
            for variant in sorted(context.variants.values(), key=lambda v: v.sort_order)
            if not variant.archived or variant.id in context.kept.variant_ids
        },
    }
