from datetime import UTC
from datetime import datetime

import pytest

from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.workspace.domain.entities.product_device import ProductDeviceComponent
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKind
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKindParameter
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKindPosition
from src.modules.workspace.domain.entities.product_device_option import ProductDeviceOption
from src.modules.workspace.domain.errors import ProductDeviceOptionInvalidError
from src.modules.workspace.domain.errors import ProductDeviceReferenceInvalidError
from src.modules.workspace.domain.policies.product_device_rules import check_marker
from src.modules.workspace.domain.policies.product_device_rules import check_option
from src.modules.workspace.domain.policies.product_device_rules import check_position
from src.modules.workspace.domain.policies.product_device_rules import clean_parameters
from src.modules.workspace.domain.policies.product_device_rules import clean_travel_times
from src.modules.workspace.domain.policies.product_device_rules import duplicate_eplan_tags
from src.modules.workspace.domain.policies.product_device_rules import initial_position_value
from src.modules.workspace.domain.services.product_device_resource_rules import PositionDraft
from src.modules.workspace.domain.services.product_device_resource_rules import normalize_letter
from src.modules.workspace.domain.services.product_device_resource_rules import sync_positions
from src.modules.workspace.domain.value_objects.product_device_option_category import (
    ProductDeviceOptionCategory,
)
from src.modules.workspace.domain.value_objects.product_device_parameter_type import (
    ProductDeviceParameterType,
)

NOW = datetime(2026, 10, 22, tzinfo=UTC)


def _label(text: str) -> LocalizedText:
    return LocalizedText.of({"enGB": text})


def _kind() -> ProductDeviceKind:
    return ProductDeviceKind(
        id=1,
        created=NOW,
        changed=NOW,
        changes=[],
        label=_label("Linear drive"),
        sort_order=0,
        creator_id=1,
        positions=[
            ProductDeviceKindPosition(
                id=10,
                kind_id=1,
                label=_label("Retracted"),
                takes_value=False,
                unit=None,
                sort_order=0,
            ),
            ProductDeviceKindPosition(
                id=11,
                kind_id=1,
                label=_label("Intermediate"),
                takes_value=True,
                unit="mm",
                sort_order=1,
            ),
            ProductDeviceKindPosition(
                id=12,
                kind_id=1,
                label=_label("Old"),
                takes_value=False,
                unit=None,
                sort_order=2,
                archived=True,
            ),
        ],
        parameters=[
            ProductDeviceKindParameter(
                id=20,
                kind_id=1,
                label=_label("Bore"),
                unit="mm",
                value_type=ProductDeviceParameterType.NUMBER,
                sort_order=0,
            ),
            ProductDeviceKindParameter(
                id=21,
                kind_id=1,
                label=_label("Cushioned"),
                unit=None,
                value_type=ProductDeviceParameterType.BOOLEAN,
                sort_order=1,
            ),
        ],
    )


def _option(
    category: ProductDeviceOptionCategory, *, archived: bool = False
) -> ProductDeviceOption:
    return ProductDeviceOption(
        id=5,
        created=NOW,
        changed=NOW,
        changes=[],
        category=category,
        label=_label("Pneumatics"),
        letter="P" if category is ProductDeviceOptionCategory.DRIVING_MEDIUM else None,
        sort_order=0,
        creator_id=1,
        archived=archived,
    )


def test_product_device_rules_letter_required_for_driving_medium() -> None:
    assert normalize_letter(ProductDeviceOptionCategory.DRIVING_MEDIUM, " HP ") == "HP"
    with pytest.raises(ProductDeviceOptionInvalidError):
        normalize_letter(ProductDeviceOptionCategory.DRIVING_MEDIUM, "p")
    with pytest.raises(ProductDeviceOptionInvalidError):
        normalize_letter(ProductDeviceOptionCategory.DRIVING_MEDIUM, None)


def test_product_device_rules_letter_refused_for_other_categories() -> None:
    assert normalize_letter(ProductDeviceOptionCategory.COMPONENT_ROLE, "") is None
    with pytest.raises(ProductDeviceOptionInvalidError):
        normalize_letter(ProductDeviceOptionCategory.COMPONENT_ROLE, "V")


def test_product_device_rules_sync_positions_archives_removed_and_orders_by_list() -> None:
    kind = _kind()
    result = sync_positions(
        1,
        kind.positions,
        [
            PositionDraft(11, _label("Middle"), True, " mm "),
            PositionDraft(None, _label("Extended"), False, ""),
            PositionDraft(12, _label("Old again"), False, None),
        ],
    )
    by_label = {p.label.resolve("enGB", "enGB"): p for p in result}
    assert by_label["Middle"].sort_order == 0
    assert by_label["Middle"].unit == "mm"
    assert by_label["Extended"].id == 0
    assert by_label["Extended"].unit is None
    assert by_label["Old again"].archived is False
    assert by_label["Retracted"].archived is True


def test_product_device_rules_sync_positions_rejects_foreign_id() -> None:
    with pytest.raises(ProductDeviceReferenceInvalidError):
        sync_positions(1, _kind().positions, [PositionDraft(99, _label("X"), False, None)])


