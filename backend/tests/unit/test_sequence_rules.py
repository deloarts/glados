from dataclasses import replace
from datetime import UTC
from datetime import datetime

import pytest

from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.quality.domain.errors import SequenceInvalidError
from src.modules.quality.domain.services.sequence_rules import SequenceContext
from src.modules.quality.domain.services.sequence_rules import check_content
from src.modules.quality.domain.services.sequence_rules import clean_name
from src.modules.quality.domain.services.sequence_rules import freeze_names
from src.modules.quality.domain.services.sequence_rules import references_of
from src.modules.quality.domain.value_objects.sequence_content import TARGET_END
from src.modules.quality.domain.value_objects.sequence_content import SequenceAction
from src.modules.quality.domain.value_objects.sequence_content import SequenceActionKind
from src.modules.quality.domain.value_objects.sequence_content import SequenceComparator
from src.modules.quality.domain.value_objects.sequence_content import SequenceConditionKind
from src.modules.quality.domain.value_objects.sequence_content import SequenceConditionTerm
from src.modules.quality.domain.value_objects.sequence_content import SequenceStep
from src.modules.quality.domain.value_objects.sequence_content import SequenceTransition
from src.modules.quality.domain.value_objects.sequence_content import VariantValue
from src.modules.quality.domain.value_objects.sequence_content import steps_from_data
from src.modules.quality.domain.value_objects.sequence_content import steps_to_data
from src.modules.workspace.domain.entities.product_device import ProductDevice
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKind
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKindPosition
from src.modules.workspace.domain.entities.product_variant import ProductVariant

NOW = datetime(2026, 10, 23, tzinfo=UTC)


def _position(
    id: int, takes_value: bool = False, archived: bool = False
) -> ProductDeviceKindPosition:
    return ProductDeviceKindPosition(
        id=id,
        kind_id=1,
        label=LocalizedText.of({"enGB": f"P{id}"}),
        takes_value=takes_value,
        unit="mm" if takes_value else None,
        sort_order=id,
        archived=archived,
    )


def _context(**overrides: object) -> SequenceContext:
    kind = ProductDeviceKind(
        id=1,
        created=NOW,
        changed=NOW,
        changes=[],
        label=LocalizedText.of({"enGB": "Linear drive"}),
        sort_order=0,
        creator_id=1,
        positions=[_position(10), _position(11, takes_value=True), _position(12, archived=True)],
    )
    device = ProductDevice(
        id=5,
        created=NOW,
        changed=NOW,
        changes=[],
        product_id=1,
        location="B01",
        name="Lift",
        driving_medium_id=1,
        number=1,
        name_utf8="B01 Lift P1",
        name_ascii="B01_Lift_P1",
        name_ascii_key="b01_lift_p1",
        group_key="b01|lift|p",
        kind_id=1,
        creator_id=1,
        initial_position_id=10,
    )
    variants = {
        1: ProductVariant(id=1, product_id=1, name="Clamp 60", sort_order=0),
        2: ProductVariant(id=2, product_id=1, name="Clamp 80", sort_order=1),
    }
    context = SequenceContext(devices={5: device}, kinds={1: kind}, variants=variants)
    return replace(context, **overrides)  # type: ignore[arg-type]


def _move(key: str, position_id: int, value: VariantValue | None = None) -> SequenceAction:
    return SequenceAction(
        key=key, kind=SequenceActionKind.DEVICE, device_id=5, position_id=position_id, value=value
    )


def _step(key: str, *actions: SequenceAction, target: str = "next") -> SequenceStep:
    return SequenceStep(
        key=key, actions=actions, transitions=(SequenceTransition(key=f"{key}t", target=target),)
    )


def test_check_content_accepts_a_cycle_with_values_per_variant() -> None:
    steps = [
        _step("s1", _move("a1", 11, VariantValue(per_variant={1: 60, 2: 80}))),
        _step("s2", _move("a2", 10), target="s1"),
    ]
    check_content(steps, _context())


@pytest.mark.parametrize(
    "steps",
    [
        # The last step has no next step.
        [_step("s1", _move("a1", 10))],
        # A value for only one of two variants and no common value.
        [_step("s1", _move("a1", 11, VariantValue(per_variant={1: 60})), target=TARGET_END)],
        # A position that takes no value gets one.
        [_step("s1", _move("a1", 10, VariantValue(common=1)), target=TARGET_END)],
        # An archived position.
        [_step("s1", _move("a1", 12), target=TARGET_END)],
        # A step condition names an unknown step.
        [
            SequenceStep(
                key="s1",
                transitions=(
                    SequenceTransition(
                        key="t1",
                        target=TARGET_END,
                        condition=(
                            SequenceConditionTerm(
                                kind=SequenceConditionKind.STEP_COMPLETE, step_key="s9"
                            ),
                        ),
                    ),
                ),
            )
        ],
    ],
)
def test_check_content_rejects(steps: list[SequenceStep]) -> None:
    with pytest.raises(SequenceInvalidError):
        check_content(steps, _context())


