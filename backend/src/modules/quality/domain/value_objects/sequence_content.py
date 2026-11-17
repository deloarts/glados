"""
The content of a flow sequence, shaped after GRAFCET (IEC 60848) and the
sequential function charts of IEC 61131-3.

A sequence is an ordered list of steps; their numbers come from the order.
A step holds actions that start together when the step becomes active, and
leaves through one or more transitions, each with a target step (or the
end) and an optional condition. One transition to the next step is the
plain case; a transition back to step 1 makes a cycle, and several
transitions with exclusive conditions make an alternative branch.

Steps, actions and transitions carry a stable key, so references between
them survive reordering. Values that depend on the product's variant hold a
common value and values per variant.

The estimated times are rough planning data, not a part of the control: an
action may override the travel time of its device, and a step may say how
long it is expected to take, which covers waiting for something outside
the device list.
"""

from dataclasses import dataclass
from dataclasses import field
from enum import unique
from typing import Any

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum

# A transition target that is not a step key.
TARGET_NEXT = "next"
TARGET_END = "end"


@unique
class SequenceActionKind(StrValueEnum):
    # Moves a device of the product to a position of its kind.
    DEVICE = "device"
    # Anything outside the device list, described in words.
    TEXT = "text"


@unique
class SequenceActionQualifier(StrValueEnum):
    """How long an action applies, after GRAFCET and IEC 61131-3."""

    # Stays in effect after the step ends (S), the normal case for moving a
    # cylinder out.
    STORED = "stored"
    # Only while the step is active (N), such as vacuum on.
    CONTINUOUS = "continuous"
    # Once when the step starts (P), such as resetting a counter.
    PULSE = "pulse"


@unique
class SequenceConditionKind(StrValueEnum):
    # The device is in the position, confirmed by its signals.
    DEVICE_POSITION = "device_position"
    # The device's value at a position compared with a threshold.
    DEVICE_VALUE = "device_value"
    # Another step is complete.
    STEP_COMPLETE = "step_complete"
    # At least this time has passed since the step became active (t/Xn).
    TIME = "time"
    # A named signal outside the device list, such as "robot ready".
    EXTERNAL = "external"


@unique
class SequenceComparator(StrValueEnum):
    GE = "ge"
    LE = "le"


@dataclass(frozen=True)
class VariantValue:
    """A number that may differ per product variant. A variant without its
    own value uses the common one."""

    common: float | None = None
    per_variant: dict[int, float] = field(default_factory=dict)

    def for_variant(self, variant_id: int) -> float | None:
        return self.per_variant.get(variant_id, self.common)


@dataclass(frozen=True)
class SequenceConditionTerm:
    kind: SequenceConditionKind
    device_id: int | None = None
    position_id: int | None = None
    comparator: SequenceComparator | None = None
    value: VariantValue | None = None
    step_key: str | None = None
    # TIME: milliseconds, possibly per variant.
    duration_ms: VariantValue | None = None
    text: str | None = None


@dataclass(frozen=True)
class SequenceAction:
    key: str
    kind: SequenceActionKind
    qualifier: SequenceActionQualifier = SequenceActionQualifier.STORED
    device_id: int | None = None
    position_id: int | None = None
    value: VariantValue | None = None
    text: str | None = None
    description: str | None = None
    # All terms must hold before the action starts.
    condition: tuple[SequenceConditionTerm, ...] = ()
    # The estimated time in ms, possibly per variant; None uses the device's
    # travel time to the target position.
    duration_ms: VariantValue | None = None


@dataclass(frozen=True)
class SequenceTransition:
    key: str
    # A step key, TARGET_NEXT or TARGET_END.
    target: str = TARGET_NEXT
    condition: tuple[SequenceConditionTerm, ...] = ()


@dataclass(frozen=True)
class SequenceStep:
    key: str
    actions: tuple[SequenceAction, ...] = ()
    transitions: tuple[SequenceTransition, ...] = ()
    description: str | None = None
    # A fault when the step is not complete in this time; None for none.
    timeout_ms: int | None = None
    # How long the step is expected to take in ms, possibly per variant.
    expected_duration_ms: VariantValue | None = None


