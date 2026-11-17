"""
Turns a save command into a checked product device, shared by create and
update. It loads everything the device points at, hands it to the domain
rules, builds the name and makes sure no other device of the product holds
it, and returns the device ready to save. The caller checks permissions
first and commits afterwards.
"""

from dataclasses import dataclass

from src.modules.catalogue.ports.outbound.catalogue_queries import IBoughtItemQueries
from src.modules.workspace.application.dto.product_device_dto import ProductDeviceComponentDraft
from src.modules.workspace.application.dto.product_device_dto import SaveProductDeviceCommand
from src.modules.workspace.domain.entities.product import Product
from src.modules.workspace.domain.entities.product_device import ProductDevice
from src.modules.workspace.domain.entities.product_device import ProductDeviceComponent
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKind
from src.modules.workspace.domain.errors import ProductDeviceEplanTagTakenError
from src.modules.workspace.domain.errors import ProductDeviceNameInvalidError
from src.modules.workspace.domain.errors import ProductDeviceNameTakenError
from src.modules.workspace.domain.errors import ProductDeviceReferenceInvalidError
from src.modules.workspace.domain.policies.product_device_naming import LOCATION_MAX_LENGTH
from src.modules.workspace.domain.policies.product_device_naming import NAME_MAX_LENGTH
from src.modules.workspace.domain.policies.product_device_naming import DeviceName
from src.modules.workspace.domain.policies.product_device_naming import clean_part
from src.modules.workspace.domain.policies.product_device_naming import compose_device_name
from src.modules.workspace.domain.policies.product_device_naming import group_key
from src.modules.workspace.domain.policies.product_device_rules import check_driver
from src.modules.workspace.domain.policies.product_device_rules import check_driving_medium
from src.modules.workspace.domain.policies.product_device_rules import check_kind
from src.modules.workspace.domain.policies.product_device_rules import check_marker
from src.modules.workspace.domain.policies.product_device_rules import check_option
from src.modules.workspace.domain.policies.product_device_rules import check_position
from src.modules.workspace.domain.policies.product_device_rules import clean_eplan_tag
from src.modules.workspace.domain.policies.product_device_rules import clean_parameters
from src.modules.workspace.domain.policies.product_device_rules import clean_position_labels
from src.modules.workspace.domain.policies.product_device_rules import clean_position_map
from src.modules.workspace.domain.policies.product_device_rules import clean_signals
from src.modules.workspace.domain.policies.product_device_rules import clean_travel_times
from src.modules.workspace.domain.policies.product_device_rules import duplicate_eplan_tags
from src.modules.workspace.domain.policies.product_device_rules import initial_position_value
from src.modules.workspace.domain.value_objects.product_device_option_category import (
    ProductDeviceOptionCategory,
)
from src.modules.workspace.domain.value_objects.product_device_signal import ProductDeviceSignal
from src.modules.workspace.ports.outbound.repositories.product_device_repository import (
    IProductDeviceRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_device_resource_repository import (
    IProductDeviceKindRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_device_resource_repository import (
    IProductDeviceOptionRepository,
)

DESCRIPTION_MAX_LENGTH = 1000
NOTE_MAX_LENGTH = 500


@dataclass(frozen=True)
class NameParts:
    location: str
    name: str
    letter: str
    group_key: str


@dataclass
class ProductDeviceAssembler:
    devices: IProductDeviceRepository
    options: IProductDeviceOptionRepository
    kinds: IProductDeviceKindRepository
    bought_items: IBoughtItemQueries

    async def name_parts(
        self, location: str, name: str, medium_id: int | None, current_medium_id: int | None
    ) -> NameParts:
        """The checked name parts. Without a driving medium the name has no
        letter, for a device of a kind without one."""
        letter = ""
        if medium_id is not None:
            medium = await self.options.get_by_id(medium_id)
            check_option(
                medium,
                ProductDeviceOptionCategory.DRIVING_MEDIUM,
                current_medium_id,
                "driving medium",
            )
            assert medium is not None
            letter = medium.letter or ""
        cleaned_location = clean_part(
            location, "location", required=False, max_length=LOCATION_MAX_LENGTH
        )
        cleaned_name = clean_part(name, "name", required=True, max_length=NAME_MAX_LENGTH)
        return NameParts(
            cleaned_location,
            cleaned_name,
            letter,
            group_key(cleaned_location, cleaned_name, letter),
        )

    async def number_for(
        self,
        product_id: int,
        parts: NameParts,
        requested: int | None,
        current: ProductDevice | None,
    ) -> int:
        """The requested number, or the device's own number while its
        location, name and letter stay the same, or the next free one."""
        if requested is not None:
            if requested < 1:
                raise ProductDeviceNameInvalidError("The device number starts at 1.")
            return requested
        if current is not None and current.group_key == parts.group_key:
            return current.number
        highest = await self.devices.max_number(product_id, parts.group_key)
        return (highest or 0) + 1

    async def name_taken(self, product_id: int, name: DeviceName, own_id: int) -> bool:
        for holder in (
            await self.devices.get_by_name(product_id, name.utf8),
            await self.devices.get_by_ascii_key(product_id, name.ascii_key),
        ):
            if holder is not None and holder.id != own_id:
                return True
        return False

    async def apply(
        self, device: ProductDevice, product: Product, cmd: SaveProductDeviceCommand
    ) -> None:
        """Writes the checked command onto `device`, new (id 0) or stored."""
        is_new = device.id == 0
        kind = check_kind(
            await self.kinds.get_by_id(cmd.kind_id), None if is_new else device.kind_id
        )
        check_driving_medium(kind, cmd.driving_medium_id)
        parts = await self.name_parts(
            cmd.location,
            cmd.name,
            cmd.driving_medium_id,
            None if is_new else device.driving_medium_id,
        )
        number = await self.number_for(product.id, parts, cmd.number, None if is_new else device)
        name = compose_device_name(parts.location, parts.name, parts.letter, number)
        if await self.name_taken(product.id, name, device.id):
            raise ProductDeviceNameTakenError(
                f"Product {product.product_number!r} already has a device named {name.utf8!r}."
            )

        same_kind = not is_new and device.kind_id == kind.id
        check_position(
            kind,
            cmd.initial_position_id,
            device.initial_position_id if same_kind else None,
            "initial position",
        )
        for option_id, current_id, what in (
            (
                cmd.energy_loss_behaviour_id,
                device.energy_loss_behaviour_id,
                "energy loss behaviour",
            ),
            (
                cmd.energy_restoration_behaviour_id,
                device.energy_restoration_behaviour_id,
                "energy restoration behaviour",
            ),
        ):
            if option_id is not None:
                check_option(
                    await self.options.get_by_id(option_id),
                    ProductDeviceOptionCategory.ENERGY_BEHAVIOUR,
                    None if is_new else current_id,
                    what,
                )
        if cmd.monitoring_time_ms is not None and cmd.monitoring_time_ms < 0:
            raise ProductDeviceReferenceInvalidError("The monitoring time cannot be negative.")
        check_marker(cmd.marker_x, cmd.marker_y)
        driver = await self.devices.get_by_id(cmd.driven_by_id) if cmd.driven_by_id else None
        check_driver(
            device,
            driver,
            cmd.driven_by_id,
            product.id,
            not is_new and await self.devices.count_driven_by(device.id) > 0,
            None if is_new else device.driven_by_id,
        )
        driver_kind = await self.kinds.get_by_id(driver.kind_id) if driver else None

        components = await self._components(device, product.id, kind, same_kind, cmd.components)

        device.location = parts.location
        device.name = parts.name
        device.driving_medium_id = cmd.driving_medium_id
        device.number = number
        device.name_utf8 = name.utf8
        device.name_ascii = name.ascii
        device.name_ascii_key = name.ascii_key
        device.group_key = parts.group_key
        device.kind_id = kind.id
        device.description = _clean_text(cmd.description, DESCRIPTION_MAX_LENGTH, "description")
        device.initial_position_id = cmd.initial_position_id
        device.initial_position_value = initial_position_value(
            kind, cmd.initial_position_id, cmd.initial_position_value
        )
        device.energy_loss_behaviour_id = cmd.energy_loss_behaviour_id
        device.energy_restoration_behaviour_id = cmd.energy_restoration_behaviour_id
        device.monitoring_time_ms = cmd.monitoring_time_ms
        device.driven_by_id = cmd.driven_by_id
        device.driven_position_map = clean_position_map(kind, driver_kind, cmd.driven_position_map)
        device.safety_relevant = cmd.safety_relevant
        device.parameters = clean_parameters(kind, cmd.parameters)
        device.position_labels = clean_position_labels(kind, cmd.position_labels)
        device.travel_times_ms = clean_travel_times(kind, cmd.travel_times_ms)
        device.marker_x = cmd.marker_x
        device.marker_y = cmd.marker_y
        device.components = components

    async def _components(
        self,
        device: ProductDevice,
        product_id: int,
        kind: ProductDeviceKind,
        same_kind: bool,
        drafts: list[ProductDeviceComponentDraft],
    ) -> list[ProductDeviceComponent]:
        stored = {c.id: c for c in device.components}
        result: list[ProductDeviceComponent] = []
        for index, draft in enumerate(drafts):
            current = _stored_component(stored, draft)
            await self._check_component_references(draft, current)
            _check_reliability(draft)
            result.append(_component(device, product_id, kind, same_kind, index, draft, current))
        await self._check_eplan_tags(device, product_id, result)
        return result

    async def _check_component_references(
        self, draft: ProductDeviceComponentDraft, current: ProductDeviceComponent | None
    ) -> None:
        check_option(
            await self.options.get_by_id(draft.role_id),
            ProductDeviceOptionCategory.COMPONENT_ROLE,
            current.role_id if current else None,
            "component role",
        )
        if draft.bought_item_id is not None and (
            await self.bought_items.get_by_id(draft.bought_item_id) is None
        ):
            raise ProductDeviceReferenceInvalidError(
                f"Bought item #{draft.bought_item_id} does not exist."
            )

    async def _check_eplan_tags(
        self, device: ProductDevice, product_id: int, components: list[ProductDeviceComponent]
    ) -> None:
        """A tag appears once in the device and on no other device of the
        product; the first check needs no query."""
        duplicates = duplicate_eplan_tags(components)
        if duplicates:
            raise ProductDeviceEplanTagTakenError(
                f"The EPLAN tag {sorted(duplicates)[0]!r} appears twice in this device."
            )
        for component in components:
            if component.eplan_tag is None:
                continue
            holder = await self.devices.get_component_by_eplan_tag(product_id, component.eplan_tag)
            if holder is not None and holder.device_id != device.id:
                raise ProductDeviceEplanTagTakenError(
                    f"Another device of this product already uses the EPLAN tag "
                    f"{component.eplan_tag!r}."
                )


def _stored_component(
    stored: dict[int, ProductDeviceComponent], draft: ProductDeviceComponentDraft
) -> ProductDeviceComponent | None:
    """The stored component a draft updates, or None for a new one."""
    if draft.id is None:
        return None
    current = stored.get(draft.id)
    if current is None:
        raise ProductDeviceReferenceInvalidError(
            f"Component #{draft.id} is not part of this device."
        )
    return current


def _check_reliability(draft: ProductDeviceComponentDraft) -> None:
    if draft.b10d_cycles is not None and draft.b10d_cycles <= 0:
        raise ProductDeviceReferenceInvalidError("B10d must be a positive number.")
    if draft.mttfd_years is not None and draft.mttfd_years <= 0:
        raise ProductDeviceReferenceInvalidError("MTTFd must be a positive number.")


def _component(
    device: ProductDevice,
    product_id: int,
    kind: ProductDeviceKind,
    same_kind: bool,
    index: int,
    draft: ProductDeviceComponentDraft,
    current: ProductDeviceComponent | None,
) -> ProductDeviceComponent:
    """The checked component for a draft, keeping the identity of the
    stored component it updates."""
    # Positions and kind signals the component refers to today may stay even
    # if archived, as long as the kind is unchanged.
    current_positions = (
        {
            position_id
            for s in current.signals
            for position_id in (s.confirms_position_id, s.drives_position_id)
            if position_id
        }
        if current and same_kind
        else set()
    )
    current_kind_signals = (
        {s.kind_signal_id for s in current.signals if s.kind_signal_id}
        if current and same_kind
        else set()
    )
    component = ProductDeviceComponent(
        id=current.id if current else 0,
        device_id=device.id,
        product_id=product_id,
        role_id=draft.role_id,
        sort_order=index,
        bought_item_id=draft.bought_item_id,
        eplan_tag=clean_eplan_tag(draft.eplan_tag),
        b10d_cycles=draft.b10d_cycles,
        mttfd_years=draft.mttfd_years,
        note=_clean_text(draft.note, NOTE_MAX_LENGTH, "component note"),
        signals=clean_signals(
            kind,
            [
                ProductDeviceSignal(
                    s.signal_type,
                    s.meaning,
                    s.confirms_position_id,
                    s.drives_position_id,
                    s.safety,
                    s.address,
                    s.tag_suffix,
                    s.tag_name,
                    s.kind_signal_id,
                )
                for s in draft.signals
            ],
            current_positions,
            current_kind_signals,
        ),
    )
    if current is not None:
        component.public_id = current.public_id
    return component


def _clean_text(value: str | None, max_length: int, what: str) -> str | None:
    text = (value or "").strip()
    if len(text) > max_length:
        raise ProductDeviceReferenceInvalidError(
            f"The {what} is longer than {max_length} characters."
        )
    return text or None