def test_product_device_rules_option_category_and_archive() -> None:
    medium = _option(ProductDeviceOptionCategory.DRIVING_MEDIUM)
    with pytest.raises(ProductDeviceReferenceInvalidError):
        check_option(medium, ProductDeviceOptionCategory.COMPONENT_ROLE, None, "role")

    archived = _option(ProductDeviceOptionCategory.DRIVING_MEDIUM, archived=True)
    with pytest.raises(ProductDeviceReferenceInvalidError):
        check_option(archived, ProductDeviceOptionCategory.DRIVING_MEDIUM, None, "medium")
    # Must not raise: a device may keep an archived entry it already has.
    check_option(archived, ProductDeviceOptionCategory.DRIVING_MEDIUM, 5, "medium")
    assert archived.archived


def test_product_device_rules_position_must_belong_to_kind_and_be_live_when_new() -> None:
    kind = _kind()
    with pytest.raises(ProductDeviceReferenceInvalidError):
        check_position(kind, 99, None, "initial position")
    with pytest.raises(ProductDeviceReferenceInvalidError):
        check_position(kind, 12, None, "initial position")
    # Must not raise: the archived position is the one the device has.
    check_position(kind, 12, 12, "initial position")
    assert kind.positions[2].archived


def test_product_device_rules_initial_value_kept_only_when_position_takes_one() -> None:
    kind = _kind()
    assert initial_position_value(kind, 11, 47.0) == 47.0
    assert initial_position_value(kind, 10, 47.0) is None
    assert initial_position_value(kind, None, 47.0) is None


def test_product_device_rules_parameters_checked_by_type() -> None:
    kind = _kind()
    assert clean_parameters(kind, {"20": 32, "21": True}) == {"20": 32, "21": True}
    assert clean_parameters(kind, {"20": None}) == {}
    with pytest.raises(ProductDeviceReferenceInvalidError):
        clean_parameters(kind, {"20": "32"})
    with pytest.raises(ProductDeviceReferenceInvalidError):
        clean_parameters(kind, {"20": True})
    with pytest.raises(ProductDeviceReferenceInvalidError):
        clean_parameters(kind, {"99": 1})


def test_product_device_rules_marker_needs_both_coordinates_in_range() -> None:
    with pytest.raises(ProductDeviceReferenceInvalidError):
        check_marker(0.5, None)
    with pytest.raises(ProductDeviceReferenceInvalidError):
        check_marker(1.5, 0.5)
    # Must not raise: both set and inside the image.
    check_marker(0.25, 0.75)
    check_marker(None, None)
    assert True


def test_product_device_rules_duplicate_eplan_tags() -> None:
    def component(tag: str | None) -> ProductDeviceComponent:
        return ProductDeviceComponent(
            id=0, device_id=1, product_id=1, role_id=1, sort_order=0, eplan_tag=tag
        )

    assert duplicate_eplan_tags([component("-BG1"), component("-BG1"), component(None)]) == {"-BG1"}
    assert duplicate_eplan_tags([component("-BG1"), component("-BG2")]) == set()


def _typed_kind() -> ProductDeviceKind:
    def parameter(id: int, value_type: ProductDeviceParameterType) -> ProductDeviceKindParameter:
        return ProductDeviceKindParameter(
            id=id,
            kind_id=1,
            label=_label(value_type.value),
            unit=None,
            value_type=value_type,
            sort_order=id,
        )

    kind = _kind()
    kind.parameters = [
        parameter(20, ProductDeviceParameterType.NUMBER),
        parameter(21, ProductDeviceParameterType.BOOLEAN),
        parameter(22, ProductDeviceParameterType.TEXT),
    ]
    return kind


def test_product_device_rules_parameters_drop_empty_values_and_trim_text() -> None:
    kind = _typed_kind()
    cleaned = clean_parameters(kind, {"20": 1.5, "21": False, "22": "  Bore 32  "})
    assert cleaned == {"20": 1.5, "21": False, "22": "Bore 32"}
    assert clean_parameters(kind, {"20": "", "21": None, "22": "   "}) == {}
    assert clean_parameters(kind, {"22": "x" * 200}) == {"22": "x" * 200}


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ({"99": None}, "Parameter #99 is not a parameter of this kind."),
        ({"20": float("nan")}, "Parameter #20 takes a number."),
        ({"20": float("inf")}, "Parameter #20 takes a number."),
        ({"20": False}, "Parameter #20 takes a number."),
        ({"21": 1}, "Parameter #21 takes yes or no."),
        ({"21": "yes"}, "Parameter #21 takes yes or no."),
        ({"22": 5}, "Parameter #22 takes a text."),
        ({"22": "x" * 201}, "Parameter #22 is too long."),
        ({"22": "  ", "21": 1}, "Parameter #21 takes yes or no."),
    ],
)
def test_product_device_rules_parameters_refuse_a_value_of_the_wrong_type(
    raw: dict[str, object], message: str
) -> None:
    with pytest.raises(ProductDeviceReferenceInvalidError) as raised:
        clean_parameters(_typed_kind(), raw)
    assert str(raised.value) == message


def test_product_device_rules_travel_times_need_a_position_of_the_kind_and_a_sane_time() -> None:
    assert clean_travel_times(_kind(), {"10": 350, "11": 0}) == {"10": 350, "11": 0}
    with pytest.raises(ProductDeviceReferenceInvalidError, match="not a position"):
        clean_travel_times(_kind(), {"99": 350})
    with pytest.raises(ProductDeviceReferenceInvalidError, match="travel time"):
        clean_travel_times(_kind(), {"10": -1})
    with pytest.raises(ProductDeviceReferenceInvalidError, match="travel time"):
        clean_travel_times(_kind(), {"10": 2 * 60 * 60 * 1000})