# ── Stored form ───────────────────────────────────────────────────────
# The steps are stored and sent as plain JSON data. Variant ids are JSON
# object keys there, so they travel as strings.


def _value_from_data(raw: Any) -> VariantValue | None:
    if raw is None:
        return None
    per_variant = {int(k): float(v) for k, v in (raw.get("per_variant") or {}).items()}
    common = raw.get("common")
    return VariantValue(common=None if common is None else float(common), per_variant=per_variant)


def _value_to_data(value: VariantValue | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "common": value.common,
        "per_variant": {str(k): v for k, v in sorted(value.per_variant.items())},
    }


def _term_from_data(raw: dict[str, Any]) -> SequenceConditionTerm:
    comparator = raw.get("comparator")
    return SequenceConditionTerm(
        kind=SequenceConditionKind(raw["kind"]),
        device_id=raw.get("device_id"),
        position_id=raw.get("position_id"),
        comparator=None if comparator is None else SequenceComparator(comparator),
        value=_value_from_data(raw.get("value")),
        step_key=raw.get("step_key"),
        duration_ms=_value_from_data(raw.get("duration_ms")),
        text=raw.get("text"),
    )


def _term_to_data(term: SequenceConditionTerm) -> dict[str, Any]:
    return {
        "kind": term.kind.value,
        "device_id": term.device_id,
        "position_id": term.position_id,
        "comparator": None if term.comparator is None else term.comparator.value,
        "value": _value_to_data(term.value),
        "step_key": term.step_key,
        "duration_ms": _value_to_data(term.duration_ms),
        "text": term.text,
    }


def _condition_from_data(raw: Any) -> tuple[SequenceConditionTerm, ...]:
    return tuple(_term_from_data(term) for term in raw or ())


def steps_from_data(raw: list[dict[str, Any]]) -> list[SequenceStep]:
    """Reads the steps from their stored or sent form."""
    return [
        SequenceStep(
            key=step["key"],
            description=step.get("description"),
            timeout_ms=step.get("timeout_ms"),
            expected_duration_ms=_value_from_data(step.get("expected_duration_ms")),
            actions=tuple(
                SequenceAction(
                    key=action["key"],
                    kind=SequenceActionKind(action["kind"]),
                    qualifier=SequenceActionQualifier(
                        action.get("qualifier") or SequenceActionQualifier.STORED.value
                    ),
                    device_id=action.get("device_id"),
                    position_id=action.get("position_id"),
                    value=_value_from_data(action.get("value")),
                    text=action.get("text"),
                    description=action.get("description"),
                    condition=_condition_from_data(action.get("condition")),
                    duration_ms=_value_from_data(action.get("duration_ms")),
                )
                for action in step.get("actions") or ()
            ),
            transitions=tuple(
                SequenceTransition(
                    key=transition["key"],
                    target=transition.get("target") or TARGET_NEXT,
                    condition=_condition_from_data(transition.get("condition")),
                )
                for transition in step.get("transitions") or ()
            ),
        )
        for step in raw
    ]


def steps_to_data(steps: list[SequenceStep]) -> list[dict[str, Any]]:
    """The stored and sent form of the steps."""
    return [
        {
            "key": step.key,
            "description": step.description,
            "timeout_ms": step.timeout_ms,
            "expected_duration_ms": _value_to_data(step.expected_duration_ms),
            "actions": [
                {
                    "key": action.key,
                    "kind": action.kind.value,
                    "qualifier": action.qualifier.value,
                    "device_id": action.device_id,
                    "position_id": action.position_id,
                    "value": _value_to_data(action.value),
                    "text": action.text,
                    "description": action.description,
                    "condition": [_term_to_data(term) for term in action.condition],
                    "duration_ms": _value_to_data(action.duration_ms),
                }
                for action in step.actions
            ],
            "transitions": [
                {
                    "key": transition.key,
                    "target": transition.target,
                    "condition": [_term_to_data(term) for term in transition.condition],
                }
                for transition in step.transitions
            ],
        }
        for step in steps
    ]
