"""Catalogue's facades on the request's session, for the factories of the
modules above it that wire them into their use cases."""

from fastapi import Depends

from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_made_item_repo
from src.modules.catalogue.application.facade.made_item_material_source import (
    MadeItemMaterialSources,
)
from src.modules.catalogue.ports.outbound.repositories.made_item_repository import (
    IMadeItemRepository,
)


def get_made_item_material_sources(
    made_item_repo: IMadeItemRepository = Depends(get_made_item_repo),
) -> MadeItemMaterialSources:
    return MadeItemMaterialSources(made_item_repo)
