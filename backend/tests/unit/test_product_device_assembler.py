"""
The component pass of the product device assembler with stub repositories:
which drafts it refuses, how a stored component keeps its identity and its
archived references, and the EPLAN tag checks within the device and across
the product.
"""

from datetime import UTC
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.workspace.application.dto.product_device_dto import ProductDeviceComponentDraft
from src.modules.workspace.application.dto.product_device_dto import ProductDeviceSignalDraft
from src.modules.workspace.application.use_cases.product_device.assembler import (
    ProductDeviceAssembler,
)
from src.modules.workspace.domain.entities.product_device import ProductDevice
from src.modules.workspace.domain.entities.product_device import ProductDeviceComponent
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKind
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKindPosition
from src.modules.workspace.domain.entities.product_device_option import ProductDeviceOption
from src.modules.workspace.domain.errors import ProductDeviceEplanTagTakenError
from src.modules.workspace.domain.errors import ProductDeviceReferenceInvalidError
from src.modules.workspace.domain.value_objects.product_device_option_category import (
    ProductDeviceOptionCategory,
)
from src.modules.workspace.domain.value_objects.product_device_signal import ProductDeviceSignal
from src.modules.workspace.domain.value_objects.product_device_signal import ProductDeviceSignalType

NOW = datetime(2026, 10, 24, tzinfo=UTC)
PRODUCT_ID = 3
ROLE_ID = 7
ARCHIVED_ROLE_ID = 8
ARCHIVED_POSITION_ID = 12


def _option(id: int, *, archived: bool = False) -> ProductDeviceOption:
    return ProductDeviceOption(
        id=id,
        created=NOW,
        changed=NOW,
        changes=[],
        category=ProductDeviceOptionCategory.COMPONENT_ROLE,
        label=LocalizedText.of({"enGB": "Sensor"}),
        letter=None,
        sort_order=0,
        creator_id=1,
        archived=archived,
    )


def _kind() -> ProductDeviceKind:
    def position(id: int, archived: bool = False) -> ProductDeviceKindPosition:
        return ProductDeviceKindPosition(
            id=id,
            kind_id=1,
            label=LocalizedText.of({"enGB": f"P{id}"}),
            takes_value=False,
            unit=None,
            sort_order=id,
            archived=archived,
        )

    return ProductDeviceKind(
        id=1,
        created=NOW,
        changed=NOW,
        changes=[],
        label=LocalizedText.of({"enGB": "Linear drive"}),
        sort_order=0,
        creator_id=1,
        positions=[position(10), position(ARCHIVED_POSITION_ID, archived=True)],
    )


def _stored(id: int, **overrides: Any) -> ProductDeviceComponent:
    values: dict[str, Any] = {
        "id": id,
        "device_id": 5,
        "product_id": PRODUCT_ID,
        "role_id": ROLE_ID,
        "sort_order": 0,
    }
    values.update(overrides)
    return ProductDeviceComponent(**values)


def _device(*components: ProductDeviceComponent) -> ProductDevice:
    return ProductDevice(
        id=5,
        created=NOW,
        changed=NOW,
        changes=[],
        product_id=PRODUCT_ID,
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
        components=list(components),
    )


def _assembler(
    *, bought_items: set[int] | None = None, tag_holders: dict[str, int] | None = None
) -> ProductDeviceAssembler:
    options = {
        ROLE_ID: _option(ROLE_ID),
        ARCHIVED_ROLE_ID: _option(ARCHIVED_ROLE_ID, archived=True),
    }
    known_items = bought_items or set()
    holders = tag_holders or {}

    async def option_by_id(option_id: int) -> ProductDeviceOption | None:
        return options.get(option_id)

    async def bought_item_by_id(item_id: int) -> object | None:
        return object() if item_id in known_items else None

    async def component_by_tag(product_id: int, tag: str) -> ProductDeviceComponent | None:
        assert product_id == PRODUCT_ID
        holder = holders.get(tag)
        return None if holder is None else _stored(99, device_id=holder, eplan_tag=tag)

    devices = AsyncMock()
    devices.get_component_by_eplan_tag.side_effect = component_by_tag
    option_repo = AsyncMock()
    option_repo.get_by_id.side_effect = option_by_id
    bought_item_repo = AsyncMock()
    bought_item_repo.get_by_id.side_effect = bought_item_by_id
    return ProductDeviceAssembler(
        devices=devices, options=option_repo, kinds=AsyncMock(), bought_items=bought_item_repo
    )


async def _components(
    drafts: list[ProductDeviceComponentDraft],
    device: ProductDevice | None = None,
    *,
    same_kind: bool = True,
    **assembler: Any,
) -> list[ProductDeviceComponent]:
    return await _assembler(**assembler)._components(
        device or _device(), PRODUCT_ID, _kind(), same_kind, drafts
    )


def _confirming(position_id: int) -> ProductDeviceSignalDraft:
    return ProductDeviceSignalDraft(
        signal_type=ProductDeviceSignalType.DI, meaning=" end  ", confirms_position_id=position_id
    )


