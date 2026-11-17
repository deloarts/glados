"""
Bought item picture endpoints, built by _item_picture_router.py. The routes
are mounted under /bought-items; the bulk listing of the pictures shown is
mounted under /bought-items-pictures, since a flat path under /bought-items
would be taken for an item id.
"""

from src.modules.catalogue.adapters.inbound.api.deps.item_pictures import BOUGHT_ITEM_PICTURE_DEPS
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints._item_picture_router import (
    build_bulk_item_picture_router,
)
from src.modules.catalogue.adapters.inbound.api.v1.web.endpoints._item_picture_router import (
    build_item_picture_router,
)

router = build_item_picture_router(BOUGHT_ITEM_PICTURE_DEPS)
bulk_router = build_bulk_item_picture_router(BOUGHT_ITEM_PICTURE_DEPS)
