"""
Pure domain entity. No SQLAlchemy, no Pydantic, no FastAPI.

A product carries the data of the machine it describes that the CE
assessment needs: its designation and type, where it is installed, when it
is planned to be placed on the market and the legal act it is assessed
against. Checklists of the product copy this data into their header.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime
from typing import TYPE_CHECKING

from src.shared_kernel.domain.entities.base import Entity

if TYPE_CHECKING:
    from src.modules.catalogue.domain.entities.customer import Customer
    from src.modules.platform.domain.entities.user import User


@dataclass
class Product(Entity):
    created: datetime
    changed: datetime | None = None
    changes: list[str] = field(default_factory=list)
    archived: bool = False

    is_active: bool = True
    designated_user_id: int = 0

    product_number: str = ""
    customer_id: int | None = None
    customer: "Customer | None" = None
    description: str | None = None

    # ── Machine data for the CE assessment ────────────────────────────
    designation: str | None = None
    machine_type: str | None = None
    installation_site: str | None = None
    installation_location: str | None = None
    planned_placing_on_market: date | None = None
    # "directive" for Directive 2006/42/EC, "regulation" for Regulation (EU)
    # 2023/1230, which replaces it for machinery placed on the market from
    # 2027-01-20.
    legal_basis: str | None = None
    # The PLC environment the machine's tags are built for; None uses the
    # default environment.
    plc_environment_id: int | None = None
    # The disciplines the machine has, which pick the plans a device rename
    # must reach (pneumatics plan, hydraulics plan, EPLAN and PLC code, robot
    # program).
    contains_pneumatics: bool = False
    contains_hydraulics: bool = False
    contains_electrics: bool = False
    contains_robotics: bool = False

    creator_id: int = 0
    creator: "User | None" = None

    # Moves on every change of the row, whoever writes it, so an edit form can
    # send the version it read and learn of a concurrent edit
    # (platform/domain/services/edit_version.py).
    edit_version: int = 0