async def test_components_builds_new_and_stored_components_in_order() -> None:
    stored = _stored(40, public_id=uuid4())
    result = await _components(
        [
            ProductDeviceComponentDraft(
                role_id=ROLE_ID,
                bought_item_id=2,
                eplan_tag=" -BG1 ",
                b10d_cycles=1000,
                mttfd_years=0.5,
                note="  checked  ",
                signals=[_confirming(10)],
            ),
            ProductDeviceComponentDraft(id=40, role_id=ROLE_ID, note="   "),
        ],
        _device(stored),
        bought_items={2},
    )

    new, kept = result
    assert (new.id, new.sort_order, new.device_id, new.product_id) == (0, 0, 5, PRODUCT_ID)
    assert new.bought_item_id == 2
    assert new.eplan_tag == "-BG1"
    assert (new.b10d_cycles, new.mttfd_years) == (1000, 0.5)
    assert new.note == "checked"
    assert new.signals == [ProductDeviceSignal(ProductDeviceSignalType.DI, "end", 10)]
    assert (kept.id, kept.sort_order, kept.public_id) == (40, 1, stored.public_id)
    assert kept.note is None
    assert kept.eplan_tag is None


async def test_components_lets_a_stored_component_keep_its_archived_role() -> None:
    stored = _stored(40, role_id=ARCHIVED_ROLE_ID)
    result = await _components(
        [ProductDeviceComponentDraft(id=40, role_id=ARCHIVED_ROLE_ID)], _device(stored)
    )
    assert result[0].role_id == ARCHIVED_ROLE_ID


async def test_components_keeps_an_archived_position_only_on_the_same_kind() -> None:
    stored = _stored(
        40,
        signals=[ProductDeviceSignal(ProductDeviceSignalType.DI, "old", ARCHIVED_POSITION_ID)],
    )
    draft = ProductDeviceComponentDraft(
        id=40, role_id=ROLE_ID, signals=[_confirming(ARCHIVED_POSITION_ID)]
    )

    result = await _components([draft], _device(stored))
    assert result[0].signals[0].confirms_position_id == ARCHIVED_POSITION_ID

    with pytest.raises(ProductDeviceReferenceInvalidError, match="archived"):
        await _components([draft], _device(stored), same_kind=False)
    with pytest.raises(ProductDeviceReferenceInvalidError, match="archived"):
        await _components([draft.model_copy(update={"id": None})], _device(stored))


async def test_components_lets_a_device_keep_its_own_eplan_tag() -> None:
    result = await _components(
        [ProductDeviceComponentDraft(role_id=ROLE_ID, eplan_tag="-BG1")], tag_holders={"-BG1": 5}
    )
    assert result[0].eplan_tag == "-BG1"


@pytest.mark.parametrize(
    ("drafts", "message"),
    [
        (
            [ProductDeviceComponentDraft(id=41, role_id=ROLE_ID)],
            "Component #41 is not part of this device.",
        ),
        ([ProductDeviceComponentDraft(role_id=99)], "The component role does not exist."),
        (
            [ProductDeviceComponentDraft(role_id=ARCHIVED_ROLE_ID)],
            "The component role is archived and cannot be chosen.",
        ),
        (
            [ProductDeviceComponentDraft(role_id=ROLE_ID, bought_item_id=6)],
            "Bought item #6 does not exist.",
        ),
        (
            [ProductDeviceComponentDraft(role_id=ROLE_ID, b10d_cycles=0)],
            "B10d must be a positive number.",
        ),
        (
            [ProductDeviceComponentDraft(role_id=ROLE_ID, mttfd_years=-1)],
            "MTTFd must be a positive number.",
        ),
        (
            [ProductDeviceComponentDraft(role_id=ROLE_ID, note="x" * 501)],
            "The component note is longer than 500 characters.",
        ),
        (
            [ProductDeviceComponentDraft(role_id=ROLE_ID, eplan_tag="x" * 61)],
            "The EPLAN tag is too long.",
        ),
        (
            # The role is checked before the bought item and the numbers.
            [ProductDeviceComponentDraft(role_id=99, bought_item_id=6, b10d_cycles=0)],
            "The component role does not exist.",
        ),
        (
            # The bought item is checked before the reliability data.
            [ProductDeviceComponentDraft(role_id=ROLE_ID, bought_item_id=6, b10d_cycles=0)],
            "Bought item #6 does not exist.",
        ),
        (
            # B10d before MTTFd.
            [ProductDeviceComponentDraft(role_id=ROLE_ID, b10d_cycles=0, mttfd_years=0)],
            "B10d must be a positive number.",
        ),
    ],
)
async def test_components_refuses_an_invalid_draft(
    drafts: list[ProductDeviceComponentDraft], message: str
) -> None:
    with pytest.raises(ProductDeviceReferenceInvalidError) as raised:
        await _components(drafts, _device(_stored(40)))
    assert str(raised.value) == message


async def test_components_refuses_a_tag_twice_in_the_device_before_asking_the_product() -> None:
    drafts = [
        ProductDeviceComponentDraft(role_id=ROLE_ID, eplan_tag=tag)
        for tag in ("-BG2", "-BG1", "-BG2", "-BG1")
    ]
    with pytest.raises(ProductDeviceEplanTagTakenError) as raised:
        await _components(drafts, tag_holders={"-BG1": 6})
    assert str(raised.value) == "The EPLAN tag '-BG1' appears twice in this device."


async def test_components_refuses_a_tag_another_device_of_the_product_uses() -> None:
    drafts = [
        ProductDeviceComponentDraft(role_id=ROLE_ID),
        ProductDeviceComponentDraft(role_id=ROLE_ID, eplan_tag="-BG1"),
    ]
    with pytest.raises(ProductDeviceEplanTagTakenError) as raised:
        await _components(drafts, tag_holders={"-BG1": 6})
    assert str(raised.value) == (
        "Another device of this product already uses the EPLAN tag '-BG1'."
    )