def test_check_content_lets_a_draft_keep_an_archived_position() -> None:
    steps = [_step("s1", _move("a1", 12), target=TARGET_END)]
    check_content(steps, _context(kept=references_of(steps)))


def test_steps_survive_their_stored_form() -> None:
    steps = [
        _step("s1", _move("a1", 11, VariantValue(common=5, per_variant={2: 80}))),
        _step("s2", target=TARGET_END),
    ]
    assert steps_from_data(steps_to_data(steps)) == steps


def test_freeze_names_keeps_the_start_state_and_variants() -> None:
    frozen = freeze_names("M26001", _context())
    device = frozen["devices"]["5"]
    assert device["name"] == "B01 Lift P1"
    assert device["initial_position_id"] == 10
    assert device["positions"]["11"]["unit"] == "mm"
    assert device["positions"]["11"]["takes_value"] is True
    assert frozen["variants"] == {"1": "Clamp 60", "2": "Clamp 80"}


def test_clean_name_collapses_spaces_and_needs_text() -> None:
    assert clean_name("  Automatic   cycle ") == "Automatic cycle"
    with pytest.raises(SequenceInvalidError):
        clean_name("   ")


def _with_term(term: SequenceConditionTerm) -> list[SequenceStep]:
    transition = SequenceTransition(key="t1", target=TARGET_END, condition=(term,))
    return [SequenceStep(key="s1", transitions=(transition,))]


_KIND = SequenceConditionKind


@pytest.mark.parametrize(
    "term",
    [
        SequenceConditionTerm(kind=_KIND.DEVICE_POSITION, device_id=5, position_id=10),
        SequenceConditionTerm(
            kind=_KIND.DEVICE_VALUE,
            device_id=5,
            comparator=SequenceComparator.GE,
            value=VariantValue(common=1),
        ),
        SequenceConditionTerm(
            kind=_KIND.DEVICE_VALUE,
            device_id=5,
            position_id=11,
            comparator=SequenceComparator.LE,
            value=VariantValue(per_variant={1: 1, 2: 2}),
        ),
        SequenceConditionTerm(kind=_KIND.STEP_COMPLETE, step_key="s1"),
        SequenceConditionTerm(kind=_KIND.TIME, duration_ms=VariantValue(common=0)),
        SequenceConditionTerm(
            kind=_KIND.TIME,
            duration_ms=VariantValue(common=None, per_variant={1: 5, 2: 86_400_000}),
        ),
        SequenceConditionTerm(kind=_KIND.EXTERNAL, text="Robot ready"),
    ],
)
def test_check_content_accepts_each_condition_kind(term: SequenceConditionTerm) -> None:
    check_content(_with_term(term), _context())


@pytest.mark.parametrize(
    ("term", "message"),
    [
        (
            SequenceConditionTerm(kind=_KIND.TIME, device_id=5),
            "the 'time' condition names no device",
        ),
        (
            SequenceConditionTerm(kind=_KIND.EXTERNAL, position_id=10, text="x"),
            "the 'external' condition names no device",
        ),
        (
            SequenceConditionTerm(kind=_KIND.DEVICE_POSITION, comparator=SequenceComparator.GE),
            "only a device value condition compares",
        ),
        (
            SequenceConditionTerm(kind=_KIND.STEP_COMPLETE, value=VariantValue(common=1)),
            "only a device value condition compares",
        ),
        (
            SequenceConditionTerm(kind=_KIND.TIME, step_key="s1"),
            "only a step condition names a step",
        ),
        (
            SequenceConditionTerm(kind=_KIND.EXTERNAL, duration_ms=VariantValue(common=1)),
            "only a time condition has a duration",
        ),
        (
            SequenceConditionTerm(kind=_KIND.STEP_COMPLETE, step_key="s1", text="x"),
            "only an external condition has a text",
        ),
        (
            SequenceConditionTerm(kind=_KIND.DEVICE_POSITION, device_id=5),
            "a position condition needs a position",
        ),
        (
            SequenceConditionTerm(kind=_KIND.DEVICE_POSITION, device_id=9, position_id=10),
            "device #9 is not one of the product's",
        ),
        (
            SequenceConditionTerm(kind=_KIND.DEVICE_POSITION, device_id=5, position_id=99),
            "position #99 is not a position of device #5",
        ),
        (
            SequenceConditionTerm(
                kind=_KIND.DEVICE_VALUE, device_id=5, value=VariantValue(common=1)
            ),
            "a value condition needs a device and a comparison",
        ),
        (
            SequenceConditionTerm(
                kind=_KIND.DEVICE_VALUE,
                comparator=SequenceComparator.GE,
                value=VariantValue(common=1),
            ),
            "a value condition needs a device and a comparison",
        ),
        (
            SequenceConditionTerm(
                kind=_KIND.DEVICE_VALUE,
                device_id=9,
                comparator=SequenceComparator.GE,
                value=VariantValue(common=1),
            ),
            "device #9 is not one of the product's",
        ),
        (
            SequenceConditionTerm(
                kind=_KIND.DEVICE_VALUE,
                device_id=5,
                position_id=12,
                comparator=SequenceComparator.GE,
                value=VariantValue(common=1),
            ),
            "position #12 is archived",
        ),
        (
            SequenceConditionTerm(
                kind=_KIND.DEVICE_VALUE, device_id=5, comparator=SequenceComparator.GE
            ),
            "a value condition needs a value",
        ),
        (
            SequenceConditionTerm(
                kind=_KIND.DEVICE_VALUE,
                device_id=5,
                comparator=SequenceComparator.GE,
                value=VariantValue(per_variant={1: 1}),
            ),
            "a value condition needs a common value or one for every variant",
        ),
        (
            SequenceConditionTerm(kind=_KIND.STEP_COMPLETE),
            "a step condition names an unknown step",
        ),
        (
            SequenceConditionTerm(kind=_KIND.TIME),
            "a time condition needs a value",
        ),
        (
            SequenceConditionTerm(kind=_KIND.TIME, duration_ms=VariantValue(common=-1)),
            "a duration is out of range",
        ),
        (
            SequenceConditionTerm(
                kind=_KIND.TIME,
                duration_ms=VariantValue(common=1, per_variant={2: 86_400_001}),
            ),
            "a duration is out of range",
        ),
        (
            SequenceConditionTerm(kind=_KIND.EXTERNAL),
            "a text is missing",
        ),
        (
            SequenceConditionTerm(kind=_KIND.EXTERNAL, text="   "),
            "a text is missing",
        ),
    ],
)
def test_check_content_rejects_a_malformed_condition(
    term: SequenceConditionTerm, message: str
) -> None:
    with pytest.raises(SequenceInvalidError, match=f"^Step 1: {message}"):
        check_content(_with_term(term), _context())


