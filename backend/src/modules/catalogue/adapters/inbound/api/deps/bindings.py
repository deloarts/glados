"""
The dependencies of Catalogue's routes whose implementations live in the
modules above it, which the composition root binds at startup
(`src/bootstrap/bindings.py`).
"""

from collections.abc import Callable

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.catalogue.ports.outbound.bought_item_usage_port import IBoughtItemUsages
from src.modules.catalogue.ports.outbound.cad_source_port import ICadSource
from src.modules.catalogue.ports.outbound.contact_copies_port import IContactCopies
from src.modules.catalogue.ports.outbound.default_machine_port import IDefaultMachineLookup
from src.modules.catalogue.ports.outbound.inspection_method_usage_port import IInspectionMethodUsage
from src.modules.catalogue.ports.outbound.made_item_usage_port import IMadeItemUsages
from src.modules.platform.adapters.inbound.api.deps.binding import Binding
from src.modules.platform.adapters.inbound.api.deps.database import get_db

cad_source: Binding[Callable[[AsyncSession], ICadSource]] = Binding("The CAD source")
bought_item_usages: Binding[Callable[[AsyncSession], IBoughtItemUsages]] = Binding(
    "The bought item usages"
)
made_item_usages: Binding[Callable[[AsyncSession], IMadeItemUsages]] = Binding(
    "The made item usages"
)
inspection_method_usage: Binding[Callable[[AsyncSession], IInspectionMethodUsage]] = Binding(
    "The use of an inspection method as the default of production steps"
)
default_machine_lookup: Binding[Callable[[AsyncSession], IDefaultMachineLookup]] = Binding(
    "The default machine lookup"
)
contact_copies: Binding[Callable[[AsyncSession], IContactCopies]] = Binding(
    "The copies of contacts that other records keep"
)


def get_cad_source(db: AsyncSession = Depends(get_db, scope="function")) -> ICadSource:
    return cad_source.get()(db)


def get_bought_item_usages(
    db: AsyncSession = Depends(get_db, scope="function"),
) -> IBoughtItemUsages:
    return bought_item_usages.get()(db)


def get_made_item_usages(db: AsyncSession = Depends(get_db, scope="function")) -> IMadeItemUsages:
    return made_item_usages.get()(db)


def get_default_machine_lookup(
    db: AsyncSession = Depends(get_db, scope="function"),
) -> IDefaultMachineLookup:
    return default_machine_lookup.get()(db)


def get_contact_copies(db: AsyncSession = Depends(get_db, scope="function")) -> IContactCopies:
    return contact_copies.get()(db)


def get_inspection_method_usage(
    db: AsyncSession = Depends(get_db, scope="function"),
) -> IInspectionMethodUsage:
    return inspection_method_usage.get()(db)
