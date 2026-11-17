"""
A device of a product (machine): a cylinder, motor, gripper or swivel drive,
in reality a group of parts such as a cylinder with its valve and two
sensors. The device carries the name that follows the house naming
convention, the data a PLC programmer needs, and optionally its parts as
components.

The name is built from location, name, driving medium letter and number
(see product_device_naming.py) and stored without the product number, in
UTF-8 and in ASCII. Both are unique per product, the ASCII one compared
case-insensitively; archived devices keep their names and numbers, so a
number never comes back for a different device.

Components carry no name of their own. Their EPLAN tag is optional and
unique per product once set; the device itself has none. Which position of
the kind a component reports is said by its input signals, one position per
signal.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from typing import Any

from src.modules.platform.domain.entities.user import User
from src.modules.workspace.domain.value_objects.product_device_signal import ProductDeviceSignal
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class ProductDeviceComponent(Entity):
    device_id: int
    product_id: int
    role_id: int
    sort_order: int
    bought_item_id: int | None = None
    eplan_tag: str | None = None
    # Reliability data for ISO 13849-1: B10d for fluid power and
    # electromechanical parts, MTTFd for electronic parts.
    b10d_cycles: int | None = None
    mttfd_years: float | None = None
    note: str | None = None
    signals: list[ProductDeviceSignal] = field(default_factory=list)

    # Denormalized for display, not persisted.
    bought_item_part_number: str | None = None
    bought_item_article_name: str | None = None


@dataclass
class ProductDevice(Entity):
    created: datetime
    changed: datetime
    changes: list[str]

    product_id: int

    # ── Name inputs ───────────────────────────────────────────────────
    location: str
    name: str
    # None for a device of a kind without driving medium.
    driving_medium_id: int | None
    number: int

    # ── Name, stored without the product number ───────────────────────
    name_utf8: str
    name_ascii: str
    # name_ascii lower-cased, for the case-insensitive uniqueness.
    name_ascii_key: str
    # Location, name and letter as compared for numbering.
    group_key: str

    kind_id: int

    creator_id: int
    creator: User | None = None
    changed_by_id: int | None = None
    changed_by: User | None = None
    archived: bool = False

    description: str | None = None

    # ── PLC data ──────────────────────────────────────────────────────
    initial_position_id: int | None = None
    initial_position_value: float | None = None
    energy_loss_behaviour_id: int | None = None
    energy_restoration_behaviour_id: int | None = None
    monitoring_time_ms: int | None = None
    # Another device of the product whose output moves this one too, such as
    # a second clamp cylinder on the first one's valve. The driver owns the
    # valve; this device keeps only its own sensors. A driven device drives
    # nothing itself.
    driven_by_id: int | None = None
    # Driver position id to own position id, both as strings (JSON keys);
    # only for a driver of another kind. Of the same kind each position
    # follows the driver's position of the same id.
    driven_position_map: dict[str, str] = field(default_factory=dict)
    safety_relevant: bool = False
    # Parameter definition id (as a string, JSON keys are strings) to value.
    parameters: dict[str, Any] = field(default_factory=dict)
    # Kind position id to this device's own label for it, such as "Robot
    # pickup" for a swivel drive's end A.
    position_labels: dict[str, str] = field(default_factory=dict)
    # Kind position id (as a string) to the nominal time in milliseconds the
    # device takes to reach it, for the estimated cycle time of a sequence.
    travel_times_ms: dict[str, int] = field(default_factory=dict)

    # ── Images, set through their own upload (see images.py) ─────────
    rendering_file_id: int | None = None
    # A rendering of the parent assembly the device is installed in.
    assembly_file_id: int | None = None
    # Marker on the product's overview image, normalised to 0..1.
    marker_x: float | None = None
    marker_y: float | None = None

    components: list[ProductDeviceComponent] = field(default_factory=list)

    # Denormalized for display, not persisted.
    product_number: str | None = None
    driving_medium_letter: str | None = None

    # Moves on every change of the row, whoever writes it, so an edit form can
    # send the version it read and learn of a concurrent edit
    # (platform/domain/services/edit_version.py).
    edit_version: int = 0