def test_check_content_refuses_moving_a_driven_device() -> None:
    context = _context()
    driver = context.devices[5]
    follower = replace(driver, id=6, name_utf8="B01 Lift P2", driven_by_id=5)
    context = replace(context, devices={5: driver, 6: follower})
    steps = [
        SequenceStep(
            key="s1",
            actions=(
                SequenceAction(
                    key="a1", kind=SequenceActionKind.DEVICE, device_id=6, position_id=10
                ),
            ),
            transitions=(SequenceTransition(key="t1", target=TARGET_END),),
        )
    ]
    with pytest.raises(SequenceInvalidError, match="moves with B01 Lift P1"):
        check_content(steps, context)
    # Its sensors may still be checked in a condition.
    check_content(
        [
            SequenceStep(
                key="s1",
                actions=(_move("a1", 10),),
                transitions=(
                    SequenceTransition(
                        key="t1",
                        target=TARGET_END,
                        condition=(
                            SequenceConditionTerm(
                                kind=SequenceConditionKind.DEVICE_POSITION,
                                device_id=6,
                                position_id=10,
                            ),
                        ),
                    ),
                ),
            )
        ],
        context,
    )


def test_estimated_times_survive_their_stored_form() -> None:
    steps = [
        SequenceStep(
            key="s1",
            expected_duration_ms=VariantValue(common=2000, per_variant={2: 3000}),
            actions=(replace(_move("a1", 10), duration_ms=VariantValue(per_variant={1: 400})),),
            transitions=(SequenceTransition(key="t1", target=TARGET_END),),
        )
    ]
    assert steps_from_data(steps_to_data(steps)) == steps
    # An estimate may be left open for a variant.
    check_content(steps, _context())


@pytest.mark.parametrize("field", ["expected_duration_ms", "action"])
def test_check_content_rejects_an_estimate_out_of_range(field: str) -> None:
    too_long = VariantValue(common=25 * 60 * 60 * 1000)
    action = _move("a1", 10)
    step = SequenceStep(
        key="s1",
        actions=(replace(action, duration_ms=too_long) if field == "action" else action,),
        transitions=(SequenceTransition(key="t1", target=TARGET_END),),
        expected_duration_ms=too_long if field == "expected_duration_ms" else None,
    )
    with pytest.raises(SequenceInvalidError, match="duration is out of range"):
        check_content([step], _context())


def test_check_content_rejects_an_estimate_for_an_unknown_variant() -> None:
    step = SequenceStep(
        key="s1",
        expected_duration_ms=VariantValue(per_variant={9: 100}),
        transitions=(SequenceTransition(key="t1", target=TARGET_END),),
    )
    with pytest.raises(SequenceInvalidError, match="Variant #9"):
        check_content([step], _context())


def test_freeze_names_keeps_the_travel_times() -> None:
    context = _context()
    context.devices[5].travel_times_ms = {"10": 350}
    positions = freeze_names("M26001", context)["devices"]["5"]["positions"]
    assert positions["10"]["travel_time_ms"] == 350
    assert positions["11"]["travel_time_ms"] is None
