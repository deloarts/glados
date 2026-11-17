"""
The dependencies of Operations' routes whose implementations live in the read
tier, which the composition root binds at startup (`src/bootstrap/bindings.py`).
"""

from collections.abc import Callable

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.operations.application.services.infoscreen_feed_builder import (
    IInfoscreenFeedBuilder,
)
from src.modules.platform.adapters.inbound.api.deps.binding import Binding
from src.modules.platform.adapters.inbound.api.deps.database import get_db

infoscreen_feed_builder: Binding[Callable[[AsyncSession], IInfoscreenFeedBuilder]] = Binding(
    "The infoscreen feed builder"
)


def get_infoscreen_feed_builder(
    db: AsyncSession = Depends(get_db, scope="function"),
) -> IInfoscreenFeedBuilder:
    return infoscreen_feed_builder.get()(db)
