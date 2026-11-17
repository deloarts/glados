"""
Source item picture endpoints, built by _item_picture_router.py. The routes
are mounted under /source-items; the bulk listing of the pictures shown is
mounted under /source-items-pictures, since a flat path under /source-items
would be taken for an item id.
"""

from src.modules.catalogue.adapters.inbound.api.deps.item_pictures import SOURCE_ITEM_PICTURE_DEPS
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints._item_picture_router import (
    build_bulk_item_picture_router,
)
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints._item_picture_router import (
    build_item_picture_router,
)

router = build_item_picture_router(SOURCE_ITEM_PICTURE_DEPS)
bulk_router = build_bulk_item_picture_router(SOURCE_ITEM_PICTURE_DEPS)
